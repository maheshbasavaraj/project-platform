"""Centralised, environment-driven configuration for the learning platform.

Every knob lives here instead of scattered hardcoded literals across modules.
Values come from environment variables with safe local-dev defaults.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


ROOT = Path(__file__).resolve().parents[1]


class Settings:
    """Runtime configuration. Instantiated once, imported by the app factory."""

    def __init__(self) -> None:
        # Persistence
        self.data_dir = Path(
            os.environ.get("PLATFORM_DATA_DIR", str(ROOT / "data"))
        )
        self.database_path = Path(
            os.environ.get("PLATFORM_DB_PATH", str(self.data_dir / "platform.db"))
        )

        # Authentication
        self.api_keys: set[str] = {
            key.strip()
            for key in os.environ.get("PLATFORM_API_KEYS", "").split(",")
            if key.strip()
        }
        self.auth_enabled = _env_bool("PLATFORM_AUTH_ENABLED", bool(self.api_keys))

        # Rate limiting (per-IP, in-memory token bucket)
        self.rate_limit_enabled = _env_bool("PLATFORM_RATE_LIMIT_ENABLED", True)
        self.rate_limit_capacity = _env_int("PLATFORM_RATE_LIMIT_CAPACITY", 60)
        self.rate_limit_refill_per_second = float(
            os.environ.get("PLATFORM_RATE_LIMIT_REFILL", "1.0")
        )
        # Stricter budget for the expensive generation endpoint.
        self.generate_rate_capacity = _env_int("PLATFORM_GENERATE_RATE_CAPACITY", 5)
        self.generate_rate_refill_per_second = float(
            os.environ.get("PLATFORM_GENERATE_RATE_REFILL", "0.1")
        )

        # Game Forge generation
        self.ollama_url = os.environ.get(
            "OLLAMA_URL", "http://127.0.0.1:11434"
        )
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4:12b")

        # CORS (comma-separated origins; empty = same-origin only)
        self.cors_origins = [
            origin.strip()
            for origin in os.environ.get("PLATFORM_CORS_ORIGINS", "").split(",")
            if origin.strip()
        ]

        # Operational
        self.debug = _env_bool("PLATFORM_DEBUG", False)
        self.environment = os.environ.get("PLATFORM_ENV", "development")

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
