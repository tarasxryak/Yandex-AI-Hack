from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import build_client_schema, get_introspection_query, print_schema
from openai import OpenAI

OPENAI_TOKEN = "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"
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
GQL_BASE_URL = "https://rickandmortyapi.com/graphql"

SYSTEM_PROMPT = """
Тебе предоставлена схема GraphQL API. Твоя задача: используя схему, генерировать запросы по моим желаниям. Только запрос и ничего лишнего. Можно добавить короткий комментарий-уточнение. Либо, если выполнить запрос совсем невозможно, сообщить об этом. Ничего лишнего. Не добавляй Markdown формат для запроса.

ВСЯ СХЕМА ПРЕДСТАВЛЕНА НИЖЕ:

{}
"""

transport = AIOHTTPTransport(url=GQL_BASE_URL)
gql_client = Client(transport=transport)

introspect_query = gql(get_introspection_query(descriptions=True))
introspect_response = gql_client.execute(introspect_query)
schema = print_schema(build_client_schema(introspect_response)) # pyright: ignore[reportArgumentType]

print("Схема:")
print(f"{schema[:200]}")
print("...\n")

client = OpenAI(api_key=OPENAI_TOKEN, base_url=OPENAI_BASE_URL)

try:
    while True:
        prompt = input("> ")

        response = client.chat.completions.create(
            model="deepseek/deepseek-v4-flash:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(schema)},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )

        query = response.choices[0].message.content

        print("Ответ от модели:")
        print(query)
        print()

        print("Попытка запроса:")
        try:
            response = gql_client.execute(gql(query))
            print(response)
        except Exception as e:
            print(f"ну сорян не получилось чето: {e}")

except KeyboardInterrupt:
    pass
