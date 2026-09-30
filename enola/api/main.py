"""FastAPI application factory.

This is the one place that: configures CORS from settings, attaches a request id
to every log line, and translates exceptions into the single error shape.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from enola.api.routers import (
    academics,
    approvals,
    auth,
    chat,
    dashboard,
    documents,
    finance,
    health,
    jobs,
    learning,
    log,
    mail,
    memory,
    notifications,
    people,
    projects,
    tasks,
)
from enola.core.config import get_settings
from enola.core.errors import EnolaError, ErrorBody, ErrorResponse
from enola.core.logging import bind_context, configure_logging, get_logger

logger = get_logger(__name__)


def _error_response(status: int, code: str, message: str, details: dict[str, object] | None = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump())


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _origin_rejected(request: Request, allowed_origins: list[str]) -> bool:
    """Cheap CSRF defence for cookie auth: a browser's mutating request must be
    same-origin (its Origin matches the Host it was sent to, which is the case through
    the dev proxy from any device on the LAN) or come from a listed origin. Non-browser
    clients send no Origin header and are unaffected because cookies are not attached
    automatically there."""
    if request.method in _SAFE_METHODS:
        return False
    origin = request.headers.get("origin")
    if origin is None or origin in allowed_origins:
        return False
    host = request.headers.get("host", "")
    origin_host = origin.split("://", 1)[-1]
    return origin_host.lower() != host.lower()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="Enola",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        # Every error, on every route, has this one shape.
        responses={"4XX": {"model": ErrorResponse}, "5XX": {"model": ErrorResponse}},
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        with bind_context(request_id=request_id):
            if _origin_rejected(request, settings.allowed_origins):
                return _error_response(403, "forbidden", "Request origin is not allowed.")
            response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(EnolaError)
    async def handle_enola_error(_: Request, exc: EnolaError) -> JSONResponse:
        if exc.status >= 500:
            logger.error("request_failed", code=exc.code, message=exc.message)
        return _error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(422, "invalid_input", "Request failed validation.", {"errors": exc.errors()})

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", error=str(exc))
        return _error_response(500, "internal_error", "Something went wrong on the server.")

    app.include_router(health.router)
    for module in (auth, people, tasks, jobs, academics, finance, projects, learning, log, memory, approvals, chat, documents, dashboard, notifications, mail):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
