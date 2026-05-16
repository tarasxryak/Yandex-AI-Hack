# ruchki_ebuchie

Flask API that stores one GraphQL schema per chat and builds GraphQL operations
from user requests through YandexGPT.

## Storage

SQLite has exactly one application table:

```sql
CREATE TABLE workspaces (
    chat_id TEXT PRIMARY KEY,
    schema TEXT NOT NULL
);
```

`chat_id` is the external chat identifier. `schema` is GraphQL SDL received from
introspection.

## Services

When started with Docker Compose:

- `ruchki`: `http://localhost:8080`
- `docs-parser`: `http://localhost:8081`

`docs-parser` is an internal service for introspection. Public API clients should
call only `ruchki`. `ruchki` calls `docs-parser` internally through:

```bash
DOCS_PARSER_URL=http://docs-parser:8080
```

## Environment

Put Yandex credentials into `.env` in this directory:

```bash
YANDEX_API_KEY="..."
YANDEX_FOLDER_ID="..."
```

Optional:

```bash
YANDEX_MODEL_URI="gpt://<folder_id>/yandexgpt/latest"
YANDEX_OPENAI_BASE_URL="https://llm.api.cloud.yandex.net/v1"
YANDEX_TEMPERATURE="0.3"
YANDEX_MAX_TOKENS="2000"
SQLITE_PATH="sqlite.db"
DOCS_PARSER_URL="http://docs-parser:8080"
```

## Run

```bash
docker compose up --build -d
```

Local Python run:

```bash
pip install -r requirements.txt
python app.py
```

## Contracts

### GET /healthz

Response `200`:

```json
{
  "status": "ok"
}
```

### POST /create_workspace

Creates or updates schema for a chat. The service runs GraphQL introspection for
`endpoint` and saves returned SDL into `workspaces.schema` by `chat_id`.

Request:

```json
{
  "chat_id": "telegram-chat-123",
  "endpoint": "https://target-api.com/graphql"
}
```

Request with private introspection:

```json
{
  "chat_id": "telegram-chat-123",
  "endpoint": "https://target-api.com/graphql",
  "headers": {
    "Authorization": "Bearer TOKEN"
  }
}
```

Alternative auth shortcut:

```json
{
  "chat_id": "telegram-chat-123",
  "endpoint": "https://target-api.com/graphql",
  "token": "TOKEN"
}
```

Success response `201`:

```json
{
  "success": true,
  "workspace": {
    "chat_id": "telegram-chat-123",
    "schema": "type Query { ... }"
  },
  "introspection": {
    "success": true,
    "status": "ok",
    "endpoint": "https://target-api.com/graphql",
    "sdl": "type Query { ... }"
  }
}
```

Auth required response `401`:

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

Builds a GraphQL operation using schema saved for `chat_id`.

Request:

```json
{
  "chat_id": "telegram-chat-123",
  "query": "Составь GraphQL запрос персонажа по id: id name status species",
  "request_body": {
    "id": "1"
  }
}
```

`request_body` is optional if the text in `query` already contains all needed
values. The alias `body` is also accepted.

Success response `200`:

```json
{
  "success": true,
  "chat_id": "telegram-chat-123",
  "answer": "...raw model answer...",
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

Schema missing response `404`:

```json
{
  "success": false,
  "error": "schema not found for chat_id"
}
```

## Rick And Morty Example

Create schema for chat:

```bash
curl -X POST http://localhost:8080/create_workspace \
  -H 'Content-Type: application/json' \
  -d '{
    "chat_id": "rick-chat",
    "endpoint": "https://rickandmortyapi.com/graphql"
  }'
```

Build query:

```bash
curl -X POST http://localhost:8080/query \
  -H 'Content-Type: application/json' \
  -d '{
    "chat_id": "rick-chat",
    "query": "Составь GraphQL запрос персонажа по id: id name status species image origin.name location.name",
    "request_body": {
      "id": "1"
    }
  }'
```
