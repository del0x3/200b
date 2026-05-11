from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from app.dependencies import get_chat_service
from app.models import Feedback, User
from app.schemas import ChatAnswerForm, ChatFeedbackForm, ChatPivotForm, ChatStartForm
from app.security import current_user
from app.services import ChatService
from app.templating import templates

router = APIRouter(prefix="/chat")


def _render_question(request: Request, session_id: int, question_id: int, text: str) -> Response:
    return templates.TemplateResponse(
        request,
        "partials/question.html",
        {
            "session_id": session_id,
            "question_id": question_id,
            "question_text": text,
        },
    )


@router.get("/session/{session_id}", response_class=HTMLResponse)
def session_page(
    request: Request,
    session_id: int,
    user: User = Depends(current_user),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    view = service.get_session_view(user=user, session_id=session_id)
    if view is None:
        return Response(content="Сессия не найдена.", status_code=404)
    return templates.TemplateResponse(
        request,
        "session.html",
        {"view": view},
    )


@router.post("/continue", response_class=HTMLResponse)
async def continue_session(
    request: Request,
    session_id: int = Form(...),
    user: User = Depends(current_user),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    try:
        current = await service.continue_session(user=user, session_id=session_id)
    except ValueError:
        return Response(content="Сессия не найдена.", status_code=404)
    return _render_question(request, current.session_id, current.question.id, current.question.question_text)


@router.post("/start", response_class=HTMLResponse)
async def start(
    request: Request,
    topic: str = Form(...),
    user: User = Depends(current_user),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    try:
        form = ChatStartForm(topic=topic)
    except ValidationError:
        return Response(content="Тема не может быть пустой.", status_code=400)
    current = await service.start(user=user, topic=form.topic)
    return _render_question(request, current.session_id, current.question.id, current.question.question_text)


@router.post("/feedback", response_class=HTMLResponse)
async def feedback(
    request: Request,
    question_id: int = Form(...),
    feedback: str = Form(...),
    user: User = Depends(current_user),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    try:
        form = ChatFeedbackForm(question_id=question_id, feedback=feedback)
    except ValidationError:
        return Response(content="Некорректные данные.", status_code=400)
    try:
        fb_enum = Feedback(form.feedback)
    except ValueError:
        return Response(content="Некорректный тип реакции.", status_code=400)
    try:
        current = await service.feedback_and_next(
            user=user, question_id=form.question_id, feedback=fb_enum
        )
    except ValueError:
        return Response(content="Вопрос не найден.", status_code=404)
    return _render_question(request, current.session_id, current.question.id, current.question.question_text)


@router.post("/answer", response_class=HTMLResponse)
async def answer(
    request: Request,
    question_id: int = Form(...),
    answer_text: str = Form(...),
    user: User = Depends(current_user),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    try:
        form = ChatAnswerForm(question_id=question_id, answer_text=answer_text.strip())
    except ValidationError:
        return Response(content="Ответ не может быть пустым.", status_code=400)
    try:
        current = await service.answer_and_next(
            user=user, question_id=form.question_id, answer_text=form.answer_text
        )
    except ValueError:
        return Response(content="Вопрос не найден.", status_code=404)
    return _render_question(request, current.session_id, current.question.id, current.question.question_text)


@router.post("/pivot", response_class=HTMLResponse)
async def pivot(
    request: Request,
    session_id: int = Form(...),
    user: User = Depends(current_user),
    service: ChatService = Depends(get_chat_service),
) -> Response:
    try:
        form = ChatPivotForm(session_id=session_id)
    except ValidationError:
        return Response(content="Некорректные данные.", status_code=400)
    try:
        current = await service.pivot(user=user, session_id=form.session_id)
    except ValueError:
        return Response(content="Сессия не найдена.", status_code=404)
    return _render_question(request, current.session_id, current.question.id, current.question.question_text)
