import streamlit as st
import pandas as pd
from datetime import datetime
from search_service import ProcurementSearchService

# Настройка страницы
st.set_page_config(
    page_title="Поиск похожих закупок",
    page_icon="",
    layout="wide"
)

# Кэширование сервиса поиска
@st.cache_resource
def load_search_service():
    """Загружаем сервис поиска (кэшируется для оптимизации)"""
    return ProcurementSearchService()

def format_currency(amount):
    """Форматирование денежных сумм"""
    if pd.isna(amount) or amount is None:
        return "Не указано"
    try:
        return f"{int(amount):,}".replace(",", " ") + " ₸"
    except:
        return str(amount) + " ₸"

def format_date(date_str):
    """Форматирование даты"""
    if pd.isna(date_str) or date_str is None:
        return "Не указано"
    try:
        if isinstance(date_str, str):
            date_obj = pd.to_datetime(date_str)
        else:
            date_obj = date_str
        return date_obj.strftime("%d.%m.%Y")
    except:
        return str(date_str)

def truncate_text(text, max_length=100):
    """Обрезка текста с добавлением '...'"""
    if not text or pd.isna(text):
        return ""
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def get_similarity_level(score):
    """Определение уровня схожести"""
    if score >= 0.8:
        return "Очень высокая", "🟢"
    elif score >= 0.7:
        return "Высокая", "🟡"
    elif score >= 0.5:
        return "Средняя", "🟠"
    else:
        return "Низкая", "🔴"

def main():
    st.title("🔍 Поиск похожих закупок")
    st.markdown("Введите описание закупки для поиска похожих предложений в базе данных")
    
    try:
        search_service = load_search_service()
        available_etps = search_service.get_available_etps()
    except Exception as e:
        st.error(f"Ошибка инициализации сервиса поиска: {e}")
        st.stop()
    
    # Разделяем основной ввод и кнопку на две колонки
    search_col, button_col = st.columns([5, 1])

    with search_col:
        search_query = st.text_input(
            "Введите описание закупки для поиска:",
            placeholder="Опишите товары, услуги или ключевые слова...",
            label_visibility="collapsed"
        )

    with button_col:
        # Для st.text_input кнопка выравнивается хорошо без доп. отступов
        search_button = st.button(
            "Найти", type="primary", use_container_width=True
        )

    # Управляющие элементы под основным полем, с соотношением 40%/60%
    col1, col2 = st.columns([2, 3])
    
    with col1:
        num_results = st.number_input(
            "🔢 Количество результатов:", min_value=1, max_value=100, value=20, step=5,
            help="Максимальное количество закупок для отображения"
        )
    
    with col2:
        if available_etps:
            selected_etps = st.multiselect(
                "🏢 Фильтр по ЭТП:", options=available_etps, default=available_etps,
                help="Выберите электронные торговые площадки для поиска"
            )
        else:
            st.warning("Не удалось загрузить список ЭТП")
            selected_etps = []
    
    if search_button and search_query.strip():
        if not selected_etps:
            st.warning("Пожалуйста, выберите хотя бы одну ЭТП для поиска")
        else:
            with st.spinner("Выполняется поиск похожих закупок..."):
                try:
                    results = search_service.search_similar_procurements(
                        query_text=search_query, limit=num_results, etp_filter=selected_etps,
                        similarity_threshold=0.5, initial_candidate_count=1000
                    )
                    
                    if results:
                        st.success(f"Найдено {len(results)} похожих закупок")
                        
                        for i, procurement in enumerate(results, 1):
                            similarity_score = procurement.get('similarity_score', 0)
                            similarity_level, emoji = get_similarity_level(similarity_score)
                            
                            description_preview = truncate_text(procurement.get('description', ''), 80)
                            title = f"{emoji} {similarity_score:.1%} | {procurement.get('etp', 'Н/Д')} | {format_currency(procurement.get('price'))} | {description_preview}"
                            
                            with st.expander(title):
                                left_col, right_col = st.columns([2, 1])
                                
                                # --- ЛЕВАЯ КОЛОНКА ---
                                with left_col:
                                    st.subheader("📋 Описание закупки")
                                    st.write(procurement.get('description', 'Описание отсутствует'))

                                    st.subheader(f"⚡️ Наиболее похожий фрагмент (схожесть: {similarity_score:.2f})")
                                    st.info(f"**{procurement.get('best_chunk_text', '')}**")
                                    
                                    st.subheader("👥 Участники тендера")
                                    participants = search_service.format_participants(procurement)
                                    if participants:
                                        winner = procurement.get('winner')
                                        df_participants = pd.DataFrame(participants, columns=["Участник"])
                                        df_participants['Статус'] = [
                                            '🏆 Победитель' if p == winner and p not in ['-', None, 'NaN'] else 'Участник' 
                                            for p in df_participants['Участник']
                                        ]
                                        df_participants = df_participants[['Статус', 'Участник']]
                                        st.table(df_participants)
                                    else:
                                        st.write("Информация об участниках отсутствует")

                                # --- ПРАВАЯ КОЛОНКА ---
                                with right_col:
                                    st.subheader("📊 Информация о лоте")
                                    st.metric("Общая сумма", format_currency(procurement.get('price')))
                                    st.write(f"**ЭТП:** {procurement.get('etp', 'Не указано')}")
                                    st.write(f"**Дата публикации:** {format_date(procurement.get('publish_date'))}")
                                    st.write(f"**Заказчик:** {procurement.get('customer', 'Не указано')}")
                                    st.write(f"**Количество:** {procurement.get('quantity', 'Не указано')}")
                                    st.write(f"**Цена за ед.:** {format_currency(procurement.get('price_per_unit'))}")
                                    st.write(f"**Ед. измерения:** {procurement.get('unit_of_measurement', 'Не указано')}")

                    else:
                        st.info("По вашему запросу ничего не найдено. Попробуйте:")
                        st.write("• Изменить описание")
                        st.write("• Выбрать больше ЭТП")
                        
                except Exception as e:
                    st.error(f"Ошибка при выполнении поиска: {e}")
                    st.write("Проверьте подключение к базе данных и настройки")
                    
    elif search_button and not search_query.strip():
        st.warning("Пожалуйста, введите описание для поиска")
    
    if not search_query and not search_button:
        st.info("💡 **Как пользоваться системой:**")
        st.write("1. Введите описание товаров или услуг в поле выше")
        st.write("2. Настройте количество результатов и выберите ЭТП")
        st.write("3. Нажмите кнопку 'Найти похожие закупки'")
        st.write("4. Изучите результаты в развернутых карточках")

if __name__ == "__main__":
    main() 