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

## ⚠️ Security trade-off

Пароли хешируются `sha256(salt + password)` с per-user солью. Это сознательное упрощение в пользу скорости разработки — bcrypt/argon2 защищают сильно лучше от GPU-перебора. Заменить позже — это переписать две функции в `app/security.py`, столбец `password_hash` тот же.
