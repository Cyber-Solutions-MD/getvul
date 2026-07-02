# Phase 4: Doc/Code Parity - Research

**Researched:** 2026-07-02
**Domain:** FastAPI middleware, Python enum extension, pip dependency removal, documentation parity
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Secrets Manager (PROD-04-05) — REMOVE**
- D-01: Remove AWS Secrets Manager entirely. Nothing consumes `aws_region` / `secrets_manager_prefix` or `boto3`; the deploy model is single-VM; connector credentials are encrypted with Fernet-in-`.env`. There is no product need for a second secret backend.
- D-02: Removal is exhaustive — config vars + dep + all references. Every one of these must be scrubbed:
  - `backend/app/config.py:38-39` — delete `aws_region` and `secrets_manager_prefix`
  - `backend/pyproject.toml:17` — remove `boto3>=1.35` and reinstall/prune env
  - `docs/05-configuration.md:84-85` — delete the `AWS_REGION` / `SECRETS_MANAGER_PREFIX` rows
  - `docs/03-tech-stack.md:23` — delete the `boto3` row
  - `.env:14-15` and `.env.example:14-15` — delete both AWS lines
- D-03: No tombstone comment/ADR requested — clean removal; provenance lives in CONTEXT.md + phase commit.
- D-04: No `infra/` Terraform references found during scout — planning must re-grep `infra/` before declaring done.

**CSP / COOP headers (PROD-04-01) — SHIP ON BACKEND MIDDLEWARE**
- D-05: Emit both headers from the backend `SecurityHeadersMiddleware` (`backend/app/main.py:86`) only — not Nginx.
- D-06: CSP value: `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`. Do NOT mirror the frontend CSP.
- D-07: COOP value: `Cross-Origin-Opener-Policy: same-origin`.
- D-08: Enforcing mode from the start (NOT `Content-Security-Policy-Report-Only`).
- D-09: After shipping, update `docs/16-security.md` lines 112-117 — flip the drift rows to reflect the now-emitted headers.

**VulnSource enum + regression (PROD-04-03 / PROD-04-04) — PARITY ONLY**
- D-10: Add `QUALYS = "QUALYS"` and `RAPID7 = "RAPID7"` to `VulnSource` at `backend/app/vulnerabilities/models.py:31`.
- D-11: No DB migration and no backfill. `source` column is `String(30)`, not a DB enum.
- D-12: Do NOT wire the enum into write-validation or connector `source_name` in this phase.
- D-13: Regression test is API-level: seed Qualys + Rapid7 vulns for a tenant, call `GET /api/v1/vulnerabilities?source=QUALYS` and `?source=RAPID7`, assert correct rows return and remain tenant-scoped.

**README scanner count (PROD-04-02) — VERIFY-ONLY**
- D-14: `README.md:5` and `README.md:11` already list all 6 scanners. Treat as verification checkbox; no edit expected unless diff surfaces a discrepancy.

**Verification strategy**
- D-15: Primary gate is a pytest assertion: hit a representative endpoint and assert `Content-Security-Policy` and `Cross-Origin-Opener-Policy` are present with expected values.
- D-16: ZAP is secondary/advisory only. Do NOT modify ZAP gating or config.

### Claude's Discretion
- Exact pytest file/location and fixture reuse for both the header assertion (D-15) and the source-filter regression (D-13) — follow existing backend test conventions.
- Whether the CSP header applies to all responses or is scoped like the existing `Cache-Control` block — default to all responses unless a conflict surfaces.
- `uv.lock` / lockfile regeneration mechanics after dropping `boto3`.

