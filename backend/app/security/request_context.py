"""Cross-cutting request identity and conservative local login throttling."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("x-request-id", "").strip()
        request_id = supplied[:128] if supplied else uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-process login throttle; reverse proxies should add distributed limits.

    The limiter intentionally protects only the login endpoint so ordinary API
    traffic is unaffected. It stores timestamps only; credentials are never kept.
    """

    WINDOW_SECONDS = 60
    MAX_ATTEMPTS = 10
    _attempts: dict[str, deque[float]] = defaultdict(deque)
    _lock = Lock()

    @classmethod
    def _allowed(cls, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - cls.WINDOW_SECONDS
        with cls._lock:
            bucket = cls._attempts[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= cls.MAX_ATTEMPTS:
                return False
            bucket.append(now)
            return True

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path == "/api/auth/login":
            forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
            client = forwarded or (request.client.host if request.client else "unknown")
            if not self._allowed(client):
                return JSONResponse(
                    {"detail": "Zu viele Anmeldeversuche. Bitte kurz warten."},
                    status_code=429,
                    headers={"Retry-After": str(self.WINDOW_SECONDS)},
                )
        return await call_next(request)
