"""FastAPI application factory: lifespan, router wiring, exception handlers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_303_SEE_OTHER

from app.config import settings
from app.db import db
from app.deepseek import DeepSeekClient
from app.routers import auth as auth_router
from app.routers import chat as chat_router
from app.routers import home as home_router
from app.routers import onboarding as onboarding_router
from app.routers import profile as profile_router
from app.security import RedirectToLogin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("200b")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.create_all()
    client = DeepSeekClient(api_key=settings.deepseek_api_key)
    await client.open()
    app.state.deepseek = client
    logger.info("startup: db=%s, deepseek_ready=%s", settings.effective_database_url, bool(settings.deepseek_api_key))
    try:
        yield
    finally:
        await client.close()
        logger.info("shutdown complete")


app: FastAPI = FastAPI(title="200b", lifespan=lifespan)


STATIC_DIR: Path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth_router.router)
app.include_router(onboarding_router.router)
app.include_router(profile_router.router)
app.include_router(home_router.router)
app.include_router(chat_router.router)


@app.exception_handler(RedirectToLogin)
async def _redirect_unauth(_request: Request, _exc: RedirectToLogin) -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)
    from fastapi.exception_handlers import http_exception_handler

    return await http_exception_handler(request, exc)