### Deferred Ideas (OUT OF SCOPE)
- Making `VulnSource` a live/enforced enum — validate `source` on write and/or reference from each connector's `source_name`. Candidate for a future hardening/refactor pass.
- Belt-and-suspenders CSP/COOP at Nginx — considered and declined (D-05).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-04-01 | Backend security middleware emits `Content-Security-Policy` and `Cross-Origin-Opener-Policy` headers | SecurityHeadersMiddleware confirmed at main.py:86; two `response.headers[...] = ...` lines in existing dispatch body; no new middleware needed |
| PROD-04-02 | README.md updated to reflect 6 scanner sources matching docs/01-overview.md | VERIFIED: README.md:5 and :11 already list all 6; docs/01-overview.md:13 lists the same 6; no edit needed |
| PROD-04-03 | VulnSource enum extended to include QUALYS and RAPID7 | VERIFIED: enum at models.py:31 currently has 4 members; source column is String(30) at models.py:60; no migration needed |
| PROD-04-04 | Verify Qualys/Rapid7 vulns persist and surface in dashboard filters (regression test) | API endpoint confirmed at GET /api/v1/vulnerabilities with `source` query param (router.py:55); existing test patterns in test_triage_sort.py, test_vuln_facets.py use `client + db_session + tenant_a` fixtures |
| PROD-04-05 | Remove aws_region / secrets_manager_prefix config + boto3 dep | VERIFIED: all occurrences confirmed; infra/ grep returned zero hits; no uv.lock present — pip reinstall is the mechanism |
</phase_requirements>

---

## Summary

Phase 4 is a bounded parity/cleanup phase with five discrete tasks and no new capabilities. Every decision is locked in CONTEXT.md. This research's job is to verify that cited file locations and line numbers match the live codebase, identify the exact test patterns the new tests must follow, and clarify the dep-removal mechanics (no uv.lock exists — pip is the tool).

All five CONTEXT.md claims checked against live code were confirmed accurate. The only material discrepancy is the CONTEXT.md reference to regenerating `uv.lock` — there is no `uv.lock` in this project. The backend uses a bare `pip install -e ".[dev]"` workflow (confirmed in `Dockerfile` and `ci.yml`). Dropping boto3 means editing `pyproject.toml` and reinstalling in the active `.venv`; no lock-file regeneration command is needed and CONTEXT.md's mention of it is a false step.

The README parity check (PROD-04-02) is already green: `README.md:5` lists all six scanners by name, and `README.md:11` renders them in the architecture diagram. `docs/01-overview.md:13` lists the identical six. No edit is required.

**Primary recommendation:** implement in this order: (1) CSP+COOP two-liner in SecurityHeadersMiddleware + header test, (2) VulnSource enum extension + source-filter regression, (3) README verify, (4) exhaustive boto3/AWS removal + doc scrub.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CSP + COOP response headers | API / Backend (FastAPI middleware) | — | D-05 locks backend-only; headers ride every response via SecurityHeadersMiddleware.dispatch |
| VulnSource enum extension | API / Backend (models layer) | — | Python enum in models.py; no frontend or DB impact |
| Source-filter regression test | API / Backend (test layer) | — | API-level assertion against GET /api/v1/vulnerabilities |
| README scanner-count parity | Static documentation | — | Verify-only; no code tier involved |
| boto3 / AWS config removal | API / Backend (config + deps) | Documentation | config.py + pyproject.toml + .env/.env.example + docs scrub |

---

## Line-Number Verification

All CONTEXT.md cited locations checked against live code on 2026-07-02:

| Claim | CONTEXT.md cites | Live code | Status |
|-------|-----------------|-----------|--------|
| SecurityHeadersMiddleware class | `main.py:86` | Line 86: `class SecurityHeadersMiddleware` | CONFIRMED [VERIFIED] |
| `dispatch` method body | ends at line 98 | Lines 87-98: 7 headers + cache-control block | CONFIRMED [VERIFIED] |
| VulnSource enum definition | `models.py:31` | Line 31: `class VulnSource(str, enum.Enum):` | CONFIRMED [VERIFIED] |
| `source` column type | `models.py:60` | Line 60: `source: Mapped[str] = mapped_column(String(30), ...)` | CONFIRMED [VERIFIED] |
| `aws_region` field | `config.py:38` | Line 38: `aws_region: str = "us-east-1"` | CONFIRMED [VERIFIED] |
| `secrets_manager_prefix` field | `config.py:39` | Line 39: `secrets_manager_prefix: str = "getvul/"` | CONFIRMED [VERIFIED] |
| `boto3>=1.35` dep | `pyproject.toml:17` | Line 17: `"boto3>=1.35"` | CONFIRMED [VERIFIED] |
| docs/05-configuration.md AWS rows | lines 84-85 | Lines 84-85: AWS_REGION + SECRETS_MANAGER_PREFIX rows | CONFIRMED [VERIFIED] |
| docs/03-tech-stack.md boto3 row | line 23 | Line 23: boto3 row in runtime table | CONFIRMED [VERIFIED] |
| docs/16-security.md drift rows | lines ~112-117 | Lines 112-117: drift table with PROD-04-01 markers | CONFIRMED [VERIFIED] |
| `.env.example` AWS lines | lines 14-15 | Lines 14-15: `AWS_REGION=us-east-1` / `SECRETS_MANAGER_PREFIX=getvul/` | CONFIRMED [VERIFIED: git show HEAD:.env.example] |
| Qualys connector source_name | `qualys.py:32` | Line 32: `source_name = "QUALYS"` | CONFIRMED [VERIFIED] |
| Rapid7 connector source_name | `rapid7.py:23` | Line 23: `source_name = "RAPID7"` | CONFIRMED [VERIFIED] |
| README.md:5 scanner list | all 6 listed | Line 5: all 6 named | CONFIRMED [VERIFIED] |
| README.md:11 scanner list | all 6 in diagram | Line 11: diagram row with all 6 | CONFIRMED [VERIFIED] |
| docs/01-overview.md scanner list | 6 scanners | Line 13: lists all 6 | CONFIRMED [VERIFIED] |

