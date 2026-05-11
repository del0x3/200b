"""Register / login / logout end-to-end."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_redirects_to_onboarding(client: TestClient) -> None:
    r = client.post(
        "/register",
        data={"email": "new@test.local", "password": "secret123"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/onboarding"
    assert "token=" in r.headers.get("set-cookie", "")


def test_register_rejects_short_password(client: TestClient) -> None:
    r = client.post("/register", data={"email": "x@x.com", "password": "12"})
    assert r.status_code == 400
    assert "email" in r.text.lower() or "пароль" in r.text.lower()


def test_register_rejects_invalid_email(client: TestClient) -> None:
    r = client.post("/register", data={"email": "not-an-email", "password": "secret123"})
    assert r.status_code == 400


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {"email": "dup@test.local", "password": "secret123"}
    r1 = client.post("/register", data=payload, follow_redirects=False)
    assert r1.status_code == 303
    # second registration should fail with 400
    fresh = TestClient(client.app)
    fresh.cookies.clear()
    r2 = fresh.post("/register", data=payload)
    assert r2.status_code == 400
    assert "email" in r2.text.lower()


def test_login_with_correct_creds(client: TestClient) -> None:
    client.post("/register", data={"email": "li@test.local", "password": "secret123"})
    # New session, no cookies
    client.cookies.clear()
    r = client.post(
        "/login",
        data={"email": "li@test.local", "password": "secret123"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert "token=" in r.headers.get("set-cookie", "")


def test_login_with_wrong_password(client: TestClient) -> None:
    client.post("/register", data={"email": "wp@test.local", "password": "secret123"})
    client.cookies.clear()
    r = client.post("/login", data={"email": "wp@test.local", "password": "wrong-pwd"})
    assert r.status_code == 400
    assert "неверный" in r.text.lower() or "invalid" in r.text.lower()


def test_login_with_unknown_email(client: TestClient) -> None:
    r = client.post("/login", data={"email": "ghost@test.local", "password": "anything"})
    assert r.status_code == 400


def test_email_normalised_to_lower(client: TestClient) -> None:
    client.post("/register", data={"email": "MixedCase@TEST.local", "password": "secret123"})
    client.cookies.clear()
    r = client.post(
        "/login",
        data={"email": "mixedcase@test.local", "password": "secret123"},
        follow_redirects=False,
    )
    assert r.status_code == 303


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post("/register", data={"email": "lo@test.local", "password": "secret123"})
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    set_cookie = r.headers.get("set-cookie", "")
    assert "token=" in set_cookie
    # The cookie should be cleared (empty value or expires in the past)
    assert ('token=""' in set_cookie or "token=;" in set_cookie or "max-age=0" in set_cookie.lower() or
            "expires=Thu, 01 Jan 1970" in set_cookie)


def test_unauthenticated_redirects_to_login(client: TestClient) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_invalid_jwt_redirects_to_login(client: TestClient) -> None:
    client.cookies.set("token", "garbage.jwt.value")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
