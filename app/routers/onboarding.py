from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from app.dependencies import get_onboarding_service
from app.models import User
from app.schemas import OnboardingAnswerForm
from app.security import current_user
from app.services import OnboardingService
from app.templating import templates

router = APIRouter()


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(
    request: Request,
    user: User = Depends(current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> Response:
    progress = service.progress(user)
    if progress.is_complete:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "onboarding.html",
        {
            "question": progress.next_question,
            "answered": progress.answered,
            "total": progress.total,
        },
    )


@router.post("/onboarding/answer", response_class=HTMLResponse)
def submit_answer(
    request: Request,
    question_key: str = Form(...),
    answer_text: str = Form(...),
    user: User = Depends(current_user),
    service: OnboardingService = Depends(get_onboarding_service),
) -> Response:
    try:
        form = OnboardingAnswerForm(question_key=question_key, answer_text=answer_text)
    except ValidationError:
        return Response(content="Ответ не может быть пустым.", status_code=400)
    progress = service.save_answer(
        user=user, question_key=form.question_key, answer_text=form.answer_text
    )
    if progress.is_complete:
        response = Response(status_code=204)
        response.headers["HX-Redirect"] = "/"
        return response
    return templates.TemplateResponse(
        request,
        "partials/onboarding_q.html",
        {
            "question": progress.next_question,
            "answered": progress.answered,
            "total": progress.total,
        },
    )
