import json
import os

import matplotlib.pyplot as plt
import pandas as pd
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import build_client_schema, get_introspection_query, print_schema
from markdown_pdf import MarkdownPdf, Section
from openai import OpenAI

OPENAI_TOKEN = "AQVNxtekqb7zxOvH82zgdIue11AZEZ-PJ2M1lRaB"
OPENAI_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
OPENAI_PROJECT = "b1g0vs725b6umolm2eed"
OPENAI_MODEL = "aliceai-llm"
GQL_BASE_URL = "https://rickandmortyapi.com/graphql"

# Промпт №1: Генерация GraphQL-запроса
GQL_PROMPT_TEMPLATE = """
Ты - API-интерфейс, преобразующий естественный язык в GraphQL-запросы.
Твоя задача: генерировать только GraphQL-запросы на основе предоставленной схемы.

СХЕМА:
%SCHEMA%

ПРАВИЛА ВЫВОДА:
1. Выводи ТОЛЬКО валидный JSON-объект. Никаких Markdown (не используй ```json), никаких вводных слов, никаких пояснений вне JSON.
2. Структура ответа должна быть строго следующей:
{
  "query": "GraphQL запрос здесь",
  "note": "Краткое примечание или пустая строка",
  "hints": ["Подсказка 1", "Подсказка 2", "Подсказка 3"]
}
3. В поле "query" пиши чистый GraphQL-код. Не пытайся вручную экранировать кавычки или переносы строк - просто пиши запрос, а формат JSON обеспечит валидность структуры.
4. Если сформировать запрос невозможно, оставь поле "query" пустым, а в "note" опиши причину.
5. Поле "hints" должно содержать 3 конкретных и полезных пользовательских промпта, основанных на доступных полях схемы, которые дополняют текущий запрос.

Пример ожидаемого формата:
{
  "query": "query { users { id name } }",
  "note": "",
  "hints":["Получить email пользователя", "Отфильтровать пользователей по дате регистрации", "Включить список постов автора"]
}
"""


REPORT_PROMPT_TEMPALTE = """Ты — аналитик данных. Твоя задача — составить строгий, профессиональный и информативный статистический отчет на основе полученных данных из API по запросу пользователя: "{user_input}"

Сформируй отчет в формате Markdown (.md). Избегай маркетингового сленга и лишнего пафоса. Тон должен быть деловым, сфокусированным строго на фактах и статистических закономременностях.

Структура отчета:
все пункты максимально тезисно и читаемо для человека. ЭМОДЗИ И СМАЙЛИКИ ЗАПРЕЩЕНЫ.
1. # Аналитический отчет по запросу: [Суть запроса]
2. ##  Общая сводка и статистика (Объем выборки, структура данных, ключевые наблюдаемые параметры).
3. ##  Таблица данных (Построй аккуратную Markdown-таблицу. Обязательно переведи технические названия полей из JSON на понятный русский язык, например: status -> Статус, species -> Раса/Вид, origin.name -> Родная планета).
4. %CHART%

Правила:
- Не сокращай данные, даже если выборка кажется слишком большой. Итоговая таблица должна быть полной.
- Верни ИСКЛЮЧИТЕЛЬНО Markdown-текст отчета. Не добавляй никаких фраз от себя до или после Markdown-блока.

СЫРЫЕ ДАННЫЕ ИЗ API:
%RAW%
"""

transport = AIOHTTPTransport(url=GQL_BASE_URL)
gql_client = Client(transport=transport)

introspect_query = gql(get_introspection_query(descriptions=True))
introspect_response = gql_client.execute(introspect_query)
schema = print_schema(build_client_schema(introspect_response))

print("Система аналитики готова. Жду промпт...\n")

client = OpenAI(api_key=OPENAI_TOKEN, base_url=OPENAI_BASE_URL)


