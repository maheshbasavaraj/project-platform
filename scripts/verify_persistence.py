"""Runtime proof that submissions survive a server restart (SQLite persistence).

Spawns the real FastAPI app twice against the same database file and verifies a
SWE Quiz submission written before the restart is still readable after it.
Run: PYTHONPATH=. uv run --with fastapi --with fastmcp --with httpx --with uvicorn python scripts/verify_persistence.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8099
BASE = f"http://127.0.0.1:{PORT}"


def _env(tmp: str, db: str) -> dict[str, str]:
    return dict(
        os.environ,
        PLATFORM_DATA_DIR=tmp,
        PLATFORM_DB_PATH=db,
        PLATFORM_RATE_LIMIT_ENABLED="0",
    )


def _start(env: dict[str, str]):
    return __import__("subprocess").Popen(
        [sys.executable, "-m", "uvicorn", "platform_app.app:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT),
        env=env,
        stdout=__import__("subprocess").DEVNULL,
        stderr=__import__("subprocess").DEVNULL,
    )


def _wait(url: str, tries: int = 50) -> bool:
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.4)
    return False


def _http(path: str, method: str = "GET", data=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def main() -> int:
    import subprocess

    tmp = tempfile.mkdtemp(prefix="hermes-platform-persist-")
    db = os.path.join(tmp, "platform.db")
    env = _env(tmp, db)

    p1 = _start(env)
    assert _wait(BASE + "/api/ready"), "server 1 did not start"
    print("READY", _http("/api/ready"))

    scenario = _http("/swe-quiz/api/scenarios")["scenarios"][0]
    full = _http(f"/swe-quiz/api/scenarios/{scenario['id']}")
    selections = {q["id"]: q["options"][0]["id"] for q in full["questions"]}
    submitted = _http(
        f"/swe-quiz/api/scenarios/{scenario['id']}/submit",
        "POST",
        {"selections": selections},
    )
    submission_id = submitted["submission_id"]
    print("SUBMIT id=%s score=%s" % (submission_id, submitted["score"]))
    print("DB_FILE_EXISTS %s size=%s" % (os.path.exists(db), os.path.getsize(db)))

    p1.terminate()
    p1.wait()
    print("SERVER_1_STOPPED")

    p2 = _start(env)
    assert _wait(BASE + "/api/ready"), "server 2 did not start"
    recovered = _http(f"/swe-quiz/api/submissions/{submission_id}")
    ok = recovered["submission"]["id"] == submission_id
    print("RECOVERED_AFTER_RESTART %s score=%s" % (ok, recovered["submission"]["score"]))

    err = _http("/swe-quiz/api/scenarios/nope")
    print("CODED_ERROR_SHAPE code=%s" % err.get("code"))

    p2.terminate()
    p2.wait()
    print("SERVER_2_STOPPED")
    print("TEMP_DIR", tmp)

    if not ok:
        return 1
    subprocess.run(["rm", "-rf", tmp], shell=True) if os.name != "nt" else None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
