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

The browser uses same-origin `/api/*`; Next.js rewrites to server-side `API_URL=http://api:8000`. API uses the Compose `db:5432` connection to `investment_tracker`. The unrelated host PostgreSQL port 5432 is not used. Existing SQLAlchemy runtime pooling remains unchanged.

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

## Cloud target — not implemented

Pending provisioning — blocked by Supabase project quota.

Approved target: one Vercel Project, Web (`apps/web`) and API (`apps/api`) Services, with Web → API Service Binding exposed as server-side `API_URL`. Preview uses staging Supabase PostgreSQL only; Production uses a separate production Supabase project only. Production credentials must never be available in Preview.

No cloud resources, cloud environment variables, cloud migrations, credentials or deployments are supplied by this local pass. Runtime transaction pooling, direct operator migrations, deployment protection and a verified logical backup/restore drill remain future cloud-pass requirements. Production real-data use remains blocked until those safety gates are satisfied.
