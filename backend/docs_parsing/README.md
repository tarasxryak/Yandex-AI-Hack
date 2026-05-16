# Docs Parser

GraphQL introspection proxy service.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --host 0.0.0.0 --port 8080
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

The service returns SDL generated from GraphQL introspection with `graphql-core`
`build_client_schema` and `print_schema`. It does not return the raw
introspection JSON:

```json
{
  "success": true,
  "status": "ok",
  "sdl": "type Query {\n  user(id: ID!): User\n}\n..."
}
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
