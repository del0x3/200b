from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.deepseek import DeepSeekClient, DeepSeekError
from app.models import ChatQuestion, ChatSession, Feedback, User
from app.profile_md import (
    answered_count,
    first_unanswered,
    upsert_answer,
)
from app.prompts import FALLBACK_QUESTION, PromptBuilder
from app.questions import QUESTIONS_BY_KEY, TOTAL_ONBOARDING_QUESTIONS, OnboardingQuestion
from app.repositories import ChatRepository, UserRepository
from app.security import JwtService, PasswordHasher

logger = logging.getLogger(__name__)


class AuthError(Exception):
    pass


class EmailTakenError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


@dataclass(frozen=True)
class AuthResult:
    user: User
    token: str


class AuthService:
    def __init__(self, db: Session, hasher: PasswordHasher, jwt: JwtService) -> None:
        self._users: UserRepository = UserRepository(db)
        self._hasher: PasswordHasher = hasher
        self._jwt: JwtService = jwt

    def register(self, *, email: str, password: str) -> AuthResult:
        if self._users.get_by_email(email) is not None:
            raise EmailTakenError("такой email уже зарегистрирован")
        ph = self._hasher.hash(password)
        user = self._users.create(
            email=email, password_hash=ph.hash_hex, password_salt=ph.salt_hex
        )
        token = self._jwt.issue(user.id)
        return AuthResult(user=user, token=token)

    def login(self, *, email: str, password: str) -> AuthResult:
        user = self._users.get_by_email(email)
        if user is None:
            raise InvalidCredentialsError("неверный email или пароль")
        if not self._hasher.verify(password, user.password_hash, user.password_salt):
            raise InvalidCredentialsError("неверный email или пароль")
        token = self._jwt.issue(user.id)
        return AuthResult(user=user, token=token)


@dataclass(frozen=True)
class OnboardingProgress:
    answered: int
    total: int
    next_question: OnboardingQuestion | None

    @property
    def is_complete(self) -> bool:
        return self.next_question is None


class OnboardingService:
    def __init__(self, db: Session) -> None:
        self._users: UserRepository = UserRepository(db)

    def progress(self, user: User) -> OnboardingProgress:
        if user.onboarding_complete:
            return OnboardingProgress(
                answered=TOTAL_ONBOARDING_QUESTIONS,
                total=TOTAL_ONBOARDING_QUESTIONS,
                next_question=None,
            )
        next_q: OnboardingQuestion | None = first_unanswered(user.profile_md)
        return OnboardingProgress(
            answered=answered_count(user.profile_md),
            total=TOTAL_ONBOARDING_QUESTIONS,
            next_question=next_q,
        )

    def save_answer(
        self, *, user: User, question_key: str, answer_text: str
    ) -> OnboardingProgress:
        question: OnboardingQuestion | None = QUESTIONS_BY_KEY.get(question_key)
        if question is None:
            raise ValueError(f"unknown question key: {question_key}")
        new_md: str = upsert_answer(user.profile_md, key=question.key, answer_text=answer_text)
        self._users.set_profile_md(user, new_md)
        progress = self.progress(user)
        if progress.next_question is None and not user.onboarding_complete:
            self._users.set_onboarding_complete(user, True)
        return progress


class ProfileService:
    def __init__(self, db: Session) -> None:
        self._users: UserRepository = UserRepository(db)

    def save_markdown(self, user: User, markdown: str) -> None:
        self._users.set_profile_md(user, markdown)

    def import_markdown(self, user: User, markdown: str) -> None:
        """Заливка пользовательского MD: сохраняет и помечает онбординг как пройденный."""
        self._users.set_profile_md(user, markdown)
        if not user.onboarding_complete and markdown.strip():
            self._users.set_onboarding_complete(user, True)


@dataclass(frozen=True)
class CurrentQuestion:
    session_id: int
    question: ChatQuestion


@dataclass(frozen=True)
class SessionSummary:
    session: ChatSession
    questions_count: int


@dataclass(frozen=True)
class SessionView:
    session: ChatSession
    pairs: list[tuple[ChatQuestion, str | None]]
    last_question: ChatQuestion | None
    last_unanswered: ChatQuestion | None


