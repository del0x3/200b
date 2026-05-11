"""Builds the LLM prompt for question generation.

The system message holds invariant rules (form, content, anti-hallucination),
while the user message is assembled per-call from the author's portrait,
the current topic, the in-session Q&A history, optional cross-session
prior experience (for the global session), and the user's own custom
prompts and resource links.
"""

from __future__ import annotations

from app.deepseek import ChatMessage
from app.models import ChatQuestion, Feedback

SYSTEM_PROMPT: str = (
    "Ты — внимательный интервьюер. Твоя единственная задача — задавать автору "
    "ОДИН короткий вопрос, который помогает ему глубже раскрыть СЕБЯ в контексте "
    "сегодняшней темы.\n"
    "\n"
    "ЖЁСТКИЕ ПРАВИЛА ФОРМЫ:\n"
    "1. Ровно одно предложение. Не больше 15 слов. На русском.\n"
    "2. Ноль тире внутри вопроса. Ноль конструкций «Ты, кто X, ...». "
    "Ноль вводных оборотов через запятую перед подлежащим. Подлежащее «ты» "
    "идёт в начале или после короткого вопросительного слова, и точка.\n"
    "3. Не цитируй портрет в самом вопросе. Не вставляй «как человек, который X», "
    "«ты, для кого X — Y», «учитывая, что ты X». Портрет — это твой контекст, "
    "а не материал для вопроса.\n"
    "4. Прямое «ты», простой синтаксис, разговорный тон, без канцелярита.\n"
    "\n"
    "ЖЁСТКИЕ ПРАВИЛА СОДЕРЖАНИЯ:\n"
    "5. АНТИ-ГАЛЛЮЦИНАЦИЯ. Запрещено вводить любые термины, технологии, "
    "аббревиатуры, имена людей, названия методов, продуктов или проектов, "
    "которых нет дословно ни в портрете автора, ни в сегодняшней теме. "
    "Если ты не видишь слово в этих двух блоках — ты его не пишешь. Особенно "
    "это касается технических терминов (RAG, MVP, KPI, ICP и т.п.) и названий "
    "инструментов — даже если они «логично подходят» к роли автора.\n"
    "6. Спрашивай про конкретику автора: воспоминание, эпизод, мнение, "
    "противоречие, страх, конкретный случай, недавний разговор. Не задавай "
    "абстрактных «как ты относишься к...», «что ты думаешь о...».\n"
    "7. Никаких «придумай идею для рилса», «сними видео», «формат», «сценарий», "
    "«контент-план», «оформи пост». Это запрещено.\n"
    "8. Без преамбул («отличная тема», «интересно», «расскажи»), без советов, "
    "без объяснений своего выбора, без приветствий и благодарностей. Только "
    "сам вопрос, заканчивающийся знаком «?».\n"
    "\n"
    "ПРИМЕРЫ ХОРОШИХ ВОПРОСОВ:\n"
    "- «Когда ты в последний раз молчал в чужом разговоре, хотя знал, что прав?»\n"
    "- «Какой момент в этой теме до сих пор бесит тебя лично, а не «вообще»?»\n"
    "- «За что бы ты сам себя раскритиковал, если бы был зрителем?»\n"
    "\n"
    "ПРИМЕРЫ ПЛОХИХ (не делай так):\n"
    "- «Ты, для кого честность — ценность, — какой твой неудобный вывод после "
    "RAG-проекта, который ты бы не сказал на митапе?» — три греха: вложенное "
    "обращение через тире, длинно, и слова «RAG» нет ни в портрете, ни в теме.\n"
    "- «Ты, как продакт в SaaS, что думаешь о...» — обращение-определение перед "
    "вопросом, запрещено правилом 2.\n"
    "- «Расскажи о случае...» — это просьба, а не вопрос.\n"
    "- «Что ты думаешь о современных трендах в твоей нише?» — абстракция.\n"
    "\n"
    "Перед тем как выдать ответ, мысленно проверь: одно предложение? ≤15 слов? "
    "Ноль тире? Ни одного слова, которого нет в портрете и теме? Если хоть "
    "один пункт нарушен — переформулируй."
)

FALLBACK_QUESTION: str = "Что в этой теме задевает лично тебя сильнее всего — и почему именно сейчас?"


