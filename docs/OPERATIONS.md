# Operations

## Local development

Prerequisite: Docker Desktop running Linux containers, with Compose v2 or newer. Keep host ports 3000, 8000 and 55432 free. No host Node/Python installation is required for the normal browser runtime. This is a loopback-only development environment, not a public deployment or an authentication boundary.

From the repository root:

```bash
docker compose up --build
```

For background operation and readiness checks:

```bash
docker compose up --build -d --wait
docker compose ps
docker compose logs -f web api db
```

| Endpoint             | Address                      |
| -------------------- | ---------------------------- |
| Browser              | http://localhost:3000        |
| API                  | http://localhost:8000        |
| API health           | http://localhost:8000/health |
| PostgreSQL from host | 127.0.0.1:55432              |

The browser uses same-origin `/api/*`; a Next.js route handler proxies to server-side `API_URL=http://api:8000` at request time. API uses the Compose `db:5432` connection to `investment_tracker`. The unrelated host PostgreSQL port 5432 is not used. Existing SQLAlchemy runtime pooling remains unchanged.

Startup order is healthy DB → `alembic upgrade head` → Uvicorn → healthy API → Next.js. Migration failure prevents API startup. Inspect `docker compose logs api` before retrying; never bypass a failed migration to serve requests.

### Source changes and rebuilds

API source/migrations are bind-mounted; Uvicorn watches source using polling. Web source is bind-mounted; Next.js uses its built-in Webpack dev server with polling for Windows Docker Desktop. Source edits need no image rebuild. Host `node_modules`, `.next` and Python `.venv` do not become container dependencies: Web uses dedicated named volumes and API dependencies stay inside the image.

After dependency, Dockerfile or runtime configuration changes:

```bash
docker compose up --build -d --wait
```

Dependencies install using `uv sync --locked --no-dev` and pnpm 11.25.0 `install --frozen-lockfile`. Web also re-syncs its dependency volume on startup. Host checks and container Web should not run simultaneously against the same source tree because Next.js can generate shared type files; stop Web before host build/typecheck.

### Stop and persistence

```bash
docker compose down
```

Normal down removes containers/network, not named volumes. The existing `postgres_data` volume, Compose project identity and PostgreSQL 18.6 data path are preserved. Restart with the same repository/project name to reuse data. Avoid changing the Compose project name for normal operation.

`docker compose restart` restarts containers and retains records; it does not apply changed Compose settings. Use `up --build` for those changes.

**Destructive reset warning:** `docker compose down -v` deletes named volumes, including all normal local financial records. It is not a normal stop command. Do not use it without an intentional data reset and an independently verified backup. This local pass does not establish backup/restore or production real-data readiness.

## Isolated tests

Normal browser runtime always uses `investment_tracker`. Backend tests and Playwright always use disposable `investment_tracker_test`. Never point E2E at `http://localhost:3000` while it proxies the normal Compose API.

Use the existing host-based test workflow; no test URL guard is relaxed for the Docker network. Start only the database if the full runtime is stopped:

```bash
docker compose up -d --wait db
```

With Python 3.14 and uv on the host, from `apps/api`, ensure the shell has no exported `DATABASE_URL`/`TEST_DATABASE_URL` overrides, then:

```bash
uv sync --locked
uv run --env-file .env.example alembic upgrade head
uv run --env-file .env.example pytest
uv run --env-file .env.example alembic check
```

The committed example uses host `127.0.0.1:55432`, development `investment_tracker`, and disposable `investment_tracker_test`. Pytest recreates only the test database. Existing guards reject non-local servers, unexpected database names, query overrides and mismatched development/test server coordinates. CI retains its isolated service/credentials unchanged.

After pytest completes, for E2E start a separate host API from `apps/api`. Set `DATABASE_URL` in that shell to the disposable local URL below, then run the test API on a separate port:

```text
postgresql+psycopg://investment_tracker:local_development_only@127.0.0.1:55432/investment_tracker_test
```

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

From `apps/web`, with Node 24/pnpm 11.25.0 on the host and no exported `WEB_PORT`/`API_URL` overrides, run:

```bash
pnpm install --frozen-lockfile
pnpm exec playwright install chromium
pnpm test:e2e
```