class ChatService:
    def __init__(
        self,
        db: Session,
        deepseek: DeepSeekClient,
        prompts: PromptBuilder | None = None,
    ) -> None:
        self._chat: ChatRepository = ChatRepository(db)
        self._deepseek: DeepSeekClient = deepseek
        self._prompts: PromptBuilder = prompts or PromptBuilder()

    async def start(self, *, user: User, topic: str) -> CurrentQuestion:
        topic_clean = topic.strip()
        session: ChatSession = self._chat.create_session(user_id=user.id, topic=topic_clean)
        question_text: str = await self._generate(user=user, session=session, history=[])
        question = self._chat.add_question(
            session_id=session.id, position=0, text=question_text
        )
        return CurrentQuestion(session_id=session.id, question=question)

    async def feedback_and_next(
        self, *, user: User, question_id: int, feedback: Feedback
    ) -> CurrentQuestion:
        question: ChatQuestion | None = self._lookup_question(user, question_id)
        if question is None:
            raise ValueError("question not found")
        self._chat.set_feedback(question, feedback)
        session: ChatSession | None = self._chat.get_session(
            session_id=question.session_id, user_id=user.id
        )
        if session is None:
            raise ValueError("session not found")
        return await self._generate_next(user=user, session=session)

    async def answer_and_next(
        self, *, user: User, question_id: int, answer_text: str
    ) -> CurrentQuestion:
        question: ChatQuestion | None = self._lookup_question(user, question_id)
        if question is None:
            raise ValueError("question not found")
        self._chat.upsert_answer(question, answer_text)
        session: ChatSession | None = self._chat.get_session(
            session_id=question.session_id, user_id=user.id
        )
        if session is None:
            raise ValueError("session not found")
        return await self._generate_next(user=user, session=session)

    async def pivot(self, *, user: User, session_id: int) -> CurrentQuestion:
        session: ChatSession | None = self._chat.get_session(session_id=session_id, user_id=user.id)
        if session is None:
            raise ValueError("session not found")
        return await self._generate_next(user=user, session=session, pivot=True)

    async def _generate_next(
        self, *, user: User, session: ChatSession, pivot: bool = False
    ) -> CurrentQuestion:
        history: list[ChatQuestion] = self._chat.list_questions(session.id)
        answers: dict[int, str] = self._chat.answers_by_question_id(session.id)
        question_text: str = await self._generate(
            user=user, session=session, history=history, answers=answers, pivot=pivot
        )
        next_position: int = max((q.position for q in history), default=-1) + 1
        next_q = self._chat.add_question(
            session_id=session.id, position=next_position, text=question_text
        )
        return CurrentQuestion(session_id=session.id, question=next_q)

    async def _generate(
        self,
        *,
        user: User,
        session: ChatSession,
        history: list[ChatQuestion],
        answers: dict[int, str] | None = None,
        pivot: bool = False,
    ) -> str:
        messages = self._prompts.build(
            profile_md=user.profile_md,
            topic=session.topic,
            history=history,
            answers=answers or {},
            pivot=pivot,
        )
        try:
            return await self._deepseek.chat(messages)
        except DeepSeekError as exc:
            logger.error("DeepSeek failed, using fallback: %s", exc)
            return FALLBACK_QUESTION

    def _lookup_question(self, user: User, question_id: int) -> ChatQuestion | None:
        return self._chat.get_question_owned_by(question_id=question_id, user_id=user.id)

    def list_sessions(self, user: User) -> list[SessionSummary]:
        return [
            SessionSummary(session=s, questions_count=n)
            for s, n in self._chat.list_user_sessions(user.id)
        ]

    def get_session_view(self, *, user: User, session_id: int) -> SessionView | None:
        session = self._chat.get_session_owned_by(session_id=session_id, user_id=user.id)
        if session is None:
            return None
        questions: list[ChatQuestion] = self._chat.list_questions(session.id)
        answers: dict[int, str] = self._chat.answers_by_question_id(session.id)
        pairs: list[tuple[ChatQuestion, str | None]] = [
            (q, answers.get(q.id)) for q in questions
        ]
        last_q = questions[-1] if questions else None
        last_unanswered = (
            last_q if last_q is not None and last_q.id not in answers else None
        )
        return SessionView(
            session=session, pairs=pairs, last_question=last_q, last_unanswered=last_unanswered
        )

    async def continue_session(self, *, user: User, session_id: int) -> CurrentQuestion:
        session = self._chat.get_session_owned_by(session_id=session_id, user_id=user.id)
        if session is None:
            raise ValueError("session not found")
        questions: list[ChatQuestion] = self._chat.list_questions(session.id)
        answers: dict[int, str] = self._chat.answers_by_question_id(session.id)
        last_q: ChatQuestion | None = questions[-1] if questions else None
        if last_q is not None and last_q.id not in answers:
            return CurrentQuestion(session_id=session.id, question=last_q)
        return await self._generate_next(user=user, session=session)
