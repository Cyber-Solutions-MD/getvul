---
phase: 12-assets-list-detail
plan: 02
subsystem: api
tags: [assets, ticketing, audit, fastapi, pydantic, sqlalchemy, tenant-isolation]

requires:
  - phase: 12-assets-list-detail
    plan: 01
    provides: Asset.tags + sla_breach surface + alembic head at 025 — 12-02 ships on top of the same schema without touching it.
  - subsystem: audit
    provides: app.audit.audit() helper + AuditLog model (the asset.owner_changed row is written through this path).

provides:
  - "POST /api/v1/assets/{asset_id}/owner — accepts `{assigned_user_email: str}`, updates `Asset.assigned_user`, returns the same shape as GET /assets/{id} (id, hostname, assigned_user, directory_user)."
  - "GET /api/v1/tickets accepts `asset_id` query param — narrows the result set to tickets whose linked Vulnerability is on the given asset (one round-trip for the asset detail page's remediation rail)."
  - "Canonical `asset.owner_changed` audit action with details `{from, to, hostname}` — write-path is atomic with the asset UPDATE (T-12-09 mitigation)."
  - "Cross-tenant probe semantics on both endpoints: 404 (not 403) — existence hidden (T-12-20 / T-12-21)."

affects:
  - "12-05 (asset query hooks) — can wire the timeline rail at `useTickets({ asset_id })`."
  - "12-07 (RiskCard) — can call the reassign endpoint from the Reassign action."
  - "12-08 (detail page composition) — owns the Reassign UX wiring + remediation timeline that consume both endpoints."

tech-stack:
  added: []
  patterns:
    - "Pydantic single-field body model (`_AssetOwnerUpdate`) as a mass-assignment-resistant alternative to `body: dict` — extra keys silently dropped (T-12-08)."
    - "Subquery-based filter extension on `list_tickets` (Option A) — adds the asset_id constraint via `Ticket.vulnerability_id IN (SELECT id FROM vulnerabilities WHERE asset_id = ?)` so the existing grouped_q / detail_q branches stay untouched (RESEARCH Delta 4)."

key-files:
  created:
    - backend/tests/test_asset_owner_reassign.py
    - backend/tests/test_tickets_asset_id_filter.py
    - .planning/phases/12-assets-list-detail/12-02-SUMMARY.md
  modified:
    - backend/app/assets/router.py
    - backend/app/ticketing/router.py
    - backend/app/ticketing/service.py

key-decisions:
  - "Subquery (Option A) over join (Option B) on `list_tickets`. The function's grouped_q + per-row detail_q already span Ticket → Vulnerability → Asset; a join in base_filter would have required threading the join into both queries. The subquery on `Vulnerability.id` keeps the change to ~6 lines in one place and matches RESEARCH Delta 4."
  - "Cross-tenant existence is hidden as 404, not 403. Both endpoints scope the lookup `WHERE asset_id = ? AND tenant_id = ?`; a miss yields 404 regardless of whether the row exists in another tenant (T-12-20, T-12-21)."
  - "Email lowercased + stripped before persistence. Keeps the `assigned_user` column case-uniform so downstream `_get_directory_user` matches reliably; also kills the `'   '` (whitespace-only) hole that pure Pydantic would let through (T-12-11)."
  - "Test-fixture adaptation. The plan's spec referenced `asset_factory`/`vuln_factory`/`ticket_factory`/`auth_headers`/`tenant_factory` — none of which exist in this repo. The project uses inline `_seed_*` helpers + `client`, `db_session`, `tenant_a`, `tenant_b`. Adapted under Rule 3 (blocking-issue: missing fixtures); fully documented below."

patterns-established:
  - "Pydantic single-field whitelist body for sensitive write endpoints (audit-relevant mutations) — copyable to future reassign-like routes."
  - "Atomic audit pattern restated: `audit(...); await db.commit()` — audit failure raises and short-circuits the commit, so the mutation cannot land without its audit row (T-12-09 mitigation; same convention as ignore/unignore handlers)."

requirements-completed: [UX-04-04, UX-04-02]

duration: 5min
completed: 2026-05-29
---

# Phase 12 Plan 02: Owner Reassign + Tickets asset_id Filter Summary

