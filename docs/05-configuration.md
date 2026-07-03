# 05 — Configuration

Every environment variable read by GetVul, where it's read, what it does, what the default is, and which component depends on it.

> **Note on `.env.example`** — At doc-generation time the harness denied direct read access to `.env.example`. The table below is derived from the canonical sources: [backend/app/config.py](../backend/app/config.py), [docker-compose.yml](../docker-compose.yml), [docker-compose.ci.yml](../docker-compose.ci.yml), [install.sh](../install.sh), and [infra/gcp/startup.sh](../infra/gcp/startup.sh). If `.env.example` adds variables not listed here, please open a PR to update this doc.

## Configuration loading

The backend uses `pydantic-settings` (see [backend/app/config.py:7](../backend/app/config.py#L7)):

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

That means: env vars from the process environment win, and `.env` (CWD) is the fallback. In Docker the env vars come from `compose.yml`'s `environment:` block.

The frontend reads only `NEXT_PUBLIC_*` variables — those are baked at build time by Next.js.

## Variable reference

### Core

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `APP_NAME` | `GetVul` | no | `Settings.app_name` ([config.py:9](../backend/app/config.py#L9)) | Cosmetic title in API docs |
| `DEBUG` | `false` | no | `Settings.debug` ([config.py:10](../backend/app/config.py#L10)) | Exposes `/docs` and `/redoc`; widens CORS to `http://localhost:3000` ([main.py:174-181](../backend/app/main.py#L174-L181)) |
| `ENVIRONMENT` | `production` | no | `Settings.environment` ([config.py:11](../backend/app/config.py#L11)) | If `development` or `production`, lifespan starts the in-process scheduler ([main.py:40](../backend/app/main.py#L40)) |

### Database & cache

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `DATABASE_URL` | `postgresql+asyncpg://getvul:getvul@localhost:5432/getvul` | yes | `Settings.database_url`, asyncpg engine | Async SQLAlchemy DSN. In compose, points at the `postgres` service. |
| `REDIS_URL` | `redis://localhost:6379/0` | yes | `Settings.redis_url`, lifespan ([main.py:45-50](../backend/app/main.py#L45-L50)), conftest fixture | OIDC state + rate limiter live in this DB. Tests force db=1. |

### Authentication

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `JWT_SECRET_KEY` | `CHANGE-ME-IN-PRODUCTION` | yes (in prod) | `backend/app/auth/jwt.py` | HS256 signing key. **Must be rotated in prod** — `install.sh:58` generates a 32-byte hex key. |
| `JWT_ALGORITHM` | `HS256` | no | same | Signing algorithm. Don't change without changing all token consumers. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | no | same | Access-token lifetime. |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | no | same | Refresh-token lifetime. |

### Encryption

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `ENCRYPTION_KEY` | `CHANGE-ME-generate-with-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key` | yes (in prod) | `backend/app/encryption.py` | Fernet symmetric key. Used for connector credential encryption (and SMTP password encryption). **Lose this and every encrypted credential is unrecoverable** — Phase 5 will document backup/rotation. |

Generate a fresh key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Google Workspace OIDC (optional)

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `GOOGLE_CLIENT_ID` | `""` | only if Google SSO is used | `Settings.google_client_id` | OAuth 2.0 client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | `""` | only if Google SSO is used | `Settings.google_client_secret` | OAuth 2.0 client secret |
| `GOOGLE_REDIRECT_URI` | `https://app.getvul.app/auth/callback/google` | when Google SSO is used | `Settings.google_redirect_uri` | Must match exactly the redirect URI registered with Google |

### Azure Entra ID OIDC (optional)

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `AZURE_CLIENT_ID` | `""` | only if Azure SSO is used | `Settings.azure_client_id` | App registration client ID |
| `AZURE_CLIENT_SECRET` | `""` | only if Azure SSO is used | `Settings.azure_client_secret` | App registration client secret |
| `AZURE_REDIRECT_URI` | `https://app.getvul.app/auth/callback/azure` | when Azure SSO is used | `Settings.azure_redirect_uri` | Must match the redirect URI on the app registration |

### Connectors

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `SYNC_INTERVAL_MINUTES` | `15` | no | `Settings.sync_interval_minutes` | Default sync cadence for new connector configs (each connector can override). |

### Frontend (Next.js)

Only `NEXT_PUBLIC_*` variables are visible to the browser bundle.

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `NEXT_PUBLIC_API_URL` | `""` (empty in `next.config.js` fallback) | yes for non-localhost deploys | [frontend/src/lib/api.ts](../frontend/src/lib/api.ts), [frontend/src/lib/auth.tsx](../frontend/src/lib/auth.tsx) | Base URL of the FastAPI backend. In compose dev: `http://localhost:8000`. In CI: `http://backend:8000`. In production behind nginx: leave empty (relative `/api/`). |

> **Production gotcha** — the CSP in `next.config.js` allows `connect-src 'self' http://localhost:8000 https://*.getvul.app`. If your prod domain isn't `*.getvul.app`, update the CSP header **and** set `NEXT_PUBLIC_API_URL` accordingly, otherwise the browser silently blocks API calls.

### Postgres container

| Variable | Default | Required | Read by | What it does |
|----------|---------|----------|---------|--------------|
| `POSTGRES_USER` | `getvul` | no | `postgres:16-alpine` entrypoint | DB user for the local container |
| `POSTGRES_PASSWORD` | `getvul` | no | same | DB password (compose-only; ignored in cloud deploys with externally managed DBs) |
| `POSTGRES_DB` | `getvul` | no | same | DB name |

These are set in [docker-compose.yml:21-23](../docker-compose.yml#L21-L23) and the CI variant [docker-compose.ci.yml:5-7](../docker-compose.ci.yml#L5-L7).

## Where each component reads its config

```mermaid
flowchart LR
    subgraph "Sources"
        ENV[".env on the host"]
        COMPOSE["compose environment:"]
        OS[OS environment]
    end

    subgraph "Backend"
        SETTINGS["pydantic_settings.BaseSettings<br/>backend/app/config.py"]
        AUTH["auth/jwt.py<br/>JWT_SECRET_KEY, JWT_ALGORITHM, JWT_*_EXPIRE_*"]
        ENC["encryption.py<br/>ENCRYPTION_KEY"]
        OIDC["auth/providers.py<br/>GOOGLE_*, AZURE_*"]
        DB["db/session.py<br/>DATABASE_URL"]
        LIFE["main.py lifespan<br/>REDIS_URL, ENVIRONMENT"]
    end

    subgraph "Frontend"
        BUILD["next build<br/>(reads NEXT_PUBLIC_API_URL)"]
        APIJS["lib/api.ts<br/>fetch(NEXT_PUBLIC_API_URL + path)"]
    end

    ENV --> SETTINGS
    OS --> SETTINGS
    COMPOSE --> SETTINGS
    SETTINGS --> AUTH & ENC & OIDC & DB & LIFE

    COMPOSE --> BUILD
    OS --> BUILD
    BUILD --> APIJS
```

Source: [diagrams/configuration-flow.mmd](diagrams/configuration-flow.mmd).

## Generating production secrets

```bash
# JWT key — 32 random bytes, hex-encoded
openssl rand -hex 32

# Fernet key — 32 random bytes, base64 url-safe
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`install.sh:58-60` does this automatically when bootstrapping a fresh VM.

## Secret-management roadmap

Today: secrets live in `/opt/getvul/.env` on the host. No KMS integration. Phase 5 (PROD-05) will document backup/rotation and Phase 4 (PROD-04-05) will decide whether to wire AWS Secrets Manager or remove the unused config fields.
