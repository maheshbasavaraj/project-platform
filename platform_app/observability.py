"""Structured logging, unified error responses, and observability helpers."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from platform_app.config import settings


def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


logger = logging.getLogger("learning-platform")


def _payload(
    status: int,
    message: str,
    *,
    code: str = "error",
    detail: Any = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": status,
        "code": code,
        "message": message,
    }
    if detail is not None:
        body["detail"] = detail
    return body


def install_error_handlers(app: FastAPI) -> None:
    """Give every error a consistent, machine-readable JSON shape."""

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            _payload(exc.status_code, str(exc.detail), code="http_error", detail=exc.detail),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            _payload(422, "Request validation failed", code="validation_error", detail=exc.errors()),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s", request.url.path, exc_info=exc)
        if settings.debug:
            return JSONResponse(
                _payload(500, str(exc), code="internal_error", detail=str(exc)),
                status_code=500,
            )
        return JSONResponse(
            _payload(500, "Internal server error", code="internal_error"),
            status_code=500,
        )


def log_request(request: Request, status: int, duration_ms: float) -> None:
    logger.info(
        '%s %s -> %s (%.1fms)',
        request.method,
        request.url.path,
        status,
        duration_ms,
    )
