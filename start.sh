#!/usr/bin/env bash
set -e  # Остановить скрипт при любой ошибке

# --- НАСТРОЙКИ (поправьте под ваш app/database.py) ---
DB_NAME="youtube_mvp"
DB_USER="postgres"
DB_PASS="postgres"
DB_HOST="localhost"
DB_PORT="5432"

echo "=== 1. Проверка и создание базы данных PostgreSQL ==="
# Проверяем, запущен ли сервис PostgreSQL
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
    echo "PostgreSQL не запущен. Пытаемся запустить службу..."
    sudo service postgresql start || sudo systemctl start postgresql
fi

# Создаём пользователя, если его нет (если это не стандартный postgres)
if [ "$DB_USER" != "postgres" ]; then
    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER'" | grep -q 1 || \
        sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
fi

# Создаём базу данных, если она ещё не существует
DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")
if [ "$DB_EXISTS" != "1" ]; then
    echo "Создаём базу данных '$DB_NAME'..."
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
else
    echo "База данных '$DB_NAME' уже существует."
fi

echo "=== 2. Настройка окружения и установка зависимостей ==="
if [ ! -d "venv" ]; then
    echo "Создаём виртуальное окружение venv..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "Устанавливаем зависимости из requirements.txt..."
    pip install -r requirements.txt
else
    echo "Файл requirements.txt не найден, ставим базовый набор..."
    pip install fastapi uvicorn[standard] sqlalchemy asyncpg aiofiles jinja2 python-multipart passlib[bcrypt] python-jose[cryptography]
fi

echo "=== 3. Запуск FastAPI сервера ==="
# Таблицы создадутся автоматически через lifespan в app/main.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload