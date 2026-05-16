# Docs Parser

GraphQL introspection proxy service.

## Run Locally

```bash
go run ./cmd/docs-parser -serve :8080
```

## Docker

Build and run:

```bash
docker build -t docs-parser .
docker run --rm -p 8080:8080 docs-parser
```

Or with Compose:

```bash
docker compose up --build
```

Health check:

```bash
curl http://localhost:8080/healthz
```

## API

```bash
curl -X POST http://localhost:8080/introspect \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://target-api.com/graphql"
  }'
```

With auth:

```bash
curl -X POST http://localhost:8080/introspect \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://target-api.com/graphql",
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN"
    }
  }'
```

By default the service returns a compact preprocessed schema instead of raw
GraphQL introspection JSON. It also includes SDL generated from that compact
schema:

```json
{
  "success": true,
  "status": "ok",
  "schema": {
    "query_type": "Query",
    "queries": [
      {
        "name": "user",
        "type": "User",
        "args": [
          {"name": "id", "type": "ID!", "required": true}
        ]
      }
    ],
    "types": [
      {
        "name": "User",
        "fields": [
          {"name": "id", "type": "ID!"},
          {"name": "name", "type": "String"}
        ]
      }
    ]
  },
  "sdl": "type Query {\n  user(id: ID!): User\n}\n..."
}
```

To also include the raw introspection response:

```bash
curl -X POST http://localhost:8080/introspect \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://target-api.com/graphql",
    "include_raw": true
  }'
```
