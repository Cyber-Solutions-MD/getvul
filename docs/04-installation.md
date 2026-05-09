# 04 — Installation

This is the local-development quick start. For cloud deployment to GCP/AWS/Azure, see [13-deployment.md](13-deployment.md). For the per-variable description of every config knob, see [05-configuration.md](05-configuration.md).

## Prerequisites

| Tool | Minimum version | Notes |
|------|-----------------|-------|
| Docker Engine | 24.0 | Tested on 28.x |
| Docker Compose plugin | v2 | Invoked as `docker compose`, not `docker-compose` |
| Git | 2.30 | For clone, branching |
| (optional) Python | 3.12 | Only needed for `make test-local` and other local-venv targets |
| (optional) Node | 20 LTS | Only needed for `make fe-dev` and other local-venv targets |
| Free TCP ports | 80, 443, 3000, 5432, 6379, 8000 | Stop anything else listening on these |
| Disk | ~5 GB | Image build + `pgdata` volume |

## 1. Clone

```bash
git clone https://github.com/Cyber-Solutions-MD/getvul.git
cd getvul
```

## 2. Create `.env`

```bash
cp .env.example .env
```

Edit `.env` if you need to. The defaults work for local dev; in production you must rotate `JWT_SECRET_KEY` and `ENCRYPTION_KEY`. See [05-configuration.md](05-configuration.md) for every variable.

> If you skip this step, [docker-compose.yml:53-59](../docker-compose.yml#L53-L59) supplies dev defaults inline (`JWT_SECRET_KEY=dev-secret-change-in-prod`, etc.) — fine for local, never for prod.

## 3. Build and start the stack

```bash
make dev          # foreground (logs in your terminal)
# or
make dev-d        # detached / background
```

Both expand to `docker compose up --build`. First build is 2–5 minutes; subsequent runs use the cache.

The compose file ([docker-compose.yml](../docker-compose.yml)) brings up five services and waits on Postgres + Redis healthchecks before starting the backend. The backend command runs `alembic upgrade head` then `uvicorn app.main:app --reload` ([docker-compose.yml:48-50](../docker-compose.yml#L48-L50)) — migrations are applied automatically on every start.

## 4. Create the default admin

The compose stack does **not** seed an admin user automatically (only `install.sh` does that). For local dev:

```bash
docker compose exec -T backend python create_admin.py
```

This creates:

| Field | Value |
|-------|-------|
| Email | `admin@getvul.local` |
| Password | `Admin123!` |
| Role | OWNER |
| Tenant | GetVul (`slug=getvul`, `domain=localhost`, `idp_provider=LOCAL`) |

The script is idempotent — it skips itself if any user with a `password_hash` already exists. See [backend/create_admin.py](../backend/create_admin.py).

> **Change `Admin123!` immediately after first login.** This is a known-default credential. Phase 6 (PROD-06) will force a first-login rotation.

## 5. (Optional) Seed demo data

```bash
docker compose exec -T backend python seed_data.py
```

Populates ~25 assets, 150+ vulnerabilities, 20 CSPM findings, 10 Jira tickets, 15 users, 5 notifications, 7 connectors. Useful for evaluating dashboards.

## 6. Verify

| Check | Command | Expected |
|-------|---------|----------|
| Compose status | `docker compose ps` | All five services `Up` (postgres + redis `(healthy)`) |
| Backend health | `curl -sS http://localhost:8000/health` | `{"status":"ok","service":"getvul-api"}` |
| API docs (DEBUG only) | open `http://localhost:8000/docs` | Swagger UI |
| Frontend | open `http://localhost:3000` | Login page |
| Nginx HTTPS | open `https://localhost` (accept self-signed cert) | Login page |
| Redis | `docker compose exec -T redis redis-cli ping` | `PONG` |
| Postgres | `docker compose exec -T postgres psql -U getvul -d getvul -c '\dt'` | List of tables |

Then log in at `http://localhost:3000` with `admin@getvul.local / Admin123!`.

## 7. Run the test suite

```bash
make test         # in-container, with coverage
# or
make test-local   # host-side venv (must `pip install -e ".[dev]"` first under backend/)
```

Phase 1 multi-replica tests require Redis at `redis://localhost:6379/1` (db=1, isolated from app's db=0). The `flushed_redis` fixture in [backend/tests/conftest.py](../backend/tests/conftest.py) asserts this and `FLUSHDB`s before/after each test.

## Common setup issues

| Symptom | Cause / fix |
|---------|-------------|
| `bind: address already in use` on 6379 | Another Redis is running (e.g. local Homebrew). `brew services stop redis` or stop the conflicting container. |
| `connection refused` on `localhost:8000` | Backend still booting. `docker compose logs -f backend` and wait for `Started server process`. |
| Frontend stuck on "Loading…" | `NEXT_PUBLIC_API_URL` mismatch. In dev it must be `http://localhost:8000` (set by [docker-compose.yml:77](../docker-compose.yml#L77)). |
| Login returns 500 | DB not migrated. `make migrate` (or restart backend — it migrates on boot). |
| Self-signed cert warning | Expected in dev. The first nginx start auto-generates a cert via [nginx/entrypoint.sh](../nginx/entrypoint.sh). |
| `make test` fails with Redis errors | The test suite needs db=1 free. Make sure no other test is running. |

More entries in [17-troubleshooting.md](17-troubleshooting.md).

## Resetting state

```bash
make down-v     # stops everything AND removes Postgres + certbot volumes
make dev-d      # rebuild + restart with a fresh DB
docker compose exec -T backend python create_admin.py   # re-create admin
```

## What's running where

| Service | Host port | Container port | Image / build |
|---------|-----------|----------------|---------------|
| nginx | 80, 443 | 80, 443 | `nginx:alpine` + [nginx/nginx.conf](../nginx/nginx.conf) + [nginx/entrypoint.sh](../nginx/entrypoint.sh) |
| frontend | 3000 | 3000 | build of [frontend/Dockerfile](../frontend/Dockerfile) |
| backend | 8000 | 8000 | build of [backend/Dockerfile](../backend/Dockerfile) |
| postgres | 5432 | 5432 | `postgres:16-alpine`, volume `pgdata` |
| redis | 6379 | 6379 | `redis:7-alpine` (no persistence) |

Stop everything: `make down`. Tail logs: `make logs`.