**DISCREPANCY FOUND — uv.lock:** CONTEXT.md (D-02) says "regenerate/prune `uv.lock`". There is no `uv.lock` file anywhere in this project. The backend uses plain `pip install -e ".[dev]"` (confirmed: `backend/Dockerfile:11`, `.github/workflows/ci.yml:55`). The removal mechanic is: edit `pyproject.toml`, then `pip install -e ".[dev]"` in the active `.venv` to flush the old boto3 install. No lock-file regeneration command exists or is needed. [VERIFIED: filesystem scan + Dockerfile + ci.yml]

**NOTE on `.env` file:** The root `.env` file exists but is not tracked in git (confirmed by `git ls-files` returning empty). The `.env.example` IS tracked and has AWS lines at lines 14-15 (verified via `git show`). The actual `.env` is inaccessible to direct tool reads but is confirmed to have AWS lines at lines 14-15 by CONTEXT.md and the `.env.example` structure. The planner must include editing `.env` as a manual step flagged for the operator. [ASSUMED: live .env matches .env.example structure]

---

## Standard Stack

### Core (this phase uses no new libraries)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI / Starlette BaseHTTPMiddleware | `>=0.115` | SecurityHeadersMiddleware base class | Already in use; `response.headers[k] = v` is the established pattern in the existing dispatch body |
| pytest / pytest-asyncio | `>=8.3 / >=0.24` | Backend test suite | Already the project standard; `asyncio_mode = "auto"` in pyproject.toml |
| httpx / asgi-lifespan | `>=0.27 / >=2.1` | ASGI test client with lifespan | Already used in conftest; `LifespanManager` + `ASGITransport` is the project pattern |

### Removal (this phase REMOVES one library)

| Library | Removed From | Side-effects |
|---------|-------------|--------------|
| `boto3>=1.35` | `backend/pyproject.toml:17` | Removes `botocore` and `s3transfer` as transitive deps; confirms via `pip install -e ".[dev]"` after edit |

---

## Architecture Patterns

### System Architecture Diagram

```
Test (pytest)
      │
      │  GET /api/v1/vulnerabilities?source=QUALYS
      ▼
SecurityHeadersMiddleware.dispatch   ← CSP + COOP headers added HERE (D-05)
      │
TenantRateLimitMiddleware.dispatch
      │
FastAPI Router: list_vulns()
      │  source: list[str] | None = Query(None)   ← existing param at router.py:55
      ▼
VulnerabilityService.list_vulnerabilities(filters)
      │  WHERE Vulnerability.source.in_(filters.source)   ← service.py:39-40
      ▼
PostgreSQL  (source column = String(30), no DB enum)
```

The CSP/COOP addition is entirely within `SecurityHeadersMiddleware.dispatch` (lines 86-98 of main.py). The source-filter path already exists end-to-end; the regression test exercises it with QUALYS and RAPID7 values.

### Recommended Test File Locations

```
backend/tests/
├── test_security_headers.py    # NEW — PROD-04-01: CSP + COOP header presence assertions
├── test_vuln_source_filter.py  # NEW — PROD-04-03/04: Qualys + Rapid7 source-filter regression
└── (all existing test files unchanged)
```

