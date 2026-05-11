# 200b — генератор вопросов-идей для reels

Сервис задаёт автору наводящие вопросы, которые помогают придумать тему для очередного короткого видео. Стек: FastAPI + Postgres + Jinja/HTMX + DeepSeek. Деплой на Render.

## Локальный запуск (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
# открой .env и впиши DEEPSEEK_API_KEY

uvicorn app.main:app --reload
```

Открой http://localhost:8000. Без `DATABASE_URL` в .env используется SQLite-файл `dev.db` рядом с проектом — Postgres локально не нужен.

## Деплой на Render

1. Залить репо на GitHub.
2. Render → New → Blueprint → подключить репо → Apply. Render прочитает `render.yaml`, создаст web-service и managed Postgres.
3. В дашборде web-service открыть Environment → задать `DEEPSEEK_API_KEY` (юзер вписывает руками, sync: false).
4. После первого деплоя БД пустая, миграции не нужны — `Base.metadata.create_all()` создаёт таблицы на старте.

### Free-tier нюансы
- Web service засыпает после 15 минут бездействия — первый запрос будет ~30 сек холодным.
- Free Postgres удаляется через 90 дней. Для прода нужен платный план.

## Структура

```
app/
├─ main.py          # FastAPI app, lifespan, маунты
├─ config.py        # pydantic-settings
├─ db.py            # engine, Base, get_db
├─ models.py        # ORM модели
├─ security.py      # SHA256+соль, JWT, current_user
├─ questions.py     # 20 онбординг-вопросов
├─ deepseek.py      # httpx-клиент
├─ prompts.py       # сборка контекста для LLM
├─ routers/         # auth/onboarding/home/chat
├─ templates/       # Jinja + HTMX
└─ static/          # CSS
```

## Аутентификация

Пароли хешируются `bcrypt` (cost factor 12). Для старых юзеров с прошлой схемой `sha256(salt + password)` есть прозрачный апгрейд: при успешном логине хеш переписывается на bcrypt. Колонки `password_hash` / `password_salt` остаются те же — bcrypt хранит соль внутри хеша, поэтому `password_salt` для bcrypt-юзеров пустой.
