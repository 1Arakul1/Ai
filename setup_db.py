import pyodbc

# --- НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ---
# Сначала подключаемся к системной базе данных 'master', 
# чтобы проверить наличие нашей базы и иметь права на её создание.
CONNECTION_MASTER = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost;"  # Твой проверенный адрес сервера
    "Database=master;"
    "Trusted_Connection=yes;"
)

DB_NAME = "AIChatBase"

def setup_database():
    print("=== ЗАПУСК АВТОМАТИЧЕСКОЙ НАСТРОЙКИ БАЗЫ ДАННЫХ ИИ ===")
    try:
        # Включаем autocommit=True, так как команду 'CREATE DATABASE' 
        # нельзя выполнять внутри обычной транзакции pyodbc.
        print(f"1. Подключение к локальному SQL Server (системная база master)...")
        conn = pyodbc.connect(CONNECTION_MASTER, autocommit=True)
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже база данных с таким именем
        cursor.execute(f"SELECT database_id FROM sys.databases WHERE name = '{DB_NAME}'")
        row = cursor.fetchone()
        
        if not row:
            print(f"2. База данных '{DB_NAME}' не найдена. Создаю новую БД...")
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"   -> База данных '{DB_NAME}' успешно создана!")
        else:
            print(f"2. База данных '{DB_NAME}' уже существует. Пропускаю создание базы.")
        
        cursor.close()
        conn.close()
        
        # --- НАСТРОЙКА ТАБЛИЦЫ ---
        # Теперь подключаемся уже напрямую к нашей целевой базе данных
        CONNECTION_APP = (
            "Driver={ODBC Driver 17 for SQL Server};"
            f"Server=localhost;"
            f"Database={DB_NAME};"
            "Trusted_Connection=yes;"
        )
        
        print(f"3. Подключение к базе '{DB_NAME}' для проверки таблиц...")
        conn = pyodbc.connect(CONNECTION_APP)
        cursor = conn.cursor()
        
        # SQL-скрипт для безопасного создания таблицы (только если её нет)
        table_script = """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AI_Memories]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[AI_Memories] (
                [id] INT IDENTITY(1,1) PRIMARY KEY,
                [keyword] NVARCHAR(255) NOT NULL,
                [memory_text] NVARCHAR(MAX) NOT NULL,
                [created_at] DATETIME DEFAULT GETDATE()
            );
            PRINT '   -> Таблица [AI_Memories] успешно создана!';
        END
        ELSE
        BEGIN
            PRINT '   -> Таблица [AI_Memories] уже существует. Структура в порядке.';
        END
        """
        
        cursor.execute(table_script)
        conn.commit()
        
        cursor.close()
        conn.close()
        print("\n[УСПЕХ] Все конфигурации MSSQL успешно применены! Можно запускать основное приложение.")
        
    except Exception as e:
        print(f"\n[ОШИБКА] Не удалось настроить базу данных автоматически: {e}")
        print("\nВозможные решения:")
        print("1. Убедись, что служба SQL Server запущена на твоем компьютере.")
        print("2. Если у тебя используется SQL Express, измени в начале этого скрипта строку сервера на: 'Server=localhost\\\\SQLEXPRESS;'")
        print("3. Проверь, установлен ли в системе компонент 'ODBC Driver 17 for SQL Server'.")

if __name__ == "__main__":
    setup_database()