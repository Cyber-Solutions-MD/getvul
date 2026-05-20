# 12 — Pipelines / CI / CD

GetVul uses **GitHub Actions** for both CI and CD. Two workflow files live in [.github/workflows/](../.github/workflows/): `ci.yml` and `cd.yml`. There is no GitLab CI, CircleCI, or Jenkins config in the repo.

## Pipeline at a glance

```mermaid
flowchart LR
    DEV[Developer<br/>git push] --> BR[branch on GitHub]
    BR --> WD[manual dispatch<br/>workflow_dispatch only<br/>see PROD-02]
    WD --> CI

    subgraph CI [ci.yml — 5 jobs]
        BE[backend<br/>ruff · format · mypy* · alembic · pytest+cov]
        FE[frontend<br/>npm install · lint* · tsc* · build]
        TF[terraform<br/>fmt · init -backend=false · validate]
        SAST[semgrep<br/>semgrep ci]
        DAST[zap dast<br/>3 scans · continue-on-error]
        BE & FE -.depends.-> DAST
    end

    REL[GitHub release<br/>published] --> CD
    MANUAL[Manual cd dispatch] --> CD

    subgraph CD [cd.yml — deploy to GCE]
        SSH[SSH to VM]
        PULL[git fetch + reset --hard origin/main]
        BUILD[docker compose build --no-cache]
        UP[docker compose up -d]
        HC[health-check loop]
        VER[verify external /health]
        SSH --> PULL --> BUILD --> UP --> HC --> VER
    end

    CRON[Hourly cron on VM<br/>install.sh:108] -.also pulls.-> BUILD

    note["* = soft-fail today<br/>(|| true / continue-on-error)<br/>Phase 2 removes the masks"]
```

Source: [diagrams/pipelines-cicd.mmd](diagrams/pipelines-cicd.mmd).

---

## CI — `ci.yml`

Full file: [.github/workflows/ci.yml](../.github/workflows/ci.yml).

### Triggers

```yaml
on:
  workflow_dispatch:  # Manual trigger only — re-enable push/PR triggers when ready
  # push:
  #   branches: [main]
  # pull_request:
  #   branches: [main]
```

⚠ **Today CI runs only on manual dispatch.** Push and PR triggers are commented out (lines 5–8). PROD-02 (Phase 2: CI Gating) will re-enable them and remove the soft-fail masks listed below.

### Job: `backend`

Runs on Ubuntu latest, Python 3.12, with sidecar Postgres 16 + Redis 7 services.

