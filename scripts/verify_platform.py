"""Focused verification for the single FastAPI learning platform."""
from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DSDS_ROOT = ROOT / "dsds"
if str(DSDS_ROOT) not in sys.path:
    sys.path.insert(0, str(DSDS_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from platform_app.app import app  # noqa: E402


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"{status} {name}{': ' + detail if detail else ''}")
    if not condition:
        raise SystemExit(1)


def main() -> None:
    required = [
        "platform_app/app.py",
        "platform_app/game_forge.py",
        "platform_app/swe_quiz.py",
        "platform_app/static/index.html",
        "platform_app/game_forge_static/index.html",
        "platform_app/swe_quiz_static/index.html",
        "docker-compose.yml",
        "Dockerfile",
        "requirements.txt",
    ]
    for rel in required:
        check("required file", (ROOT / rel).is_file(), rel)

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    check("single compose service", compose.count("    build:") == 1)
    check("single published port", '"8080:8080"' in compose)
    check("no old service ports", all(port not in compose for port in ["8000:8000", "8001:8000", "3000:3000", "3001:3001"]))

    for rel in ["platform_app/app.py", "platform_app/game_forge.py", "platform_app/swe_quiz.py"]:
        py_compile.compile(str(ROOT / rel), doraise=True)
    print("PASS python compilation")

    client = TestClient(app)
    health = client.get("/api/health")
    check("platform health", health.status_code == 200)
    check("three modules", health.json()["modules"] == ["game-forge", "dsds", "swe-quiz"])

    for path, marker in [
        ("/", "Learning Platform"),
        ("/game-forge/", "Game Forge"),
        ("/dsds/", "Data Structure Design Studio"),
        ("/swe-quiz/", "SWE Quiz"),
    ]:
        response = client.get(path)
        check(f"page {path}", response.status_code == 200)
        check(f"page marker {path}", marker in response.text)

    check("Game Forge health", client.get("/game-forge/health").json()["status"] == "ok")
    check("Game Forge catalog", len(client.get("/game-forge/api/games").json()["games"]) >= 1)
    check("DSDS health", client.get("/dsds/api/health").json()["service"] == "dsds")
    check("DSDS static mount", client.get("/dsds/static/app.js").status_code == 200)
    check("SWE Quiz health", client.get("/swe-quiz/api/health").json()["service"] == "swe-quiz")
    check("SWE Quiz static mount", client.get("/swe-quiz/static/app.js").status_code == 200)

    scenarios = client.get("/swe-quiz/api/scenarios").json()["scenarios"]
    check("SWE Quiz scenarios", len(scenarios) > 0)
    scenario = client.get(f"/swe-quiz/api/scenarios/{scenarios[0]['id']}").json()
    check("SWE Quiz playable scenario", len(scenario["questions"]) > 0)
    option = scenario["questions"][0]["options"][0]
    check("SWE Quiz hides answer score", "score" not in option)
    selections = {q["id"]: q["options"][0]["id"] for q in scenario["questions"]}
    submitted = client.post(
        f"/swe-quiz/api/scenarios/{scenario['id']}/submit",
        json={"selections": selections},
    )
    check("SWE Quiz submission", submitted.status_code == 200)
    submission_id = submitted.json()["submission_id"]
    check("SWE Quiz result", client.get(f"/swe-quiz/api/submissions/{submission_id}").status_code == 200)

    print("RESULT unified FastAPI platform verification passed")


if __name__ == "__main__":
    main()
