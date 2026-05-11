"""Password hashing, JWT issuing/decoding, and FastAPI auth dependencies."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
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
    """Result of hashing a password.

    Attributes:
        hash_hex: The hash value as stored in the DB. For bcrypt this is
            the full bcrypt string starting with ``$2``; for the legacy
            sha256 scheme this is the 64-char hex digest.
        salt_hex: Hex-encoded salt for the legacy scheme. Empty string for
            bcrypt (bcrypt stores its salt inside the hash itself).
    """

    hash_hex: str
    salt_hex: str


class PasswordHasher:
    """bcrypt с прозрачным апгрейдом старых sha256-хешей.

    Колонки в БД (password_hash, password_salt) сохранены для совместимости:
    - bcrypt: hash_hex = bcrypt-строка ($2b$...), salt_hex = "" (bcrypt хранит соль в хеше).
    - legacy sha256: hash_hex = sha256-hex, salt_hex = hex-соль (16 байт).
    """

    BCRYPT_ROUNDS: int = 12
    LEGACY_SALT_BYTES: int = 16

    def hash(self, password: str) -> PasswordHash:
        bcrypt_hash: bytes = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(rounds=self.BCRYPT_ROUNDS)
        )
        return PasswordHash(hash_hex=bcrypt_hash.decode("ascii"), salt_hex="")

    def verify(self, password: str, hash_hex: str, salt_hex: str) -> bool:
        if hash_hex.startswith("$2"):
            try:
                return bcrypt.checkpw(password.encode("utf-8"), hash_hex.encode("ascii"))
            except ValueError:
                return False
        # legacy sha256 + per-user salt
        try:
            salt: bytes = bytes.fromhex(salt_hex)
        except ValueError:
            return False
        candidate: str = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(candidate, hash_hex)

    def needs_rehash(self, hash_hex: str) -> bool:
        return not hash_hex.startswith("$2")


class JwtService:
    """Issues and verifies short-lived JWT session tokens.

    Tokens carry only `sub` (user id), `iat`, and `exp`. The secret comes
    from ``settings.jwt_secret`` (Render generates a random one via
    `render.yaml`'s `generateValue: true`).
    """

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
    """Marker exception. The global handler in `main.py` turns it into a 303 → /login."""

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
