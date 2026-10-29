# Learning Platform

One FastAPI application and one browser origin for three educational modules:

1. **Game Forge** — learn by playing short browser games.
2. **Data Structure Design Studio** — learn data structures by choosing under constraints.
3. **SWE Quiz** — learn software architecture by making design choices.

## Run locally with Docker

Prerequisite: Docker Desktop.

The three source repositories should be inside this platform folder:

```text
project-platform/game_MCP
project-platform/dsds
project-platform/SWE_QUIZ
```

Start one FastAPI process:

```bash
cd project-platform
docker compose up --build
```

Open the single student origin:

```text
http://localhost:8080
```

All modules are now paths on that same origin:

| Module | URL |
|---|---|
| Platform home | http://localhost:8080/ |
| Game Forge | http://localhost:8080/game-forge/ |
| DSDS | http://localhost:8080/dsds/ |
| SWE Quiz | http://localhost:8080/swe-quiz/ |
| Unified health | http://localhost:8080/api/health |

To stop everything:

```bash
docker compose down
```

## Run without Docker

Use one Python environment and one FastAPI process:

```bash
cd project-platform
python -m pip install -r requirements.txt
PYTHONPATH=dsds uvicorn platform_app.app:app --host 0.0.0.0 --port 8080
```

Then open `http://localhost:8080`.

## Classroom LAN

Run the platform on the teacher PC using `--host 0.0.0.0` / Docker port publishing. Find the teacher PC's private IP (for example `192.168.1.42`). Students on the same Wi-Fi open:

```text
http://192.168.1.42:8080
```

Allow Docker/Python/Node through Windows Firewall on a **Private** network.

## Cloud deployment

Deploy the platform as one Python web service using the root `Dockerfile`, or use the equivalent FastAPI start command:

```bash
uvicorn platform_app.app:app --host 0.0.0.0 --port $PORT
```

The three modules are mounted inside that one service. See `DEPLOY.md`.

## Architecture

```text
Student browser
      │
      ▼
Learning Platform :8080  (one FastAPI / ASGI application)
      ├── /game-forge  (FastAPI + browser games)
      ├── /dsds        (FastAPI + static student UI)
      └── /swe-quiz    (FastAPI + static student UI + JSON scenarios)
```

SWE Quiz's student runtime has been migrated from Express/Prisma/Next to FastAPI and a static browser client. Its original TypeScript/Prisma source remains in the repository as historical/reference material, but it is not part of the unified runtime.

The three modules share the same FastAPI process, origin, route conventions, JSON API style, and deployment unit.

## Verification

```bash
python scripts/verify_platform.py
```

This checks the hub, compose shape, repository files, and service routes where dependencies are available.

## Repositories

- https://github.com/maheshbasavaraj/game_MCP
- https://github.com/maheshbasavaraj/dsds
- https://github.com/maheshbasavaraj/SWE_QUIZ