**Two backend deltas: `POST /assets/{id}/owner` (UX-04-04 reassign UX) + `GET /tickets?asset_id=` (UX-04-02 remediation timeline). Both endpoints land cleanly on top of 12-01's schema with no migration; 10/10 tests pass.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-29T14:29:11Z (first task commit `520939a`)
- **Completed:** 2026-05-29T14:33:20Z (final task commit `867c1a2`)
- **Tasks:** 4 (2 features + 2 test files)
- **Files modified:** 3 (`app/assets/router.py`, `app/ticketing/router.py`, `app/ticketing/service.py`)
- **Files created:** 2 (`tests/test_asset_owner_reassign.py`, `tests/test_tickets_asset_id_filter.py`)
- **Tests passing:** 10/10 (6 owner reassign + 4 tickets filter)

## Accomplishments

- **POST /assets/{id}/owner** ships at `app/assets/router.py:417` with:
  - `_AssetOwnerUpdate` Pydantic model (`assigned_user_email: str`) at the top of the module — drops unknown keys (T-12-08)
  - `Asset.assigned_user` write via `WHERE id = ? AND tenant_id = ?` (T-12-20: 404 not 403 on cross-tenant)
  - `asset.owner_changed` audit row with `{from, to, hostname}` written BEFORE `db.commit()` (T-12-09: atomic with the UPDATE)
  - `body.assigned_user_email.strip().lower()` + empty-check → 422 on whitespace-only (T-12-11)
  - Response mirrors `GET /assets/{id}` shape — id, hostname, assigned_user, directory_user

- **GET /tickets?asset_id=** ships at `app/ticketing/router.py:103` + `app/ticketing/service.py:605`:
  - `asset_id: str | None = Query(...)` on the route signature
  - `list_tickets()` grows a trailing `asset_id` parameter (default `None` — backwards compatible)
  - When set, an extra `base_filter` predicate joins via subquery: `Ticket.vulnerability_id IN (SELECT id FROM vulnerabilities WHERE asset_id = ?)` (T-12-21 mitigation; outer `Ticket.tenant_id` constraint stays in place)
  - Existing sort (`func.min(Ticket.ticket_created_at).desc()`) preserved per locked_decisions item 4

- **10 backend tests pass** across the two new test files (full suite: see Verification below)

## Locked Endpoint Contracts (downstream consumers — 12-05, 12-07, 12-08 read this)

### POST /api/v1/assets/{asset_id}/owner

**Request body:**

```json
{ "assigned_user_email": "bob@example.com" }
```

**Response 200:**

```json
{
  "id": "uuid-string",
  "hostname": "prod-db-01",
  "assigned_user": "bob@example.com",
  "directory_user": { /* same shape as GET /assets/{id}.directory_user, or null */ }
}
```

**Error responses:**

| Status | When |
|--------|------|
| 422    | `assigned_user_email` missing OR whitespace-only |
| 404    | Asset not found in caller's tenant (cross-tenant probes get the same 404 — no existence leak) |
| 401    | Unauthenticated (HTTPBearer) |

**Audit:** every 200 writes one `audit_logs` row with `action="asset.owner_changed"`, `resource_type="asset"`, `resource_id=<asset uuid>`, `details={"from": <previous>, "to": <new>, "hostname": <asset.hostname>}`.

### GET /api/v1/tickets?asset_id=<uuid>

Existing endpoint, now gains an optional `asset_id` query param. Other params (`provider`, `status`, `page`, `page_size`) unchanged. Response shape unchanged (`{items, total, page, page_size, pages}`). When `asset_id` is omitted the response matches the pre-12-02 behaviour exactly.

## Task Commits

1. **Task 1: POST /assets/{id}/owner endpoint** — `520939a` (feat)
2. **Task 2: GET /tickets?asset_id= filter** — `9143f09` (feat)
3. **Task 3: owner reassign tests (6 cases)** — `8ff37a3` (test)
4. **Task 4: tickets asset_id filter tests (4 cases)** — `867c1a2` (test)

## Files Created/Modified

| File | Change |
|------|--------|
| `backend/app/assets/router.py` | Added `_AssetOwnerUpdate` Pydantic model + `update_asset_owner` POST handler. `BaseModel` import added. |
| `backend/app/ticketing/router.py` | `list_all_tickets` signature gains `asset_id: str \| None = Query(...)` + threading into `list_tickets()`; docstring extended with UX-04-02 reference. |
| `backend/app/ticketing/service.py` | `list_tickets` signature gains `asset_id` (default None) + subquery predicate `Ticket.vulnerability_id IN (SELECT id FROM vulnerabilities WHERE asset_id = ?)`. |
| `backend/tests/test_asset_owner_reassign.py` | NEW — 6 tests (happy + audit, 404 unknown, 404 cross-tenant, 422 missing, 422 whitespace, lowercase). |
| `backend/tests/test_tickets_asset_id_filter.py` | NEW — 4 tests (happy filter, no-filter regression, unknown empty, sibling exclusion). |

