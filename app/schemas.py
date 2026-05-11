from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE: str = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterForm(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=_EMAIL_RE)
    password: str = Field(min_length=4, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class LoginForm(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=_EMAIL_RE)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class OnboardingAnswerForm(BaseModel):
    question_key: str = Field(min_length=1, max_length=64)
    answer_text: str = Field(min_length=1, max_length=4000)


class ChatStartForm(BaseModel):
    topic: str = Field(min_length=1, max_length=2000)


class ChatFeedbackForm(BaseModel):
    question_id: int
    feedback: str = Field(pattern=r"^(like|dislike)$")


class ChatPivotForm(BaseModel):
    session_id: int


class ChatAnswerForm(BaseModel):
    question_id: int
    answer_text: str = Field(min_length=1, max_length=10000)
