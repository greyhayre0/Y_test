# Проект: MVP Клон YouTube

## Стек
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2
- DB: PostgreSQL 16
- Хранилище: Локальная файловая система (папка `uploads/`).
- Frontend: HTML, CSS, Vanilla JS (без сборки). Файлы лежат в папке `frontend/`.
- Auth: JWT (HS256), `python-jose`, хеширование паролей через `passlib[bcrypt]`.

## Структура папок (строго придерживайся)
- `app/` — код бэкенда
  - `main.py` — точка входа FastAPI, подключение роутеров и статики
  - `database.py` — настройка async engine и сессий SQLAlchemy
  - `models.py` — SQLAlchemy модели (таблицы)
  - `schemas.py` — Pydantic схемы (валидация запросов/ответов)
  - `auth.py` — JWT токены, хеширование паролей, зависимости (get_current_user)
  - `routers/`
    - `auth.py` — регистрация, логин
    - `videos.py` — загрузка, список, просмотр, лайки
    - `comments.py` — комментарии
- `frontend/`
  - `css/`, `js/`, `html/`
- `uploads/` — загруженные видеофайлы
- `tests/`
- `docs/`
- `.env`, `.env.example`
- `alembic/`, `alembic.ini`

## Схема базы данных (строго придерживайся этих полей)
1. **User**: id, email (unique), hashed_password, role (enum: 'user', 'moderator', 'admin'), created_at
2. **Video**: id, title, description, file_path (путь к файлу в uploads/), is_private (bool, default False), owner_id (FK -> User.id), created_at
3. **Comment**: id, text, video_id (FK -> Video.id), user_id (FK -> User.id), created_at
4. **Like**: id, video_id (FK -> Video.id), user_id (FK -> User.id). Уникальная связка (video_id, user_id).
   - Каскадное удаление: `ondelete='CASCADE'` на обеих FK.

## API-контракт (строго придерживайся путей, методов и форматов)

Базовый префикс всех эндпоинтов — `/api`. Аутентификация — `Authorization: Bearer <token>`.
Схемы запросов/ответов описаны в `app/schemas.py` (см. раздел «Pydantic-схемы»).

### Auth
- `POST /api/auth/register`
  - Body (JSON): `UserCreate { email: EmailStr, password: str (min 8) }`
  - 201 → `UserOut { id, email, role, created_at }`
  - 400 — email уже занят
- `POST /api/auth/login`
  - Body: `application/x-www-form-urlencoded` (OAuth2PasswordRequestForm: `username`=email, `password`)
  - 200 → `Token { access_token: str, token_type: "bearer" }`
  - 401 — неверные креды

### Videos
- `POST /api/videos` (auth required)
  - Body: `multipart/form-data`: `title` (str, 1..255), `description` (str, 0..5000), `is_private` (bool, default false), `file` (UploadFile)
  - 201 → `VideoOut`
  - 400 — недопустимый MIME / слишком большой файл
- `GET /api/videos?skip=0&limit=20` (auth optional)
  - Возвращает публичные видео + приватные, где `owner_id == current_user.id` (если авторизован). Если не авторизован — только публичные.
  - 200 → `list[VideoOut]`
- `GET /api/videos/{video_id}` (auth optional)
  - 200 → `VideoOut`
  - 404 — не найдено ИЛИ чужое приватное (не раскрываем существование)
- `GET /api/videos/{video_id}/stream` (auth optional)
  - → `FileResponse` (Starlette сам обрабатывает `Range`; **не пиши ручной парсинг Range и StreamingResponse**)
  - 404 — не найдено / нет доступа
- `DELETE /api/videos/{video_id}` (auth required; owner или admin)
  - 204 → пустой
  - 403 — не owner и не admin
  - 404 — не найдено

### Likes
- `POST /api/videos/{video_id}/like` (auth required) — идемпотентно ставит лайк
  - 200 → `LikeStatus { likes_count: int, liked_by_me: true }`
  - 404 — видео не найдено / нет доступа
- `DELETE /api/videos/{video_id}/like` (auth required) — идемпотентно снимает лайк
  - 200 → `LikeStatus { likes_count: int, liked_by_me: false }`

### Comments
- `GET /api/videos/{video_id}/comments?skip=0&limit=50` (auth optional)
  - 200 → `list[CommentOut]`
  - 404 — видео не найдено / нет доступа
- `POST /api/videos/{video_id}/comments` (auth required)
  - Body (JSON): `CommentCreate { text: str (1..2000) }`
  - 201 → `CommentOut`
  - 404 — видео не найдено / нет доступа
- `DELETE /api/comments/{comment_id}` (auth required; автор или admin)
  - 204 → пустой
  - 403 — не автор и не admin

### Health
- `GET /api/health` → `{ "status": "ok" }` (без БД, для проверки живости)

