"""FastAPI replacement for SWE Quiz's Express/Prisma API and Next UI."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "SWE_QUIZ" / "scenarios_simpler_plus_extras.json"
STATIC = ROOT / "platform_app" / "swe_quiz_static"


def _slug(value: str, index: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or f"option-{index}"
    return base[:45]


def _load_scenarios() -> dict[str, dict[str, Any]]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        questions = []
        for q_index, question in enumerate(item.get("questions", [])):
            options = []
            used: set[str] = set()
            for option_index, option in enumerate(question.get("options", [])):
                option_id = _slug(str(option.get("option", "")), option_index)
                if option_id in used:
                    option_id = f"{option_id}-{option_index}"
                used.add(option_id)
                options.append(
                    {
                        "id": option_id,
                        "label": option.get("option", ""),
                        "rating": option.get("rating", "Poor"),
                        "score": float(option.get("score", 0)),
                        "justification": option.get("justification", ""),
                    }
                )
            questions.append(
                {
                    "id": question.get("id", f"question-{q_index}"),
                    "prompt": question.get("prompt", "Choose an option."),
                    "options": options,
                }
            )
        result[item["id"]] = {
            "id": item["id"],
            "title": item.get("title", "Untitled scenario"),
            "difficulty": item.get("level", "unknown"),
            "description": {
                "summary": item.get("summary", ""),
                "key_priorities": item.get("key_priorities", []),
                "user_stories": item.get("user_stories", []),
                "scale_and_performance": item.get("scale_and_performance", {}),
                "security_and_compliance": item.get("security_and_compliance", {}),
            },
            "questions": questions,
        }
    return result


SCENARIOS = _load_scenarios()
from platform_app.store import store  # noqa: E402

app = FastAPI(title="SWE Quiz", version="0.3.0")


class SubmissionIn(BaseModel):
    selections: dict[str, str] = Field(default_factory=dict)


def _public_option(option: dict[str, Any]) -> dict[str, str]:
    return {"id": option["id"], "label": option["label"]}


def _public_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "difficulty": scenario["difficulty"],
        "description": scenario["description"],
        "questions": [
            {
                "id": question["id"],
                "prompt": question["prompt"],
                "options": [_public_option(option) for option in question["options"]],
            }
            for question in scenario["questions"]
        ],
    }


def _summary(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "difficulty": scenario["difficulty"],
        "summary": scenario["description"]["summary"],
        "question_count": len(scenario["questions"]),
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "swe-quiz"}


@app.get("/api/scenarios")
def list_scenarios() -> dict[str, Any]:
    return {"scenarios": [_summary(s) for s in SCENARIOS.values()]}


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _public_scenario(scenario)


@app.post("/api/scenarios/{scenario_id}/submit")
def submit_scenario(scenario_id: str, body: SubmissionIn) -> dict[str, Any]:
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    score = 0.0
    feedback: dict[str, Any] = {}
    for question in scenario["questions"]:
        selected_id = body.selections.get(question["id"])
        selected = next(
            (option for option in question["options"] if option["id"] == selected_id),
            None,
        )
        if selected is None:
            feedback[question["id"]] = {
                "selected_option_label": "No answer",
                "rating": "Poor",
                "justification": "Choose an option so the trade-off can be evaluated.",
            }
            continue
        score += selected["score"]
        feedback[question["id"]] = {
            "selected_option_label": selected["label"],
            "rating": selected["rating"],
            "justification": selected["justification"],
        }

    submission_id = store.save_submission(
        scenario_id=scenario_id,
        score=score,
        selections=body.selections,
        feedback=feedback,
    )
    return {"submission_id": submission_id, "score": score, "feedback": feedback}


@app.get("/api/submissions/{submission_id}")
def get_submission(submission_id: str) -> dict[str, Any]:
    submission = store.get_submission(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"submission": submission, "scenario": _public_scenario(SCENARIOS[submission["scenario_id"]])}


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="swe-quiz-static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/{full_path:path}")
def frontend_routes(full_path: str) -> FileResponse:
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC / "index.html")
