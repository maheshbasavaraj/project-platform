# Deploying the Learning Platform

## Local or classroom deployment

Run Docker Desktop on one teacher PC:

```bash
docker compose up --build
```

The single student URL is:

```text
http://TEACHER-PC-LAN-IP:8080
```

Example: `http://192.168.1.42:8080`.

The teacher PC must stay on. Windows Firewall must allow port `8080` on a Private network.

## Public deployment

Deploy **one** Python web service from the repository root.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn platform_app.app:app --host 0.0.0.0 --port $PORT
```

If the host supports Docker, use the root `Dockerfile` instead. It runs the same command.

Health check:

```text
/api/health
```

The public routes are:

```text
/
/game-forge/
/dsds/
/swe-quiz/
/api/health
```

## Architecture

All student-facing functionality is in one FastAPI/ASGI process:

```text
learning-platform.example.com/
├── /game-forge  → FastAPI module + browser games
├── /dsds        → existing DSDS FastAPI app + static UI
└── /swe-quiz    → migrated FastAPI API + static UI
```

SWE Quiz's old Express/Prisma/Next implementation remains under `SWE_QUIZ/` as source/reference material, but it is not started by the unified platform. The active runtime uses the JSON scenario file and in-memory submissions.

## Persistence note

SWE Quiz submissions currently live in process memory. They disappear when the service restarts. For real classroom history, add a shared SQLite/Postgres persistence layer behind a common repository interface before production use.

Game Forge MCP is mounted inside the unified FastAPI app at `/game-forge/mcp/`. The Game Forge page exposes FastAPI controls that call the real MCP tools (`build_game_prompt`, `save_game`, `review_checklist`, `list_games`). Game generation uses local Ollama with `gemma4:12b`; start Ollama and pull that model before using **Generate game**. Protect `/game-forge/mcp/` with authentication before public anonymous deployment.

## Verification

Use the direct FastAPI contract check when `pytest` is unavailable:

```bash
PYTHONPATH= "/c/Users/MAHESH/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" -c "from fastapi.testclient import TestClient; from platform_app.app import app; print(TestClient(app).get('/api/health').json())"
```
