# Scoring API Test Framework

API-тесты сервиса скоринга транзакций. Выросло из одного файла
`code_review_file.py` после код-ревью и приведено к формату рабочего проекта:
`api/` + `utils/`, Allure-разметка, классы тестов, dict-константы,
валидаторы `assert_status_code` / `assert_valid_json`, `HTTP_STATUS_*`.

## Структура

```
scoring_test_framework/
├── conftest.py                  # точка входа pytest: список плагинов с фикстурами
├── fixtures/
│   ├── environment.py           # конфиг прогона и CLI-опции (системный слой)
│   ├── clients.py               # scoring_client — одна фикстура
│   ├── database.py              # scoring_db — одна фикстура
│   └── data.py                  # test_data, created_users — setup и teardown данных
├── pytest.ini                   # pythonpath, маркеры, логирование, отключение чужих плагинов
├── ruff.toml                    # правила линтера, line-length 110 (наследует pyproject.toml проекта)
├── requirements.txt
├── .env.example                 # какие переменные окружения нужны
├── api/
│   ├── models.py                # Pydantic: *Payload на запрос, User/Transaction на ответ
│   ├── clients/
│   │   ├── base_client.py       # HTTP-транспорт: Retry/backoff, таймауты, логи, attach в Allure
│   │   ├── scoring_client.py     # доменные методы API + wait_for_scored (поллинг вместо sleep)
│   │   ├── base_db_client.py    # транспорт БД: engine, пул, cursor() и transaction()
│   │   └── scoring_db_client.py # SQL и именованные запросы к БД
│   └── utils/
│       ├── constants.py         # SCR_RESPONSE_KEYS, SCR_INVALID_DATA, SCR_LIMITS, enum'ы
│       ├── payloads.py          # фабрики тел запросов: new_user(), high_risk_transaction(), …
│       ├── validators.py        # assert_status_code, assert_valid_json, assert_created, …
│       └── db_validators.py     # assert_db_decision, assert_db_count (fail() общий)
├── utils/
│   ├── config.py                # Config.from_env(): адреса, URL БД, таймауты, ретраи
│   ├── logger.py                # get_logger(), mask_secrets(), preview()
│   └── utils.py                 # HTTP_STATUS_*, RETRYABLE_STATUSES, env-хелперы
├── stub/
│   └── scoring_stub.py          # заглушка сервиса на stdlib: чтобы сьют можно было запустить
└── tests/
    ├── test_users.py            # TestUsers
    ├── test_transactions.py     # TestTransactionScoring
    └── test_frequency_rule.py   # TestFrequencyRule
```

Правило слоёв: тест знает только про клиент, фабрики данных, константы и
валидаторы. URL, SQL, таймауты, ретраи и креды в тестах не встречаются —
в тестовых модулях нет ни одного хелпера, только сценарии.

Код и комментарии в модулях — на английском.

## Формат теста

```python
@allure.epic("Scoring API")
@allure.feature("Transactions")
@allure.description("Tests for transaction creation, scoring decision and persistence.")
class TestTransactionScoring:
    @allure.title("Positive: POST transaction returns 200 and gets scored")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_post_transaction(self, scoring_client, test_data):
        payload = high_risk_transaction(test_data["user_id"])

        response = scoring_client.create_transaction(payload)
        assert_status_code(response, HTTP_STATUS_OK)

        scored = scoring_client.wait_for_decision(test_data["user_id"], Decision.BLOCK)
        assert_decision(scored, Decision.BLOCK)
```

Негативные кейсы, где невалидное тело нельзя собрать моделью, идут через
`*_raw`-методы клиента, а само тело — из фабрики в `payloads.py`:

```python
response = scoring_client.create_user_raw(user_body_without_name())
assert_status_code(response, HTTP_STATUS_BAD_REQUEST)
```

Тело запроса из модели отдаётся методом `.body()` — модель сама знает, как
превратиться в JSON-совместимый словарь:

```python
def create_transaction(self, payload: TransactionPayload) -> requests.Response:
    return self.post(transactions_path(), json=payload.body())
```

### Одно «пустое» состояние вместо `None`

В коде нет ни одного `X | None`. Модели ответов объявляют только те поля,
которые фреймворк реально читает (`id`, `decision`), остальное тело сохраняется
как есть и по-прежнему видно в `as_dict()` — в логах и сообщениях о падении.
Отсутствующее значение — это пустая строка, а не `None`:

