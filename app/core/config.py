from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "demo-slot"
    environment: str = "local"
    debug: bool = False

    # Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/dbname
    database_url: str = "postgresql+asyncpg://demo_slot:demo_slot@localhost:5432/demo_slot"

    # Sync URL used by Alembic (asyncpg has no sync driver; psycopg handles migrations).
    database_url_sync: str = "postgresql+psycopg://demo_slot:demo_slot@localhost:5432/demo_slot"

    # Default currency assumed for sessions when the caller does not specify one.
    # NOTE (open question, TZ §14): multi-currency support is not decided yet.
    # Default: single currency per deployment, stored as an ISO 4217 code string
    # on the Session for display purposes only; balances are an internal credit
    # abstraction (TZ §13), no FX conversion. Confirm with product if this is enough.
    default_currency: str = "USD"

    # New Session starting balance (TZ §13: balance is an internal credit
    # abstraction, no deposit/payment flow exists yet).
    default_starting_balance: int = 1_000_000

    # CORS (stage 5): the frontend (front/) is served by a separate static
    # server on another port. Comma-separated explicit origins, plus a regex
    # for "any localhost port" in dev so you don't have to enumerate ports.
    cors_allow_origins: str = ""
    cors_allow_origin_regex: str = r"^http://(localhost|127\.0\.0\.1):\d+$"

    # Shared access code protecting the public demo backend (Railway) from
    # anonymous abuse. When set, every /api/v1 request must carry a matching
    # `X-Access-Code` header. Empty (the default) disables the gate, so local
    # dev and the test suite are unaffected.
    access_code: str = ""

    # Simple per-IP rate limit for the API, requests per minute. 0 disables it
    # (default), keeping local dev and tests unthrottled; set a value in prod.
    rate_limit_per_minute: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
