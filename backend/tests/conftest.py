"""Test harness for the Mapa de IA backend.

Tests run against a **real Postgres/PostGIS** instance (the models use PostGIS
geometry, CITEXT and a migration-owned generated FTS column, so SQLite can't
stand in). The session fixture drops and recreates a throwaway database, applies
the real Alembic migrations, and points the app engine at it.

Point the harness at any Postgres via `TEST_DATABASE_URL` (defaults to a local
`mapadeia_test` on the compose dev DB). Bring one up with `make dev-db` or
`docker compose up -d db`, then run `pytest` from `backend/`.
"""

import os
import sys
from pathlib import Path

# Must be set BEFORE importing anything from `app` (settings + engine are built
# at import time and read DATABASE_URL). A real env var wins over any .env file.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://mapadeia:mapadeia@localhost:5432/mapadeia_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Use a strong signing key in tests. This keeps the suite off the insecure
# default and forward-compatible with TODO #4 (which rejects weak keys at boot).
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-0123456789abcdef")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))  # so `import app` works regardless of cwd

import psycopg
import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url

from alembic import command


def _admin_dsn(url) -> str:
    """libpq DSN to the maintenance `postgres` DB on the same server."""
    port = url.port or 5432
    return f"postgresql://{url.username}:{url.password}@{url.host}:{port}/postgres"


def _recreate_database(url) -> None:
    dbname = url.database
    with psycopg.connect(_admin_dsn(url), autocommit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (dbname,),
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        cur.execute(f'CREATE DATABASE "{dbname}"')


@pytest.fixture(scope="session")
def _database():
    """Drop/recreate the test DB and run migrations once per test session."""
    url = make_url(TEST_DATABASE_URL)
    _recreate_database(url)

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture
async def client(_database):
    """In-process ASGI client; the app engine already targets the test DB."""
    from app.cache import clear as clear_cache
    from app.db import engine
    from app.main import app

    clear_cache()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


@pytest_asyncio.fixture
async def registered_user(client):
    """Register + log in a normal (non-superuser) user; returns headers + creds."""
    creds = {"email": "tester@example.com", "password": "Str0ng-Passw0rd!"}
    r = await client.post("/auth/register", json=creds)
    assert r.status_code in (200, 201), r.text
    r = await client.post(
        "/auth/jwt/login",
        data={"username": creds["email"], "password": creds["password"]},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"creds": creds, "headers": {"Authorization": f"Bearer {token}"}}
