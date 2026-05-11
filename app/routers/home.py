"""Home page: lists prior chat sessions and the new-session form."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.dependencies import get_chat_service, get_onboarding_service
from app.models import User
from app.security import current_user
from app.services import ChatService, OnboardingService
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    user: User = Depends(current_user),
    onboarding: OnboardingService = Depends(get_onboarding_service),
    chat: ChatService = Depends(get_chat_service),
) -> Response:
    progress = onboarding.progress(user)
    if not progress.is_complete:
        return RedirectResponse(url="/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    sessions = chat.list_sessions(user)
    return templates.TemplateResponse(
        request, "home.html", {"user": user, "sessions": sessions}
    )
