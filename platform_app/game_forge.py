"""Game Forge FastAPI surface backed by the repository's real MCP server.

Student flow:
    FastAPI page -> build_game_prompt MCP tool -> Ollama -> save_game MCP tool
    -> playable HTML under the same /game-forge origin.

The original ``game_MCP/app.py`` remains the source of truth for MCP tools,
resource, prompt, and generated-game storage. This module mounts that MCP app
and exposes a student-friendly FastAPI form around it.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from platform_app.store import store

ROOT = Path(__file__).resolve().parents[1]
MCP_SOURCE = ROOT / "game_MCP" / "app.py"
GAME_ORCHESTRATOR = ROOT / "game_MCP" / "game.py"
STATIC = ROOT / "platform_app" / "game_forge_static"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Import actual MCP definitions. No duplicate tool implementation here.
_mcp_server = _load_module("game_forge_mcp_server", MCP_SOURCE)
_mcp_orchestrator = _load_module("game_forge_mcp_orchestrator", GAME_ORCHESTRATOR)
mcp = _mcp_server.mcp
mcp_app = _mcp_server.mcp_app
GAMES = _mcp_server.GAMES_DIR
build_game_prompt = _mcp_server.build_game_prompt

app = FastAPI(title="Game Forge", version="1.0.0")


class GamePromptIn(BaseModel):
    topic: str = Field(..., min_length=2, max_length=120)
    audience: str = Field(default="ages 8-12", min_length=2, max_length=80)
    session_minutes: int = Field(default=7, ge=3, le=60)


class GenerateGameIn(GamePromptIn):
    name: str | None = Field(default=None, max_length=120)
    checklist: bool = False


async def _call_mcp(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call real FastMCP tool in-process through MCP protocol client."""
    from fastmcp import Client

    async with Client(mcp) as client:
        result = await client.call_tool(tool_name, arguments)
    if getattr(result, "data", None) is not None:
        return result.data
    content = getattr(result, "content", []) or []
    if not content:
        return None
    text = getattr(content[0], "text", None)
    if text is None:
        return content[0]
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return text


def _normalise_game_url(value: str) -> str:
    if value.startswith("/game-forge/"):
        return value
    return "/game-forge/" + value.lstrip("/")


async def _generate_html(system_prompt: str, user_prompt: str) -> str:
    # Fail fast when local Ollama is not running. The MCP prompt/save path
    # remains usable, while the browser gets an actionable error instead of
    # waiting for the orchestrator's 600-second network timeout.
    try:
        with urllib.request.urlopen(
            _mcp_orchestrator.OLLAMA_URL + "/api/tags", timeout=2
        ) as response:
            tags = json.loads(response.read().decode("utf-8"))
        model_names = {str(model.get("name", "")) for model in tags.get("models", [])}
        configured = _mcp_orchestrator.OLLAMA_MODEL
        if model_names and configured not in model_names:
            raise HTTPException(
                status_code=503,
                detail=f"Ollama model {configured!r} not found. Pull it before generating.",
            )
    except HTTPException:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama is not reachable. Start Ollama and pull the configured "
                f"model ({_mcp_orchestrator.OLLAMA_MODEL}). Error: {exc}"
            ),
        ) from exc
    try:
        return await asyncio.to_thread(
            _mcp_orchestrator.generate_with_ollama,
            system_prompt,
            user_prompt,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama generation unavailable. Start Ollama and pull the configured "
                f"model ({_mcp_orchestrator.OLLAMA_MODEL}). Original error: {exc}"
            ),
        ) from exc


def _extract_html(raw: str) -> str:
    try:
        return _mcp_orchestrator.extract_html(raw)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "game-forge",
        "mcp": "mounted",
        "games": len(list(GAMES.glob("*.html"))),
    }


@app.get("/api/mcp/tools")
async def mcp_tools() -> dict[str, Any]:
    from fastmcp import Client

    async with Client(mcp) as client:
        tools = await client.list_tools()
    return {"tools": [tool.name for tool in tools]}


@app.get("/api/games")
async def list_games() -> dict[str, Any]:
    games = await _call_mcp("list_games", {})
    return {"games": games or []}


@app.get("/api/prompt")
async def preview_prompt_get(topic: str = "equivalent fractions", audience: str = "ages 8-12", session_minutes: int = 7) -> dict[str, Any]:
    return await _preview_prompt(GamePromptIn(topic=topic, audience=audience, session_minutes=session_minutes))


@app.post("/api/prompt")
async def preview_prompt(body: GamePromptIn) -> dict[str, Any]:
    return await _preview_prompt(body)


async def _preview_prompt(body: GamePromptIn) -> dict[str, Any]:
    prompt = await _call_mcp(
        "build_game_prompt",
        {
            "topic": body.topic,
            "audience": body.audience,
            "session_minutes": body.session_minutes,
        },
    )
    return {
        "topic": body.topic,
        "audience": body.audience,
        "session_minutes": body.session_minutes,
        "prompt": prompt,
        "mcp_tool": "build_game_prompt",
    }


@app.post("/api/generate")
async def generate_game(body: GenerateGameIn) -> dict[str, Any]:
    """Generate through Ollama, save through actual MCP, return playable URL."""
    prompt_data = await _preview_prompt(body)
    user_prompt = (
        f"Build complete single-file HTML game for: {body.topic}. "
        f"Audience: {body.audience}. Session: ~{body.session_minutes} minutes. "
        "Output ONLY raw HTML document; no prose, markdown fences, or commentary."
    )
    raw = await _generate_html(str(prompt_data["prompt"]), user_prompt)
    html = _extract_html(raw)

    saved = await _call_mcp(
        "save_game",
        {"name": body.name or body.topic, "html": html},
    )
    if not isinstance(saved, dict) or "url" not in saved:
        raise HTTPException(status_code=502, detail="MCP save_game returned unexpected data")

    # Durable registry entry so generated games survive restarts and can be
    # managed (listed/deleted) independently of the raw files on disk.
    html_path = str(GAMES / saved.get("file", Path(saved["url"]).name))
    store.register_game(
        name=saved.get("file", body.name or body.topic),
        html_path=html_path,
        bytes_size=int(saved.get("bytes", len(html))),
        topic=body.topic,
        audience=body.audience,
    )

    result: dict[str, Any] = {
        "topic": body.topic,
        "mcp_tools": ["build_game_prompt", "save_game"],
        "game": {**saved, "url": _normalise_game_url(saved["url"])},
    }

    if body.checklist:
        checklist = await _call_mcp("review_checklist", {})
        result["checklist"] = checklist
        result["checklist_tool"] = "review_checklist"

    return result


@app.get("/games/{filename}")
def play_game(filename: str) -> FileResponse:
    safe = Path(filename).name
    path = GAMES / safe
    if path.suffix != ".html" or not path.is_file():
        raise HTTPException(status_code=404, detail="Game not found")
    return FileResponse(path, media_type="text/html")


@app.delete("/api/games/{game_id}")
def delete_game(game_id: str) -> dict[str, Any]:
    """Remove a generated game from the registry and its file from disk."""
    games = store.list_games()
    target = next((g for g in games if g["id"] == game_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Game not found")
    path = Path(target["html_path"])
    if path.is_file():
        path.unlink()
    store.delete_game(game_id)
    return {"deleted": game_id, "name": target["name"]}


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="game-forge-static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


# Actual FastMCP Streamable HTTP endpoint: /game-forge/mcp/ after parent mount.
app.mount("/mcp", mcp_app)