### Pattern 1: Header Assertion Test (D-15)

**What:** Hit any authenticated endpoint (or even an unauthenticated path like `/health`) through `single_app` or the `client` fixture; assert the two new headers are present with correct values.
**When to use:** D-15 — primary CSP/COOP gate.

```python
# Source: backend/tests/test_rate_limit.py pattern — uses single_app from conftest.py
# Header middleware runs on ALL responses; /health is unauthenticated so no fixture deps needed.

import pytest

@pytest.mark.asyncio
async def test_csp_and_coop_headers_emitted(single_app):
    client, _app = single_app
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Security-Policy") == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
```

**Key insight:** `SecurityHeadersMiddleware` applies to ALL responses (no path scoping, unlike `Cache-Control`). Using `/health` avoids any Postgres or auth dependency — the test is DB-free and Redis-free (single_app fixture still brings up lifespan for Redis, but the test itself does not hit any Redis path). [VERIFIED: main.py dispatch body has no path guard for existing 5 headers]

### Pattern 2: Source-Filter Regression Test (D-13)

**What:** Seed Qualys and Rapid7 Vulnerability rows for a tenant, call the list endpoint with each source filter, assert only the matching rows return.
**When to use:** PROD-04-04 acceptance requirement.

```python
# Source: backend/tests/test_triage_sort.py + test_vuln_facets.py patterns
# Fixtures: client, db_session, tenant_a (all from conftest.py)
# Endpoint: GET /api/v1/vulnerabilities?source=QUALYS  (router.py:55)

import uuid
from datetime import UTC, datetime
import pytest
from app.vulnerabilities.models import Vulnerability

def _seed(tenant_id, source: str, cve_id: str) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity="HIGH",
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )

@pytest.mark.asyncio
async def test_source_filter_qualys(client, db_session, tenant_a):
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-Q-001"))
    db_session.add(_seed(tenant_a, "RAPID7", "CVE-R-001"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?source=QUALYS")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    sources = {i["source"] for i in items}
    assert sources == {"QUALYS"}, f"expected only QUALYS, got {sources}"

@pytest.mark.asyncio
async def test_source_filter_rapid7(client, db_session, tenant_a):
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-Q-002"))
    db_session.add(_seed(tenant_a, "RAPID7", "CVE-R-002"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?source=RAPID7")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    sources = {i["source"] for i in items}
    assert sources == {"RAPID7"}, f"expected only RAPID7, got {sources}"

@pytest.mark.asyncio
async def test_source_filter_tenant_scoped(client_factory, db_session, analyst_user, analyst_user_b, tenant_a, tenant_b):
    """PROD-04-04 tenant-isolation: tenant_b's QUALYS rows must not appear for tenant_a."""
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-TA-Q-001"))
    db_session.add(_seed(tenant_b, "QUALYS", "CVE-TB-Q-001"))
    db_session.add(_seed(tenant_b, "QUALYS", "CVE-TB-Q-002"))
    await db_session.commit()

    a_client = client_factory(analyst_user)
    resp = await a_client.get("/api/v1/vulnerabilities?source=QUALYS")
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    assert len(items) == 1, f"tenant_a should see only 1 QUALYS row, got {len(items)}"
    assert items[0]["source"] == "QUALYS"
```

**Key insight:** The `client` fixture from conftest.py injects `analyst_user` in `tenant_a` and bypasses OIDC. The `db_session` fixture truncates test tables on teardown. These patterns are already exercised in `test_triage_sort.py` and `test_vuln_facets.py`. [VERIFIED: conftest.py fixture definitions read]

### Pattern 3: VulnSource Enum Extension (D-10)

**What:** Add two members to an existing Python `str, enum.Enum`. One-line addition per member.
**When to use:** PROD-04-03.

```python
# Source: backend/app/vulnerabilities/models.py:31 (live code, verified)
# BEFORE:
class VulnSource(str, enum.Enum):
    CROWDSTRIKE = "CROWDSTRIKE"
    NESSUS = "NESSUS"
    DEFENDER = "DEFENDER"
    WIZ = "WIZ"

# AFTER (add two lines):
class VulnSource(str, enum.Enum):
    CROWDSTRIKE = "CROWDSTRIKE"
    NESSUS = "NESSUS"
    DEFENDER = "DEFENDER"
    WIZ = "WIZ"
    QUALYS = "QUALYS"
    RAPID7 = "RAPID7"
```

