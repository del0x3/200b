from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.dependencies import get_onboarding_service
from app.models import User
from app.security import current_user
from app.services import OnboardingService
from app.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    user: User = Depends(current_user),
    onboarding: OnboardingService = Depends(get_onboarding_service),
) -> Response:
    progress = onboarding.progress(user)
    if not progress.is_complete:
        return RedirectResponse(url="/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "home.html", {"user": user})
