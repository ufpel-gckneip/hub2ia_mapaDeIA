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

- [~] **3. Linters / formatters** — `chore/linting` _(implemented — backend verified; frontend needs your `npm install`)_
  Backend **ruff** (lint+format) config in `backend/pyproject.toml`, wired into CI. Frontend
  **eslint** (flat config) + **prettier** + **svelte-check**, scripts in `package.json`,
  wired into CI (`npm ci` → lint → check → build).
  _Done when:_ `ruff check .` and `npm run lint` pass.
  **Backend — verified here:** `ruff check` clean, `ruff format` stable, 8 tests still green.
  **Frontend — verified green** via `make fe-verify` (runs in `node:20-slim`; only Docker
  needed): eslint 0 errors, svelte-check 0 errors (4 a11y/unused-CSS **warnings** deferred
  to #13), build OK. `frontend/package-lock.json` committed for reproducible `npm ci`.
  Individual steps: `make fe-lint` / `fe-check` / `fe-format` / `fe-build`.

- [ ] **4. Enforce `SECRET_KEY`, remove insecure default** — `fix/secret-key`
  `config.py`: drop the `"CHANGE-ME-IN-PRODUCTION"` default; assert a strong key at startup.
  _Done when:_ the app refuses to boot without a strong key.

- [ ] **5. Password policy** — `feat/password-policy`
  `users.py`: override `UserManager.validate_password` (min length ≥ 10, reject
  email-in-password). Add `minlength` on the login form.
  _Done when:_ a weak password is rejected server-side (422).

- [ ] **6. Harden JWT handling** — `feat/jwt-hardening`
  Move token to an `HttpOnly` cookie **or** add short-lived access + refresh tokens with
  a documented tradeoff. `api.js`, `users.py`.
  _Done when:_ cookies are in place, or refresh tokens + a documented decision exist.

## P1 — Correctness & scale

- [ ] **7. Graph endpoint: filter edges in SQL** — `fix/graph-edge-sql`
  `graph.py`: replace the Python `if source in ids` filter with a SQL join/`IN` on the
  degree-filtered node set so `min_degree` reduces DB→app transfer.
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

---

## Changelog

_Newest first. One entry per merged item._

- **2026-09-15** · #2 — GitHub Actions CI (`chore/ci`, PR #3): backend (pytest on a
  `postgis` service container) + frontend (build) jobs on PRs/pushes to `main`; README badge.
- **2026-09-15** · #1 — Backend test harness + smoke tests (`chore/backend-tests`, PR #2):
  8-test pytest suite (auth, researchers/graph shape, admin authz) against a throwaway
  `mapadeia_test` DB with the real migrations; `make test` runner.

<!-- - **YYYY-MM-DD** · #N — <title> (`branch`): <one-line summary>. -->