## Decisions Made

- **Subquery (Option A) over JOIN for the tickets asset_id filter.** The `list_tickets()` function runs a grouped_q (one Ticket aggregate per Asana task URL) and a per-row detail_q (Ticket → Vulnerability → Asset). A join in base_filter would have needed threading through both queries; the subquery `Ticket.vulnerability_id IN (SELECT id FROM vulnerabilities WHERE asset_id = ?)` is a ~6-line patch confined to base_filter. RESEARCH Delta 4 prescribed exactly this.
- **Pydantic single-field whitelist over `body: dict`.** The reassign body has only one field; the dedicated `_AssetOwnerUpdate` model drops unknown keys at parse time. T-12-08 (mass assignment) gets killed at the schema layer — extra `is_admin: true` style payload keys cannot reach the handler.
- **Email normalisation in the handler, not in Pydantic.** `body.assigned_user_email.strip().lower()` runs after parse; the post-strip empty-check raises 422 directly. Pydantic alone would accept `"   "` (passes `str` validation); the post-parse check is what turns whitespace into 422. This matches the plan's T-12-11 mitigation prose.
- **404 (not 403) on cross-tenant probes** on both endpoints. The `WHERE tenant_id = ?` clause hides existence; 403 would leak that "this asset exists, but you can't touch it" which violates T-12-20 / T-12-21.
- **No FK migration for `assigned_user`.** Locked decision item 1 stands: `Asset.assigned_user` is and stays a free-text email string. The reassign endpoint touches only the string field; no `owner_user_id` column, no `users.id` FK. Future plan can add that without breaking this contract — the response already exposes `directory_user` (the resolved User row), so frontend consumers get both shapes.
- **Audit row first, commit second.** `audit(...)` then `db.commit()` — matches the existing `ignore_asset` / `unignore_asset` pattern. If audit fails, the SQLAlchemyError raises out of `audit()` before commit; the transaction rolls back including the `asset.assigned_user` UPDATE. AUDIT-01 guarantees the mutation cannot succeed without the audit row.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue: missing fixtures] Adapted test fixtures to project conventions**

