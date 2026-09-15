# Backend tests

End-to-end smoke tests for the FastAPI app: health, the auth flow
(register → login → `/users/me`), a filtered read path (`/api/researchers`,
`/api/graph`), and admin authorization (401 unauth, 403 for a normal user).

## Why they need a real Postgres

The models use PostGIS `geometry`, `CITEXT`, and a migration-owned generated
`tsvector` FTS column, so SQLite can't substitute. The suite runs against a real
Postgres/PostGIS server and applies the actual Alembic migrations, so it also
guards against migration drift.

## Running

```bash
make dev-db          # start Postgres/PostGIS on localhost:5432
make test            # installs dev deps, then runs pytest
```

`make test` calls the interpreter via `$(PYTHON)` (default `python`). Override it
for pyenv/venv setups — e.g. `make test PYTHON=.venv/bin/python` or
`make test PYTHON=python3.12`. Use a Python with prebuilt wheels for the deps
(3.11–3.13 are safest; very new interpreters may lack `pydantic-core`/`psycopg`
wheels and try to build from source).

Or directly:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest
```

The harness drops and recreates a throwaway **`mapadeia_test`** database on each
run (your real `mapadeia` data is never touched). Point it elsewhere with:

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/some_test_db pytest
```

The DB user must be able to `CREATE DATABASE` (the default compose `mapadeia`
superuser can). CI provides this via a PostGIS service container — see
`.github/workflows/ci.yml` (added in TODO item 2).
