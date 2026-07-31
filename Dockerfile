FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /srv/app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/start.sh ./scripts/start.sh

RUN uv pip install --system --no-cache . \
    && chmod +x ./scripts/start.sh

EXPOSE 8000

# Runs migrations, then serves on $PORT (Railway) or 8000. docker-compose
# overrides this with its own command, so local compose is unaffected.
CMD ["./scripts/start.sh"]