def generate_auto_chart(api_response: dict) -> tuple[bool, str]:
    """Анализирует данные и строит график распределения, ТОЛЬКО если это уместно."""
    if os.path.exists("report_chart.png"):
        try:
            os.remove("report_chart.png")
        except Exception:
            pass

    try:
        df = None
        for key, value in api_response.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, list):
                        df = pd.json_normalize(sub_value)
                        break
        if df is None:
            df = pd.json_normalize(api_response)

        if df.empty:
            return False, ""

        analytical_cols = ["status", "species", "gender", "origin.name", "location.name"]
        target_col = None

        for col in analytical_cols:
            if col in df.columns:
                nunique = df[col].nunique()
                if 1 < nunique < len(df):
                    target_col = col
                    break

        if target_col:
            plt.figure(figsize=(8, 4.5))
            counts = df[target_col].value_counts().head(10)
            counts.plot(kind="bar", color="#2b5c8f", edgecolor="black", alpha=0.85)

            plt.title(f"Статистическое распределение выборки по полю: {target_col}", fontsize=11, fontweight="bold")
            plt.ylabel("Количество записей", fontsize=9)
            plt.xlabel(target_col, fontsize=9)
            plt.grid(axis="y", linestyle="--", alpha=0.5)
            plt.xticks(rotation=25, ha="right", fontsize=9)
            plt.tight_layout()

            plt.savefig("report_chart.png", dpi=150)
            plt.close()
            return True, target_col

    except Exception as e:
        print(f"⚠️ Ошибка анализа распределений: {e}")

    return False, ""


try:
    while True:
        user_input = input("> ")

        # --- ШАГ 1: GraphQL Генерация ---
        response = client.chat.completions.create(
            model=f"gpt://{OPENAI_PROJECT}/{OPENAI_MODEL}",
            messages=[
                {"role": "system", "content": GQL_PROMPT_TEMPLATE.replace("%SCHEMA%", schema, count=1)},
                {"role": "user", "content": user_input},
            ],
            stream=False,
            response_format={"type": "json_object"}
        )

        query = response.choices[0].message.content
        if query.startswith("```"):
            query = query.replace("```graphql", "").replace("```json", "").replace("```", "").strip()

        query_json = json.loads(query)

        print("\n[Сгенерированный сырой GraphQL-запрос]:")
        print(query)

        print("\nЗапрос:")
        print(query_json["query"])

        print("\nЗамечания:")
        print(query_json["note"])

        print("\nПодсказки:")
        print(query_json["hints"])

        if not query_json["query"]:
            print("Запрос пустой, отчет не составляется.")
            continue

        # --- ШАГ 2: Запрос к API ---
        print("\n🚀 Запрос к API...")
        try:
            api_response = gql_client.execute(gql(query_json["query"]))
        except Exception as e:
            print(f"❌ Ошибка выполнения запроса: {e}\n")
            continue

        print("Ответ от API:")
        print(api_response)

        # --- ШАГ 3: Умная проверка надобности графика ---
        chart_created, chart_column = generate_auto_chart(api_response)

        if chart_created:
            print(f"📊 Обнаружена вариативность по признаку '{chart_column}'. График 'report_chart.png' успешно создан.")
            chart_instruction = f"## 🖼️ Визуализация данных\nНиже представлена диаграмма распределения выборки по признаку '{chart_column}':\n![Аналитический график](report_chart.png)\nОпиши структуру распределения."
        else:
            print("📉 В данных нет значимых распределений (все уникальны или одинаковы). График не требуется.")
            chart_instruction = "Никаких графиков строить не нужно, так как данные представляют собой последовательный список без группировочных метрик. Не добавляй блок визуализации."

        # --- ШАГ 4: Динамическая сборка промпта ---
        product_prompt = REPORT_PROMPT_TEMPALTE.replace("%CHART%", chart_instruction, 1).replace("%RAW%", str(api_response), 1)

        print("🧠 Модель формирует аналитический отчет...")

        prod_response = client.chat.completions.create(
            model=f"gpt://{OPENAI_PROJECT}/{OPENAI_MODEL}",
            messages=[
                {"role": "system", "content": product_prompt},
            ],
            stream=False,
        )

        md_report = prod_response.choices[0].message.content

        pdf = MarkdownPdf()
        pdf.add_section(Section(md_report))
        pdf.save("product_report.pdf")

        print(f"💾 Отчет обновлен: product_report.pdf\n")

except KeyboardInterrupt:
    pass
