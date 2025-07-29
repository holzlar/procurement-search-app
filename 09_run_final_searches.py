import os
import getpass
import psycopg
import numpy as np
import pandas as pd
import sys
import time
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

# --- Конфигурация ---
DB_USER = "postgres.vdrykmvkwzuiwouocinh"
DB_HOST = "aws-0-eu-central-1.pooler.supabase.com"
DB_PORT = "5432"
DB_NAME = "postgres"
MODEL_NAME = 'ai-forever/ru-en-RoSBERTa'
# ИЗМЕНЕНИЕ: Используем финальную функцию
SEARCH_FUNCTION_NAME = 'search_procurements_final'
DATA_TABLE_NAME = 'procurement_data_final'

# --- Поисковые запросы для теста ---
TEST_QUERIES = [
    'полотно обтирочное полотно безворсовое аверфос или хэлфос препараты от гнуса перчатки х б с пвх полотно обтирочное ветошь ширина 140 5 см плотность 175 гр м2',
    'материалы верхнего строения железнодорожных путей шпалы железобетонные ш1 р 65 в комплекте',
    'электротовары',
    'багор пожарный',
    'электрод',
    'экскаватор',
    'автобус',
    '3d принтер',
    'бензин аи 92',
    'samsung',
    'картридж'
]

def get_db_connection_string():
    db_password = os.environ.get('DB_PASSWORD') or getpass.getpass("Пароль от БД: ")
    if not db_password:
        raise ValueError("Пароль не может быть пустым.")
    return f"postgresql://{DB_USER}:{db_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def main():
    """Запускает тестовые поисковые запросы по ВСЕЙ базе с фильтром по ЭТП."""
    print("--- 🚀 Запуск финальных тестов по всей базе (с фильтром ЭТП) ---")

    try:
        print("1. Загрузка embedding-модели...")
        model = SentenceTransformer(MODEL_NAME, device='cpu')

        conn_string = get_db_connection_string()
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                print("\n2. Получение списка всех ЭТП для создания фильтра...")
                cur.execute(f"SELECT DISTINCT etp FROM {DATA_TABLE_NAME} WHERE etp IS NOT NULL;")
                all_etps = [row[0] for row in cur.fetchall()]
                etps_to_include = [etp for etp in all_etps if etp != 'Goszakup']
                print(f"   - Исключаем 'Goszakup'. Поиск будет по {len(etps_to_include)} ЭТП.")

                for query in TEST_QUERIES:
                    print("\n" + "="*80)
                    print(f"🔍 ТЕСТОВЫЙ ЗАПРОС: '{query}'")
                    print("="*80)

                    query_embedding = model.encode(query, normalize_embeddings=True)

                    p_match_threshold = 0.5
                    p_match_count = 5
                    p_initial_candidate_count = 20000
                    
                    start_time = time.time()

                    cur.execute(
                        f"SELECT * FROM {SEARCH_FUNCTION_NAME}(%s, %s, %s, %s, %s);",
                        (
                            str(query_embedding.tolist()),
                            p_match_threshold,
                            p_match_count,
                            etps_to_include,
                            p_initial_candidate_count
                        )
                    )

                    results = cur.fetchall()
                    end_time = time.time()
                    duration = end_time - start_time

                    if not results:
                        print("--- Результаты не найдены ---")
                        print(f"\n⏱️  Время выполнения запроса: {duration:.2f} сек.")
                        continue

                    colnames = [desc[0] for desc in cur.description]
                    df = pd.DataFrame(results, columns=colnames)
                    
                    pd.set_option('display.max_rows', None)
                    pd.set_option('display.max_columns', None)
                    pd.set_option('display.width', 1000)
                    pd.set_option('display.max_colwidth', 60)

                    print(df[['similarity_score', 'best_chunk_text', 'etp', 'publish_date', 'participant_1', 'winner', 'description']].head())
                    print(f"\n⏱️  Время выполнения запроса: {duration:.2f} сек.")

    except Exception as e:
        print(f"\n--- ❌ Произошла критическая ошибка: {e} ---")

if __name__ == "__main__":
    main() 