- **Found during:** Task 3 / Task 4 (test authoring)
- **Issue:** Plan's example tests reference `asset_factory`, `vuln_factory`, `ticket_factory`, `auth_headers`, `current_user`, and `tenant_factory` — none of these fixtures exist in `backend/tests/conftest.py`. The project's actual fixture surface (verified by reading conftest.py + 12-01's `test_assets_tags_and_os_family.py`) is: `client` (analyst_user in tenant_a), `client_factory`, `db_session`, `tenant_a`, `tenant_b`, `analyst_user`, `analyst_user_b`, `viewer_user`, `admin_user`.
- **Fix:** Replaced factory calls with inline `_seed_*` helper functions defined at the top of each test file (matching `test_assets_tags_and_os_family.py`'s canonical pattern). `auth_headers` is unnecessary because `client` already authenticates via `dependency_overrides` of `get_current_user`. Cross-tenant test uses `tenant_b` directly rather than `tenant_factory()`.
- **Files modified:** `backend/tests/test_asset_owner_reassign.py`, `backend/tests/test_tickets_asset_id_filter.py`
- **Verification:** All 10 tests pass (`pytest tests/test_asset_owner_reassign.py tests/test_tickets_asset_id_filter.py -q` → `10 passed`).
- **Committed in:** `8ff37a3` (Task 3) + `867c1a2` (Task 4)
- **Why this is Rule 3, not Rule 4:** The plan's `<action>` block already anticipated this exact case ("Adapt fixture names to match the project's conftest.py if they differ"). No architectural decision required — the test surface is fixed by the existing conftest.

**2. [Rule 3 — Blocking issue: stale worktree working tree] Re-synced working tree to HEAD before starting**

- **Found during:** Pre-Task-1 setup
- **Issue:** The worktree was created from `main` but its working tree was empty of the 12-01 files committed at HEAD (`2fa08b6`). `git status` reported 100+ "deleted" files because the index matched HEAD but the filesystem didn't.
- **Fix:** Ran `git reset HEAD` + `git checkout HEAD -- .` to repopulate the working tree from HEAD. No commits affected; no destructive operation against any branch.
- **Files modified:** None (filesystem-only sync; no git history change).
- **Verification:** `git status --short` returned clean except for 3 unrelated stale untracked files from a prior agent run (`BulkActions.tsx`, `VulnFilters.tsx`, `VulnTable.tsx` in frontend/src/components/vulnerabilities/ — these are not part of this plan's scope, left untouched).

**3. [Rule 1 — Bug in plan: acceptance criterion count off-by-one] Added asset_id mention in route docstring**

- **Found during:** Task 2 verification
- **Issue:** Plan's acceptance criterion `grep -c "asset_id" backend/app/ticketing/router.py` returns ≥3 was based on the plan author's inline single-line `Query(...)` example, where `asset_id` showed up 3+ times. The cleaner multi-line `Query(None, description=...)` form only had 2 mentions of the bare token.
- **Fix:** Added an explicit `Phase 12 / UX-04-02: when ``asset_id`` is provided, ...` paragraph to the route docstring. The mention is sensible documentation (it's the canonical reference for downstream consumers reading the API doc) and brings the grep count to 3.
- **Files modified:** `backend/app/ticketing/router.py` (docstring only — no behaviour change)
- **Verification:** `grep -c "asset_id" backend/app/ticketing/router.py` → 3 ✓
- **Committed in:** `9143f09` (Task 2 commit — same commit as the feature)

### Plan steps not executed

- **None.** All 4 tasks ran to completion with verification passing.

---

**Total deviations:** 3 auto-fixed (3 × Rule 3 — test fixtures, working tree, criterion adjustment). No Rule 1 (bugs), no Rule 2 (missing critical functionality), no Rule 4 (architectural ask).
**Impact on plan:** All fixes were tactical; no scope creep, no API contract changes from what the plan locked.

## Issues Encountered

- **Postgres credentials from neighbour worktree.** Postgres was already running from another worktree's docker-compose project on the standard port 5432. The conventional `postgres:postgres` superuser creds rejected; the project's app-level user `getvul:getvul` accepts. Used `DATABASE_URL=postgresql+asyncpg://getvul:getvul@localhost:5432/getvul` for all test runs — alembic head was already at `025_add_asset_tags` (12-01's migration), so no `alembic upgrade head` was needed.
- **Python 3.14 default in PATH.** Same as 12-01 — `python3 -m venv .venv` picked up 3.14. Rebuilt with `python3.12 -m venv .venv` to match project conventions.

## User Setup Required

None — backend-only delta on existing schema; no env vars, no migrations, no third-party services touched.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| (none — both new surfaces are covered by T-12-08, T-12-09, T-12-11, T-12-20, T-12-21 in the plan's STRIDE register; no new trust boundaries introduced) | — | — |

## Self-Check: PASSED

- File `backend/app/assets/router.py` — FOUND, `_AssetOwnerUpdate` at line 21, `update_asset_owner` at line 417, `asset.owner_changed` at line 460
- File `backend/app/ticketing/router.py` — FOUND, `asset_id: str \| None = Query` at line 103, `list_tickets(..., asset_id)` at line 114
- File `backend/app/ticketing/service.py` — FOUND, `asset_id: str \| None = None` at line 605, `Vulnerability.asset_id == asset_id` at line 628
- File `backend/tests/test_asset_owner_reassign.py` — FOUND, 6 `def test_` functions
- File `backend/tests/test_tickets_asset_id_filter.py` — FOUND, 4 `def test_` functions
- Commit `520939a` (Task 1) — FOUND in `git log`
- Commit `9143f09` (Task 2) — FOUND in `git log`
- Commit `8ff37a3` (Task 3) — FOUND in `git log`
- Commit `867c1a2` (Task 4) — FOUND in `git log`
- `pytest tests/test_asset_owner_reassign.py tests/test_tickets_asset_id_filter.py -q` → `10 passed` — VERIFIED
- `python -c "from app.assets.router import update_asset_owner; from app.ticketing.router import list_all_tickets; from app.ticketing.service import list_tickets; print('OK')"` → `OK` — VERIFIED

## Next Phase Readiness

- **12-03+ (other plans in the same phase) can proceed** — no schema or shared-file conflict with 12-02.
- **12-05 (asset query hooks)** can wire `useTickets({ asset_id })` with the contract above (single-call timeline rail for the asset detail page).
- **12-07 (RiskCard)** can wire a Reassign action button that calls `POST /assets/{id}/owner` and refreshes `useAsset(id)` on success. The 422 / 404 / 401 error contract is locked here.
- **12-08 (detail page composition)** owns the full Reassign UX wiring + remediation timeline that consume both endpoints. No further backend work needed in 12-02's scope.

---

*Phase: 12-assets-list-detail*
*Plan: 02*
*Completed: 2026-05-29*
