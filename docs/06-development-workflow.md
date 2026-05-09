# 06 — Development Workflow

How to actually get changes from your laptop into `main`.

## Branching

`main` is the only long-lived branch. Cut feature branches from `main`, merge back via PR.

| Convention | Example |
|------------|---------|
| Feature | `feat/oidc-state-redis` |
| Bug fix | `fix/rate-limit-fail-open` |
| Docs | `docs/api-reference-update` |
| Chore | `chore/bump-fastapi-0.116` |
| GSD phase | `gsd/phase-1-multi-replica-state` (auto-named when the GSD planning workflow is used — see `.planning/`) |

There is no `develop` or `release/*` workflow. Releases are cut by tagging on `main`.

## Commits

Recent history follows a Conventional-Commits-ish style — scope-by-area is encouraged but not enforced:

```
feat(01-02): replace _rate_limit_store with Redis sorted-set sliding window
docs(phase-01): evolve PROJECT.md after phase completion
chore(01-00): add asgi-lifespan>=2.1 dev dep
fix(auth): fail-closed on Redis unreachable in OIDC callback
test(01-03): add 4 PROD-01-03 cross-replica integration tests
```

Run `git log --oneline -20` to see the active style. The first line should fit in ~72 characters; longer rationale goes in the body.

### Atomic commits per task

The GSD phase plans (see [.planning/phases/](../.planning/phases/)) commit each plan task individually rather than batching — small commits are preferred. Example: Plan 01-02 produced 4 commits (`feat`, `test`, `docs`, summary) instead of one mega-commit.

## Pull requests

1. Push your branch: `git push -u origin <branch>`.
2. Open a PR against `main` (`gh pr create` or the GitHub UI).
3. PR title mirrors the headline commit; body uses the template:
   ```markdown
   ## Summary
   - bullet 1
   - bullet 2

   ## Test plan
   - [ ] make test
   - [ ] make typecheck
   - [ ] manual: <what you verified in the browser>
   ```
4. CI runs (`workflow_dispatch` only at the moment — see [12-pipelines-cicd.md](12-pipelines-cicd.md)). When Phase 2 lands, push/PR triggers will be re-enabled.
5. Merge with **squash** preferred for feature branches (keeps `main` linear); use a merge commit for branches that benefit from preserving the multi-commit history (rare).

> **Note:** [.github/](../.github/) currently has **no PR template, no issue templates, no `CODEOWNERS`**. PRs use the GitHub default. Adding these is good first-issue territory.

## Lint, format, type-check

Backend ([Makefile](../Makefile)):

```bash
make lint        # ruff check .          → fails on style/unused-import errors
make fmt         # ruff format .         → applies fixes
make typecheck   # mypy app/             → strict (currently soft-fails in CI)
```

Frontend:

```bash
make fe-lint     # cd frontend && npm run lint    → soft-fails in CI today
cd frontend && npx tsc --noEmit                   → soft-fails in CI today
```

The "soft-fails" are part of the Phase 2 (CI Gating) work-list — `mypy`, `npm lint`, and `tsc` all carry `|| true` in [.github/workflows/ci.yml](../.github/workflows/ci.yml) at lines 59, 95, 97.

## Tests

```bash
make test         # in container, with coverage
make test-local   # host venv (must `pip install -e ".[dev]"` first)
```

`pytest -v --cov=app --cov-report=term-missing`. Test fixtures and conftest details in [14-testing.md](14-testing.md).

## Migrations

```bash
make migrate-new MSG="add device_iso_country to assets"
# → autogenerates a new file under backend/alembic/versions/
make migrate           # apply (also auto-applies on `make dev`)
make migrate-down      # roll back the last migration
```

Hand-edit the generated file before committing — Alembic's autogen is a starting point, not a finished migration. Add forward-compatible defaults so deploys don't error on existing rows.

## Local debugging

| Want to … | Do |
|-----------|-----|
| See backend logs live | `make logs` (all services) or `docker compose logs -f backend` |
| psql shell | `make db-shell` |
| Bash inside backend container | `make backend-shell` |
| Inspect Redis | `docker compose exec -T redis redis-cli` |
| Hit Swagger UI | Set `DEBUG=true`, restart, open `http://localhost:8000/docs` |
| Reset DB completely | `make down-v && make dev-d && docker compose exec -T backend python create_admin.py` |
| Use a Python debugger | `breakpoint()` works because uvicorn runs with `--reload`; attach with `docker compose exec backend python` |

## Pre-commit hooks

Currently **none configured** (no `.pre-commit-config.yaml`, no Husky in `frontend/package.json`). [`.gitleaks.toml`](../.gitleaks.toml) exists at the repo root but is config-only — no hook invokes it locally. CI runs Semgrep on every workflow run.

Adding a `.pre-commit-config.yaml` with `ruff check`, `ruff format --check`, `mypy app/`, and `gitleaks` is recommended (and overlaps with PROD-02 work).

## Code review expectations

Reviewers should check, at minimum:

1. **Tenant isolation.** Any new query must filter by `tenant_id` from JWT (see `get_current_user` dependency).
2. **Migrations.** New columns are nullable or have defaults. Drops are split into deprecate-then-drop across two releases.
3. **Secrets.** No real keys in code, fixtures, or `.env.example`. Dev/test keys must be in [`.gitleaks.toml`](../.gitleaks.toml) allowlist.
4. **Audit logging.** Mutating endpoints emit `await audit(db, user, action, resource_type, resource_id, details)` (see [`backend/app/audit.py`](../backend/app/audit.py)).
5. **RBAC.** Every Analyst/Admin/Owner-only route uses `Depends(require_role(...))` rather than raw `get_current_user`.
6. **Tests.** New behavior has at least one happy-path and one failure test. For Redis-touching code, use the `flushed_redis` / `two_apps` fixtures so it's exercised cross-replica.

## Working on a "phase"

The repo uses the GSD workflow (`.claude/get-shit-done/`) for milestone work. The skills you'll see:

| Slash command | Purpose |
|---------------|---------|
| `/gsd-progress` | Where am I, what's next |
| `/gsd-discuss-phase N` | Gather context + decisions before planning |
| `/gsd-plan-phase N` | Generate `PLAN.md` with goal-backward verification |
| `/gsd-execute-phase N` | Run all plans in the phase (parallel waves) |
| `/gsd-verify-work N` | Manual UAT and gap diagnosis |
| `/gsd-code-review N` / `/gsd-code-review-fix N` | Auto code review + auto fix |

Generated artefacts land in [`.planning/`](../.planning/). They aren't shipped products — they're the build trail.

## Reading the planning artefacts

| File | Purpose |
|------|---------|
| `.planning/PROJECT.md` | What the project is, validated/active requirements, key decisions |
| `.planning/REQUIREMENTS.md` | Catalogued requirement IDs |
| `.planning/ROADMAP.md` | Phase breakdown for the active milestone |
| `.planning/STATE.md` | Current focus, last activity |
| `.planning/phases/<N>-<slug>/` | Per-phase artefacts: `PLAN.md`, `RESEARCH.md`, `CONTEXT.md`, `SUMMARY.md`, `VERIFICATION.md`, `REVIEW.md` |
