# Scoring API Test Framework

API-тесты сервиса скоринга транзакций: pytest + requests + Pydantic + SQLAlchemy + Allure.

Сервис принимает транзакции пользователя, асинхронно проставляет каждой решение
(`APPROVE` / `MANUAL_REVIEW` / `BLOCK`) и сохраняет результат в Postgres. Сьют
проверяет и то, что отдаёт API, и то, что легло в базу.

В комплекте mock-сервис на стандартной библиотеке, поэтому тесты можно
запустить сразу после клонирования, без доступа к стенду.

## Быстрый старт

```bash
pip install -r requirements.txt

python3 -m mock_server &
SCORING_BASE_URL=http://127.0.0.1:8099 pytest -m "not db"
```

Ожидаемый результат — `18 passed`.

## Запуск против стенда

```bash
cp .env.example .env     # и подставить адреса своего стенда

export SCORING_BASE_URL="http://<host>:8080"
export SCORING_DB_URL="postgresql+psycopg2://<user>:<password>@<host>:5432/scoring"

pytest                                       # весь сьют
pytest -m smoke                              # смоук
pytest -m positive        / -m negative      # позитив / негатив
pytest -m "not db"                           # без похода в базу
pytest --scoring-base-url http://stage:8080  # адрес флагом вместо переменной

pytest --alluredir=allure-results
allure serve allure-results
```

Без `SCORING_DB_URL` тесты с маркером `db` скипаются, остальные работают.
Все настройки — таймауты, ретраи, интервал опроса — читаются из окружения,
список с значениями по умолчанию лежит в `.env.example`.

## Структура

```
scoring_test_framework/
├── conftest.py              точка входа pytest: список плагинов с фикстурами
├── pytest.ini               маркеры и логирование
├── ruff.toml                правила линтера
├── requirements.txt
├── .env.example             переменные окружения
│
├── tests/                   сценарии — и больше ничего
│   ├── test_users.py
│   ├── test_transactions.py
│   └── test_frequency_rule.py
│
├── fixtures/
│   ├── environment.py       конфигурация прогона и CLI-опции
│   ├── clients.py           scoring_client
│   ├── database.py          scoring_db
│   └── data.py              test_data, created_users — данные и их уборка
│
├── api/
│   ├── models.py            Pydantic-модели запросов и ответов
│   ├── clients/
│   │   ├── base_client.py       HTTP-транспорт: ретраи, таймауты, логи, Allure
│   │   ├── scoring_client.py    методы API и ожидание асинхронного решения
│   │   ├── base_db_client.py    транспорт БД: движок, пул, курсоры
│   │   └── scoring_db_client.py SQL и именованные запросы
│   └── utils/
│       ├── constants.py     эндпоинты, лимиты, перечисления, невалидные данные
│       ├── payloads.py      фабрики тел запросов
│       ├── validators.py    assert_status_code, assert_valid_json, assert_decision …
│       └── db_validators.py проверки того, что легло в базу
│
├── utils/
│   ├── config.py            конфигурация из окружения
│   ├── logger.py            логгеры и маскировка секретов
│   └── utils.py             HTTP_STATUS_*, env-хелперы
│
└── mock_server/             mock-сервис для локального запуска
    ├── scoring.py           состояние, правила скоринга, эндпоинты
    ├── server.py            таблица маршрутов и диспетчер
    └── __main__.py          python3 -m mock_server
```

Правило слоёв: тест знает только клиент, фабрики данных, константы и валидаторы.
URL, SQL, таймауты, ретраи и креды в тестовых модулях не встречаются — там нет
даже вспомогательных функций, только сценарии.

Код, комментарии и сообщения об ошибках — на английском.

## Как выглядит тест

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

        scored = scoring_client.wait_for_scored(test_data["user_id"])
        assert_decision(scored, Decision.BLOCK)