```python
class Transaction(ResponseModel):
    id: str = ""
    decision: str = NOT_SCORED  # пусто, пока скоринг не отработал
```

Сравнение с enum при этом работает как раньше (`Decision` — это `StrEnum`):
`transaction.decision == Decision.BLOCK`. Так же устроен и репозиторий БД —
`last_decision()` возвращает пустую строку, если транзакций ещё нет, а
`_fetch_one()` — пустой кортеж вместо `None`.

### Клиент ждёт, тест проверяет

`wait_for_scored()` ждёт, пока сервис проставит **любое** решение, и возвращает
транзакцию. Какое именно решение ожидается — проверяет сам тест:

```python
scored = scoring_client.wait_for_scored(test_data["user_id"])
assert_decision(scored, Decision.BLOCK)
```

Это не стилистика, а работоспособность проверки. Если клиент ждёт конкретного
решения, то при неверном решении он молча крутится до таймаута, а `assert` в
тесте становится декоративным — упасть он не может никогда. С текущим разделением
неверное решение падает сразу и по делу:

```
AssertionError: Expected BLOCK, got APPROVE: {'id': '2e2f1ff3-…', 'decision': 'APPROVE', 'amount': 75000, …}
```

## Фикстуры

`conftest.py` держит только оглавление — сами фикстуры лежат в `fixtures/`,
разделённые по назначению: системный слой (конфиг, CLI) отдельно от того, с чем
работает автор теста (клиент, БД, тестовые данные).

```python
# conftest.py целиком
pytest_plugins = [
    "fixtures.environment",
    "fixtures.clients",
    "fixtures.database",
    "fixtures.data",
]
```

| Фикстура | Модуль | Скоуп | Что даёт |
|---|---|---|---|
| `config` | environment | session | `Config` из окружения, `--scoring-base-url` перекрывает `SCORING_BASE_URL` |
| `scoring_client` | clients | session | клиент API; HTTP-сессия с ретраями закрывается на выходе |
| `scoring_db` | database | session | доступ к БД; без `SCORING_DB_URL` db-тесты скипаются |
| `test_data` | data | function | созданный пользователь (`test_data["user_id"]`), удаляется в teardown |
| `created_users` | data | function | реестр id для тестов, которые создают юзера сами; удаляются в teardown |

## Запуск

Быстрый старт без стенда — на встроенной заглушке:

```bash
pip install -r requirements.txt
python3 stub/scoring_stub.py &
SCORING_BASE_URL=http://127.0.0.1:8099 pytest -m "not db"    # 18 passed
```

Против реального сервиса:

```bash
cp .env.example .env          # и подставить свой стенд

export SCORING_BASE_URL="http://<host>:8080"
export SCORING_DB_URL="postgresql+psycopg2://<user>:<password>@<host>:5432/scoring"

pytest                                  # весь сьют
pytest -m smoke                         # только смоук
pytest -m positive / -m negative        # позитив / негатив
pytest -m "not db"                      # без похода в БД
pytest --scoring-base-url http://stage:8080

pytest --alluredir=allure-results       # отчёт
allure serve allure-results
```

Без `SCORING_DB_URL` тесты с маркером `db` скипаются, остальные работают.

Прогон не оставляет мусора в каталоге проекта: в `addopts` отключён глобально
установленный плагин `playwright_visual_snapshot`, который иначе создаёт
`snapshot_failures/` и `__snapshots__/` при каждом запуске. Сьют чисто
API-шный и скриншотов не делает. Флаг безопасен и там, где плагина нет.

## Работа с БД

Подключение — через SQLAlchemy. Адрес задаётся SQLAlchemy-URL:

```bash
export SCORING_DB_URL="postgresql+psycopg2://<user>:<password>@<host>:5432/scoring"
```

Устройство слоя:

Слой разделён так же, как HTTP: транспорт отдельно, домен отдельно.

| Файл | Отвечает за |
|---|---|
| `base_db_client.py` | `build_engine()`, пул, `cursor()`, `transaction()`, `fetch_one()` — *как* запрос доходит до базы |
| `scoring_db_client.py` | SQL-константы и именованные запросы (`last_decision`, `count_transactions`) — *какой* это запрос |

* `scoring_database(url)` — контекстный менеджер на весь прогон: создаёт
  `Engine` и гарантированно вызывает `dispose()` на выходе, даже если прогон
  прерван. Клиент API устроен симметрично — `scoring_api(config)`. `pool_pre_ping=True` — одна дешёвая проверка при выдаче соединения,
  чтобы не падать на протухшем коннекте после передеплоя стенда;