| Step | What it runs | Soft-fail? |
|------|--------------|------------|
| Checkout | `actions/checkout@v5` | — |
| Setup Python | `actions/setup-python@v6` (3.12) | — |
| Install deps | `pip install -e ".[dev]"` | — |
| Lint | `ruff check .` | hard-fail |
| Format check | `ruff format --check .` | hard-fail |
| Type check | `mypy app/ \|\| true` | ⚠ **soft** ([line 59](../.github/workflows/ci.yml#L59)) |
| Migrate | `alembic upgrade head` against `getvul_test` DB | hard-fail |
| Test | `pytest -v --cov=app --cov-report=xml` (env: `JWT_SECRET_KEY=test-secret`, `ENVIRONMENT=test`) | hard-fail |
| Coverage upload | `codecov/codecov-action@v5` (only on PRs) | — |

### Job: `frontend`

| Step | What it runs | Soft-fail? |
|------|--------------|------------|
| Checkout | `actions/checkout@v5` | — |
| Setup Node | `actions/setup-node@v5` (20, with `cache: npm`) | — |
| Install | `npm install --legacy-peer-deps` | — |
| Lint | `npm run lint \|\| true` | ⚠ **soft** ([line 95](../.github/workflows/ci.yml#L95)) |
| Type check | `npx tsc --noEmit \|\| true` | ⚠ **soft** ([line 97](../.github/workflows/ci.yml#L97)) |
| Build | `npm run build` (`NEXT_PUBLIC_API_URL=http://localhost:8000`) | hard-fail |

### Job: `terraform`

| Step | What it runs |
|------|--------------|
| Setup | `hashicorp/setup-terraform@v4` (1.7) |
| Format check | `terraform fmt -check -recursive` |
| Init | `terraform init -backend=false` |
| Validate | `terraform validate` |

Hard-fails on any issue. This validates AWS, GCP, and Azure modules even though only GCP is the active target.

### Job: `semgrep`

Runs in `semgrep/semgrep` container. One step:

```yaml
- run: semgrep ci
  env:
    SEMGREP_APP_TOKEN: ${{ secrets.SEMGREP_APP_TOKEN }}
```

If the token is set, results are published to semgrep.dev for tracking.

### Job: `dast`

`needs: [backend, frontend]`. Spins up the slim CI compose ([docker-compose.ci.yml](../docker-compose.ci.yml)), polls `/health` until ready, then runs three ZAP scans.

| Step | Target | Soft-fail? |
|------|--------|------------|
| ZAP API Scan | `http://localhost:8000/openapi.json` | ⚠ `continue-on-error: true` ([line 164](../.github/workflows/ci.yml#L164)) |
| ZAP Baseline (backend) | `http://localhost:8000` | ⚠ `continue-on-error: true` ([line 173](../.github/workflows/ci.yml#L173)) |
| ZAP Baseline (frontend) | `http://localhost:3000` | ⚠ `continue-on-error: true` ([line 182](../.github/workflows/ci.yml#L182)) |
| Cleanup | `docker compose -f docker-compose.ci.yml down -v` | always runs (`if: always()`) |

Each ZAP step uploads its report as a CI artifact (e.g. `zap-api-scan`).

### Soft-fail summary (Phase 2 cleanup target)

| Step | File:line |
|------|-----------|
| `mypy app/` | [.github/workflows/ci.yml:59](../.github/workflows/ci.yml#L59) |
| `npm run lint` | [.github/workflows/ci.yml:95](../.github/workflows/ci.yml#L95) |
| `npx tsc --noEmit` | [.github/workflows/ci.yml:97](../.github/workflows/ci.yml#L97) |
| ZAP API Scan | [.github/workflows/ci.yml:164](../.github/workflows/ci.yml#L164) |
| ZAP Baseline backend | [.github/workflows/ci.yml:173](../.github/workflows/ci.yml#L173) |
| ZAP Baseline frontend | [.github/workflows/ci.yml:182](../.github/workflows/ci.yml#L182) |

PROD-02 deliverables (from [.planning/REQUIREMENTS.md](../.planning/REQUIREMENTS.md)):

- PROD-02-01 — re-enable push + pull_request triggers
- PROD-02-02 — remove the three `|| true` masks above
- PROD-02-03 — make a definitive ZAP gating decision
- PROD-02-04 — branch protection on `main` requires CI green

---

## CD — `cd.yml`

Full file: [.github/workflows/cd.yml](../.github/workflows/cd.yml).

### Triggers

```yaml
on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      force:
        description: "Force deploy (skip CI check)"
        type: boolean
        default: false
```

So CD runs on **GitHub release publish** or **manual dispatch**.

### Job: `deploy`

Single job, `runs-on: ubuntu-latest`.

1. **Configure SSH** — drops `secrets.GCE_SSH_PRIVATE_KEY` into `~/.ssh/deploy_key`, runs `ssh-keyscan -H $GCE_VM_IP` to populate `known_hosts`.
2. **Deploy to VM** — opens an SSH session as `deploy@$GCE_VM_IP` and runs:
   ```bash
   cd /opt/getvul
   git fetch origin main
   git reset --hard origin/main      # ⚠ destructive — see PROD-03-03 below
   docker compose build --no-cache
   docker compose up -d
   for i in $(seq 1 30); do
     if curl -sf http://localhost:8000/health; then break; fi
     sleep 5
   done
   curl -sf http://localhost:8000/health || exit 1
   docker image prune -f
   ```
3. **Verify deployment** — back on the runner, curls `http://$GCE_VM_IP/health` and checks the body for `"status":"ok"`. Exits 1 if not.

### Required secrets

| Secret | Purpose |
|--------|---------|
| `GCE_VM_IP` | Public IP of the production VM (used in `ssh -i ~/.ssh/deploy_key deploy@$VM_IP`) |
| `GCE_SSH_PRIVATE_KEY` | SSH private key authorized in the VM's `~/.ssh/authorized_keys` |
| `SEMGREP_APP_TOKEN` (CI only) | Optional — enables result publishing |

### Known issues (Phase 3 — PROD-03)

- **PROD-03-01** — There are two competing update paths: (a) this CD job on release, and (b) the hourly cron installed by `install.sh` (line 108) which `git pull`s + rebuilds every hour. Either one can deploy unreleased code in the wrong race condition.
- **PROD-03-02** — The hourly cron must be disabled (or made conditional) when CD is the chosen path.
- **PROD-03-03** — The CD `git reset --hard origin/main` deploys whatever HEAD is on `main`, not the released tag. Released tags should be checked out by SHA.
- **PROD-03-04** — No documented rollback. To roll back today: SSH to the VM, `git reset --hard <previous-sha>`, `docker compose up -d --build`. This should be scripted.

---

## Pre-commit hooks and local gates

| Tool | Configured? | Notes |
|------|-------------|-------|
| `.pre-commit-config.yaml` | ✗ none | Adding one is recommended (see [06-development-workflow.md](06-development-workflow.md)) |
| Husky / lint-staged | ✗ none | Frontend has no commit-time hooks |
| `.gitleaks.toml` | ✓ exists | Allowlist for dev keys; not invoked by any local hook |

`make lint`, `make fmt`, `make typecheck`, `make test` are the local equivalents of CI checks.

## Artefacts

| Artefact | Where it goes |
|----------|---------------|
| ZAP reports | CI artifacts: `zap-api-scan`, `zap-backend-baseline`, `zap-frontend-baseline` (default 90-day retention) |
| Coverage XML | uploaded to codecov.io on PRs |
| Build images | Built but **not pushed** to a registry — the CD path rebuilds on the VM with `docker compose build --no-cache` rather than pulling pre-built images. Phase 3 may revisit this. |

## What's missing

- No image build + push to GHCR / GCR / ECR. Cloud builds use the host's local Docker daemon.
- No staging environment. CD goes straight to production.
- No canary or blue/green deploys. The `docker compose up -d` rolls forward in place.
- No deploy notifications (Slack, email).

These are deliberate scope choices for the single-VM model and would be revisited if a multi-replica or multi-region deployment becomes a priority.
