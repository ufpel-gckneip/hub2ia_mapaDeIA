# Mapa de IA — convenience targets. Run `make help`.
COMPOSE = docker compose
DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml
DB_URL = postgresql+psycopg://mapadeia:mapadeia@localhost:5432/mapadeia

.PHONY: help up load states down clean logs psql superuser \
        dev-db dev-backend dev-load dev-frontend

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
		DATABASE_URL=$(DB_URL) uvicorn app.main:app --reload

dev-load: states
	ALLOW_DB_RELOAD=1 DATABASE_URL=$(DB_URL) python files/06_load_db.py

dev-frontend:
	cd frontend && npm install && npm run dev
