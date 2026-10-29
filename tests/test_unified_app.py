"""Integration contract for the single-origin FastAPI learning platform."""

from __future__ import annotations

from fastapi.testclient import TestClient

from platform_app.app import app


client = TestClient(app)


def test_platform_health_lists_three_fastapi_modules():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "learning-platform"
    assert body["modules"] == ["game-forge", "dsds", "swe-quiz"]


def test_homepage_is_single_platform_shell():
    response = client.get("/")
    assert response.status_code == 200
    assert "Learning Platform" in response.text
    assert "/game-forge/" in response.text
    assert "/dsds/" in response.text
    assert "/swe-quiz/" in response.text


def test_dsds_is_mounted_under_same_origin():
    response = client.get("/dsds/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "dsds"


def test_game_forge_is_mounted_under_same_origin():
    response = client.get("/game-forge/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_swe_quiz_fastapi_api_is_mounted_under_same_origin():
    response = client.get("/swe-quiz/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "swe-quiz"


def test_swe_quiz_scenarios_and_submission_flow():
    scenarios = client.get("/swe-quiz/api/scenarios")
    assert scenarios.status_code == 200
    data = scenarios.json()
    assert data["scenarios"]
    scenario = data["scenarios"][0]
    assert scenario["id"]
    detail = client.get(f"/swe-quiz/api/scenarios/{scenario['id']}")
    assert detail.status_code == 200
    playable = detail.json()
    assert playable["questions"]
    assert "score" not in playable["questions"][0]["options"][0]

    question = playable["questions"][0]
    option = question["options"][0]["id"]
    submitted = client.post(
        f"/swe-quiz/api/scenarios/{scenario['id']}/submit",
        json={"selections": {question["id"]: option}},
    )
    assert submitted.status_code == 200
    result = submitted.json()
    assert 0 <= result["score"]
    assert result["submission_id"]
    assert question["id"] in result["feedback"]


def test_swe_quiz_frontend_is_served_by_fastapi():
    response = client.get("/swe-quiz/")
    assert response.status_code == 200
    assert "SWE Quiz" in response.text
    assert "/swe-quiz/static/app.js" in response.text
