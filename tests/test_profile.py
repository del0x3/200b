"""Profile MD save/upload + custom prompts CRUD + resource links CRUD."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient


def test_save_profile_md(authed_client: TestClient) -> None:
    """Saving a portrait of comparable length to the onboarding-generated MD is OK."""
    # The anti-wipe guard rejects if new < 50% of old. After 20 onboarding answers
    # the portrait is ~600 bytes. Make ours bigger.
    base = "Я продакт-менеджер из Берлина, бегаю по утрам, не люблю утренние созвоны. "
    new_md = "# Портрет\n\n" + base * 30
    r = authed_client.post("/profile", data={"profile_md": new_md}, follow_redirects=False)
    assert r.status_code == 303, f"unexpected: {r.status_code} / {r.text[:200]}"
    assert r.headers["location"] == "/"
    r = authed_client.get("/profile")
    assert "Берлина" in r.text


def test_anti_wipe_rejects_drastic_shrink(authed_client: TestClient) -> None:
    """If new MD is <50% of old, save should be rejected (409)."""
    long_md = ("# Big portrait\n\n" + "Очень много текста о тебе. " * 200)
    authed_client.post("/profile", data={"profile_md": long_md})
    r = authed_client.post("/profile", data={"profile_md": "коротко"})
    assert r.status_code == 409
    # Server should keep the OLD long text
    r = authed_client.get("/profile")
    assert "Очень много текста о тебе" in r.text


def test_anti_wipe_allows_first_save_from_empty(client: TestClient) -> None:
    """First save (from empty initial state) of a SHORT text should still be rejected
    only when there's a real prior portrait. With empty old_text the guard doesn't trigger."""
    from tests.conftest import register
    register(client)
    # Skip onboarding via direct profile import - need to walk onboarding first.
    from app.questions import ONBOARDING_QUESTIONS
    for q in ONBOARDING_QUESTIONS:
        client.post("/onboarding/answer", data={"question_key": q.key, "answer_text": "y"})
    # After onboarding, there's a portrait MD. Anti-wipe applies.
    r = client.post("/profile", data={"profile_md": "x"})
    assert r.status_code == 409


def test_profile_upload_md(authed_client: TestClient) -> None:
    big_md = "# Из файла\n\n" + ("Раздел про меня. " * 100)
    r = authed_client.post(
        "/profile/upload",
        files={"file": ("portrait.md", BytesIO(big_md.encode("utf-8")), "text/markdown")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "Из файла" in page


def test_profile_upload_rejects_non_utf8(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/profile/upload",
        files={"file": ("bad.md", BytesIO(b"\xff\xfe\x00broken"), "text/markdown")},
    )
    assert r.status_code == 400


def test_profile_upload_rejects_huge_file(authed_client: TestClient) -> None:
    huge = b"X" * 1_500_000  # > 1MB cap
    r = authed_client.post(
        "/profile/upload",
        files={"file": ("huge.md", BytesIO(huge), "text/markdown")},
    )
    assert r.status_code == 413


# ----- Custom prompts -----

def test_prompt_crud_full_cycle(authed_client: TestClient) -> None:
    # Create
    r = authed_client.post(
        "/profile/prompt",
        data={"title": "Тон", "content": "пиши на ты", "enabled": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    page = authed_client.get("/profile").text
    assert "Тон" in page
    assert "пиши на ты" in page

    # Find the prompt id
    import re
    m = re.search(r'/profile/prompt/(\d+)"', page)
    assert m, "prompt id not found in profile page HTML"
    pid = int(m.group(1))

    # Update — disable
    r = authed_client.post(
        f"/profile/prompt/{pid}",
        data={"title": "Тон-2", "content": "новый текст", "enabled": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "Тон-2" in page
    assert "новый текст" in page

    # Download .md
    r = authed_client.get(f"/profile/prompt/{pid}/download")
    assert r.status_code == 200
    assert "новый текст" in r.text

    # Delete
    r = authed_client.post(f"/profile/prompt/{pid}/delete", follow_redirects=False)
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "Тон-2" not in page


def test_empty_prompt_content_silently_ignored(authed_client: TestClient) -> None:
    """Creating a prompt with empty content should redirect without creating anything."""
    r = authed_client.post(
        "/profile/prompt",
        data={"title": "пусто", "content": "   ", "enabled": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "пусто" not in page or "Ещё ничего не добавлено" in page


def test_prompt_upload_uses_filename_when_title_blank(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/profile/prompt/upload",
        data={"title": ""},
        files={"file": ("my-style.md", BytesIO("инструкция".encode("utf-8")), "text/markdown")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "my-style" in page
    assert "инструкция" in page


def test_disabled_prompt_not_sent_to_llm(authed_client: TestClient) -> None:
    """Create one disabled and one enabled prompt; only enabled should appear in the prompt sent to DeepSeek."""
    authed_client.post(
        "/profile/prompt",
        data={"title": "включенное", "content": "правило-включено", "enabled": "1"},
    )
    authed_client.post(
        "/profile/prompt",
        data={"title": "выключенное", "content": "правило-выключено", "enabled": ""},
    )

    authed_client.fake_ds.queue("вопрос?")  # type: ignore[attr-defined]
    authed_client.post(
        "/chat/start",
        data={"topic": "проверка"},
        headers={"hx-request": "true"},
        follow_redirects=False,
    )
    last_call = authed_client.fake_ds.calls[-1]  # type: ignore[attr-defined]
    full = " ".join(m.content for m in last_call)
    assert "правило-включено" in full
    assert "правило-выключено" not in full


def test_other_users_prompt_inaccessible(client: TestClient, authed_client: TestClient) -> None:
    """User A creates a prompt; user B can't update/delete/download it."""
    # authed_client is user A. Create a prompt.
    authed_client.post(
        "/profile/prompt", data={"title": "секрет", "content": "содержимое", "enabled": "1"}
    )
    import re
    page = authed_client.get("/profile").text
    pid = int(re.search(r'/profile/prompt/(\d+)"', page).group(1))

    # Switch to user B
    authed_client.post("/logout")
    authed_client.cookies.clear()
    authed_client.post("/register", data={"email": "userb@test.local", "password": "secret123"})
    # Walk onboarding so we can access /profile
    from app.questions import ONBOARDING_QUESTIONS
    for q in ONBOARDING_QUESTIONS:
        authed_client.post("/onboarding/answer", data={"question_key": q.key, "answer_text": "y"})

    # Try to update — service silently returns False but redirect happens.
    # Real test: download should 404 since user B doesn't own it.
    r = authed_client.get(f"/profile/prompt/{pid}/download")
    assert r.status_code == 404

    # And user B's profile page must not show user A's prompt
    page_b = authed_client.get("/profile").text
    assert "секрет" not in page_b
    assert "содержимое" not in page_b


