"""The fixed list of 20 onboarding questions and lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnboardingQuestion:
    """One onboarding step.

    Attributes:
        key: Stable machine identifier used in form fields and MD markers.
            Never shown to the user.
        text: Human-readable question shown in the onboarding UI.
    """

    key: str
    text: str


ONBOARDING_QUESTIONS: tuple[OnboardingQuestion, ...] = (
    OnboardingQuestion("name_age_city", "Как тебя зовут, сколько тебе лет и откуда ты?"),
    OnboardingQuestion("occupation", "Чем ты занимаешься профессионально? Опиши в 2-3 предложениях."),
    OnboardingQuestion("niche", "В какой нише/тематике ты делаешь контент (или собираешься)?"),
    OnboardingQuestion("audience", "Опиши свою целевую аудиторию: возраст, пол, чем живёт, что её бесит."),
    OnboardingQuestion("goal", "Зачем тебе reels? Деньги, аудитория, личный бренд, что-то ещё?"),
    OnboardingQuestion("expertise", "В чём ты эксперт сильнее большинства? Чему мог бы научить."),
    OnboardingQuestion("hobbies", "Какие у тебя хобби и нерабочие увлечения?"),
    OnboardingQuestion("values", "3-5 ценностей, которые для тебя важны и которые ты готов отстаивать публично."),
    OnboardingQuestion("voice", "Какой у тебя тон голоса в контенте: дерзкий, тёплый, ироничный, экспертный?"),
    OnboardingQuestion("favorite_formats", "Какие форматы reels тебе ближе: личное мнение, разборы, истории, лайфхаки, споры?"),
    OnboardingQuestion("inspirations", "Назови 2-3 блогеров/каналов, чей контент тебе нравится. Что именно цепляет?"),
    OnboardingQuestion("annoyances", "Что тебя бесит в чужих рилсах в твоей нише?"),
    OnboardingQuestion("turning_points", "Какие 2-3 переломных момента были в твоей жизни/карьере?"),
    OnboardingQuestion("strong_opinions", "Какие у тебя есть непопулярные мнения, готовые к публикации?"),
    OnboardingQuestion("recurring_questions", "Какие вопросы тебе чаще всего задают в твоей теме?"),
    OnboardingQuestion("failures", "Какие свои факапы ты готов(а) разобрать на камеру?"),
    OnboardingQuestion("daily_routine", "Опиши свой обычный рабочий день — что в нём интересного для зрителя?"),
    OnboardingQuestion("taboo", "Какие темы ты НЕ готов(а) трогать ни при каких обстоятельствах?"),
    OnboardingQuestion("dream_outcome", "Опиши идеальный результат: через год reels принесли тебе ___."),
    OnboardingQuestion("anything_else", "Что ещё важно знать о тебе и твоём контексте, чего не спросили?"),
)

QUESTIONS_BY_KEY: dict[str, OnboardingQuestion] = {q.key: q for q in ONBOARDING_QUESTIONS}
TOTAL_ONBOARDING_QUESTIONS: int = len(ONBOARDING_QUESTIONS)