Playwright defaults to its own Web server at 3001 and explicitly passes `API_URL=http://127.0.0.1:8001` to it. Existing Web servers are never reused. If the isolated API is absent, tests fail without falling back to normal Docker Web/API at 3000/8000. Explicit endpoint overrides must retain test database isolation. Do not run pytest concurrently with E2E, as it recreates the test database. Stop the test API/Web processes afterwards. The next pytest run clears synthetic test records. See README for the remaining host quality checks.

## Cloud Runtime v0.1 — synthetic acceptance passed

One Vercel project deploys Web (`apps/web`, Next.js/Node 24) and API (`apps/api`, FastAPI/Python 3.14) Services. Public routing exposes Web only. Browser `/api/*` requests use a server-side route handler and the runtime-only `API_URL` service binding to that deployment's private API. Missing cloud binding fails closed; there is no cloud localhost fallback. Functions use the project Frankfurt `fra1` region; build-machine location is independent.

### Environment mapping

| Vercel target | Runtime database | Policy |
| --- | --- | --- |
| Preview | Neon Investment Tracker Staging, `calm-credit-61662826`, shared main | Synthetic/non-production only |
| Production | Neon Investment Tracker Production, `young-unit-23492458`, main | Separate project; no real data until readiness gates pass |
| Development | No cloud DATABASE_URL | Use local Docker |

Both projects use PostgreSQL 18 in `aws-eu-central-1`. `DATABASE_URL` is stored as a separate Vercel Secret per target, never public/client-side. No Production credentials in Preview and no Staging credentials in Production. Shared Staging is not isolated per Preview: concurrent Preview writes can affect each other. Never use Production as a Preview parent. The rejected managed Neon integration was disconnected and uninstalled; mapping is manual, with no dynamic branch creation or integration-owned env variables. `.vercelignore` explicitly excludes operator secrets, backups and local temporary/cache files from CLI uploads; Git ignore rules alone are not the deployment packaging boundary.

Cloud SQLAlchemy uses `NullPool`; Neon pooled runtime URLs retain TLS/channel-binding parameters and normal Psycopg prepared-statement behavior. `VERCEL` selects serverless policy automatically; `DATABASE_POOL_MODE=serverless` is also available for operator checks. Cloud runtime requires a Neon pooled URL with TLS. Local Docker retains ordinary pooling.

### Explicit operator migrations

Valuation & Unrealised Result v0.1 adds only revision `0002_market_prices`, creating `market_price_observations`. Validate upgrade/downgrade/re-upgrade and drift locally first. Local Docker applies this revision before API startup. Cloud deployment does not apply it: the operator must explicitly upgrade Neon Staging before Preview valuation acceptance, and upgrade Neon Production only after Preview acceptance and a verified Production backup. Ordinary implementation/test runs must not migrate Production or reset cloud databases.

Set `MIGRATION_DATABASE_URL` only in the operator process to the selected project's direct/unpooled Neon URL. Do not print it, commit it, put it into browser variables or normal Vercel runtime, or pass it in shell command arguments. Set `DATABASE_POOL_MODE=serverless`, then from `apps/api` run:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Cloud migration fails if the operator URL is absent, pooled, non-Neon or lacks TLS. Local/CI retains DATABASE_URL fallback. No cloud startup/request performs migrations. Verify project identity before any operation; migrate Staging first and Production only after Preview acceptance, with a direct-connection backup before Production migration. Never run the ordinary pytest database-reset fixture against cloud databases.

### Deployment order and protection

Keep Vercel Authentication on All Deployments; do not weaken it for verification. Use authenticated browser access or `vercel curl` for checks, and separately confirm unauthenticated access is denied/redirected.

Vercel's first deployment is Production. The approved one-time exception uses deployment-only `CLOUD_BOOTSTRAP_ONLY=1`: `app.vercel:app` exposes health only, imports no persistence application and does no SQL. Production DATABASE_URL may be present but must not be used. This infrastructure bootstrap is not Production application acceptance. Never persist the bootstrap flag in project env; subsequent Preview and full Production deploys must omit it.

After bootstrap: deploy Preview, explicitly migrate Staging, verify browser Web/API/DB synthetic CRUD and persistence. Only after Preview passes: back up/migrate Production, deploy Production with Production-only credentials, smoke-test synthetic create/read/delete and remove all smoke records. Do not promote a Preview artifact into Production: rebuild with the Production environment.

### Readiness and cleanup gates