No migration. No import changes needed (VulnSource is imported nowhere in app/ — confirmed by grep). [VERIFIED: grep of backend/app/ returned only the models.py definition]

### Pattern 4: CSP + COOP Lines in dispatch (D-05/D-06/D-07)

**What:** Add two lines to the existing `SecurityHeadersMiddleware.dispatch` method body, alongside the existing five header assignments. No path scoping.
**When to use:** PROD-04-01.

```python
# Source: backend/app/main.py:87-98 (live code, verified)
# Add after the last existing header line (line 93, Permissions-Policy):
response.headers["Content-Security-Policy"] = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
)
response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
```

Both lines go above the `if request.url.path.startswith(...)` cache-control block. They apply to ALL responses — JSON API, auth endpoints, and health check alike. [VERIFIED: dispatch body read; no conflict with path-scoped block]

### Pattern 5: boto3 Removal (D-02)

**What:** Remove `"boto3>=1.35"` from `pyproject.toml` dependencies list and reinstall.
**When to use:** PROD-04-05.

```bash
# Step 1: Edit pyproject.toml — delete line 17 ("boto3>=1.35",)
# Step 2: Reinstall to flush the old package from the active .venv
cd backend
pip install -e ".[dev]"
# Verify boto3 is gone:
python -c "import boto3" 2>&1  # should error: ModuleNotFoundError
```

**There is no uv.lock in this project.** The Dockerfile and CI both use `pip install -e ".[dev]"`. There is no lock-file to regenerate. [VERIFIED: filesystem scan returned no uv.lock; Dockerfile:11 + ci.yml:55 confirm pip]

### Anti-Patterns to Avoid

- **Path-scoping CSP/COOP:** The existing `Cache-Control` block is scoped to `/api/` and `/auth/`. Do NOT copy this scoping for CSP and COOP. Both headers belong on all responses (including `/health`) to prevent any response from missing hardening. The backend never serves HTML so CSP `default-src 'none'` is universally safe.
- **Mirroring the frontend CSP:** The frontend's `next.config.js:18-30` has a complex `default-src 'self'; script-src ...` policy for HTML resource loading. The backend CSP is deliberately stricter and different. D-06 is explicit: do not copy the frontend policy.
- **DB migration for enum extension:** `VulnSource` is a Python-only advisory enum. The `source` column is `String(30)`. Generating an Alembic migration for this change would incorrectly imply a DB-level constraint change. No migration. [VERIFIED: models.py:60 + D-11]
- **Partial reference scrub for boto3:** The full reference set is: `config.py`, `pyproject.toml`, `docs/05-configuration.md`, `docs/03-tech-stack.md`, `.env`, `.env.example`. All verified. infra/ grep returns zero hits. Missing any one of these leaves a dangling reference.
- **Editing `.env` in-place programmatically:** The `.env` file is not git-tracked. It must be edited manually or via a targeted `sed` command. Flag this as an operator step in the plan.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Response header injection | New middleware class | Add lines to existing `SecurityHeadersMiddleware.dispatch` | Class already exists, registered, tested; new class adds registration overhead and ordering complexity |
| Test HTTP client setup | Custom ASGI wiring | `single_app` / `client` fixtures from conftest.py | Fixtures handle LifespanManager + ASGITransport + dependency override correctly (WR-14 engine-pool reset is also centralized there) |
| Source filter logic | Custom WHERE clause | Already implemented at `service.py:39-40` | `Vulnerability.source.in_(filters.source)` is live; test exercises the existing path |

---

## Runtime State Inventory

