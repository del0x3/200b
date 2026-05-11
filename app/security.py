from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

COOKIE_NAME: str = "token"
JWT_ALGORITHM: str = "HS256"
JWT_TTL_DAYS: int = 30


@dataclass(frozen=True)
class PasswordHash:
    hash_hex: str
    salt_hex: str


class PasswordHasher:
    SALT_BYTES: int = 16

    def hash(self, password: str) -> PasswordHash:
        salt: bytes = secrets.token_bytes(self.SALT_BYTES)
        digest: str = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
        return PasswordHash(hash_hex=digest, salt_hex=salt.hex())

    def verify(self, password: str, hash_hex: str, salt_hex: str) -> bool:
        salt: bytes = bytes.fromhex(salt_hex)
        candidate: str = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(candidate, hash_hex)


class JwtService:
    def __init__(self, secret: str, algorithm: str = JWT_ALGORITHM, ttl_days: int = JWT_TTL_DAYS) -> None:
        self._secret: str = secret
        self._algorithm: str = algorithm
        self._ttl: timedelta = timedelta(days=ttl_days)

    def issue(self, user_id: int) -> str:
        now: datetime = datetime.now(tz=timezone.utc)
        payload: dict[str, object] = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + self._ttl).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_user_id(self, token: str) -> int | None:
        try:
            payload: dict[str, object] = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError:
            return None
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub.isdigit():
            return None
        return int(sub)


password_hasher = PasswordHasher()
jwt_service = JwtService(settings.jwt_secret)


def set_auth_cookie(response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=JWT_TTL_DAYS * 24 * 3600,
        path="/",
    )


def clear_auth_cookie(response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


class RedirectToLogin(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth-required")


def current_user(
    request: Request,
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise RedirectToLogin()
    user_id: int | None = jwt_service.decode_user_id(token)
    if user_id is None:
        raise RedirectToLogin()
    user: User | None = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise RedirectToLogin()
    return user


def optional_user(
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None
    user_id: int | None = jwt_service.decode_user_id(token)
    if user_id is None:
        return None
    return db.scalar(select(User).where(User.id == user_id))


def redirect_unauth_handler(_request: Request, _exc: RedirectToLogin) -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