Verified on 2026-10-04, before milestone review:

- Infrastructure bootstrap: `dpl_3pCC2vmZENiJNbFXXgAoF5Yu7hh7`, health-only Production deployment, no SQL or migrations. This is infrastructure bootstrap, not application Production acceptance.
- Preview: [deployment](https://investment-tracker-4zxazfukh-snake1612-del.vercel.app), `dpl_7uyxz1eUCgqZfUuUkKSPjwk4E4cn`, READY. Browser synthetic create/read/update, refresh/persistence and API delete passed against Staging. Exact corrected `125.00000001` was independently confirmed in Staging and a restored backup; deletion persisted after refresh.
- Production: [protected alias](https://investment-tracker-wine-eight.vercel.app). Initial application acceptance used `dpl_4oNHQdNjoAzCsJAr6QPGKf26BRm4` (READY at acceptance; subsequently replaced and retired during packaging cleanup). Browser synthetic create/read and refresh/persistence, then API delete passed against Production. All synthetic Production transactions, Accounts and Portfolios were removed; all four canonical tables are empty.
- Both explicit direct migrations reached `0001_initial_persistence (head)`; Alembic check passed with no new operations. No new migration was created.
- Both authenticated health requests returned 200; unauthenticated health requests returned 302 to Vercel Authentication. All Deployments protection and `fra1` Function placement were retained. Environment mapping was verified independently using distinct project data.
- Backend 552 tests, Web 90 tests, Playwright desktop 4 / narrow 4, Ruff, Pyright, Web lint/typecheck/format/build and local Alembic checks passed. Local Compose Web/API/DB startup and proxy health passed using a temporary DB host-port override to 55433 because another project's container owns 55432. Committed local ports are unchanged; verification containers were stopped without volume removal. E2E used a fresh Web on 3002 because 3001 was already occupied; isolated API remained 8001 with only the test database.

No real investment data has been entered. The logical backup/restore gate below passed for synthetic data; review is still required before milestone closure. Never restore destructively into Production.

### Logical backup and restore

Decision 022 defines the authoritative operator workflow. See [Backup & Restore](BACKUP_RESTORE.md) for environment bindings, encrypted Production storage, empty-target restore, compatibility and post-restore verification. Use PostgreSQL 18 native clients and a direct/unpooled connection supplied securely through `BACKUP_DATABASE_URL` / `RESTORE_DATABASE_URL`; never expose credentials in command arguments or logs.

From `apps/api`, with the selected Local recovery endpoints configured:

```bash
uv run python -m operator_tools.backup backup --environment local --output ../../tmp/backups
uv run python -m operator_tools.backup validate ../../tmp/backups/<artifact>.tar
uv run python -m operator_tools.backup restore ../../tmp/backups/<artifact>.tar --environment local
```

Restore never drops/truncates an occupied database and uses one fail-fast PostgreSQL transaction. Verify exact persisted facts, relations, identity state and application reads after restoring; forward-migrate known older revisions explicitly before application use. Artifact-valid is structural validation, not recovery readiness. Production artifacts may only restore into explicitly designated Production recovery, never shared Staging/Preview/test infrastructure. Clear credential environment variables afterwards.

This milestone exported Staging through its direct connection, restored it into separate local PostgreSQL 18 and confirmed exact `125.00000001` from the synthetic journal. A direct logical Production backup was also captured before its first migration. Ignored verification artifacts are retained locally under `tmp/`; they contain synthetic data only and are not committed. This proves the logical procedure, not a scheduled backup service, retention policy or recovery SLA; maintain independent backups before real-data use and each Production migration.

Packaging verification identified synthetic backup files in early CLI deployment sources. No secret env files were uploaded. `.vercelignore` was added, its dry-run/source manifest checked, and those temporary deployment copies retired after clean replacement. Verify the upload manifest whenever adding new operator artifacts; they must remain host-only.

The original Supabase cloud target is superseded by Neon. After both Neon environments passed end-to-end, the unused empty Supabase Investment Tracker Staging (`udikkyzgisvrggjmjpjv`) was permanently deleted with explicit confirmation. Before deletion it had no public tables, Auth users, Storage objects, Edge Functions or branches. Fitness RPG Pilot was restored after Free capacity became available and reached ACTIVE_HEALTHY. AI Wardrobe remained ACTIVE_HEALTHY and was not altered.
