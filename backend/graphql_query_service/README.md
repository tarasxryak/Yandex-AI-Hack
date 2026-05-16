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

На сервере Adminer и NocoDB по умолчанию слушают только `127.0.0.1`. Для доступа
с локальной машины используй SSH tunnel:

```bash
ssh -L 8082:127.0.0.1:8082 -L 8083:127.0.0.1:8083 <user>@<server-ip>
```

## Запуск на сервере

На сервере рядом должны лежать оба каталога:

```text
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
  "id": "66b35dbe07614fd687a56883f1952a72",
  "chat_id": "66b35dbe07614fd687a56883f1952a72",
  "answer": "...сырой ответ модели...",
  "graphql": {
    "query": "query GetCharacter($id: ID!) { character(id: $id) { id name status species } }",
    "variables": {
      "id": "1"
    },
    "operationName": "GetCharacter"
  },
  "raw": {}
}
```

Главное поле для клиента — `graphql`.

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
  "id": "66b35dbe07614fd687a56883f1952a72",
  "chat_id": "66b35dbe07614fd687a56883f1952a72",
  "graphql": {
    "query": "query ...",
    "variables": {},
    "operationName": "..."
  }
}
```