```

Тела запросов собираются Pydantic-моделями. Для негативных случаев, где
невалидное тело моделью не собрать, у клиента есть `*_raw`-методы, а само тело
приходит из фабрики:

```python
response = scoring_client.create_user_raw(user_body_without_name())
assert_status_code(response, HTTP_STATUS_BAD_REQUEST)
```

## Фикстуры

`conftest.py` содержит только список плагинов — сами фикстуры лежат в
`fixtures/`, разделённые по назначению.

| Фикстура | Скоуп | Что даёт |
|---|---|---|
| `config` | session | конфигурация прогона; `--scoring-base-url` перекрывает `SCORING_BASE_URL` |
| `scoring_client` | session | клиент API; HTTP-сессия с ретраями закрывается на выходе |
| `scoring_db` | session | доступ к базе; без `SCORING_DB_URL` db-тесты скипаются |
| `test_data` | function | созданный пользователь (`test_data["user_id"]`), удаляется в teardown |
| `created_users` | function | реестр id для тестов, создающих пользователя самостоятельно |

Уборка всегда живёт в teardown-половине фикстуры, поэтому отрабатывает и когда
тест упал, и когда прогон прерван.

## Асинхронное решение

Скоринг асинхронный, поэтому вместо `time.sleep()` используется опрос с
дедлайном: быстрый сервис не заставляет тест ждать, медленный не делает его
нестабильным. Таймаут и интервал берутся из конфигурации.

Клиент ждёт **любое** решение, а какое именно ожидается — проверяет тест:

```python
scored = scoring_client.wait_for_scored(test_data["user_id"])
assert_decision(scored, Decision.BLOCK)
```

Это принципиально. Если бы клиент ждал конкретного решения, при неверном
решении он молча крутился бы до таймаута, а проверка в тесте не могла бы
упасть никогда. Сейчас неверное решение падает сразу и по делу:

```
AssertionError: Expected BLOCK, got APPROVE: {'id': '2e2f1ff3-…', 'decision': 'APPROVE', 'amount': 75000, …}
```

## Работа с базой

Подключение через SQLAlchemy, адрес задаётся SQLAlchemy-URL. Слой разделён так
же, как HTTP: транспорт отдельно, домен отдельно.

| Файл | Отвечает за |
|---|---|
| `base_db_client.py` | движок, пул, `cursor()`, `transaction()`, `fetch_one()` — *как* запрос доходит до базы |
| `scoring_db_client.py` | SQL-константы и именованные запросы (`last_decision`, `count_transactions`) — *какой* это запрос |

Ключевые свойства:

* **между запросами и тестами ничего не удерживается.** Клиент владеет движком,
  а не соединением: каждый запрос берёт коннект из пула внутри `with` и сразу
  возвращает. На стенде не остаётся сессий в состоянии *idle in transaction*, и
  один тест не блокирует другой на тех же строках;
* SQL живёт в константах модуля, параметры связываются по имени (`:user_id`) —
  строки не склеиваются, инъекция невозможна;
* два контекстных менеджера с одинаковой гарантией: `cursor()` на чтение,
  `transaction()` на запись — второй коммитит на выходе из блока и откатывает
  при любом исключении, поэтому упавший тест не оставляет полузаписанных данных;
* каждый запрос логируется вместе с параметрами, поэтому упавшую проверку можно
  повторить руками прямо из лога.

```python
# разовый SELECT
with scoring_db.cursor() as cur:
    cur.execute(text("SELECT ..."), {"user_id": user_id})

# подготовка или уборка данных
with scoring_db.transaction() as cur:
    cur.execute(text("DELETE FROM transactions WHERE user_id = :user_id"), params)
```

## Логирование

Логируются все слои, а не только HTTP. Логгеры собраны в одно дерево `scoring.*`,
поэтому уровень меняется одной строкой в `pytest.ini`, а в CI можно фильтровать
по слою: `scoring.http`, `scoring.scoring`, `scoring.db`, `scoring.check`,
`scoring.fixture`.

```
INFO  scoring.fixture  run config: base_url=http://127.0.0.1:8099 db_configured=False
INFO  scoring.http     --> POST http://127.0.0.1:8099/api/transactions
INFO  scoring.http     <-- 200 OK (1 ms)
INFO  scoring.scoring  waiting up to 15.0s for a decision (user=75b42d94-…)
INFO  scoring.scoring  scored BLOCK after 0.4s (2 poll(s))
INFO  scoring.fixture  teardown: deleting user 75b42d94-…
```

* `logs/pytest.log` — полный DEBUG за весь прогон, годится как артефакт CI;
* при падении pytest печатает `Captured log` этого теста — видна вся
  последовательность запросов, приведшая к ошибке;
* живой лог в консоли выключен по умолчанию, включается флагом:
  `pytest -o log_cli=true`.

**Секреты маскируются.** Всё, что может содержать креды, проходит через
`mask_secrets()`: `password=…` превращается в `password=***`,
`Authorization: Bearer …` — в `Authorization: ***`, в SQLAlchemy-URL прячется
пароль (`postgresql+psycopg2://admin:***@host/db`). Пароль от базы не попадёт в
лог CI.

## Линтер

```bash
ruff check .
ruff format .
```

Конфигурация в `ruff.toml`, самодостаточная — внешних файлов не требует.
Длина строки 110: ruff-форматтер не «наполняет» строку, а разносит по одному
элементу всё, что не влезло, поэтому имена и группировка подобраны так, чтобы
импорты и сигнатуры укладывались в одну строку.

## Что стоит сверить с реальным сервисом

Ожидаемое поведение взято из описания API; перед первым прогоном на стенде
имеет смысл проверить:

* коды ответов: `201` на создание пользователя, `200` на транзакцию, `204` на удаление;
* схему таблицы `transactions` и имя поля `created_at`;
* порог частотного правила — сейчас `SCR_LIMITS["frequency_threshold"] = 5`.
