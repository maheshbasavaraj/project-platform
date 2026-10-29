"""Learning Hub — one student entry point for the three learning projects."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
STATIC = ROOT / "static"

app = FastAPI(title="Learning Hub", version="0.1.0")

PROJECTS: list[dict[str, Any]] = [
    {
        "id": "game-forge",
        "title": "Game Forge",
        "eyebrow": "Learn by playing",
        "description": "Short browser games that teach one idea at a time through action.",
        "topics": ["Math", "Science", "Problem solving"],
        "url": "/game-forge/",
        "health": "/game-forge/health",
        "color": "violet",
    },
    {
        "id": "dsds",
        "title": "Data Structure Design Studio",
        "eyebrow": "Learn by choosing",
        "description": "Choose the right data structure as problems and constraints change.",
        "topics": ["Arrays", "Lists", "Stacks", "Queues", "Maps", "Heaps"],
        "url": "/dsds/",
        "health": "/dsds/api/health",
        "color": "blue",
    },
    {
        "id": "swe-quiz",
        "title": "SWE Quiz",
        "eyebrow": "Learn by designing",
        "description": "Make software architecture decisions and see the trade-offs behind them.",
        "topics": ["Frontend", "Backend", "Database", "Infrastructure"],
        "url": "/swe-quiz/",
        "health": "/swe-quiz-api/scenarios",
        "color": "amber",
    },
]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "learning-hub"}


@app.get("/api/projects")
def projects(request: Request) -> dict[str, Any]:
    """Return browser-reachable links using the host the student opened."""
    host = request.headers.get("host", "localhost:8080").split(":")[0]
    ports = {"game-forge": 8000, "dsds": 8001, "swe-quiz": 3000}
    visible = []
    for project in PROJECTS:
        item = dict(project)
        item["url"] = f"http://{host}:{ports[project['id']]}"
        visible.append(item)
    return {"projects": visible}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
