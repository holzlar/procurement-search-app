import os
import re
import numpy as np
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

class ProcurementSearchService:
    def __init__(self):
        """Инициализация сервиса поиска"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Необходимо задать SUPABASE_URL и SUPABASE_SERVICE_KEY в .env")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        self.model_name = os.getenv("MODEL_NAME", "ai-forever/ru-en-RoSBERTa")
        self.model = SentenceTransformer(self.model_name)
    
    def clean_search_text(self, text: str) -> str:
        """
        Очистка текста запроса: приведение к нижнему регистру
        и замена знаков препинания на пробелы.
        """
        if not text:
            return ""
        # Приводим к нижнему регистру
        text = text.lower()
        # Заменяем все, что не является буквой, цифрой или пробелом, на пробел
        text = re.sub(r'[^a-zа-я0-9\\s]', ' ', text)
        # Заменяем несколько пробелов подряд на один
        text = re.sub(r'\\s+', ' ', text).strip()
        return text

    def get_text_embedding(self, text: str) -> List[float]:
        """Создание вектора из текста с помощью SentenceTransformer."""
        # Модель уже настроена на нормализацию
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    
    def search_similar_procurements(
        self,
        query_text: str,
        limit: int = 10,
        etp_filter: Optional[List[str]] = None,
        similarity_threshold: float = 0.3,
        initial_candidate_count: int = 10000
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих закупок по тексту с использованием финальной HNSW-функции.
        """
        cleaned_query = self.clean_search_text(query_text)
        
        query_embedding = self.get_text_embedding(cleaned_query)
        
        params = {
            'query_embedding': query_embedding,
            'p_similarity_threshold': similarity_threshold,
            'p_match_count': limit,
            'p_etp_filter': etp_filter if etp_filter else None,
            'p_initial_candidate_count': 10000, # Возвращаем на оптимальное значение
        }
        
        try:
            # ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ V2
            response = self.supabase.rpc('search_procurements_v2', params).execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"❌ Ошибка при вызове RPC функции search_procurements_v2: {e}")
            return []

    def format_participants(self, procurement: Dict[str, Any]) -> List[str]:
        """
        Форматирование списка участников для отображения.
        Победитель всегда будет первым в списке, если он есть.
        """
        participants = []
        winner = procurement.get('winner')
        
        if winner and winner not in ['-', None, 'NaN']:
            # Добавляем победителя как первого участника, но без специального текста
            participants.append(winner)
        
        for i in range(1, 11):
            participant_key = f'participant_{i}'
            participant = procurement.get(participant_key)
            
            # Добавляем участника, если он не является победителем (чтобы избежать дублирования)
            if participant and participant not in ['-', None, 'NaN'] and participant != winner:
                participants.append(participant)
        
        return participants

    def get_available_etps(self) -> List[str]:
        """Получение списка доступных ЭТП из финальной таблицы."""
        try:
            response = self.supabase.rpc('get_distinct_etps_final').execute()
            if response.data:
                return [item['etp'] for item in response.data if item['etp']]
        except Exception as e:
            print(f"Не удалось получить ЭТП через RPC: {e}. Пробуем прямой запрос.")
            try:
                # Fallback на прямой запрос, если RPC не создана
                response = self.supabase.table('procurement_data_final').select('etp', count='exact').execute()
                if response.data:
                    unique_etps = sorted(list(set(item['etp'] for item in response.data if item['etp'])))
                    return unique_etps
            except Exception as direct_e:
                print(f"Ошибка получения ЭТП напрямую: {direct_e}")

        # Возвращаем пустой список, если ничего не удалось
        return [] 