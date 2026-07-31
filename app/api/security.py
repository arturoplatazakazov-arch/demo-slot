"""Access-code gate for the public demo backend.

The frontend on GitHub Pages is world-readable, so anonymous visitors can load
it — but they can't play unless they send the shared access code, which the
server holds as an env var (never committed). This keeps random traffic off the
Railway instance. See app/core/config.py `access_code`.
"""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_access_code(
    x_access_code: str | None = Header(default=None),
) -> None:
    """Reject API calls that lack the configured access code.

    When no code is configured (local dev / tests), the gate is a no-op.
    """
    expected = get_settings().access_code
    if not expected:
        return

    # Constant-time compare so a wrong code can't be brute-forced by timing.
    if x_access_code is None or not secrets.compare_digest(x_access_code, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access code.",
        )
