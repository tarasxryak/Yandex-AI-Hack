import os
import pandas as pd
import matplotlib.pyplot as plt
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import build_client_schema, get_introspection_query, print_schema
from openai import OpenAI

OPENAI_TOKEN = "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"
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
GQL_BASE_URL = "https://rickandmortyapi.com/graphql"

# Промпт №1: Генерация GraphQL-запроса
SYSTEM_PROMPT_TEMPLATE = """
Тебе предоставлена схема GraphQL API. Твоя задача: используя схему, генерировать запросы по моим желаниям. Только запрос и ничего лишнего. Не добавляй Markdown формат для запроса (не пиши ```graphql).

ВСЯ СХЕМА ПРЕДСТАВЛЕНА НИЖЕ:
{}
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
            model="deepseek/deepseek-v4-flash:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(schema)},
                {"role": "user", "content": user_input},
            ],
            stream=False,
            extra_body={"thinking": {"type": "enabled"}},
        )

        query = response.choices[0].message.content
        if query.startswith("```"):
            query = query.replace("```graphql", "").replace("```json", "").replace("```", "").strip()

        print("\n[Сгенерированный GraphQL-запрос]:")
        print(query)

        # --- ШАГ 2: Запрос к API ---
        print("\n🚀 Запрос к API...")
        try:
            api_response = gql_client.execute(gql(query))
        except Exception as e:
            print(f"❌ Ошибка выполнения запроса: {e}\n")
            continue

        # --- ШАГ 3: Умная проверка надобности графика ---
        chart_created, chart_column = generate_auto_chart(api_response)

        if chart_created:
            print(f"📊 Обнаружена вариативность по признаку '{chart_column}'. График 'report_chart.png' успешно создан.")
            chart_instruction = f"## 🖼️ Визуализация данных\nНиже представлена диаграмма распределения выборки по признаку '{chart_column}':\n![Аналитический график](report_chart.png)\nОпиши структуру распределения."
        else:
            print("📉 В данных нет значимых распределений (все уникальны или одинаковы). График не требуется.")
            chart_instruction = "Никаких графиков строить не нужно, так как данные представляют собой последовательный список без группировочных метрик. Не добавляй блок визуализации."

        # --- ШАГ 4: Динамическая сборка промпта через f-строку (без .format) ---
        product_prompt = f"""Ты — аналитик данных. Твоя задача — составить строгий, профессиональный и информативный статистический отчет на основе полученных данных из API по запросу пользователя: "{user_input}"

Сформируй отчет в формате Markdown (.md). Избегай маркетингового сленга и лишнего пафоса. Тон должен быть деловым, сфокусированным строго на фактах и статистических закономременностях.

Структура отчета:
все пункты максимально тезисно и читаемо для человека. ЭМОДЗИ И СМАЙЛИКИ ЗАПРЕЩЕНЫ.
1. # Аналитический отчет по запросу: [Суть запроса]
2. ##  Общая сводка и статистика (Объем выборки, структура данных, ключевые наблюдаемые параметры).
3. ##  Таблица данных (Построй аккуратную Markdown-таблицу. Обязательно переведи технические названия полей из JSON на понятный русский язык, например: status -> Статус, species -> Раса/Вид, origin.name -> Родная планета).
4. {chart_instruction}

Верни ИСКЛЮЧИТЕЛЬНО Markdown-текст отчета. Не добавляй никаких фраз от себя до или после Markdown-блока. Эмодзи запрещены.

СЫРЫЕ ДАННЫЕ ИЗ API:
{str(api_response)}
"""

        print("🧠 Дипсик формирует аналитический отчет...")

        prod_response = client.chat.completions.create(
            model="deepseek/deepseek-v4-flash:free",
            messages=[
                {"role": "system", "content": product_prompt},
            ],
            stream=False,
            extra_body={"thinking": {"type": "enabled"}},
        )

        md_report = prod_response.choices[0].message.content

        print("\n✨ Сформированный отчет:")
        print(md_report)
        print()

        # --- ШАГ 5: Сохранение ---
        report_filename = "product_report.md"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(md_report)

        print(f"💾 Отчет обновлен: {os.path.abspath(report_filename)}\n")

except KeyboardInterrupt:
    pass