## Pydantic-схемы (все в `app/schemas.py`)
- `UserCreate { email: EmailStr, password: str = Field(min_length=8) }`
- `UserOut { id: int, email: EmailStr, role: Literal["user","moderator","admin"], created_at: datetime }` — `from_attributes=True`
- `Token { access_token: str, token_type: str = "bearer" }`
- `VideoOut { id, title, description, is_private, owner_id, created_at, likes_count: int, liked_by_me: bool }`
- `LikeStatus { likes_count: int, liked_by_me: bool }`
- `CommentCreate { text: str = Field(min_length=1, max_length=2000) }`
- `CommentOut { id, text, video_id, user_id, created_at }` — `from_attributes=True`

## Поведение приватных видео
- В `GET /api/videos` приватные показываются только `owner` и `admin`.
- Прямой `GET /{id}` и `/stream` для чужого приватного → **404** (не 403 — не раскрываем существование).
- `DELETE` чужого приватного → 403 (пользователь уже знает id, скрывать смысла нет).

## Ограничения загрузки
- Максимум **200 МБ** на файл (проверять размер чанками при сохранении, не грузить целиком в память).
- Допустимые MIME: `video/mp4`, `video/webm`. Проверять и `UploadFile.content_type`, и расширение.
- Имя файла на диске: `{uuid4().hex}.{ext}`. Оригинальное имя в ФС **не использовать**.
- `uploads/` резолвится относительно корня проекта через `pathlib.Path(__file__).resolve().parent.parent / "uploads"`. Папка создаётся при старте.
- При удалении видео (`DELETE`) удалять и файл с диска (best-effort, ошибку логировать, но 204 возвращать).

## Лайки
- Toggle через два отдельных эндпоинта `POST`/`DELETE`, оба идемпотентны.
- `VideoOut` всегда содержит `likes_count` и `liked_by_me` (для анонимов `liked_by_me=false`).
- Уникальность `(video_id, user_id)` обеспечивается констрейнтом в БД + `ON CONFLICT DO NOTHING` в запросе.

## CORS и статика
- Подключить `CORSMiddleware`: `allow_origins=["*"]` для MVP, `allow_credentials=False` (иначе `*` нельзя).
- Раздавать `frontend/` через `StaticFiles` по пути `/` (или `/static`), `uploads/` — только через `/api/videos/{id}/stream` (не открывать `uploads/` как статику, чтобы не обойти проверку приватности).

## Правила
- Пиши только код, необходимый для перечисленных фич MVP: регистрация, логин, загрузка видео, список видео, просмотр (HTML5 плеер), лайки, комментарии, удаление. Каждую из этих фич реализуй **полностью**, без заглушек и без `TODO`.
- Весь код — с тайп-хинтами и pydantic-схемами.
- Секреты только через `.env` (`.env.example` коммитим, `.env` — нет).
- `FileResponse` для раздачи видео — Range поддерживается из коробки, кастомный стриминг не писать.
- Проверка прав: `current_user.id == video.owner_id` или `current_user.role == "admin"` (для удаления комментария — `current_user.id == comment.user_id` или admin).
- Все обращения к БД — через `AsyncSession`, `select(...)`, `await session.execute(...)`. Никаких синхронных `session.query`.
- Alembic: обязательна первая миграция, создающая все 4 таблицы и enum `role`.

## Переменные окружения (`.env.example`)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/youtube_clone
SECRET_KEY=change-me-to-a-long-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=1440
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=200


## Порядок реализации
1. `app/database.py` → `app/models.py` → Alembic init + первая миграция.
2. `app/schemas.py` → `app/auth.py`.
3. `app/routers/auth.py` → `routers/videos.py` → `routers/comments.py`.
4. `app/main.py` (роутеры, CORS, StaticFiles).
5. `frontend/` (страницы: register, login, upload, list, watch).
6. `tests/` — smoke-тесты через `httpx.AsyncClient` + `pytest-asyncio`:
   register → login → upload (маленький mp4) → list → like → comment → delete video.

## Команды
- Запуск сервера: `uvicorn app.main:app --reload`
- Миграции: `alembic upgrade head`
- Тесты: `pytest -q`

## Антипаттерны (не делать)
- `app.mount("/", StaticFiles(...))` — перекроет /api, эндпоинты 404.
- Ручной парсинг `Range` / `StreamingResponse` для видео — `FileResponse` уже умеет.
- `session.query(...)` — только `select(...)` + `execute`.
- `bcrypt` без пина версии (ломает passlib).
- `expire_on_commit=True` (дефолт) — приведёт к `DetachedInstanceError` после коммита в ответе Pydantic.
- Хранить файл под оригинальным именем — path traversal и коллизии.
- Возвращать 403 на чужое приватное видео — раскрывает существование, нужно 404.
- `Optional[User]` в зависимостях через `try/except` — используйте `auto_error=False`.
- Раздача `uploads/` как статики — обходит проверку приватности.
- `role` как `String` — только `Enum` (иначе нет валидации и constraint).

## Основные эндпоинты

=== АВТОРИЗАЦИЯ И ПРОФИЛЬ ===

POST /auth/register
Вход: JSON { email, password }
Выход: JSON { id, email, role } (создает пользователя)

