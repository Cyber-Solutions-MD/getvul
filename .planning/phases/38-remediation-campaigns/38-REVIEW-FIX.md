---
phase: 38-remediation-campaigns
fixed_at: 2026-08-18T10:30:00Z
review_path: .planning/phases/38-remediation-campaigns/38-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 38: Code Review Fix Report

**Fixed at:** 2026-08-18T10:30:00Z
**Source review:** .planning/phases/38-remediation-campaigns/38-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (1 critical, 3 warnings — `fix_scope: critical_warning`)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Bulk-assign has no guard against a closed campaign — real tickets get created and vulnerabilities get mutated after "Close campaign"

**Files modified:** `backend/app/campaigns/router.py`, `frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx`
**Commit:** `4340581`
**Applied fix:** Added `if campaign.closed_at is not None: raise HTTPException(409, ...)` to `bulk_assign_campaign`, right after `_get_campaign_or_404`, exactly as the review suggested. On the frontend, `canCreateTickets` now reads `unticketedCount > 0 && c.status !== 'COMPLETE'`, matching the existing gate already used on the "Close campaign" button below it.
**Verification:** Re-read both files (Tier 1); `python3 -c "import ast; ast.parse(...)"` clean on router.py (Tier 2); `npx tsc --noEmit -p tsconfig.json` clean, no errors in the touched file (Tier 2); ran `backend/tests/test_campaigns.py` — 24/24 passed.

### WR-01: `POST /{campaign_id}/close` is not idempotent — re-closing overwrites `closed_at`/`close_trigger` and writes a duplicate audit row

**Files modified:** `backend/app/campaigns/router.py`
**Commit:** `26c8436`
**Applied fix:** Added `if campaign.closed_at is not None: raise HTTPException(409, "Campaign is already closed.")` at the top of `close_campaign`, before any mutation. Checked the frontend `useCloseCampaign` mutation hook (`use-campaign-mutations.ts`) — it already has a generic error toast (`"Couldn't close campaign — try again."`) on any non-2xx response, so no frontend change was needed to surface the new 409 cleanly. Checked `test_campaigns.py` for any test that calls close twice expecting 200/200 — none exists, so the guard doesn't regress existing coverage.
**Verification:** Re-read file (Tier 1); AST syntax check clean (Tier 2); `test_campaigns.py` — 24/24 passed (Tier 2/functional).

### WR-02: Per-owner ticket-creation loop has no exception isolation — one owner's failure discards tickets already created for earlier owners in the same run

**Files modified:** `backend/app/campaigns/service.py`
**Commit:** `9eeff29`
**Applied fix:** Wrapped the `client.create(...)` call in `bulk_create_campaign_tickets`'s per-owner loop in `try/except Exception: url = None`, matching the existing graceful-`None` `failed_owners.append(...); continue` contract, exactly as the review suggested. No logging call was added since this module has no logger precedent (checked imports — no `structlog`/`logging` usage anywhere in `campaigns/service.py`); kept the fix minimal and consistent with local style.
**Verification:** Re-read file (Tier 1); AST syntax check clean (Tier 2); `test_campaigns.py` — 24/24 passed (Tier 2/functional).

### WR-03: Private (`_`-prefixed) cross-module helpers imported from `ticketing/service.py`; ad hoc query key bypasses the single-source `queryKeys` registry

**Files modified:** `backend/app/ticketing/service.py`, `backend/app/campaigns/service.py`, `backend/tests/test_campaigns.py`, `backend/tests/test_ticketing_dispatch.py`, `frontend/src/lib/queries/keys.ts`, `frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx`
**Commits:** `8a8dd62` (backend rename), `ebd2b96` (frontend registry fix)
**Applied fix:** Both parts of this two-part finding were fixed (the task instructions authorized falling back to frontend-only if the rename proved too risky, but a full cross-file `grep` first confirmed the rename was safely scoped):
1. **Backend rename** — before renaming, grepped the entire `backend/` tree for `_extract_ref` and `_provider_create_kwargs` to enumerate every call site (2 definitions + 6 call sites in `ticketing/service.py`, 1 import + 2 call sites in `campaigns/service.py`, 2 docstring-only mentions in tests) and confirmed no `mock.patch`/`monkeypatch` targeted either symbol by name (which would have broken silently on rename). Renamed both to `extract_ticket_ref` / `provider_create_kwargs` (no leading underscore) in `ticketing/service.py`, updated the cross-module import and both call sites in `campaigns/service.py`, and updated two docstring references in `test_campaigns.py` / `test_ticketing_dispatch.py` for consistency. No behavior change.
2. **Frontend registry fix** — added `queryKeys.vulnerabilities.remediationHosts(remediationId)` to `keys.ts` and switched `[id]/page.tsx`'s member-hosts `useQuery` to consume it via `queryKeys.vulnerabilities.remediationHosts(remediationId ?? '')`, replacing the inline `['vulnerabilities', 'remediation-hosts', remediationId] as const` key. Confirmed (via grep) this was the only consumer of that key shape, so no other invalidation call sites needed updating.
**Verification:** Re-read all 6 files (Tier 1); AST syntax check clean on all 4 backend files (Tier 2); `npx tsc --noEmit -p tsconfig.json` clean project-wide, no errors in either touched frontend file (Tier 2); ran full regression sweep on the backend rename — `test_campaigns.py` (24 passed), `test_ticketing_dispatch.py` (43 passed), `test_ticketing_clients.py` (13 passed), `test_tickets_create.py` (5 passed).

## Skipped Issues

None — all 4 in-scope findings were fixed.

---

_Fixed: 2026-08-18T10:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