* **между запросами и тестами ничего не удерживается.** Репозиторий владеет
  движком, а не соединением: каждый запрос берёт коннект из пула внутри `with`
  и возвращает его сразу же. Выход из блока закрывает неявную транзакцию,
  поэтому на стенде не остаётся сессий в состоянии *idle in transaction*, и
  один тест не блокирует другой на тех же строках;
* SQL живёт в константах модуля, параметры связываются по имени (`:user_id`),
  строки не склеиваются — инъекция невозможна;
* два контекстных менеджера на все случаи, с одинаковой гарантией «ничего не
  удерживаем»: `cursor()` — на чтение, `transaction()` — на запись:

  ```python
  # разовый SELECT
  with scoring_db.cursor() as cur:
      cur.execute(text("SELECT ..."), {"user_id": user_id})

  # подготовка или уборка данных
  with scoring_db.transaction() as cur:
      cur.execute(text("DELETE FROM transactions WHERE user_id = :user_id"), params)
  ```

  `transaction()` коммитит на выходе из блока и откатывает при любом исключении,
  поэтому упавший на середине тест не оставляет наполовину записанных данных;

* каждый запрос логируется вместе с параметрами, поэтому упавшую проверку
  можно повторить руками прямо из лога.

```python
LAST_DECISION_SQL = """
    SELECT decision FROM transactions
     WHERE user_id = :user_id
     ORDER BY created_at DESC
     LIMIT 1
"""
```

Все импорты — на уровне модулей, ленивых импортов внутри функций в коде нет.
`SQLAlchemy` объявлена обязательной зависимостью в `requirements.txt`; драйвер
БД подтягивается только при создании движка, поэтому без `SCORING_DB_URL`
db-тесты скипаются и psycopg2 не требуется.

## Логирование

Логируем на всех слоях, а не только HTTP. Все логгеры — в одном дереве
`scoring.*`, поэтому уровень крутится одной строкой в `pytest.ini`, а в CI
можно грепать по слою:

| Логгер | Где | Что пишет |
|---|---|---|
| `scoring.http` | `api/clients/base_client.py` | `--> METHOD URL`, `<-- status (ms)`; params и тела на DEBUG |
| `scoring.scoring` | `api/clients/scoring_client.py` | созданный пользователь, отправленная транзакция, каждый poll решения |
| `scoring.db` | `api/clients/db_client.py` | создание engine (пароль скрыт), SQL с параметрами, результат |
| `scoring.check` | `api/utils/validators.py` | пройденные проверки на DEBUG, упавшие на ERROR |
| `scoring.check.db` | `api/utils/db_validators.py` | то же для проверок в БД |
| `scoring.fixture` | `conftest.py` | конфиг прогона, создание и удаление тестовых данных |

Куда идёт вывод:

* `logs/pytest.log` — полный DEBUG, весь прогон; годится как артефакт CI;
* при падении pytest сам печатает `Captured log` этого теста — видно всю
  последовательность запросов, приведшую к ошибке;
* живой лог в консоль выключен по умолчанию (иначе он дублируется в отчёте о
  падении) — включается по требованию: `pytest -o log_cli=true`.

Пример живого лога одного теста:

```
INFO  scoring.fixture  run config: base_url=http://127.0.0.1:8099 db_configured=False
INFO  scoring.http     --> POST http://127.0.0.1:8099/api/users
INFO  scoring.http     <-- 201 Created (1 ms)
INFO  scoring.scoring  user created: id=75b42d94-… name=Test User
INFO  scoring.scoring  sending transaction: user=75b42d94-… amount=75000 SAR category=crypto country=AE
INFO  scoring.http     --> POST http://127.0.0.1:8099/api/transactions
INFO  scoring.http     <-- 200 OK (1 ms)
INFO  scoring.scoring  waiting up to 5.0s for decision BLOCK (user=75b42d94-…)
INFO  scoring.scoring  got BLOCK after 0.0s (1 poll(s))
INFO  scoring.fixture  teardown: deleting user 75b42d94-…
```

Две вещи, которые стоит помнить:

* **Секреты маскируются.** Всё, что может содержать креды (DSN, заголовки,
  тела), проходит через `mask_secrets()`: `password=admin123` превращается в
  `password=***`, `Authorization: Bearer …` — в `Authorization: ***`, а в
  SQLAlchemy-URL прячется пароль: `postgresql+psycopg2://admin:***@host/db`.
  Пароль от БД не утечёт в лог CI.