POST /auth/login
Вход: JSON { email, password }
Выход: JSON { access_token, token_type } (токен для авторизации)

GET /auth/me
Вход: Заголовок Authorization: Bearer <токен>
Выход: JSON { id, email, role } (данные текущего пользователя для аватарки в шапке)
Если токена нет: 401 Unauthorized (показать кнопку "Войти")


=== ГЛАВНАЯ СТРАНИЦА (ЛЕНТА ВИДЕО) ===

GET /videos
Вход: Ничего (опционально параметры пагинации: ?skip=0&limit=50)
Выход: JSON-массив объектов видео:
[
  {
    "id": 1,
    "title": "Название",
    "description": "Описание",
    "file_path": "/uploads/video.mp4",
    "thumbnail_path": "/uploads/thumb.jpg", 
    "owner_id": 5,
    "views": 120,
    "created_at": "2026-11-15T12:00:00",
    "likes_count": 10
  }
]
Куда ведет: На этой странице JS берет этот массив и рисует карточки в сетке.


=== ПЕРЕХОД НА ПРОСМОТР ВИДЕО (КЛИК ПО КАРТОЧКЕ) ===

GET /videos/{video_id}
Вход: ID видео в URL
Выход: JSON с полными данными одного видео (title, description, file_path и т.д.)
Куда ведет: Фронтенд переходит на страницу video.html?id=... и запрашивает этот эндпоинт.


=== СОЗДАНИЕ ВИДЕО (КНОПКА "СОЗДАТЬ" В ШАПКЕ) ===

POST /videos
Вход: FormData (файл видео, название, описание) + Заголовок Authorization: Bearer <токен>
Выход: JSON с данными созданного видео
Куда ведет: После успешной загрузки пользователь остается на главной или переходит на страницу своего нового видео.


=== ЛАЙКИ И КОММЕНТАРИИ (ВНУТРИ СТРАНИЦЫ ВИДЕО) ===

POST /videos/{video_id}/like
Вход: Заголовок Authorization: Bearer <токен>
Выход: JSON { message: "Лайк поставлен", likes_count: 11 }
Куда ведет: Обновляет счетчик лайков на странице видео.

GET /videos/{video_id}/comments
Вход: ID видео в URL
Выход: JSON-массив комментариев к этому видео.

POST /videos/{video_id}/comments
Вход: JSON { text } + Заголовок Authorization: Bearer <токен>
Выход: JSON с данными созданного комментария.
Куда ведет: Добавляет новый комментарий под видео.

=== ДАННЫЕ ВИДЕО (ЗАПРАШИВАЮТСЯ ПРИ ОТКРЫТИИ СТРАНИЦЫ) ===

GET /videos/{video_id}
Вход: ID видео в URL (например, /videos/5)
Выход: JSON { 
  "id": 5, 
  "title": "Название", 
  "description": "Описание", 
  "file_path": "/uploads/5.mp4", 
  "views": 150, 
  "likes_count": 25, 
  "owner_id": 12, 
  "created_at": "2026-11-15" 
}
Куда ведет: Заполняет заголовок, описание, плеер и счетчик лайков на странице.

=== КОММЕНТАРИИ ===

GET /videos/{video_id}/comments
Вход: ID видео
Выход: JSON-массив [ { "id": 1, "text": "Круто!", "user_id": 2, "created_at": "..." } ]
Куда ведет: Отрисовывает список под плеером.

POST /videos/{video_id}/comments
Вход: JSON { "text": "Мой комментарий" } + Заголовок Authorization: Bearer <токен>
Выход: JSON с данными созданного комментария { "id": 3, "text": "...", ... }
Куда ведет: Добавляет комментарий в базу и перерисовывает список (или добавляет в конец).

=== ЛАЙКИ (ПО КНОПКЕ ПАЛЕЦ ВВЕРХ) ===

POST /videos/{video_id}/like
Вход: Заголовок Authorization: Bearer <токен>
Выход: JSON { "message": "Лайк поставлен", "likes_count": 26 }
Куда ведет: Обновляет число рядом с кнопкой лайка на странице.

=== РЕКОМЕНДАЦИИ (ПРАВАЯ КОЛОНКА) ===

GET /videos?exclude_id={video_id}
Вход: ID текущего видео (чтобы не показывать его в рекомендациях)
Выход: JSON-массив с другими видео (как на главной).
Куда ведет: Отрисовывает правую колонку "Похожие видео".

=== ПОИСК ВИДЕО ===

GET /videos/search?q={запрос}
Вход: Параметр `q` в URL (строка запроса, минимум 1 символ). Опционально: `skip`, `limit` для пагинации.
Выход: JSON-массив объектов видео (такой же, как у GET /videos):
[
  {
    "id": 1,
    "title": "Название",
    "description": "Описание",
    "file_path": "/uploads/video.mp4",
    "owner_id": 5,
    "views": 120,
    "created_at": "2026-11-15T12:00:00",
    "likes_count": 10
  }
]
Куда ведет: Страница /search?q=... в JS делает запрос к этому эндпоинту и отрисовывает результаты в сетке.