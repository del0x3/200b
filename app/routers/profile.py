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
) -> Response:
    if not user.onboarding_complete:
        return RedirectResponse(url="/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"profile_md": user.profile_md, "saved": False},
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
