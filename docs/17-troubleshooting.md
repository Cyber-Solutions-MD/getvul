# 17 — Troubleshooting

Common failure modes when running, deploying, or developing GetVul, with diagnostics and fixes. Most of these come from real incidents in the codebase's history; the rest are predictable consequences of the stack choices.

If your problem isn't here, open an issue with `docker compose logs --tail=200` for the affected service and the exact reproduction steps.

## A. Local development

### A1. `bind: address already in use` (port 6379, 5432, 8000, 3000, 80, or 443)

**Symptom** — `docker compose up` fails on one of the five services with a port-bind error.

**Cause** — Something else on your machine is listening on that port. The most common culprit is a stale test Redis container (e.g. `gsd-redis-01-01` left over after running the Phase 1 test suite).

**Fix**
```bash
# Find what's holding the port
lsof -nP -i :6379

# If it's another Docker container:
docker ps --filter "publish=6379"
docker stop <name>

# If it's a host service (Homebrew Redis, system Postgres):
brew services stop redis
brew services stop postgresql
```

### A2. Backend won't start: `connection refused` to Redis or Postgres

**Symptom** — `docker compose logs backend` shows asyncpg or redis-py refusing to connect even though all five services say `Up`.

**Cause** — Backend started before its dependency was healthy. Compose has `depends_on: condition: service_healthy` for postgres and redis ([docker-compose.yml:64-67](../docker-compose.yml#L64-L67)), but Redis sometimes flips healthy momentarily then misbehaves under heavy boot load.

**Fix**
```bash
docker compose down
docker compose up -d postgres redis      # let dependencies settle first
docker compose ps                         # confirm both (healthy)
docker compose up -d backend frontend nginx
```

### A3. Login returns 500 on a fresh checkout

**Symptom** — POST `/auth/login` returns 500, logs show `relation "users" does not exist`.

**Cause** — Migrations didn't run. Compose's backend command does `alembic upgrade head && uvicorn ...`, but if you ran a custom command or Postgres data is corrupt, the migration may have skipped.

**Fix**
```bash
make migrate
# or
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend alembic current   # confirm: 024_add_containment_status (head)
```

### A4. The default admin doesn't exist

**Symptom** — Cannot log in with `admin@getvul.local / Admin123!` after `make dev-d`.

**Cause** — Compose does **not** run `create_admin.py` automatically (only `install.sh` does). On a fresh DB you have to run it once.

**Fix**
```bash
docker compose exec -T backend python create_admin.py
```

The script is idempotent: it skips if any user with `password_hash` already exists. See [04-installation.md](04-installation.md) and [backend/create_admin.py](../backend/create_admin.py).

### A5. `curl` to `/health` works but the browser hangs / silently fails

**Symptom** — Frontend loads but sees no data; DevTools shows aborted/CORS-blocked requests to the backend.

**Cause** — Either:
- `NEXT_PUBLIC_API_URL` mismatch (compose dev expects `http://localhost:8000`; CI uses `http://backend:8000`).
- The Next.js CSP in `next.config.js` blocks `connect-src` to a non-allowlisted host.

**Fix** — In dev, confirm `docker compose exec frontend env | grep NEXT_PUBLIC_API_URL` returns `http://localhost:8000`. For prod deploys, see [05-configuration.md](05-configuration.md#frontend-nextjs).

### A6. Tests fail on `test_oidc_state.py` or `test_rate_limit.py`

**Symptom** — Phase 1 tests fail with Redis errors or assertions about db=1.

**Cause** — Either:
- The conftest's `flushed_redis` fixture asserts `db == 1` (Pitfall 4 safeguard); something forced `REDIS_URL` to db 0.
- Another process is using db 1 concurrently.

**Fix**
```bash
# Make sure REDIS_URL isn't overridden in your shell
unset REDIS_URL
make test
```

If still failing, the test suite needs an isolated Redis instance:
```bash
docker run --rm -d -p 6379:6379 --name getvul-test-redis redis:7-alpine
make test-local
docker stop getvul-test-redis
```

## B. Production / deploy

### B1. Hourly cron and CD both deploy at the same time

**Symptom** — A release went out via CD (`cd.yml`), and 30 minutes later the VM rolls back to a different SHA — or a previously-fixed bug reappears.

**Cause** — `install.sh` registers an hourly cron (`/etc/cron.d/getvul-update`, [install.sh:108](../install.sh#L108)) that does `git pull` + `docker compose up -d --build`. If `main` advanced after CD ran, the cron pulls the newer SHA. Two competing release paths — see [12-pipelines-cicd.md](12-pipelines-cicd.md) and PROD-03.

**Fix (interim)** — Disable one of them on the VM:
```bash
# Disable the cron:
sudo rm /etc/cron.d/getvul-update
# Or disable CD until Phase 3 picks one path:
# (in repo settings → Actions → workflow → Disable workflow)
```

PROD-03 will pick a canonical path.

### B2. TLS certificate expired

**Symptom** — Browsers warn the cert is expired. `openssl x509 -noout -enddate -in nginx/certs/server.crt` shows a date in the past.

**Cause** — `install.sh` and `nginx/entrypoint.sh` generate a 365-day self-signed cert; nothing renews it.

**Fix (one-time)**
```bash
# Delete the existing cert and let entrypoint regenerate
sudo rm /opt/getvul/nginx/certs/server.{crt,key}
sudo docker compose restart nginx
```

**Fix (permanent)** — Install a CA cert via `Settings → TLS/SSL` (UI), or wire up Let's Encrypt with certbot. The nginx config already exposes `/.well-known/acme-challenge/` ([nginx.conf:99-101](../nginx/nginx.conf#L99-L101)), so the webroot path is ready; you just need to add a certbot service to compose.

### B3. Lost `ENCRYPTION_KEY` — connector creds undecryptable

**Symptom** — After replacing `.env` (e.g. when migrating between VMs), every connector test fails with `cryptography.fernet.InvalidToken`.

**Cause** — Connector credentials in `connector_configs.credentials_secret_arn` are encrypted with the **previous** Fernet key. Fernet is symmetric — there's no recovery.

**Fix** — Restore the old `ENCRYPTION_KEY`. If you've truly lost it, re-create each connector through `Settings → Connectors` (the credentials are re-entered, re-encrypted with the new key). PROD-05 will document a backup/rotation procedure.

### B4. Postgres data is gone after `make down-v`

**Symptom** — Database is empty, migrations re-run from scratch, no users, no data.

**Cause** — `make down-v` runs `docker compose down -v` which **removes named volumes** including `pgdata`. This is by design for getting a clean dev DB.

**Fix** — There is no fix; this is destructive. Always `pg_dump` before `down -v` if you care about the data:
```bash
docker compose exec -T postgres pg_dump -U getvul getvul > getvul-$(date +%Y%m%d).sql
make down-v
make dev-d
docker compose exec -T postgres psql -U getvul getvul < getvul-20260509.sql
```

A scripted backup is on the PROD-05 list.

### B5. Connector sync stuck in `RUNNING`

**Symptom** — `connector_configs.last_sync_status = RUNNING` for hours; UI shows the sync hasn't moved.

**Cause** — Backend was killed mid-sync. The scheduler has no orphan-cleanup logic.

**Fix**
```bash
docker compose exec postgres psql -U getvul -d getvul -c \
  "UPDATE connector_configs SET last_sync_status='FAILED' WHERE last_sync_status='RUNNING';"
```

Then retry the sync from `Settings → Connectors → <connector> → Sync now`.

### B6. fpdf2 fails on em-dashes / non-Latin characters

**Symptom** — `scheduled_report_failed: Character "—" at index 20 in text is outside the range of characters supported by the font used: "helveticaB".`

**Cause** — fpdf2 default Helvetica is Latin-1 only; em-dash, smart quotes, and Cyrillic/CJK chars all fail.

**Fix** — Either sanitize the input (replace `—` with `--`, etc.), or load a Unicode TTF font via `pdf.add_font(...)`. This is a known issue (pre-Phase 1, surfaces in `/dashboard` scheduled reports) and is a Phase 4 candidate.

## C. Auth and Redis

### C1. OIDC callback returns 503

**Symptom** — User completes Google/Azure consent and lands on `/auth/callback/...` which returns 503.

**Cause** — Redis is unreachable. Phase 1 made the OIDC state path fail-closed (decision D-06) — the callback can't validate the state without Redis, so it refuses to exchange the code.

**Fix**
```bash
docker compose ps redis        # is it Up (healthy)?
docker compose restart redis
```

If Redis is healthy but the callback still 503s, look at backend logs for the actual exception. The state TTL is 600s, so a delayed callback can also legitimately fail with "state not found".

### C2. Rate-limit warnings spam the logs

**Symptom** — `redis_unavailable subsystem=rate_limiter` logs at high frequency; UI feels unaffected.

**Cause** — Redis is intermittently failing. The rate limiter is **fail-OPEN** by design (decision D-05) — every request is allowed through, but each one tries the pipeline and logs the error.

**Fix** — Same as C1, but the impact is lower urgency since traffic is still served.

### C3. SSO works on first replica, fails on second

**Symptom** — Behind a load balancer, OIDC login intermittently fails with "invalid state".

**Cause** — Pre-Phase 1 behavior. With the in-memory `_pending_states` dict, the replica that wrote the state had to be the one to consume it.

**Fix** — Confirm you're on the post-Phase 1 build (commit ≥ `1dfce14` on this branch). The fix is `SET ... NX EX 600` + `GETDEL` against shared Redis ([backend/app/auth/router.py](../backend/app/auth/router.py) post-Phase 1). All replicas must point at the **same** Redis URL.

## D. CI / CD

### D1. CI doesn't run on push or PR

**Symptom** — Pushing a branch and opening a PR shows no GitHub Actions runs.

**Cause** — `ci.yml` triggers on `workflow_dispatch` only ([line 4](../.github/workflows/ci.yml#L4)). Push and PR are commented out (lines 5–8). Phase 2 (PROD-02) re-enables them.

**Fix (interim)** — Run manually: `gh workflow run ci.yml --ref <branch>`.

### D2. mypy / lint / tsc errors don't fail the build

**Symptom** — A type error or lint violation merged to `main` despite "passing" CI.

**Cause** — `mypy app/`, `npm run lint`, and `npx tsc --noEmit` all carry `|| true` in CI today (lines 59, 95, 97). This is the explicit Phase 2 cleanup target (PROD-02-02).

**Fix (interim)** — Run them locally: `make typecheck && make lint && cd frontend && npx tsc --noEmit`.

### D3. CD deploys old code

**Symptom** — Released tag `v1.2.3` but the VM is running `main`'s latest commit, not the tag.

**Cause** — `cd.yml` does `git fetch origin main && git reset --hard origin/main` ([cd.yml:40-41](../.github/workflows/cd.yml#L40-L41)). It deploys `origin/main`, not the tag. PROD-03-03 will fix this.

**Fix (interim)** — Don't allow new commits on `main` between cutting the release and the CD job finishing. Or SSH to the VM after the CD run and `git checkout v1.2.3` manually.
