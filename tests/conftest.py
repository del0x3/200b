"""Pytest fixtures: isolated SQLite DB per test, mocked DeepSeek client."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Base, Database
from app.dependencies import get_deepseek
from app.db import get_db
from app.main import app
from app.security import PasswordHasher


class FakeDeepSeek:
    """In-memory DeepSeek stub for tests.

    Records every prompt that comes in and returns canned responses.
    By default emits unique "Тестовый вопрос N?" strings so different
    questions never collide.
    """

    def __init__(self) -> None:
        self.calls: list[list] = []
        self.canned: list[str] = []
        self._counter: int = 0

    def queue(self, *responses: str) -> None:
        self.canned.extend(responses)

    async def chat(self, messages, **kwargs) -> str:
        self.calls.append(list(messages))
        if self.canned:
            return self.canned.pop(0)
        self._counter += 1
        return f"Тестовый вопрос {self._counter}?"


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    """bcrypt cost factor 12 is ~250ms/hash — way too slow for fast tests."""
    monkeypatch.setattr(PasswordHasher, "BCRYPT_ROUNDS", 4)


@pytest.fixture
def test_db(tmp_path: Path) -> Database:
    """Fresh on-disk SQLite per test, with all tables created."""
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    Base.metadata.create_all(db.engine)
    return db


@pytest.fixture
def fake_ds() -> FakeDeepSeek:
    return FakeDeepSeek()


@pytest.fixture
def client(test_db: Database, fake_ds: FakeDeepSeek) -> Iterator[TestClient]:
    """TestClient with get_db + get_deepseek overridden.

    `client.fake_ds` is exposed for tests that need to queue canned
    answers or inspect outgoing prompts.
    """

    def _override_get_db():
        s = test_db.session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_deepseek] = lambda: fake_ds

    with TestClient(app) as c:
        c.fake_ds = fake_ds  # type: ignore[attr-defined]
        yield c

    app.dependency_overrides.clear()


# ---------- High-level helpers used by many tests ----------


def register(client: TestClient, email: str = "u@test.local", password: str = "pwd1234") -> None:
    """Register and stay logged in. Lands on /onboarding."""
    r = client.post("/register", data={"email": email, "password": password}, follow_redirects=False)
    assert r.status_code == 303, f"register failed: {r.status_code} {r.text[:200]}"
    assert r.headers["location"] == "/onboarding"


def complete_onboarding(client: TestClient) -> None:
    """Walk through all 20 onboarding questions answering 'тестовый ответ'."""
    from app.questions import ONBOARDING_QUESTIONS

    for q in ONBOARDING_QUESTIONS:
        r = client.post(
            "/onboarding/answer",
            data={"question_key": q.key, "answer_text": f"ответ на {q.key}"},
        )
        assert r.status_code in (200, 204), f"onboarding step {q.key}: {r.status_code}"


@pytest.fixture
def authed_client(client: TestClient) -> TestClient:
    """Client with a registered user who has finished onboarding."""
    register(client)
    complete_onboarding(client)
    return client
