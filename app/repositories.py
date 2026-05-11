from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatAnswer, ChatQuestion, ChatSession, Feedback, User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db: Session = db

    def get_by_email(self, email: str) -> User | None:
        return self._db.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: int) -> User | None:
        return self._db.scalar(select(User).where(User.id == user_id))

    def create(self, *, email: str, password_hash: str, password_salt: str) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            password_salt=password_salt,
            profile_md="",
            onboarding_complete=False,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user

    def set_profile_md(self, user: User, profile_md: str) -> None:
        user.profile_md = profile_md
        self._db.commit()

    def set_password(self, user: User, password_hash: str, password_salt: str) -> None:
        user.password_hash = password_hash
        user.password_salt = password_salt
        self._db.commit()

    def set_onboarding_complete(self, user: User, complete: bool) -> None:
        user.onboarding_complete = complete
        self._db.commit()


class ChatRepository:
    def __init__(self, db: Session) -> None:
        self._db: Session = db

    def create_session(self, *, user_id: int, topic: str) -> ChatSession:
        s = ChatSession(user_id=user_id, topic=topic)
        self._db.add(s)
        self._db.commit()
        self._db.refresh(s)
        return s

    def close_session(self, session: ChatSession) -> None:
        session.closed_at = datetime.now(tz=timezone.utc)
        self._db.commit()

    def get_session(self, *, session_id: int, user_id: int) -> ChatSession | None:
        return self._db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.user_id == user_id
            )
        )

    def latest_open_session(self, user_id: int) -> ChatSession | None:
        return self._db.scalar(
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.closed_at.is_(None))
            .order_by(ChatSession.id.desc())
        )

    def list_user_sessions(self, user_id: int) -> list[tuple[ChatSession, int]]:
        rows = self._db.execute(
            select(ChatSession, func.count(ChatQuestion.id))
            .outerjoin(ChatQuestion, ChatQuestion.session_id == ChatSession.id)
            .where(ChatSession.user_id == user_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.id.desc())
        ).all()
        return [(s, int(n or 0)) for s, n in rows]

    def get_session_owned_by(self, *, session_id: int, user_id: int) -> ChatSession | None:
        return self._db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.user_id == user_id
            )
        )

    def get_question_owned_by(self, *, question_id: int, user_id: int) -> ChatQuestion | None:
        return self._db.scalar(
            select(ChatQuestion)
            .join(ChatSession, ChatQuestion.session_id == ChatSession.id)
            .where(ChatQuestion.id == question_id, ChatSession.user_id == user_id)
        )

    def list_questions(self, session_id: int) -> list[ChatQuestion]:
        rows = self._db.scalars(
            select(ChatQuestion)
            .where(ChatQuestion.session_id == session_id)
            .order_by(ChatQuestion.position)
        ).all()
        return list(rows)

    def add_question(self, *, session_id: int, position: int, text: str) -> ChatQuestion:
        q = ChatQuestion(session_id=session_id, position=position, question_text=text)
        self._db.add(q)
        self._db.commit()
        self._db.refresh(q)
        return q

    def get_question(self, *, question_id: int, session_id: int) -> ChatQuestion | None:
        return self._db.scalar(
            select(ChatQuestion).where(
                ChatQuestion.id == question_id, ChatQuestion.session_id == session_id
            )
        )

    def set_feedback(self, question: ChatQuestion, feedback: Feedback) -> None:
        question.feedback = feedback.value
        self._db.commit()

    def upsert_answer(self, question: ChatQuestion, answer_text: str) -> ChatAnswer:
        existing = self._db.scalar(
            select(ChatAnswer).where(ChatAnswer.question_id == question.id)
        )
        if existing is None:
            existing = ChatAnswer(question_id=question.id, answer_text=answer_text)
            self._db.add(existing)
        else:
            existing.answer_text = answer_text
        self._db.commit()
        self._db.refresh(existing)
        return existing

    def answers_by_question_id(self, session_id: int) -> dict[int, str]:
        rows = self._db.scalars(
            select(ChatAnswer)
            .join(ChatQuestion, ChatAnswer.question_id == ChatQuestion.id)
            .where(ChatQuestion.session_id == session_id)
        ).all()
        return {a.question_id: a.answer_text for a in rows}
