"""Single-origin FastAPI application for all three learning projects."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from platform_app.config import settings
from platform_app.observability import (
    configure_logging,
    install_error_handlers,
    log_request,
    logger,
)
from platform_app.security import SecurityMiddleware
from platform_app.store import store

ROOT = Path(__file__).resolve().parents[1]
DSDS_PACKAGE = ROOT / "dsds"
if str(DSDS_PACKAGE) not in sys.path:
    sys.path.insert(0, str(DSDS_PACKAGE))

from dsds.web.app import app as dsds_app  # noqa: E402
from platform_app.game_forge import (  # noqa: E402
    app as game_forge_app,
    mcp_app as game_mcp_app,
)
from platform_app.swe_quiz import app as swe_quiz_app  # noqa: E402

configure_logging()

STATIC = ROOT / "platform_app" / "static"
# FastMCP's Streamable HTTP session manager needs its lifespan driven by the
# top-level ASGI application. Mounted-app lifespans are not enough.
app = FastAPI(
    title="Learning Platform",
    version="1.1.0",
    lifespan=game_mcp_app.lifespan,
)

MODULES = ["game-forge", "dsds", "swe-quiz"]

# ------------------------------------------------------------------ middleware
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(SecurityMiddleware)

# Request logging
@app.middleware("http")
async def _access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log_request(request, response.status_code, (time.perf_counter() - start) * 1000)
    return response

install_error_handlers(app)
# Mounted subapps handle their own HTTPExceptions by default; install the same
# unified error shape on each so every module returns consistent JSON errors.
install_error_handlers(game_forge_app)
install_error_handlers(swe_quiz_app)
install_error_handlers(dsds_app)


# ------------------------------------------------------------------- routes
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "learning-platform", "modules": MODULES}


@app.get("/api/ready")
def readiness() -> dict[str, Any]:
    """Readiness probe: verifies the persistence layer, not just the process."""
    db_ok = store.healthy()
    return {
        "status": "ready" if db_ok else "degraded",
        "database": "ok" if db_ok else "unavailable",
        "modules": MODULES,
        "auth_enabled": settings.auth_enabled,
        "rate_limit_enabled": settings.rate_limit_enabled,
    }


@app.get("/api/modules")
def modules() -> dict[str, Any]:
    return {
        "modules": [
            {"id": "game-forge", "title": "Game Forge", "url": "/game-forge/"},
            {"id": "dsds", "title": "Data Structure Design Studio", "url": "/dsds/"},
            {"id": "swe-quiz", "title": "SWE Quiz", "url": "/swe-quiz/"},
        ]
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="platform-static")

# One ASGI application, one browser origin, three mounted FastAPI modules.
app.mount("/game-forge", game_forge_app)
app.mount("/dsds", dsds_app)
app.mount("/swe-quiz", swe_quiz_app)

logger.info(
    "Learning Platform started (env=%s, auth=%s, rate_limit=%s, db=%s)",
    settings.environment,
    settings.auth_enabled,
    settings.rate_limit_enabled,
    settings.database_path,
)
