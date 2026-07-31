"""Tiny in-memory per-IP rate limiter for the API.

Defense-in-depth alongside the access code (app/api/security.py): even a holder
of the code can't hammer the Railway instance into burning its usage limit.
In-memory and per-process, which is fine for the single-instance demo backend.
Disabled when rate_limit_per_minute <= 0 (local dev / tests).
"""

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

_WINDOW_SECONDS = 60
# client IP -> timestamps of recent requests within the window.
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Behind Railway's proxy the real client is the first X-Forwarded-For entry;
    # fall back to the socket peer for direct/local connections.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    from app.core.config import get_settings

    limit = get_settings().rate_limit_per_minute
    # Only throttle the game API; static/docs/health are untouched.
    if limit <= 0 or not request.url.path.startswith("/api/v1"):
        return await call_next(request)

    now = time.monotonic()
    ip = _client_ip(request)
    hits = _hits[ip]
    while hits and now - hits[0] > _WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= limit:
        retry_after = int(_WINDOW_SECONDS - (now - hits[0])) + 1
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Slow down and try again."},
            headers={"Retry-After": str(retry_after)},
        )

    hits.append(now)
    return await call_next(request)
