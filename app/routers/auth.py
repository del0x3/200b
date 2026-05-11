from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from app.dependencies import get_auth_service
from app.schemas import LoginForm, RegisterForm
from app.security import clear_auth_cookie, set_auth_cookie
from app.services import AuthService, EmailTakenError, InvalidCredentialsError
from app.templating import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    try:
        form = LoginForm(email=email, password=password)
    except ValidationError:
        return templates.TemplateResponse(
            request, "login.html", {"error": "Введи корректный email и пароль."}, status_code=400
        )
    try:
        result = service.login(email=form.email, password=form.password)
    except InvalidCredentialsError as exc:
        return templates.TemplateResponse(
            request, "login.html", {"error": str(exc)}, status_code=400
        )
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    set_auth_cookie(response, result.token)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "register.html", {"error": None})


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    try:
        form = RegisterForm(email=email, password=password)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Email должен быть валидным, пароль минимум 4 символа."},
            status_code=400,
        )
    try:
        result = service.register(email=form.email, password=form.password)
    except EmailTakenError as exc:
        return templates.TemplateResponse(
            request, "register.html", {"error": str(exc)}, status_code=400
        )
    response = RedirectResponse(url="/onboarding", status_code=status.HTTP_303_SEE_OTHER)
    set_auth_cookie(response, result.token)
    return response


@router.post("/logout")
def logout() -> Response:
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_auth_cookie(response)
    return response