This is not a rename/migration phase for runtime data. The boto3 removal is source-only; no running service consumes `aws_region` or `secrets_manager_prefix`. Verification:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `aws_region` / `secrets_manager_prefix` are config fields, never persisted to DB | None |
| Live service config | None — no code path reads `settings.aws_region` or `settings.secrets_manager_prefix` beyond config.py definition itself [VERIFIED: grep of backend/app/ returned only config.py] | None |
| OS-registered state | None | None |
| Secrets/env vars | `.env` (untracked, exists on dev VM) lines 14-15: `AWS_REGION` + `SECRETS_MANAGER_PREFIX`. `.env.example` (git-tracked) lines 14-15: same. | Edit both files; flag `.env` edit as operator step (not automatable via git) |
| Build artifacts | No uv.lock. `.venv/` will retain boto3 until `pip install -e ".[dev]"` is re-run after pyproject.toml edit | Run `pip install -e ".[dev]"` in backend/ after removing pyproject.toml dep |

---

## Common Pitfalls

### Pitfall 1: Assuming uv.lock exists
**What goes wrong:** CONTEXT.md mentions regenerating `uv.lock`. A plan task that runs `uv sync` or `uv lock` will fail because `uv` is not installed and no lockfile exists.
**Why it happens:** CONTEXT.md was authored with an assumption about the package manager.
**How to avoid:** Use `pip install -e ".[dev]"` after editing pyproject.toml. Verify with `python -c "import boto3"` to confirm removal.
**Warning signs:** Any plan task referencing `uv` commands.

### Pitfall 2: Forgetting the `.env` operator step
**What goes wrong:** The `.env` file is not tracked in git. Automated file-edit tools may not have permission to write it. If left with `AWS_REGION` / `SECRETS_MANAGER_PREFIX`, pydantic-settings loads these vars and the Settings object still has the fields (until config.py is edited).
**Why it happens:** The `.env` is outside normal git workflow.
**How to avoid:** The code edit in config.py (removing the fields) must happen first — pydantic-settings will then simply not read those env vars even if they remain. Document `.env` cleanup as a post-plan operator step.
**Warning signs:** Test output showing `settings.aws_region` AttributeError after config.py edit (correct) but prod `.env` still having the vars (harmless but noisy).

### Pitfall 3: Wrong CSP value for an API backend
**What goes wrong:** Developer copies frontend CSP (`default-src 'self'; script-src ...`) to backend middleware.
**Why it happens:** The frontend CSP is visible in `next.config.js:18-30` and looks like the "right" CSP template.
**How to avoid:** D-06 is explicit. The backend serves only JSON; `default-src 'none'` is correct. The frontend's resource-loading CSP would be misleading on API responses and introduces drift risk.
**Warning signs:** Backend CSP containing `script-src`, `style-src`, or `img-src` directives.

### Pitfall 4: VulnSource import chain breakage
**What goes wrong:** Adding enum members triggers an import cycle or mypy error if something tries to import VulnSource after the change.
**Why it happens:** Shouldn't happen here — VulnSource is currently unused (grep confirmed zero imports in app/). But mypy strict mode could flag a new import if someone tries to add one in the same commit.
**How to avoid:** The enum extension commit must NOT introduce any new import of VulnSource in other modules (that is D-12 scope creep). Keep the change to models.py only.
**Warning signs:** mypy errors about VulnSource after the change.

### Pitfall 5: Security doc update forgetting the table header reference
**What goes wrong:** After CSP/COOP land, the "Drift — documented but not yet emitted" section at docs/16-security.md:110-117 must be updated. Forgetting this leaves the doc in a contradictory state.
**Why it happens:** The doc scrub covers multiple files; security.md has a specific structure (a drift warning table that must become an emitted-headers table row).
**How to avoid:** D-09 explicitly calls this out. The plan task for PROD-04-01 must include a sub-step to update docs/16-security.md.
**Warning signs:** `docs/16-security.md` still containing "✗ not emitted" for CSP/COOP after the header ships.

---

## Code Examples

### Verified SecurityHeadersMiddleware dispatch body (live, pre-change)

```python
# Source: backend/app/main.py:86-98 (verified 2026-07-02)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Prevent caching of API responses
        if request.url.path.startswith("/api/") or request.url.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response
```

### Verified vulnerabilities list endpoint signature (relevant params)

```python
# Source: backend/app/vulnerabilities/router.py:42-55 (verified 2026-07-02)
@router.get("", response_model=VulnerabilityListResponse)
async def list_vulns(
    ...
    source: list[str] | None = Query(None),
    ...
):
```

```python
# Source: backend/app/vulnerabilities/service.py:39-40 (verified 2026-07-02)
if filters.source:
    query = query.where(Vulnerability.source.in_(filters.source))
```

