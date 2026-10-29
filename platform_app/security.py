"""Security middleware: API-key authentication and in-memory rate limiting.

Both are opt-in via configuration. When disabled (the local-dev default for
keys), they pass requests through unchanged so existing tests and local work
keep running. Enable with PLATFORM_API_KEYS / PLATFORM_AUTH_ENABLED for any
shared or public deployment.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from platform_app.config import settings


class _TokenBucket:
    """Thread-safe token bucket. Refill rate configurable per bucket."""

    def __init__(self, capacity: float, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill = refill_per_second
        self._tokens = capacity
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def take(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._updated
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill)
            self._updated = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


class RateLimiter:
    """Per-key rate limiting with a strict budget for the generate endpoint."""

    def __init__(self) -> None:
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()

    def _bucket(self, key: str, capacity: float, refill: float) -> _TokenBucket:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket.capacity != capacity:
                bucket = _TokenBucket(capacity, refill)
                self._buckets[key] = bucket
            return bucket

    def allow(self, key: str, *, strict: bool = False) -> bool:
        if strict:
            return self._bucket(
                key + ":gen",
                settings.generate_rate_capacity,
                settings.generate_rate_refill_per_second,
            ).take()
        return self._bucket(
            key,
            settings.rate_limit_capacity,
            settings.rate_limit_refill_per_second,
        ).take()


limiter = RateLimiter()


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def authenticate(request: Request) -> bool:
    """Return True when the request is allowed through.

    When auth is disabled, everything passes. When enabled, the request must
    carry a valid ``X-API-Key`` header (or ``Authorization: Bearer``).
    """
    if not settings.auth_enabled:
        return True

    header = request.headers.get("x-api-key")
    if not header:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            header = auth[7:].strip()
    return header in settings.api_keys


class SecurityMiddleware:
    """Composes auth + rate limiting into a single ASGI middleware."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # Authentication-guard the MCP endpoint and the generation endpoint.
        protected = path.startswith("/game-forge/mcp") or path == "/game-forge/api/generate"
        if protected and not authenticate(request):
            response = JSONResponse(
                {"detail": "Missing or invalid API key"}, status_code=401
            )
            await response(scope, receive, send)
            return

        # Rate-limit everything; use the strict budget for generation.
        if settings.rate_limit_enabled:
            key = _client_key(request)
            strict = path == "/game-forge/api/generate"
            if not limiter.allow(key, strict=strict):
                response = JSONResponse(
                    {"detail": "Too many requests. Slow down and try again."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
