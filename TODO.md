# Mapa de IA — Implementation Backlog

Weaknesses from the post-refactor review, turned into an implementation plan.
Ordered so each phase de-risks the next: **P0** = safety net + security must-fixes,
**P1** = correctness/scale, **P2** = UX/accessibility, **P3** = pipeline & ops hardening.

## Workflow

One branch per item, merged to `main` via PR:

1. `git checkout main && git pull` — start from the latest `main`.
2. `git checkout -b <branch>` — one branch per TODO (branch names listed below).
3. Implement + document the change; tick the item here and add a changelog entry.
4. Hand off for testing → open a PR to `main`.

**Status legend:** `[ ]` todo · `[~]` in progress · `[x]` done (merged)

---

## P0 — Safety net & security must-fixes

- [x] **1. Backend test harness + smoke tests** — `chore/backend-tests` — **merged (PR #2)**
  8-test pytest smoke suite (auth flow, researchers/graph shape, admin authz) driving the
  app in-process against a throwaway `mapadeia_test` DB with the real migrations.
  `make test` runs it. See `backend/tests/README.md`.

- [x] **2. CI pipeline** — `chore/ci` — **merged (PR #3)**
  `.github/workflows/ci.yml`: runs on PRs targeting `main` + pushes to `main`. Backend
  (pytest on a `postgis` service container) + frontend (build) jobs. Badge in `README.md`,
  docs in `DOCUMENTATION.md` §9.

- [x] **3. Linters / formatters** — `chore/linting` — **merged (PR #4)**
  Backend **ruff** (lint+format, `backend/pyproject.toml`) and frontend **eslint** +
  **prettier** + **svelte-check**, both wired into CI. SvelteKit toolchain pinned to the
  Svelte-4 line; `frontend/package-lock.json` committed. Run frontend tooling without local
  npm via `make fe-verify` (Dockerized). See `DOCUMENTATION.md` §9.

- [x] **4. Enforce `SECRET_KEY`, remove insecure default** — `fix/secret-key` — **merged (PR #5)**
  Removed the insecure default; `Settings.assert_secure_secret_key()` (rejects placeholders +
  `< 32` chars) enforced at API boot in `main.py`; loader unaffected. `tests/test_config.py`.

- [x] **5. Password policy** — `feat/password-policy` — **merged (PR #6)**
  `UserManager.validate_password` rejects passwords `< 10` chars or containing the e-mail
  (HTTP 400 on register/reset); login form `minlength=10` + hint. `tests/test_auth.py`.

- [x] **6. Harden JWT handling** — `feat/jwt-hardening` — **merged (PR #11)**
  **Chosen: short-lived access + refresh tokens** (over the HttpOnly-cookie option). Access
  TTL 15 min, refresh 7 days, **distinct JWT audiences** so neither substitutes for the other.
  Custom `routers/auth.py` (`/auth/jwt/login` → pair, `/auth/jwt/refresh` → new access);
  frontend stores both and auto-refreshes on `401` (`api.js`). Tradeoff documented in
  `DOCUMENTATION.md` §5 (tokens still in `localStorage`; HttpOnly cookie is a possible
  follow-up).
  _Done when:_ refresh tokens + a documented decision exist.
  **Verified here:** login returns a pair; refresh mints a working access token; access≠refresh
  and cross-use is rejected (401). Full suite 24 passed; ruff clean. Frontend: run
  `make fe-verify` (api.js/auth.js changed).

## P1 — Correctness & scale

- [~] **7. Graph endpoint: filter edges in SQL** — `fix/graph-edge-sql` _(implemented — awaiting your testing + PR)_
  `graph.py`: replaced the Python `if source in ids` filter with a `WITH kept AS (…)` CTE over
  the degree-filtered node set, joined against both edge endpoints, so `min_degree` reduces
  DB→app transfer. The CTE mirrors the node query (same `degree >= :min_degree` + `researchers`
  join), so returned edges connect exactly the surviving nodes. Smoke test now asserts the
  invariant. `test_smoke.py::test_graph_shape`.
  _Done when:_ at `min_degree=5` only edges between surviving nodes are returned.

- [ ] **8. Reduce graph payload to the browser** — `perf/graph-payload`
  Keep `min_degree` default ≥ 3; build graphology off the main thread / consider
  pre-thinned tiers. `graph/+page.svelte`.
  _Done when:_ initial `/graph` load ships a bounded payload and the slider doesn't freeze.

- [ ] **9. Fix cache/concurrency mismatch** — `fix/cache-concurrency`
  `cache.py` is per-process but `WEB_CONCURRENCY` defaults to 2. Set `WEB_CONCURRENCY=1`
  as documented default, or add Redis-backed caching.
  _Done when:_ cache behavior is coherent across the configured worker count.

- [ ] **10. Cap the researcher-dump endpoint** — `fix/researcher-dump-cap`
  `map_data.py`: `limit` up to 20,000 allows a full dump. Lower the ceiling or require a
  bbox/filter for large pulls.
  _Done when:_ an unfiltered request can't pull the entire researcher table.

- [ ] **11. Return 422 on bad `bbox`** — `fix/bbox-validation`
  `map_data.py`: replace `except ValueError: pass` with a 422.
  _Done when:_ a malformed `bbox` returns a validation error, not silent full results.

## P2 — Frontend UX & accessibility

- [ ] **12. Guard all `apiGet` calls with error states** — `feat/frontend-error-states`
  Add try/catch → error banner + retry, reset `loading` in `finally`, for `openDetail`,
  `loadInstitutions`, `drillInto` and the list views.
  _Done when:_ a killed backend shows an error message, not a stuck "carregando…".

- [ ] **13. Accessibility pass** — `feat/a11y`
  `aria-label`s on icon-only buttons, real `<label>`s, table captions, drawer focus
  management + Esc-to-close, a skip-link.
  _Done when:_ no critical axe/`svelte-check` violations on `/`, `/login`, `/researchers`.

- [ ] **14. Theming / dark-mode cleanup** — `feat/theming` _(optional)_
  Move hardcoded `#fff`/`#888` to CSS variables.
  _Done when:_ colors come from tokens, not inline hex.

## P3 — Pipeline hardening & ops

- [ ] **15. DB backup strategy** — `ops/db-backups`
  `pg_dump` cron/one-shot service writing to a mounted volume; document restore.
  _Done when:_ a scheduled dump exists and restore is documented in `DEPLOY.md`.

- [ ] **16. Analytics retention purge** — `ops/analytics-retention`
  Enforce `analytics_retention_days` with a purge job.
  _Done when:_ old analytics rows are deleted automatically.

- [ ] **17. De-duplicate `normalize_name`** — `refactor/normalize-name`
  Extract the function copied in `02_clean_data.py` and `06_load_db.py` into a shared module.
  _Done when:_ one canonical `normalize_name`; the drift comment is gone.

- [ ] **18. Regenerate graph upstream** — `fix/graph-artifact`
  Re-run `04_explore.py` with the accent-stripped normalizer so the loader's re-normalization
  workaround is no longer needed.
  _Done when:_ the loader reports 0 re-normalized ids on a fresh artifact.

- [ ] **19. Polite & resilient crawler** — `feat/crawler-resilience`
  `01_crawl_sbc.py`: add a per-request delay and retry/backoff.
  _Done when:_ the crawl respects a delay and survives a transient 5xx.

- [ ] **20. Explicit DDL in the initial migration** — `refactor/explicit-migration` _(optional)_
  Replace `create_all` in `0001_initial_schema.py` with explicit `op.create_table` ops.
  _Done when:_ `alembic revision --autogenerate` produces an empty diff.

- [ ] **21. Frontend dependency audit & bundle size** — `chore/frontend-deps` _(surfaced during #3)_
  `npm install` reports ~10 transitive vulnerabilities (1 critical, 2 high); the main map
  chunk is ~1.6 MB (gzip ~448 kB). Triage `npm audit` (update/override without breaking
  Svelte 4), and code-split/lazy-load the heavy map/graph libs (deck.gl, maplibre, sigma).
  _Done when:_ no critical/high advisories remain and the largest initial chunk is meaningfully
  smaller (e.g. map libs loaded only on their routes).

---

## Changelog

_Newest first. One entry per merged item._

- **2026-09-16** · #6 — Harden JWT handling (`feat/jwt-hardening`, PR #11): short-lived access
  (15 min) + refresh (7 days) tokens with distinct JWT audiences; custom `/auth/jwt/login` +
  `/auth/jwt/refresh`; frontend auto-refreshes on 401. Tradeoff documented in `DOCUMENTATION.md` §5.
- **2026-09-15** · #5 — Account password policy (`feat/password-policy`, PR #6): reject
  passwords `< 10` chars or containing the e-mail (HTTP 400); login form `minlength`.
- **2026-09-15** · #4 — Enforce strong `SECRET_KEY` (`fix/secret-key`, PR #5): removed the
  insecure default; API refuses to boot with an unset/weak/placeholder key; loader unaffected.
- **2026-09-15** · #3 — Linters/formatters (`chore/linting`, PR #4): ruff (backend) +
  eslint/prettier/svelte-check (frontend), wired into CI; SvelteKit toolchain pinned to
  Svelte 4; lockfile committed; Dockerized `make fe-*` targets.
- **2026-09-15** · #2 — GitHub Actions CI (`chore/ci`, PR #3): backend (pytest on a
  `postgis` service container) + frontend (build) jobs on PRs/pushes to `main`; README badge.
- **2026-09-15** · #1 — Backend test harness + smoke tests (`chore/backend-tests`, PR #2):
  8-test pytest suite (auth, researchers/graph shape, admin authz) against a throwaway
  `mapadeia_test` DB with the real migrations; `make test` runner.

<!-- - **YYYY-MM-DD** · #N — <title> (`branch`): <one-line summary>. -->
