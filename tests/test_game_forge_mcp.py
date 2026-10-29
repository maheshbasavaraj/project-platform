"""Behavior contract for Game Forge's MCP-backed FastAPI surface."""

from __future__ import annotations

from fastapi.testclient import TestClient

from platform_app.app import app


def test_game_forge_page_exposes_mcp_generation_controls():
    with TestClient(app) as client:
        response = client.get("/game-forge/")
    assert response.status_code == 200
    assert 'name="topic"' in response.text
    assert 'name="audience"' in response.text
    assert 'name="session_minutes"' in response.text
    assert "/game-forge/mcp/" in response.text
    assert "Generate game" in response.text


def test_game_forge_mcp_endpoint_is_mounted_and_lists_tools():
    with TestClient(app) as client:
        response = client.post(
            "/game-forge/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "platform-test", "version": "0"},
                },
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
    assert response.status_code == 200
    assert '"result"' in response.text
    assert "game-forge" in response.text


def test_prompt_endpoint_calls_mcp_build_game_prompt():
    with TestClient(app) as client:
        response = client.post(
            "/game-forge/api/prompt",
            json={"topic": "volcanoes", "audience": "ages 10-12", "session_minutes": 8},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "volcanoes"
    assert "volcanoes" in body["prompt"]
    assert "ages 10-12" in body["prompt"]
    assert body["mcp_tool"] == "build_game_prompt"


def test_generate_endpoint_reports_missing_ollama_quickly():
    with TestClient(app) as client:
        response = client.post(
            "/game-forge/api/generate",
            json={
                "topic": "mcp-browser-test",
                "audience": "ages 8-12",
                "session_minutes": 5,
            },
        )
    assert response.status_code in {200, 503}
    if response.status_code == 503:
        assert "Ollama" in response.json()["detail"]
