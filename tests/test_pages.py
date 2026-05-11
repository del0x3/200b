"""Smoke-render every public page for an authed user."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_login_page_anon(client: TestClient) -> None:
    r = client.get("/login")
    assert r.status_code == 200
    assert "Вход" in r.text


def test_register_page_anon(client: TestClient) -> None:
    r = client.get("/register")
    assert r.status_code == 200


def test_home_page_authed(authed_client: TestClient) -> None:
    r = authed_client.get("/")
    assert r.status_code == 200
    # Home shows the topic-input prompt and the portrait CTA
    assert "тему дня" in r.text.lower() or "о чём хочешь" in r.text.lower()
    assert "Редактировать портрет" in r.text  # the fix from previous turn
    # The single topic form should expose BOTH actions: new thematic session and global.
    assert 'hx-post="/chat/start"' in r.text
    assert 'hx-post="/chat/global/start"' in r.text
    assert "Начать новую сессию" in r.text
    assert "Добавить в глобальный" in r.text


def test_profile_page_authed(authed_client: TestClient) -> None:
    r = authed_client.get("/profile")
    assert r.status_code == 200
    assert "Твой портрет" in r.text
    assert "Кастомные указания" in r.text
    assert "Ресурсы" in r.text


def test_profile_download_authed(authed_client: TestClient) -> None:
    r = authed_client.get("/profile/download")
    assert r.status_code == 200
    assert "text/markdown" in r.headers.get("content-type", "")


def test_static_css_served(client: TestClient) -> None:
    r = client.get("/static/style.css")
    assert r.status_code == 200
    assert "stream-panel" in r.text  # voice streaming styles must be present


def test_profile_redirects_anon(client: TestClient) -> None:
    r = client.get("/profile", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