* **Чужой DEBUG приглушён.** `silence_noisy_loggers()` в `pytest_configure`
  опускает `urllib3` и другие сторонние логгеры до WARNING, иначе на DEBUG они
  забивают собственные строки фреймворка.

## Линтер

```bash
ruff check .        # линт, 0 замечаний
ruff format .       # форматирование, line-length 110
```

Про 110 важно: ruff-форматтер не умеет «наполнять» строку — всё, что не влезло
в лимит, он разносит по одному элементу на строку. Поэтому длина ограничения
здесь не только про читаемость: имена и группировка подобраны так, чтобы каждый
импорт и каждая сигнатура укладывались в одну строку и ничего не разъезжалось
в вертикальную колонку.

`ruff.toml` наследует общий набор правил проекта (`extend = "../pyproject.toml"`)
и добавляет только то, что специфично для тестового кода:

* `S101` разрешён в `tests/` и в модулях валидаторов — `assert` тут инструмент,
  а не уязвимость;
* `ANN` выключен в `tests/` — сигнатуры тестов пишем без аннотаций, как в
  рабочем проекте; в `api/` и `utils/` аннотации обязательны;
* `ARG` выключен в `tests/` — фикстура может быть нужна ради side-effect;
* `ANN401` разрешён в клиентах — psycopg2 без стабов и passthrough-`kwargs`
  в `requests` честно типизируются как `Any`;
* `ANN401` разрешён в `api/models.py` — «before»-валидатор Pydantic получает
  то, что реально прислал сервис, и `Any` тут честнее любой выдумки;
* `runtime-evaluated-base-classes = ["pydantic.BaseModel"]` — без этой настройки
  ruff предлагает спрятать импорты enum'ов из `api/models.py` в `if TYPE_CHECKING`,
  и Pydantic перестаёт собирать модель (аннотации ему нужны в рантайме).

## Что было исправлено при разборе исходного файла

Ошибки, из-за которых код не запускался вообще:

* `import requests as r` + локальная переменная `r` → `UnboundLocalError`;
* `requests.post(url)(payload)` → вызов `Response` как функции, `TypeError`;
* `request.delete(...)` → опечатка, `NameError`;
* `BASE_URL` со вставленным markdown-линком внутри строки;
* `last` определялась внутри цикла и «утекала» в assert.

Замечания ревью и как они закрыты:

| Замечание | Где решено |
|---|---|
| URL и эндпоинты в константы | `api/utils/constants.py::SCR_ENDPOINTS` |
| креды из env/Vault, не в коде | `utils/config.py`, `.env.example` |
| ORM-подход вместо голого драйвера | SQLAlchemy в `api/clients/db_client.py` |
| билдер запросов вне тестов | `api/clients/base_client.py`, `api/clients/scoring_client.py` |
| payload по Pydantic-моделям | `api/models.py` |
| cleanup в teardown-фикстуру | `conftest.py::test_data` |
| убрать `time.sleep` из тестов | ретраи в `build_session()`, поллинг в `wait_for_decision()` |
| `HTTPStatus` вместо чисел | `utils/utils.py::HTTP_STATUS_*` |
| проверки в кастомные валидаторы | `api/utils/validators.py`, `api/utils/db_validators.py` |
| `.get()` вместо индексации ответа | модели с `| None` полями вместо `dict[...]` |
| разный набор вызовов | `@pytest.mark.parametrize` в тестах |
| Arrange / Act / Assert | табуляция блоков внутри каждого теста |

Сверх ревью: SQL параметризован (`WHERE user_id = %s`) — в исходнике был
f-string, то есть SQL-инъекция; соединение с БД закрывается через контекстный
менеджер; решение берётся по `ORDER BY created_at DESC LIMIT 1`.

## Что стоит доделать под реальный сервис

* Сверить ожидаемые коды ответов (`201` на создание пользователя, `200` на
  транзакцию, `204` на удаление) с контрактом API.
* Проверить имена полей в БД (`created_at`) и схему таблицы `transactions`.
* При желании заменить текстовый SQL на ORM-модели SQLAlchemy — репозиторий
  для этого уже изолирован, тесты трогать не придётся.
* Уточнить `SCR_LIMITS["frequency_threshold"]` — сейчас 5 по описанию правила.