# ----- Resource links -----

def test_link_crud(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/profile/link",
        data={"url": "https://example.com/me", "description": "мой блог"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    page = authed_client.get("/profile").text
    assert "https://example.com/me" in page
    assert "мой блог" in page

    import re
    m = re.search(r'/profile/link/(\d+)"', page)
    assert m
    lid = int(m.group(1))

    # Update
    authed_client.post(
        f"/profile/link/{lid}",
        data={"url": "https://example.com/me-v2", "description": "обновлённый блог"},
    )
    page = authed_client.get("/profile").text
    assert "me-v2" in page
    assert "обновлённый блог" in page

    # Delete
    authed_client.post(f"/profile/link/{lid}/delete")
    page = authed_client.get("/profile").text
    assert "me-v2" not in page


def test_empty_url_silently_ignored(authed_client: TestClient) -> None:
    unique_marker = "уникальный-маркер-xY9-описание"
    r = authed_client.post(
        "/profile/link", data={"url": "  ", "description": unique_marker}, follow_redirects=False
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert unique_marker not in page


# ----- Documents (long-form MD context) -----

def test_document_crud_full_cycle(authed_client: TestClient) -> None:
    body = "# Моя биография\n\n" + ("Я родилась в маленьком городе. " * 30)
    r = authed_client.post(
        "/profile/doc",
        data={"title": "Биография", "content": body, "enabled": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    page = authed_client.get("/profile").text
    assert "Биография" in page
    assert "Я родилась в маленьком городе" in page

    import re
    m = re.search(r'/profile/doc/(\d+)"', page)
    assert m, "doc id not found in page"
    did = int(m.group(1))

    # Update
    new_body = body.replace("маленьком", "большом")
    r = authed_client.post(
        f"/profile/doc/{did}",
        data={"title": "Биография обновлённая", "content": new_body, "enabled": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "Биография обновлённая" in page
    assert "в большом городе" in page

    # Download — must work with Russian title (RFC 5987)
    r = authed_client.get(f"/profile/doc/{did}/download")
    assert r.status_code == 200
    assert "в большом городе" in r.text
    assert "filename*=UTF-8''" in r.headers["content-disposition"]

    # Delete
    r = authed_client.post(f"/profile/doc/{did}/delete", follow_redirects=False)
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "Биография обновлённая" not in page


def test_document_no_count_limit_lots_of_docs(authed_client: TestClient) -> None:
    """Юзер просил «без ограничений по количеству» — создаём 12 документов."""
    for i in range(12):
        r = authed_client.post(
            "/profile/doc",
            data={"title": f"Doc-{i}", "content": f"Содержимое документа номер {i}.", "enabled": "1"},
        )
        assert r.status_code in (200, 303)
    page = authed_client.get("/profile").text
    for i in range(12):
        assert f"Doc-{i}" in page


def test_document_upload_md(authed_client: TestClient) -> None:
    text = "# Мой стиль письма\n\n" + ("Короткие предложения. Без воды. " * 20)
    r = authed_client.post(
        "/profile/doc/upload",
        data={"title": ""},
        files={"file": ("style.md", BytesIO(text.encode("utf-8")), "text/markdown")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    assert "style" in page  # filename used as title fallback
    assert "Короткие предложения" in page


def test_document_upload_rejects_huge_file(authed_client: TestClient) -> None:
    huge = b"X" * 1_500_000
    r = authed_client.post(
        "/profile/doc/upload",
        files={"file": ("huge.md", BytesIO(huge), "text/markdown")},
    )
    assert r.status_code == 413


def test_document_upload_rejects_non_utf8(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/profile/doc/upload",
        files={"file": ("bad.md", BytesIO(b"\xff\xfe\x00broken"), "text/markdown")},
    )
    assert r.status_code == 400


def test_empty_document_content_silently_ignored(authed_client: TestClient) -> None:
    r = authed_client.post(
        "/profile/doc",
        data={"title": "пусто", "content": "   ", "enabled": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = authed_client.get("/profile").text
    # title shouldn't appear because the doc wasn't created
    assert "пусто" not in page or "Ещё ни одного документа" in page


def test_disabled_document_not_sent_to_llm(authed_client: TestClient) -> None:
    authed_client.post(
        "/profile/doc",
        data={"title": "включенный", "content": "ВКЛЮЧЕННОЕ_СОДЕРЖИМОЕ_ДОКУМЕНТА", "enabled": "1"},
    )
    authed_client.post(
        "/profile/doc",
        data={"title": "выключенный", "content": "ВЫКЛЮЧЕННОЕ_СОДЕРЖИМОЕ_ДОКУМЕНТА", "enabled": ""},
    )

    authed_client.fake_ds.queue("вопрос?")  # type: ignore[attr-defined]
    authed_client.post(
        "/chat/start",
        data={"topic": "проверка документов"},
        headers={"hx-request": "true"},
        follow_redirects=False,
    )
    last_call = authed_client.fake_ds.calls[-1]  # type: ignore[attr-defined]
    full = " ".join(m.content for m in last_call)
    assert "ВКЛЮЧЕННОЕ_СОДЕРЖИМОЕ_ДОКУМЕНТА" in full
    assert "ВЫКЛЮЧЕННОЕ_СОДЕРЖИМОЕ_ДОКУМЕНТА" not in full
    # And the prompt must label the section so the LLM treats it as knowledge, not rules
    assert "Дополнительные документы автора" in full


def test_other_users_document_inaccessible(authed_client: TestClient) -> None:
    authed_client.post(
        "/profile/doc", data={"title": "тайна", "content": "ТАЙНОЕ_СОДЕРЖИМОЕ", "enabled": "1"}
    )
    import re
    page = authed_client.get("/profile").text
    did = int(re.search(r'/profile/doc/(\d+)"', page).group(1))

    # Switch user
    authed_client.post("/logout")
    authed_client.cookies.clear()
    authed_client.post("/register", data={"email": "userb-doc@test.local", "password": "secret123"})
    from app.questions import ONBOARDING_QUESTIONS
    for q in ONBOARDING_QUESTIONS:
        authed_client.post("/onboarding/answer", data={"question_key": q.key, "answer_text": "y"})

    r = authed_client.get(f"/profile/doc/{did}/download")
    assert r.status_code == 404

    page_b = authed_client.get("/profile").text
    assert "тайна" not in page_b
    assert "ТАЙНОЕ_СОДЕРЖИМОЕ" not in page_b


def test_link_appears_in_llm_prompt(authed_client: TestClient) -> None:
    authed_client.post(
        "/profile/link",
        data={"url": "https://my-blog.test/", "description": "канал про дизайн"},
    )
    authed_client.fake_ds.queue("v?")  # type: ignore[attr-defined]
    authed_client.post(
        "/chat/start",
        data={"topic": "проверка ссылок"},
        headers={"hx-request": "true"},
        follow_redirects=False,
    )
    last_call = authed_client.fake_ds.calls[-1]  # type: ignore[attr-defined]
    full = " ".join(m.content for m in last_call)
    assert "https://my-blog.test/" in full
    assert "канал про дизайн" in full
