"""Создаёт демо-аккаунт с заполненным MD-портретом.

Запуск из корня проекта:
    .\\.venv\\Scripts\\python.exe -m scripts.seed_demo
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import db
from app.profile_md import serialize_sections
from app.questions import ONBOARDING_QUESTIONS
from app.repositories import UserRepository
from app.security import password_hasher

DEMO_EMAIL: str = "demo@200b.local"
DEMO_PASSWORD: str = "demo1234"

DEMO_ANSWERS: dict[str, str] = {
    "name_age_city": "Артём, 29, переехал из Киева в Берлин 2 года назад.",
    "occupation": "Продакт-менеджер в B2B SaaS, специализируюсь на онбординге и активации. До этого 4 года был дизайнером.",
    "niche": "Карьера и переход из дизайна в продукт. Лайфстайл-куски про эмиграцию и быт фриланс/офис.",
    "audience": "Дизайнеры 25-32, которые задумываются о смене роли. Чуть устали от Figma-войн, хотят больше влияния на продукт, но боятся менеджмента.",
    "goal": "Личный бренд, чтобы через год получать офферы Head of Product без CV и собрать платное комьюнити менторства.",
    "expertise": "Перевод дизайн-команды на продуктовое мышление, найм первого продакта в стартап, активация в B2B (умею считать AARRR без воды).",
    "hobbies": "Готовлю рамен и делаю свой мисо, бегаю полумарафоны, перечитываю Достоевского раз в год.",
    "values": "Честность до неудобства, ремесло над хайпом, ответственность за результат, дружба-как-работа, не врать самому себе.",
    "voice": "Сухо-ироничный, без сюсюканий. Иногда жёстко, но без позы. Не люблю восклицательных знаков и эмодзи в текстах.",
    "favorite_formats": "Личные мнения с конкретным кейсом из прошлого, разборы чужих ошибок, короткие истории про факапы и что я из них вынес.",
    "inspirations": "Лёня Шевцов — за конкретику и отсутствие воды. Lenny Rachitsky — за структуру и кейсы. Меньше всего — мотивационные коучи.",
    "annoyances": "Дизайнеры, которые ноют что их не зовут в стратегию, но сами не открывают аналитику. Контент про 'мышление продакта' без единого цифры.",
    "turning_points": "1) Уволили в 25 за конфликт с CEO — это меня собрало. 2) Первый раз сам нанял продакта в 27 и просрал найм — научился собеседовать. 3) Эмиграция в 27.",
    "strong_opinions": "Большинство джунов-продактов не нужны рынку. Дизайнеры переоценивают важность портфолио. Junior-PM роль — это в 90% случаев замаскированный проджект.",
    "recurring_questions": "Как перейти из дизайна в продакт без потери в зарплате? Как продать продактовый опыт без бэкграунда в инжиниринге? Стоит ли идти в FAANG или в стартап?",
    "failures": "Запустил свой Notion-курс за 2 недели, продал 11 копий, выгорел. Уволил человека неправильно — он год со мной не разговаривал. Послал инвестора на собеседовании.",
    "daily_routine": "Подъём 7, кофе+тетрадка 30 мин, два core-блока по 2 часа без слака, обед один, вечером бегаю или варю что-то медленно. Слак закрыт после 19.",
    "taboo": "Не трогаю политику, не комментирую войну в публичном поле, не говорю про зарплаты конкретных коллег.",
    "dream_outcome": "Через год — 30к подписчиков, 2 спикерских инвайта в месяц, платное комьюнити на 100 человек, оффер Head of Product без активного поиска.",
    "anything_else": "Я лучше работаю с конкретными болями людей, чем с абстрактными темами. Не люблю когда меня называют 'эксперт' — звучит как из инфоцыганской методички.",
}


def main() -> int:
    missing: list[str] = [q.key for q in ONBOARDING_QUESTIONS if q.key not in DEMO_ANSWERS]
    if missing:
        print(f"ERROR: missing demo answers for keys: {missing}")
        return 1

    db.create_all()
    profile_md: str = serialize_sections(DEMO_ANSWERS)

    with db.session() as session:
        users = UserRepository(session)

        user = users.get_by_email(DEMO_EMAIL)
        if user is None:
            ph = password_hasher.hash(DEMO_PASSWORD)
            user = users.create(
                email=DEMO_EMAIL, password_hash=ph.hash_hex, password_salt=ph.salt_hex
            )
            print(f"created user id={user.id} email={user.email}")
        else:
            print(f"user already exists id={user.id} email={user.email} — refreshing profile")

        users.set_profile_md(user, profile_md)
        users.set_onboarding_complete(user, True)

    print(f"profile.md sections seeded: {len(DEMO_ANSWERS)}")
    print(f"\nlogin: {DEMO_EMAIL}\npassword: {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
