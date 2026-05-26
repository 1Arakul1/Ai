import streamlit as st
from openai import OpenAI
import pyodbc

# --- НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ---
# Используем проверенный адрес для локального экземпляра SQL Server.
CONNECTION_STRING = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"  # Если у тебя SQL Express, замени на localhost\\SQLEXPRESS
    "Database=AIChatBase;"
    "Trusted_Connection=yes;"
)

LM_STUDIO_URL = "http://localhost:1234/v1" 

st.set_page_config(page_title="AI Memory Core", page_icon="🧠", layout="wide")
st.title("🧠 ИИ-Ассистент с долговременной памятью (MS SQL)")

# Инициализируем клиента LM Studio
client = OpenAI(base_url=LM_STUDIO_URL, api_key="not-needed")

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---

def search_memory_in_db(user_text):
    """Ищет воспоминания, проверяя, есть ли ключевое слово в запросе пользователя"""
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        found_memories = []
        user_text_lower = user_text.lower()
        
        # Получаем все ключевые слова из базы данных
        cursor.execute("SELECT keyword, memory_text FROM AI_Memories")
        rows = cursor.fetchall()
        
        for row in rows:
            keyword = row[0].lower()
            memory_text = row[1]
            
            # Если ключевое слово из базы есть внутри фразы пользователя
            if keyword in user_text_lower:
                if memory_text not in found_memories:
                    found_memories.append(memory_text)
        
        cursor.close()
        conn.close()
        return found_memories
    except Exception as e:
        st.sidebar.error(f"Ошибка поиска в MSSQL: {e}")
        return []

def save_memory_to_db(keyword, memory_text):
    """Сохраняет новое воспоминание в базу данных MS SQL, если такого там еще нет"""
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Очищаем входящие данные
        kw = keyword.strip().lower()
        txt = memory_text.strip()
        
        # 1. Проверяем, нет ли уже ТОЧНО ТАКОЙ ЖЕ записи
        cursor.execute(
            "SELECT COUNT(*) FROM AI_Memories WHERE keyword = ? AND memory_text = ?",
            (kw, txt)
        )
        exists = cursor.fetchone()[0]
        
        if exists > 0:
            # Если дубликат найден, тихо выходим, возвращая True (ведь факт уже в базе)
            cursor.close()
            conn.close()
            return True
            
        # 2. Если записи нет — сохраняем
        cursor.execute(
            "INSERT INTO AI_Memories (keyword, memory_text) VALUES (?, ?)",
            (kw, txt)
        )
        conn.commit()
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.sidebar.error(f"Ошибка записи в MSSQL: {e}")
        return False

def auto_extract_and_save_memory(user_msg, assistant_msg):
    """Скрыто анализирует диалог через LM Studio, извлекает важные факты и сохраняет в SQL"""
    
    extraction_prompt = (
        "Ты — модуль выделения долгосрочной памяти. Твоя задача — находить и извлекать важные факты о пользователе.\n\n"
        "ОБЯЗАТЕЛЬНО ОБРАЩАЙ ВНИМАНИЕ НА:\n"
        "1. Любые личные предпочтения, вкусы, привычки и то, что пользователь любит или ненавидит (например: цвета, темы оформления, стили кода, языки программирования).\n"
        "2. Характеристики железа, софт, покупки, имена, важные даты и события.\n\n"
        "Если в сообщении пользователя есть такой факт, выдели ОДНО главное ключевое слово в начальной форме (например: 'тема', 'python', 'монитор') "
        "и текст, который нужно запомнить.\n"
        "Выведи результат СТРОГО в формате: КЛЮЧЕВОЕ_СЛОВО == ТЕКСТ_ЗАПИСИ\n"
        "Пример: тема == Пользователь не любит светлые темы в редакторах и всегда выбирает тёмные.\n"
        "Если новой важной информации, привычек или фактов о пользователе нет, ответь просто одним словом: НЕТ"
    )
    
    dialogue_context = f"Пользователь: {user_msg}\nАссистент: {assistant_msg}"
    
    try:
        response = client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": dialogue_context}
            ],
            stream=False, 
            temperature=0.0  # Максимальная строгость формата
        )
        
        ai_verdict = response.choices[0].message.content.strip()
        
        if "==" in ai_verdict:
            parts = ai_verdict.split("==", 1)
            keyword = parts[0].strip().lower()
            memory_text = parts[1].strip()
            
            if len(keyword) > 1 and memory_text:
                if save_memory_to_db(keyword, memory_text):
                    return keyword, memory_text
    except Exception as e:
        print(f"Ошибка модуля авто-памяти: {e}")
    
    return None

# --- ЛОГИКА И ИНТЕРФЕЙС ЧАТА ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# Боковая панель (Управление + Ручное добавление памяти)
with st.sidebar:
    st.header("⚙️ Управление")
    if st.button("🗑️ Очистить экран"):
        st.session_state.messages = []
        st.rerun()
        
    st.write("---")
    st.header("🧠 Добавить память вручную")
    
    new_keyword = st.text_input("Ключевое слово (например: 'сейф', 'проект')")
    new_text = st.text_area("Что запомнить?")
    
    if st.button("💾 Сохранить в память"):
        if new_keyword and new_text:
            if save_memory_to_db(new_keyword, new_text):
                st.sidebar.success(f"Успешно запомнил слово '{new_keyword}'!")
        else:
            st.sidebar.warning("Заполните оба поля!")

# Отображаем историю чата на экране
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Поле ввода вопроса пользователя
if user_input := st.chat_input("Спроси меня о чем-нибудь..."):
    
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # 1. Сбор контекста из "памяти" MS SQL
    with st.spinner("Ищу в долговременной памяти..."):
        db_memories = search_memory_in_db(user_input)
    
    # 2. Формируем системный промпт
    base_system = "You are a helpful assistant. Respond strictly in Russian."
    
    if db_memories:
        memory_context = "\n".join([f"- {m}" for m in db_memories])
        system_prompt = f"{base_system}\nУ тебя есть доступ к твоим старым воспоминаниям по этой теме. Используй их при ответе, если они уместны:\n{memory_context}"
        st.caption("ℹ️ ИИ задействовал долговременную память из MS SQL")
    else:
        system_prompt = base_system

    # Собираем контекст для отправки в LM Studio
    api_messages = [{"role": "system", "content": system_prompt}]
    
    for msg in st.session_state.messages:
        api_messages.append(msg)
    
    api_messages.append({"role": "user", "content": user_input})
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 3. Запрос к LM Studio через API и генерация ответа
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            response = client.chat.completions.create(
                model="local-model",
                messages=api_messages,
                stream=True,
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # 4. Фоновое извлечение фактов после успешного ответа
            with st.spinner("Анализирую диалог на важные факты..."):
                saved_fact = auto_extract_and_save_memory(user_input, full_response)
                
                if saved_fact:
                    # Показываем красивое всплывающее уведомление, если факт сохранен
                    st.toast(f"🧠 Автоматически запомнил факт про: **{saved_fact[0]}**", icon="💾")
            
        except Exception as e:
            st.error(f"Ошибка LM Studio: {e}")
            st.session_state.messages.pop()