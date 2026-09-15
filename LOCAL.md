# Running Mapa de IA locally (out of prod)

Your machine currently has **no Docker, no npm, and no Postgres** installed, so
you need to install *something* first. Two paths — pick one.

The pipeline data artifacts are already in `./data/`, and a local `.env` is
already generated, so once a database exists the data loads instantly.

---

## Option A — Docker (recommended, one dependency)

Everything (Postgres/PostGIS, the Python backend, the frontend build) runs in
containers. You install only Docker.

```bash
# Arch Linux
sudo pacman -S docker docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # then log out/in so `docker` works without sudo
```

Then, from the repo root:

```bash
make up      # build + start db, backend (runs migrations), frontend
make load    # load the data into Postgres (run once; safe to repeat)
```

Open **http://localhost**.

Make yourself an admin to see the 🛠️ Admin tab:

```bash
# register at http://localhost/login first, then:
make superuser EMAIL=you@inf.ufpel.edu.br
```

Handy: `make logs`, `make psql`, `make down` (stop), `make clean` (stop + wipe DB).

---

## Option B — Native (hot reload for development)

Only Postgres runs in Docker (fastest way to get PostGIS); the backend and
frontend run natively so edits reload instantly.

```bash
# Arch Linux
sudo pacman -S docker docker-compose npm
sudo systemctl enable --now docker

# terminal 1 — database
make dev-db

# terminal 2 — backend (needs the pipeline venv or a fresh one with backend/requirements.txt)
pip install -r backend/requirements.txt
make dev-load      # load data into the dev DB (once)
make dev-backend   # FastAPI on http://localhost:8000  (Swagger at /docs)

# terminal 3 — frontend
make dev-frontend  # Vite on http://localhost:5173 (proxies /api → :8000)
```

Open **http://localhost:5173**. Promote an admin the same way, but against the
exposed dev DB:

```bash
psql postgresql://mapadeia:mapadeia@localhost:5432/mapadeia \
  -c "UPDATE \"user\" SET is_superuser = true WHERE email = 'you@x';"
```

> Native backend needs Python deps that ship wheels for your Python. If your
> system Python is very new (3.14), prefer Option A, or make a 3.12 venv:
> `python3.12 -m venv .venv-backend && .venv-backend/bin/pip install -r backend/requirements.txt`.

---

## Testing checklist (either option)

1. **Data** — the map shows ~8k dots, the graph renders, tables populate.
2. **Auth** — register at `/login`, then you appear in Admin → Usuários.
3. **Tracking** — click **Aceitar** on the consent banner, browse around, then
   Admin → Eventos shows `map_view`, `researcher_view`, `graph_view`, … arriving.
4. **Per-user** — favorite a researcher (☆) while logged in.

If the choropleth (shaded states) is missing, `make states` didn't find the
GeoJSON — check `data/brazil_states.geojson` exists, then rebuild.