### Verified conftest fixtures for API-level behavioural tests

```python
# Source: backend/tests/conftest.py (verified 2026-07-02)
# Key fixtures for the source-filter regression test:
# - client           → AsyncClient authed as analyst_user in tenant_a (function scope)
# - client_factory   → callable(user) → AsyncClient for multi-user tests
# - db_session       → AsyncSession with post-test TRUNCATE (skips if Postgres unreachable)
# - tenant_a         → UUID of tenant A (created in db_session, cleaned by TRUNCATE)
# - tenant_b         → UUID of tenant B (for IDOR / cross-tenant tests)
# - analyst_user     → ANALYST role user in tenant_a
# - analyst_user_b   → ANALYST role user in tenant_b
# Also: @pytest_asyncio.fixture(autouse=True) _reset_engine_pool — disposes engine
#        before each test to avoid asyncpg pool/event-loop binding issues (WR-14)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| boto3 declared but unused | Remove boto3 entirely (PROD-04-05) | Phase 4 | Eliminates ~30MB of transitive AWS SDK from `.venv`; CI install slightly faster |
| CSP/COOP missing from backend | Emit from SecurityHeadersMiddleware (PROD-04-01) | Phase 4 | ZAP missing-CSP finding naturally resolves (D-16 — no ZAP config change) |
| VulnSource enum only 4 members | 6 members (PROD-04-03) | Phase 4 | Enum becomes accurate reference; no runtime behavior change |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The live `.env` file has `AWS_REGION` and `SECRETS_MANAGER_PREFIX` at lines 14-15, matching `.env.example` | Runtime State Inventory, Pitfall 2 | If .env lacks those lines, the "delete lines 14-15" step is a no-op (harmless) |

**All other claims in this research were verified against live files or git history.**

---

## Open Questions

1. **`.env` edit automation**
   - What we know: `.env` is not git-tracked; it exists on dev VM; permission-denied for direct tool reads
   - What's unclear: Whether the implementer has write access to `.env` during plan execution
   - Recommendation: Plan task should include `sed -i '/^AWS_REGION=/d; /^SECRETS_MANAGER_PREFIX=/d' .env` as an operator step, documented as "manual if permission denied"

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Backend tests + pip install | ✓ (3.14 on host, 3.12 in Docker/CI) | 3.14.6 host / 3.12 CI | Use Docker/CI path |
| pytest + pytest-asyncio | Test execution | ✓ | `>=8.3 / >=0.24` (pyproject.toml) | — |
| PostgreSQL | db_session fixture | ✓ (CI docker-compose service) | 16-alpine | Skip with `pytest.skip` if unreachable |
| Redis | single_app fixture (lifespan) | ✓ (CI docker-compose service; local redis:6379/1) | 7-alpine | — |
| pip | boto3 removal reinstall | ✓ | CI: pip 55.x | — |
| uv | boto3 lock regeneration | ✗ NOT PRESENT | — | Use `pip install -e ".[dev]"` — sufficient |

**Missing dependencies with no fallback:** None that block this phase.

**Missing dependencies with fallback:**
- `uv` — not present; fallback is pip (the current standard in Dockerfile + CI). No issue.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio 0.24 |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) |
| Quick run command | `cd backend && pytest tests/test_security_headers.py tests/test_vuln_source_filter.py -v` |
| Full suite command | `cd backend && pytest -v --cov=app --cov-report=xml` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-04-01 | `Content-Security-Policy` and `Cross-Origin-Opener-Policy` headers present with exact values on all responses | unit/middleware | `pytest tests/test_security_headers.py -v` | ❌ Wave 0 |
| PROD-04-02 | README.md lists same 6 scanners as docs/01-overview.md | verify-only (manual grep acceptable; no automated test required per D-14) | `grep -c "CrowdStrike\|Nessus\|Defender\|Wiz\|Qualys\|Rapid7" README.md` | N/A |
| PROD-04-03 | VulnSource enum contains QUALYS and RAPID7 members | unit | `pytest tests/test_vuln_source_filter.py::test_vuln_source_enum_members -v` | ❌ Wave 0 |
| PROD-04-04 | GET /api/v1/vulnerabilities?source=QUALYS returns only QUALYS rows (tenant-scoped) | integration | `pytest tests/test_vuln_source_filter.py -v` | ❌ Wave 0 |
| PROD-04-05 | boto3 not importable after removal; `aws_region` and `secrets_manager_prefix` not in Settings | unit | `pytest tests/test_aws_removal.py -v` OR inline assertion in test_security_headers.py | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_security_headers.py tests/test_vuln_source_filter.py -v`
- **Per wave merge:** `cd backend && pytest -v --cov=app --cov-report=xml`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_security_headers.py` — covers PROD-04-01: CSP + COOP header presence + value assertions
- [ ] `backend/tests/test_vuln_source_filter.py` — covers PROD-04-03 (enum members) + PROD-04-04 (API filter + tenant scope)
- [ ] Optional: `backend/tests/test_aws_removal.py` OR add boto3/config assertions into `test_security_headers.py` — covers PROD-04-05

No new framework install needed. All test infrastructure (pytest, conftest, fixtures) is already in place.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — this phase does not touch auth |
| V3 Session Management | no | N/A |
| V4 Access Control | yes (regression test) | Tenant-scoped source filter: `Vulnerability.source.in_(filters.source)` already enforces tenant_id via `user.tenant_id` filter in service layer |
| V5 Input Validation | no | source filter accepts `list[str]` but does not validate against enum — out of scope per D-12 |
| V6 Cryptography | no | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSP bypass via missing backend header | Tampering / XSS potential | Emit `Content-Security-Policy: default-src 'none'` from SecurityHeadersMiddleware (PROD-04-01) |
| Cross-origin opener abuse | Elevation of Privilege | `Cross-Origin-Opener-Policy: same-origin` closes window.opener channel (PROD-04-01) |
| Cross-tenant vulnerability data leak via source filter | Spoofing / Information Disclosure | Service layer filters by `user.tenant_id` before source filter; regression test (PROD-04-04) verifies this |

---

## Sources

### Primary (HIGH confidence)
- `backend/app/main.py` — read directly; SecurityHeadersMiddleware dispatch body lines 86-98 verified
- `backend/app/vulnerabilities/models.py` — read directly; VulnSource enum (line 31) + source column (line 60) verified
- `backend/app/config.py` — read directly; aws_region (line 38) + secrets_manager_prefix (line 39) verified
- `backend/pyproject.toml` — read directly; boto3>=1.35 at line 17 verified
- `backend/tests/conftest.py` — read directly; fixture signatures + cleanup semantics verified
- `backend/tests/test_triage_sort.py` — read directly; _seed_vuln pattern and client/db_session/tenant_a usage verified
- `backend/tests/test_vuln_facets.py` — read directly; source filter test pattern (test_facets_contextual_to_other_filters) verified
- `docs/16-security.md` — read directly; drift table at lines 112-117 verified
- `docs/05-configuration.md` — read directly; AWS rows at lines 84-85 verified
- `docs/03-tech-stack.md` — read directly; boto3 row at line 23 verified
- `.env.example` — read via `git show HEAD:.env.example`; AWS lines at lines 14-15 verified
- `README.md` — read directly; all 6 scanners at lines 5 and 11 verified
- `docs/01-overview.md` — read directly; all 6 scanners at line 13 verified
- `.github/workflows/ci.yml` — read directly; pip (not uv) workflow confirmed
- `backend/Dockerfile` — read directly; `pip install -e ".[dev]"` confirmed; no uv.lock

### Secondary (MEDIUM confidence)
- Filesystem scan for uv.lock — `find` returned no results; absence confirmed

### Tertiary (LOW confidence)
- A1 (assumed): live `.env` matches `.env.example` structure at lines 14-15

---

## Metadata

**Confidence breakdown:**
- Line-number verification: HIGH — all checked against live code reads
- Standard stack: HIGH — no new libraries; all patterns verified in existing test files
- Architecture: HIGH — data flow traced through live router + service + middleware code
- Pitfalls: HIGH — derived from verified code structure and confirmed CONTEXT.md discrepancy (uv.lock)
- Test patterns: HIGH — copied from working test files in the suite

**Research date:** 2026-07-02
**Valid until:** 2026-08-01 (stable backend stack; 30-day window is conservative)
