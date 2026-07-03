# 03 — Tech Stack

Every version below is read directly from the lockfiles or workflow files. Update this doc when bumping a major dependency.

## Backend (Python)

Defined in [backend/pyproject.toml](../backend/pyproject.toml).

### Runtime

| Component | Version | Why |
|-----------|---------|-----|
| Python | `>=3.12` | Async-first, modern type system, used in CI matrix |
| FastAPI | `>=0.115, <1.0` | Async HTTP, OpenAPI auto-gen, Pydantic v2 native |
| Uvicorn | `>=0.30` (`[standard]` extras) | ASGI server, WebSocket-ready |
| Pydantic | `>=2.9` | Request/response validation, `pydantic-settings >= 2.5` for env loading |
| SQLAlchemy | `>=2.0` (`[asyncio]`) | Async ORM, `Mapped[T]` style |
| asyncpg | `>=0.30` | Async Postgres driver |
| Alembic | `>=1.14` | Schema migrations (24 versions on disk) |
| Redis | `>=5.2` | Async Redis client (`redis.asyncio`) |
| python-jose | `>=3.3` (`[cryptography]`) | JWT issue/decode (HS256) |
| httpx | `>=0.27` | Async HTTP for connectors and tests |
| orjson | `>=3.10` | Fast JSON in responses |
| tenacity | `>=9.0` | Retry decorators around connector calls |
| croniter | `>=3.0` | Cron parsing for scheduled reports & ticket rules |
| structlog | `>=24.0` | Structured logs |
| cryptography | `>=43.0` | Fernet symmetric encryption for connector creds |
| bcrypt | `>=4.0` | Password hashing |
| fpdf2 | `>=2.8` | Executive PDF reports |
| python-multipart | `>=0.0.9` | File uploads (logo, TLS cert) |

### Dev / test (`pip install -e ".[dev]"`)

| Component | Version |
|-----------|---------|
| pytest | `>=8.3` |
| pytest-asyncio | `>=0.24` |
| pytest-cov | `>=6.0` |
| asgi-lifespan | `>=2.1` (added in Phase 1 for `LifespanManager`) |
| ruff | `>=0.8` |
| mypy | `>=1.13` |
| factory-boy | `>=3.3` |

### Lint / type-check config (from `[tool.ruff]` / `[tool.mypy]`)

- Ruff: `target-version = "py312"`, `line-length = 120`, rules `E F I N UP B SIM TC` (broad).
- Mypy: `strict = true`, `python_version = "3.12"`, plugin `pydantic.mypy`.

## Frontend (Node)

Defined in [frontend/package.json](../frontend/package.json).

### Runtime

| Component | Version |
|-----------|---------|
| Next.js | `^15.5.13` |
| React | `^19.0.0` |
| react-dom | `^19.0.0` |
| TypeScript | `^5.5.0` (devDep, `strict: true`) |
| Tailwind CSS | `^3.4.0` |
| autoprefixer | `^10.4.0` |
| PostCSS | `^8.4.0` |
| lucide-react | `^0.383.0` (icons) |
| recharts | `^2.12.0` (declared but currently unused — dashboard charts are pure SVG/CSS in [frontend/src/app/dashboard/page.tsx](../frontend/src/app/dashboard/page.tsx)) |
| clsx | `^2.1.0` |
| tailwind-merge | `^2.3.0` |
| eslint | `^8.57.0` |
| eslint-config-next | `^15.5.0` |

### Dependency overrides

`package.json` pins `picomatch >= 4.0.2` and `brace-expansion >= 2.0.1` to mitigate transitive CVEs.

### Build / deploy

- `next.config.js` runs in `output: standalone` (slim Docker image).
- Container runs `npm run dev` in development; `next build` + `next start` for production.

### Notably absent

| Missing piece | Status |
|---------------|--------|
| Frontend test framework (Jest, Vitest, Playwright) | None configured. Phase 8 (PROD-08) tracks adding one. |
| Prettier config | None — relies on ESLint defaults. |
| Global state library (Redux, Zustand, Jotai, SWR, React Query) | Not used. Pure React Context (`@/lib/auth`, `@/lib/theme`) + `useEffect`/`useCallback`. |
| Service worker / PWA manifest | None. |
| Husky / lint-staged | None. |

## Data layer

| Component | Version |
|-----------|---------|
| PostgreSQL | `16-alpine` (Docker image) |
| Redis | `7-alpine` (Docker image) |
| Postgres features used | `JSONB` columns (~24 sites), `gen_random_uuid()` server defaults, `UNIQUE` composite constraints, FK `ON DELETE CASCADE` for tenant scope |
| Redis usage | `oidc:state:*` (string + TTL), `ratelimit:{tenant_id}` (sorted set + TTL). **No persistence configured** — see [15-monitoring-logging.md](15-monitoring-logging.md). |

## Infrastructure

| Component | Version / Image |
|-----------|----------------|
| Docker | `>=24` recommended (project tested on 28.x) |
| Docker Compose | v2 plugin (`docker compose`) |
| Nginx | `nginx:alpine` |
| Terraform | `>=1.7` (validated by [.github/workflows/ci.yml:103-120](../.github/workflows/ci.yml#L103-L120)) |
| GCP base image | `cos-cloud/cos-stable` (Container-Optimized OS) — see [infra/gcp/main.tf](../infra/gcp/main.tf) |
| AWS base image | Latest Ubuntu 22.04 LTS — `aws_ami` data source in [infra/aws/main.tf](../infra/aws/main.tf) |
| Azure base image | Canonical Ubuntu 24.04 LTS — see [infra/azure/main.tf](../infra/azure/main.tf) |

## Tooling that touches the repo

| Tool | Where | Purpose |
|------|-------|---------|
| GitHub Actions | [.github/workflows/](../.github/workflows/) | CI (`ci.yml`), CD (`cd.yml`) |
| Semgrep | CI job + `.gitleaks.toml` allowlist in repo root | SAST |
| OWASP ZAP | CI DAST job (3 scans, currently `continue-on-error: true`) | DAST |
| codecov | CI coverage upload (PR-only) | Coverage tracking |
| gitleaks | `.gitleaks.toml` (only the config — no pre-commit hook configured) | Secret detection allowlist (dev keys whitelisted) |

## Versions in CI

[.github/workflows/ci.yml:10-12](../.github/workflows/ci.yml#L10-L12) pins:

```yaml
PYTHON_VERSION: "3.12"
NODE_VERSION: "20"
```

If you bump these, make sure [backend/pyproject.toml](../backend/pyproject.toml) `requires-python` and [frontend/Dockerfile](../frontend/Dockerfile) base image stay aligned.
