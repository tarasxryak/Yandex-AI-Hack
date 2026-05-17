# graphql_query_service

Flask API для генерации GraphQL-запросов по схеме конкретного чата.

Сервис работает так:

1. Клиент вызывает `POST /create_workspace` с GraphQL `endpoint`.
2. API внутри себя вызывает `docs-parser`, получает GraphQL SDL через introspection.
3. API создаёт id workspace/chat, сохраняет SDL в MySQL в таблицу `workspaces`
   и возвращает id клиенту.
4. Клиент вызывает `POST /query` с этим id и текстом запроса.
5. API достаёт схему из MySQL и просит YandexGPT собрать GraphQL operation.

Публичные клиенты ходят только в `api`. `docs-parser` нужен как внутренний сервис
для introspection.

## Сервисы

Docker Compose поднимает:

- `api`: `http://localhost:8080`
- `api static`: `http://localhost:8080/static/<id>.pdf`
- `docs-parser`: внутренний сервис Compose, наружу не публикуется
- `mysql`: внутренний сервис Compose, наружу не публикуется
- `adminer`: опционально через profile `tools`, `http://127.0.0.1:8082`
- `nocodb`: опционально через profile `tools`, `http://127.0.0.1:8083`

## Хранение

В MySQL используется одна прикладная таблица:

```sql
CREATE TABLE workspaces (
    chat_id VARCHAR(255) PRIMARY KEY,
    `schema` LONGTEXT NOT NULL
);
```

`chat_id` — id workspace/chat, который создаёт сервис.  
`schema` — GraphQL SDL, полученный через introspection.

## Переменные окружения

Создай `.env` в этой папке:

```bash
YANDEX_API_KEY="..."
YANDEX_FOLDER_ID="..."
```

Опциональные переменные:

```bash
YANDEX_MODEL_URI="gpt://<folder_id>/yandexgpt/latest"
YANDEX_OPENAI_BASE_URL="https://llm.api.cloud.yandex.net/v1"
YANDEX_TEMPERATURE="0.3"
YANDEX_MAX_TOKENS="2000"

MYSQL_HOST="mysql"
MYSQL_PORT="3306"
MYSQL_DATABASE="ruchki"
MYSQL_USER="ruchki"
MYSQL_PASSWORD="ruchki"

DOCS_PARSER_URL="http://docs-parser:8080"

FRONTEND_ORIGINS="https://yandex-ai-hack-zh9q.vercel.app,http://localhost:5173,http://127.0.0.1:5173"

REPORTS_DIR="/app/static"
REPORT_SOURCE_PATH="/app/core/product_report.pdf"

API_BIND="0.0.0.0"
API_PORT="8080"
ADMINER_BIND="127.0.0.1"
ADMINER_PORT="8082"
NOCODB_BIND="127.0.0.1"
NOCODB_PORT="8083"
```

## Запуск

```bash
docker compose up --build -d
```

Проверить контейнеры:

```bash
docker compose ps
```

Проверить сохранённые схемы в MySQL:

```bash
docker compose exec mysql mysql -uruchki -pruchki ruchki \
  -e 'select chat_id, length(`schema`) as schema_length from workspaces;'
```

Adminer доступен на `http://localhost:8082`.

Запустить Adminer:

```bash
docker compose --profile tools up -d adminer
```

Данные для входа:

```text
System: MySQL
Server: mysql
Username: ruchki
Password: ruchki
Database: ruchki
```

NocoDB доступен на `http://localhost:8083`.

Запустить NocoDB:

```bash
docker compose --profile tools up -d nocodb
```

Подключение к MySQL внутри NocoDB:

```text
Host: mysql
Port: 3306
Database: ruchki
Username: ruchki
Password: значение MYSQL_PASSWORD из .env
```

Для подключения к MySQL из той же Docker-сети NocoDB запускается с
`NC_ALLOW_LOCAL_EXTERNAL_DBS=true`. Без этого свежие версии NocoDB могут
отклонять `mysql` с ошибкой `Forbidden host name or IP address`.

На сервере Adminer и NocoDB по умолчанию слушают только `127.0.0.1`. Для доступа
с локальной машины используй SSH tunnel:

```bash
ssh -L 8082:127.0.0.1:8082 -L 8083:127.0.0.1:8083 <user>@<server-ip>
```

## Запуск на сервере

На сервере рядом должны лежать оба каталога:

```text
project-root/
  core/
  backend/
    docs_parsing/
    graphql_query_service/
```

Минимальный порядок:

```bash
cd backend/graphql_query_service
cp .env.example .env  # если есть шаблон; иначе создай .env вручную
nano .env
docker compose up --build -d
docker compose ps
curl http://127.0.0.1:8080/healthz
```

Для сервера в `.env` обязательно задай реальные значения:

```bash
YANDEX_API_KEY="..."
YANDEX_FOLDER_ID="..."
MYSQL_ROOT_PASSWORD="..."
MYSQL_PASSWORD="..."
API_BIND="0.0.0.0"
API_PORT="8080"
```

Если API должен быть доступен через домен, повесь reverse proxy на
`http://127.0.0.1:8080` и поменяй `API_BIND` на `127.0.0.1`, чтобы порт API не
торчал напрямую в интернет.

## Публичные ручки

### GET /healthz

Проверка, что API жив.

Ответ `200`:

```json
{
  "status": "ok"
}
```

### POST /create_workspace

Создаёт workspace/chat и сохраняет схему.

Внутри ручка делает introspection по `endpoint`, получает SDL, создаёт id и
сохраняет схему в MySQL по этому id.

Request:

```json
{
  "endpoint": "https://target-api.com/graphql"
}
```

Request для endpoint с авторизацией через headers:

```json
{
  "endpoint": "https://target-api.com/graphql",
  "headers": {
    "Authorization": "Bearer TOKEN"
  }
}
```

Request для endpoint с авторизацией через token:

```json
{
  "endpoint": "https://target-api.com/graphql",
  "token": "TOKEN"
}
```

Успешный ответ `201`:

```json
{
  "success": true,
  "id": "66b35dbe07614fd687a56883f1952a72",
  "chat_id": "66b35dbe07614fd687a56883f1952a72",
  "schema_saved": true,
  "schema_length": 12345,
  "introspection_status": "ok"
}
```

Ошибка валидации `400`:

```json
{
  "success": false,
  "error": "endpoint is required"
}
```

Если endpoint требует авторизацию, ответ `401`:

```json
{
  "success": false,
  "introspection": {
    "success": false,
    "status": "auth_required",
    "message": "GraphQL endpoint requires authorization for introspection",
    "http_status": 401,
    "endpoint": "https://target-api.com/graphql"
  }
}
```

### POST /query

Собирает GraphQL operation по схеме, сохранённой для `id`.

Request:

```json
{
  "id": "66b35dbe07614fd687a56883f1952a72",
  "query": "Составь GraphQL запрос персонажа по id: id name status species",
  "request_body": {
    "id": "1"
  }
}
```

`request_body` можно не передавать, если все нужные значения уже есть в `query`.
Также поддерживается alias `body`.

Успешный ответ `200`:

```json
{
  "success": true,
  "chat_id": "66b35dbe07614fd687a56883f1952a72",
  "graphql": {
    "query": "query GetCharacter($id: ID!) { character(id: $id) { id name status species } }",
    "variables": {
      "id": "1"
    },
    "operationName": "GetCharacter",
    "note": "",
    "hints": [
      "получи список персонажей с их именами и статусами",
      "найди персонажей по имени или статусу",
      "выведи эпизоды, в которых появлялся персонаж"
    ],
    "report_json": "http://localhost:8080/static/66b35dbe07614fd687a56883f1952a72.pdf"
  }
}
```

Главное поле для клиента — `graphql`. Стабильный контракт для фронта:

```text
graphql.query          GraphQL operation, который можно отправлять в целевой API
graphql.variables      variables для GraphQL operation
graphql.operationName  имя операции или null
graphql.note           пустая строка, если всё получилось; причина/комментарий, если нет
graphql.hints          2-3 подсказки на русском, что ещё можно запросить
graphql.report_json    ссылка на PDF-отчёт или null, если отчёт ещё не найден
```

Если `graphql.query` объявляет переменные (`$id`, `$name`, `$page`), их значения
должны лежать в `graphql.variables`:

```json
{
  "query": "query GetCharacterByName($name: String!) { characters(filter: { name: $name }) { results { id name } } }",
  "variables": {
    "name": "Rick"
  },
  "operationName": "GetCharacterByName",
  "note": "",
  "hints": [],
  "report_json": null
}
```

API дополнительно пытается дозаполнить отсутствующие variables из `request_body`
по совпадающему ключу. Например `request_body.name` попадёт в `variables.name`.
Если значение для объявленной переменной не найдено, причина будет добавлена в
`graphql.note`.

PDF берётся из `REPORT_SOURCE_PATH` (`/app/core/product_report.pdf` в Docker) и
публикуется как `/static/<chat_id>.pdf`. Если файл отчёта ещё не создан, API
вернёт `"report_json": null`.

Если модель не смогла собрать запрос, `graphql.query` будет пустой строкой, а
причина будет в `graphql.note`:

```json
{
  "graphql": {
    "query": "",
    "variables": {},
    "operationName": null,
    "note": "Не хватает id персонажа для запроса.",
    "hints": [
      "укажи id персонажа и поля, которые нужно получить",
      "получи список персонажей с их id и именами",
      "найди персонажей по имени или статусу"
    ],
    "report_json": null
  }
}
```

Если для `id` ещё нет схемы, ответ `404`:

```json
{
  "success": false,
  "error": "schema not found for chat_id"
}
```

## Пример Rick And Morty

Сначала сохраняем схему:

```bash
curl -X POST http://localhost:8080/create_workspace \
  -H 'Content-Type: application/json' \
  -d '{
    "endpoint": "https://rickandmortyapi.com/graphql"
  }'
```

Ожидаемый ответ:

```json
{
  "success": true,
  "id": "66b35dbe07614fd687a56883f1952a72",
  "chat_id": "66b35dbe07614fd687a56883f1952a72",
  "schema_saved": true,
  "schema_length": 3602,
  "introspection_status": "ok"
}
```

Потом просим собрать GraphQL-запрос:

```bash
curl -X POST http://localhost:8080/query \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "66b35dbe07614fd687a56883f1952a72",
    "query": "Составь GraphQL запрос персонажа по id: id name status species image origin.name location.name",
    "request_body": {
      "id": "1"
    }
  }'
```

Форма успешного ответа:

```json
{
  "success": true,
  "chat_id": "66b35dbe07614fd687a56883f1952a72",
  "graphql": {
    "query": "query ...",
    "variables": {},
    "operationName": "...",
    "note": "",
    "hints": [
      "получи список всех эпизодов с их названиями и датами выхода",
      "найди эпизоды, в названии которых есть определённое слово",
      "выведи информацию о конкретном эпизоде по его ID"
    ],
    "report_json": "http://localhost:8080/static/66b35dbe07614fd687a56883f1952a72.pdf"
  }
}
```
