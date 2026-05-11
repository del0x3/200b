"""Onboarding wizard: 20 questions, progress, completion guard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.questions import ONBOARDING_QUESTIONS, TOTAL_ONBOARDING_QUESTIONS

from tests.conftest import register


def test_onboarding_page_renders_first_question(client: TestClient) -> None:
    register(client)
    r = client.get("/onboarding")
    assert r.status_code == 200
    assert ONBOARDING_QUESTIONS[0].text in r.text


def test_full_onboarding_flow_marks_complete(client: TestClient) -> None:
    register(client)
    for i, q in enumerate(ONBOARDING_QUESTIONS, 1):
        r = client.post(
            "/onboarding/answer",
            data={"question_key": q.key, "answer_text": f"ответ {i}"},
        )
        if i < TOTAL_ONBOARDING_QUESTIONS:
            assert r.status_code == 200, f"step {i}/{TOTAL_ONBOARDING_QUESTIONS} failed: {r.text[:200]}"
            assert ONBOARDING_QUESTIONS[i].text in r.text  # next question shown
        else:
            assert r.status_code == 204
            assert r.headers.get("hx-redirect") == "/"


def test_onboarding_after_complete_redirects_home(client: TestClient) -> None:
    register(client)
    for q in ONBOARDING_QUESTIONS:
        client.post("/onboarding/answer", data={"question_key": q.key, "answer_text": "x"})
    r = client.get("/onboarding", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_onboarding_empty_answer_rejected(client: TestClient) -> None:
    register(client)
    r = client.post(
        "/onboarding/answer",
        data={"question_key": ONBOARDING_QUESTIONS[0].key, "answer_text": ""},
    )
    assert r.status_code in (400, 422)


def test_onboarding_unknown_key_returns_400(client: TestClient) -> None:
    """Unknown question_key must not crash — should return 400."""
    register(client)
    r = client.post(
        "/onboarding/answer",
        data={"question_key": "nonexistent_key_xyz", "answer_text": "anything"},
    )
    assert r.status_code == 400


def test_home_redirects_to_onboarding_when_incomplete(client: TestClient) -> None:
    register(client)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/onboarding"


def test_whitespace_only_answer_lets_validation_through_but_does_not_advance(
    client: TestClient,
) -> None:
    """Bug-hunt: min_length=1 on answer_text is BEFORE strip in the route.

    If pydantic accepts " ", the service writes empty section and the same
    question should reappear on next GET — no silent advance.
    """
    register(client)
    first_q = ONBOARDING_QUESTIONS[0]
    r = client.post(
        "/onboarding/answer",
        data={"question_key": first_q.key, "answer_text": "   "},
    )
    # Either reject (400) or accept-but-not-advance (still first question).
    if r.status_code == 200:
        assert first_q.text in r.text, (
            "BUG: whitespace-only answer should not advance onboarding "
            "(or should be rejected at validation)"
        )
    else:
        assert r.status_code in (400, 422)
