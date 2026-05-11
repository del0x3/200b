"""FastAPI dependency providers — build services with a per-request DB session."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.deepseek import DeepSeekClient
from app.security import jwt_service, password_hasher
from app.services import AuthService, ChatService, OnboardingService, ProfileService


def get_deepseek(request: Request) -> DeepSeekClient:
    client = getattr(request.app.state, "deepseek", None)
    if not isinstance(client, DeepSeekClient):
        raise RuntimeError("DeepSeek client is not initialized in app.state")
    return client


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db=db, hasher=password_hasher, jwt=jwt_service)


def get_onboarding_service(db: Session = Depends(get_db)) -> OnboardingService:
    return OnboardingService(db=db)


def get_profile_service(db: Session = Depends(get_db)) -> ProfileService:
    return ProfileService(db=db)


def get_chat_service(
    db: Session = Depends(get_db),
    deepseek: DeepSeekClient = Depends(get_deepseek),
) -> ChatService:
    return ChatService(db=db, deepseek=deepseek)
