# Mapa de IA — convenience targets. Run `make help`.
COMPOSE = docker compose
DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml
DB_URL = postgresql+psycopg://mapadeia:mapadeia@localhost:5432/mapadeia
# Dev-only signing key so `make dev-backend` passes the API's SECRET_KEY check.
# NEVER use this in production — set a real SECRET_KEY there (see .env.example).
DEV_SECRET_KEY = dev-secret-key-not-for-production-0123456789
# Python interpreter used for tests. NOTE: make runs recipes in /bin/sh, which
# does NOT load pyenv/conda/venv activation from your interactive shell — so a
# bare `python`/`python3` here often resolves to a system interpreter without
# pip. We therefore default to the project virtualenv at ./.venv (absolute path,
# so it survives the `cd backend` in the recipe). Override when needed, e.g.:
#   make test PYTHON=$$(which python)     # some other interpreter that has pip
# Create the venv once if you don't have it:  python -m venv .venv
PYTHON ?= $(CURDIR)/.venv/bin/python

# Frontend tooling runs inside a Node container (same major as CI), so you don't
# need npm/node installed locally — only Docker. Runs as your host UID/GID so
# files it writes (node_modules, package-lock.json) aren't owned by root, and
# points npm's cache at a writable dir since the container user has no HOME.
FE_IMAGE = node:20-slim
FE_RUN = docker run --rm -u $$(id -u):$$(id -g) \
	-e npm_config_cache=/tmp/.npm -e HOME=/tmp \
	-v $(CURDIR)/frontend:/app -w /app $(FE_IMAGE)

.PHONY: help up load states down clean logs psql superuser \
        dev-db dev-backend dev-load dev-frontend test \
        fe-install fe-lint fe-check fe-format fe-build fe-verify

help:
	@echo "Docker (full stack on http://localhost):"
	@echo "  make up            build + start db, backend, frontend"
	@echo "  make load          load the pipeline data into Postgres (one-shot)"
	@echo "  make superuser EMAIL=you@x   promote a registered user to admin"
	@echo "  make logs          tail all logs"
	@echo "  make down          stop the stack"
	@echo "  make clean         stop + delete volumes (wipes the DB)"
	@echo ""
	@echo "Native dev (hot reload; needs npm + a Python venv):"
	@echo "  make dev-db        start ONLY Postgres (port 5432 exposed)"
	@echo "  make dev-backend   run FastAPI with --reload against dev-db"
	@echo "  make dev-load      load data into dev-db"
	@echo "  make dev-frontend  run Vite dev server (proxies /api to :8000)"
	@echo ""
	@echo "Tests:"
	@echo "  make test          run backend tests (needs dev-db running)"
	@echo ""
	@echo "Frontend lint/format (runs in a Node container — only needs Docker):"
	@echo "  make fe-verify     install + format + lint + check + build (one shot)"
	@echo "  make fe-lint       eslint    · make fe-check  svelte-check"
	@echo "  make fe-format     prettier  · make fe-build  production build"

# ── Docker full stack ──
states:
	@cp -f data/brazil_states.geojson frontend/static/brazil_states.geojson 2>/dev/null \
		&& echo "copied brazil_states.geojson into frontend/static" \
		|| echo "WARN: data/brazil_states.geojson not found (choropleth disabled)"

up: states
	$(COMPOSE) up -d --build db backend frontend
	@echo "Stack starting. Run 'make load' once, then open http://localhost"

load:
	$(COMPOSE) build loader
	$(COMPOSE) run --rm loader

superuser:
	@test -n "$(EMAIL)" || (echo "Usage: make superuser EMAIL=you@example.com" && exit 1)
	$(COMPOSE) exec db psql -U mapadeia -d mapadeia \
		-c "UPDATE \"user\" SET is_superuser = true WHERE email = '$(EMAIL)';"

logs:
	$(COMPOSE) logs -f

psql:
	$(COMPOSE) exec db psql -U mapadeia -d mapadeia

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v

# ── Native dev loop ──
dev-db:
	$(DEV) up -d db
	@echo "Postgres on localhost:5432"

dev-backend:
	cd backend && DATABASE_URL=$(DB_URL) alembic upgrade head && \
		DATABASE_URL=$(DB_URL) SECRET_KEY=$(DEV_SECRET_KEY) uvicorn app.main:app --reload

dev-load: states
	ALLOW_DB_RELOAD=1 DATABASE_URL=$(DB_URL) python files/06_load_db.py

dev-frontend:
	cd frontend && npm install && npm run dev

# ── Tests ──
# Needs a Postgres/PostGIS on localhost:5432 (`make dev-db`). Uses a throwaway
# `mapadeia_test` database that is dropped/recreated each run.
test: dev-db
	@$(PYTHON) -c "import sys; print('Using', sys.executable, sys.version.split()[0])" \
		|| { echo "ERROR: '$(PYTHON)' not found. Try: make test PYTHON=\$$(pyenv which python)"; exit 1; }
	@$(PYTHON) -m pip --version >/dev/null 2>&1 \
		|| { echo "ERROR: '$(PYTHON)' has no pip. Use a venv or pyenv Python:"; \
		     echo "  make test PYTHON=\$$(pyenv which python)"; exit 1; }
	cd backend && $(PYTHON) -m pip install -q -r requirements-dev.txt && $(PYTHON) -m pytest

# ── Frontend lint/format (Dockerized Node; no local npm needed) ──
# `fe-install` populates frontend/node_modules on the host mount, so the other
# targets reuse it. `fe-verify` does everything in one container for convenience.
fe-install:
	$(FE_RUN) npm install

fe-lint:
	$(FE_RUN) npm run lint

fe-check:
	$(FE_RUN) npm run check

fe-format:
	$(FE_RUN) npm run format

fe-build:
	$(FE_RUN) npm run build

fe-verify:
	$(FE_RUN) sh -c "npm install && npm run format && npm run lint && npm run check && npm run build"