class PromptBuilder:
    """Pure function wrapper that composes the chat messages array.

    Stateless and side-effect-free — easy to unit test by inspecting the
    rendered text of the user message.
    """

    def build(
        self,
        *,
        profile_md: str,
        topic: str,
        history: list[ChatQuestion],
        answers: dict[int, str] | None = None,
        pivot: bool = False,
        prior_experience: list[tuple[str, ChatQuestion, str | None]] | None = None,
        is_global: bool = False,
        user_prompts: list[tuple[str, str]] | None = None,
        user_links: list[tuple[str, str]] | None = None,
    ) -> list[ChatMessage]:
        answers_map: dict[int, str] = answers or {}
        prior: list[tuple[str, ChatQuestion, str | None]] = prior_experience or []
        custom_prompts: list[tuple[str, str]] = user_prompts or []
        custom_links: list[tuple[str, str]] = user_links or []
        sections: list[str] = []

        cleaned_profile: str = (profile_md or "").strip()
        if cleaned_profile:
            sections.append(
                "=== Портрет автора (его собственный текст) ===\n" + cleaned_profile
            )
        else:
            sections.append(
                "=== Портрет автора ===\n(пока пусто — опирайся только на тему дня)"
            )

        if custom_prompts:
            cp_blocks: list[str] = []
            for i, (title, content) in enumerate(custom_prompts, 1):
                head = f"[{i}] {title}" if title else f"[{i}]"
                cp_blocks.append(f"{head}\n{content.strip()}")
            sections.append(
                "=== Дополнительные указания автора (применять ко всем чатам) ===\n"
                + "\n\n".join(cp_blocks)
                + "\n\nЭти указания — фон. Не цитируй их в самом вопросе, "
                "используй как ограничения/контекст."
            )

        if custom_links:
            link_lines: list[str] = []
            for url, desc in custom_links:
                desc_clean = (desc or "").strip()
                if desc_clean:
                    link_lines.append(f"- {url} — {desc_clean}")
                else:
                    link_lines.append(f"- {url}")
            sections.append(
                "=== Внешние ресурсы автора (контекст, не цитировать URL в вопросе) ===\n"
                + "\n".join(link_lines)
                + "\n\nТы знаешь, что у автора есть эти ресурсы. Не упоминай URL "
                "в самом вопросе — это нелепо звучит. Используй описания как "
                "подсказку о том, чем автор живёт."
            )

        if is_global:
            sections.append(
                "=== Режим: глобальный диалог ===\n"
                "Это не разговор по одной теме. Автор открыл общий «дневник», "
                "куда он возвращается между темами. Твоя задача — задавать "
                "вопрос, который опирается на его прошлый опыт (см. ниже) "
                "и/или на текущую историю этой глобальной сессии. "
                "Можешь подсветить связь между разными темами автора, "
                "противоречие в его ответах, повторяющийся мотив или непрожитое "
                "место. Тема не задана."
            )
        else:
            sections.append(f"=== Тема, о которой автор хочет говорить сегодня ===\n{topic}")

        if prior:
            prior_blocks: list[str] = []
            for sess_topic, q, a in prior:
                line = f"[тема: {sess_topic}] В: {q.question_text}"
                if a and a.strip():
                    line += f"\n    О: {a.strip()}"
                prior_blocks.append(line)
            sections.append(
                "=== Прошлый опыт автора (фрагменты из других сессий) ===\n"
                + "\n\n".join(prior_blocks)
                + "\n\nИспользуй эти фрагменты как контекст: ты знаешь, что "
                "автор уже отвечал на похожие вопросы или поднимал эти темы. "
                "Не повторяй формулировки, ищи новый угол поверх старых."
            )

        if history:
            history_blocks: list[str] = []
            for i, q in enumerate(history, 1):
                tag: str
                if q.feedback == Feedback.LIKE.value:
                    tag = "[ПОНРАВИЛОСЬ]"
                elif q.feedback == Feedback.DISLIKE.value:
                    tag = "[НЕ ПОНРАВИЛОСЬ]"
                else:
                    tag = "[БЕЗ ОЦЕНКИ]"
                block = f"В{i} {tag}: {q.question_text}"
                ans = (answers_map.get(q.id) or "").strip()
                if ans:
                    block += f"\nОтвет автора: {ans}"
                else:
                    block += "\n(автор не ответил, только оценил)"
                history_blocks.append(block)
            sections.append(
                "=== Уже пройденные пары «вопрос → ответ» в этой сессии ===\n"
                + "\n\n".join(history_blocks)
                + "\n\nКак использовать историю:\n"
                "- Углы из [ПОНРАВИЛОСЬ] заходят — двигайся рядом, но не повторяйся.\n"
                "- Углы из [НЕ ПОНРАВИЛОСЬ] не заходят — избегай похожих.\n"
                "- Если автор ОТВЕТИЛ — следующий вопрос углубляет именно ту "
                "конкретику, которую он раскрыл (имя, факт, эмоция из ответа).\n"
                "- Никогда не повторяй уже заданный вопрос и не задавай его "
                "перефразированную копию."
            )
        else:
            sections.append(
                "=== Уже пройденные пары «вопрос → ответ» в этой сессии ===\n"
                "(пока ни одной — это первый вопрос автору, опирайся на портрет и тему)"
            )

        if pivot:
            sections.append(
                "=== ВНИМАНИЕ: команда автора ===\n"
                "Автор нажал «сменить направление». Тема та же, но угол, под "
                "которым ты к ней подходил, ему НЕ подошёл. Радикально смени "
                "направление: возьми СОВСЕМ другой аспект той же темы — другую "
                "роль автора, другой временной период, другую эмоцию, противоположную "
                "сторону. Вопрос должен ощущаться так, будто это другой собеседник."
            )

        sections.append("Задай следующий вопрос автору. Только один. Без вступлений.")

        user_content: str = "\n\n".join(sections)
        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]
