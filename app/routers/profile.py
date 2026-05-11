"""Profile routes: portrait MD CRUD, custom prompts CRUD, resource links CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.dependencies import get_profile_service
from app.models import User
from app.security import current_user
from app.services import ProfileService
from app.templating import templates

router = APIRouter()

MAX_UPLOAD_BYTES: int = 1_000_000


@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    if not user.onboarding_complete:
        return RedirectResponse(url="/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "profile_md": user.profile_md,
            "saved": False,
            "prompts": service.list_prompts(user),
            "links": service.list_links(user),
            "documents": service.list_documents(user),
        },
    )


MIN_PROFILE_RATIO: float = 0.5


@router.post("/profile")
def profile_save(
    request: Request,
    profile_md: str = Form(""),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    if not user.onboarding_complete:
        return RedirectResponse(url="/onboarding", status_code=status.HTTP_303_SEE_OTHER)

    new_text: str = profile_md.strip()
    old_text: str = (user.profile_md or "").strip()
    if old_text and (not new_text or len(new_text) < len(old_text) * MIN_PROFILE_RATIO):
        return templates.TemplateResponse(
            request,
            "profile.html",
            {
                "profile_md": user.profile_md,
                "rejected": True,
                "rejected_text": profile_md,
            },
            status_code=409,
        )

    service.save_markdown(user, profile_md)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/profile/download")
def profile_download(user: User = Depends(current_user)) -> Response:
    return Response(
        content=user.profile_md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="profile.md"'},
    )


@router.post("/profile/prompt")
def prompt_create(
    title: str = Form(""),
    content: str = Form(""),
    enabled: str | None = Form(default=None),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    if not content.strip():
        return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)
    service.create_prompt(user, title=title, content=content, enabled=bool(enabled))
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/prompt/upload")
async def prompt_upload(
    file: UploadFile = File(...),
    title: str = Form(""),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    raw: bytes = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        return Response(content=f"Файл больше {MAX_UPLOAD_BYTES // 1000} КБ.", status_code=413)
    try:
        text: str = raw.decode("utf-8")
    except UnicodeDecodeError:
        return Response(content="Файл должен быть в UTF-8.", status_code=400)
    fallback_title = (file.filename or "Промпт").rsplit(".", 1)[0]
    service.create_prompt(
        user, title=(title.strip() or fallback_title), content=text, enabled=True
    )
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/prompt/{prompt_id}")
def prompt_update(
    prompt_id: int,
    title: str = Form(""),
    content: str = Form(""),
    enabled: str | None = Form(default=None),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    service.update_prompt(
        user, prompt_id, title=title, content=content, enabled=bool(enabled)
    )
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/prompt/{prompt_id}/delete")
def prompt_delete(
    prompt_id: int,
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    service.delete_prompt(user, prompt_id)
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/profile/prompt/{prompt_id}/download")
def prompt_download(
    prompt_id: int,
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    from urllib.parse import quote

    for p in service.list_prompts(user):
        if p.id == prompt_id:
            raw_title = (p.title or "prompt").replace('"', '')
            ascii_fallback = raw_title.encode("ascii", "replace").decode("ascii").replace("?", "_")
            quoted = quote(raw_title, safe="")
            disposition = (
                f'attachment; filename="{ascii_fallback}.md"; '
                f"filename*=UTF-8''{quoted}.md"
            )
            return Response(
                content=p.content,
                media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": disposition},
            )
    return Response(content="Не найдено.", status_code=404)


@router.post("/profile/link")
def link_create(
    url: str = Form(""),
    description: str = Form(""),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    if not url.strip():
        return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)
    service.create_link(user, url=url, description=description)
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/link/{link_id}")
def link_update(
    link_id: int,
    url: str = Form(""),
    description: str = Form(""),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    service.update_link(user, link_id, url=url, description=description)
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/link/{link_id}/delete")
def link_delete(
    link_id: int,
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    service.delete_link(user, link_id)
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


# ---- User documents (long-form context md) ----

@router.post("/profile/doc")
def doc_create(
    title: str = Form(""),
    content: str = Form(""),
    enabled: str | None = Form(default=None),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    if not content.strip():
        return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)
    service.create_document(user, title=title, content=content, enabled=bool(enabled))
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/doc/upload")
async def doc_upload(
    file: UploadFile = File(...),
    title: str = Form(""),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    raw: bytes = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        return Response(content=f"Файл больше {MAX_UPLOAD_BYTES // 1000} КБ.", status_code=413)
    try:
        text: str = raw.decode("utf-8")
    except UnicodeDecodeError:
        return Response(content="Файл должен быть в UTF-8.", status_code=400)
    fallback_title = (file.filename or "Документ").rsplit(".", 1)[0]
    service.create_document(
        user, title=(title.strip() or fallback_title), content=text, enabled=True
    )
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/doc/{doc_id}")
def doc_update(
    doc_id: int,
    title: str = Form(""),
    content: str = Form(""),
    enabled: str | None = Form(default=None),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    service.update_document(
        user, doc_id, title=title, content=content, enabled=bool(enabled)
    )
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/doc/{doc_id}/delete")
def doc_delete(
    doc_id: int,
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    service.delete_document(user, doc_id)
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/profile/doc/{doc_id}/download")
def doc_download(
    doc_id: int,
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    from urllib.parse import quote

    d = service.get_document(user, doc_id)
    if d is None:
        return Response(content="Не найдено.", status_code=404)
    raw_title = (d.title or "document").replace('"', "")
    ascii_fallback = raw_title.encode("ascii", "replace").decode("ascii").replace("?", "_")
    quoted = quote(raw_title, safe="")
    disposition = (
        f'attachment; filename="{ascii_fallback}.md"; '
        f"filename*=UTF-8''{quoted}.md"
    )
    return Response(
        content=d.content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )


@router.post("/profile/upload")
async def profile_upload(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    service: ProfileService = Depends(get_profile_service),
) -> Response:
    raw: bytes = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        return Response(
            content=f"Файл больше {MAX_UPLOAD_BYTES // 1000} КБ.",
            status_code=413,
        )
    try:
        text: str = raw.decode("utf-8")
    except UnicodeDecodeError:
        return Response(content="Файл должен быть в UTF-8.", status_code=400)
    service.import_markdown(user, text)
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)
