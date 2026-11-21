# start.ps1
$ErrorActionPreference = "Stop"

Write-Host "=== 1. Проверка виртуального окружения ===" -ForegroundColor Cyan
if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    Write-Host "venv не найден. Создаю..." -ForegroundColor Yellow
    python -m venv venv
}

Write-Host "Активация venv..." -ForegroundColor Green
& ".\venv\Scripts\Activate.ps1"

Write-Host "=== 2. Установка зависимостей ===" -ForegroundColor Cyan
if (Test-Path ".\requirements.txt") {
    pip install -r requirements.txt
} else {
    Write-Host "requirements.txt не найден. Устанавливаю основные пакеты..." -ForegroundColor Yellow
    pip install fastapi uvicorn sqlalchemy asyncpg pydantic-settings python-dotenv "pyjwt[crypto]" python-multipart alembic
}

Write-Host "=== 3. Проверка и создание базы данных PostgreSQL ===" -ForegroundColor Cyan
# ВАЖНО: замените на ваши реальные логин и пароль PostgreSQL
$PG_USER = "postgres"      # обычно postgres
$PG_PASSWORD = "postgres" # <-- ЗАМЕНИТЕ
$PG_HOST = "localhost"
$PG_PORT = "5432"
$DB_NAME = "youtube_mvp"

# Полный путь к psql для PostgreSQL 18
$psqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"

if (-not (Test-Path $psqlPath)) {
    Write-Error "psql.exe не найден по пути: $psqlPath. Проверьте версию PostgreSQL."
}

$env:PGPASSWORD = $PG_PASSWORD
$dbExists = & $psqlPath -h $PG_HOST -p $PG_PORT -U $PG_USER -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'"

if ($dbExists -eq "1") {
    Write-Host "База данных '$DB_NAME' уже существует." -ForegroundColor Green
} else {
    Write-Host "База данных '$DB_NAME' не найдена. Создаю..." -ForegroundColor Yellow
    & $psqlPath -h $PG_HOST -p $PG_PORT -U $PG_USER -c "CREATE DATABASE $DB_NAME;"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "База данных '$DB_NAME' успешно создана." -ForegroundColor Green
    } else {
        Write-Error "Не удалось создать базу данных. Проверьте, запущен ли PostgreSQL и верны ли учётные данные."
    }
}
$env:PGPASSWORD = $null

Write-Host "=== 4. Миграции базы данных ===" -ForegroundColor Cyan
alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Error "Миграции не применились. Проверьте вывод выше."
    exit 1
}
Write-Host "Миграции применены." -ForegroundColor Green

Write-Host "=== 5. Запуск приложения ===" -ForegroundColor Cyan
uvicorn app.main:app --reload