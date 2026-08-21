---
phase: 41-coverage-blind-spot-detection
verified: 2026-08-21T08:39:39Z
status: passed
score: 3/3 roadmap success criteria verified (1 accepted via override — documented UX caveat, ship-as-is decision)
overrides_applied: 1
overrides:
  - must_have: "The confirm dialog has two copy branches — owner-resolved and unresolvable-owner — per the UI-SPEC Copywriting Contract"
    reason: "Both copy branches are implemented and unit-tested in RouteToOwnerDialog, but real call sites in coverage/page.tsx cannot select the resolved branch because BlindSpotAssetResponse carries no owner-preview signal — adding one is a schema change explicitly out of this phase's reversibility scope. The end-to-end routing outcome (resolve/notify/audit) is correct regardless; only the pre-confirm dialog copy is a conservative default. Deferred to a future plan that adds an owner-preview field (see 41-UAT.md Deferred Follow-Ups)."
    accepted_by: "Igor Chemencedji"
    accepted_at: "2026-08-21T08:49:12Z"
human_verification:
  - test: "Open /dashboard/coverage as an analyst for a tenant whose blind-spot asset has a resolvable owner (assigned_user matching a real tenant User row, or a Humaans/last-login match). Click 'Route to owner' on that row (or from the drill panel) and read the confirm dialog BEFORE clicking confirm."
    expected: "Decide whether it is acceptable that the pre-confirm dialog ALWAYS shows the D-09 'No owner found for this device / We'll notify your admins and the configured alert channel instead' copy — even though the backend will, in this scenario, actually resolve the real owner and email them directly (not the admins). After confirming, the success toast will then say '{hostname} routed to {realOwnerName}', contradicting what the dialog just told the analyst."
    why_human: "This is a product/UX trust judgment, not a pass/fail code check: the underlying route-to-owner action is functionally correct end-to-end (server resolves the true owner, emails them, audits it, and the toast reports the true outcome), but the client never has an owner-preview signal to select the D-07 'resolved' dialog branch — every real call site hardcodes ownerResolved={false} (see 41-05-SUMMARY.md 'Known Stubs'). A human must decide: ship as-is (document/override), or require a follow-up plan to add an owner-preview field to BlindSpotAssetResponse (schema change, explicitly out of this phase's reversibility scope) before calling COV-03 fully done."
---

# Phase 41: Coverage & Blind-Spot Detection Verification Report

**Phase Goal:** GetVul tells a tenant what it doesn't know — assets the IdP/MDM/HR/CMDB knows about but no scanner has ever touched — instead of only reporting on what scanners already found.
**Verified:** 2026-08-21T08:39:39Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A coverage view reconciles the authoritative inventory (IdP/MDM/HR/CMDB) against scanner-seen assets and lists assets with zero findings or no last-seen date | ✓ VERIFIED | `backend/app/coverage/service.py::list_blind_spot_assets` composes `authoritative` (OR across `ENRICHMENT_SOURCES`) ∧ `never_scanned` (NOT OR across `SCANNER_SOURCES`) over `Asset.seen_by_sources`, tenant-scoped, `is_ignored` excluded, stable `hostname ASC, id ASC` order. `GET /api/v1/coverage/blind-spots` registered in `main.py:323`. `/dashboard/coverage` page renders the list with full error→loading→no-inventory→scanner-absent→all-covered→populated branch machine. 16/16 backend tests green (re-ran live), 12/12 `page.test.tsx` tests green (re-ran live), 0 TS errors. Intune sync defect (41-02) fixed and tested (4/4 tests green, re-ran live) — closes the D-01 baseline gap for Intune-only tenants and a latent cross-tenant asset-matching bug. |
| 2 | Per-connector coverage percentage and stale-source gaps (a connector that hasn't reported in N days) are visible | ✓ VERIFIED | `get_coverage_summary()` computes `coverage_pct = round(100*covered/total) if total else None` (D-11 null-safe) and `is_stale = (now - last_sync_at) > timedelta(days=7)` (strict `>`, D-06) per enabled scanner connector; wire-normalizes `last_sync_status` via the imported `_normalize_sync_status` (Pitfall 3, not re-derived). `GET /api/v1/coverage/summary` renders as `CoverageConnectorCard`s in a `StatStrip` above the blind-spot list, 3-tier SLA color family (`text-success`/`text-warning`/`text-danger`), amber (never red) `stale · {N}d` pill. 16/16 backend tests (incl. 5 COV-02 behavior tests: percentage math, zero-denominator null, stale boundary strictness, status normalization, enabled/disabled filtering) and 25/25 frontend tests (coverage-connector-card + hooks) re-ran green live. |
| 3 | A newly-discovered unmanaged asset can be routed to an owner directly from the coverage view | ⚠ VERIFIED (functional) — see human-verification item | `POST /api/v1/coverage/assets/{id}/route-to-owner` (require_analyst) resolves the owner via `get_directory_user`, emails them directly if resolved, falls back to `_email_owners_and_admins` + a fail-isolated `dispatch_channel` push (D-09) when unresolved, always writes a `coverage.route_to_owner` audit row before commit (D-08 fail-closed), returns `{hostname, routed_to}` reflecting the TRUE outcome. Client wires a per-row action AND a drill-panel footer action to one shared `RouteToOwnerDialog` + `useRouteToOwner` mutation; viewer sees the action disabled (`canRouteToOwner` RBAC gate), analyst can invoke it; success toast shows the real `routed_to`. 16/16 backend tests (incl. 5 COV-03 tests: resolved/fallback/channel-failure-isolated/RBAC/cross-tenant-404) and 12/12 page-level + 5/5 dialog tests re-ran green live. **However:** both real call sites in `coverage/page.tsx` hardcode `ownerResolved={false}` on `RouteToOwnerDialog` (no owner-preview field exists on `BlindSpotAssetResponse` — adding one was ruled out-of-scope for this phase's reversibility contract), so the pre-confirm dialog ALWAYS shows the D-09 "no owner found" copy, even in cases where the backend will actually resolve and notify a real owner directly. This is disclosed in `41-05-SUMMARY.md`'s "Known Stubs" section. The end-to-end routing action itself is not broken — only the pre-confirm dialog copy can be inaccurate for cases where a real owner resolves. |

**Score:** 3/3 roadmap success criteria functionally verified; SC3 carries one disclosed, human-judgment-worthy UX gap (see Human Verification below).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/coverage/service.py` | `list_blind_spot_assets`, `get_coverage_summary`, `route_to_owner` | ✓ VERIFIED | All three functions present, substantive, tenant-scoped throughout, matches plan interfaces verbatim (imports `SCANNER_SOURCES`/`ENRICHMENT_SOURCES`, `_normalize_sync_status`, never re-derives) |
| `backend/app/coverage/router.py` | `GET /blind-spots`, `GET /summary`, `POST /assets/{id}/route-to-owner`, `_get_asset_or_404` | ✓ VERIFIED | require_viewer on GETs, require_analyst on POST (imported from `app.auth.rbac`, not `app.auth.dependencies`); `_get_asset_or_404` tenant-scoped 404 helper used by the POST |
| `backend/app/coverage/schemas.py` | `BlindSpotAssetResponse`/`ListResponse`, `CoverageConnectorCardResponse`/`SummaryResponse`, `RouteToOwnerResponse` | ✓ VERIFIED | All fields match plan spec (`has_authoritative_inventory`, `total_authoritative_assets`, `coverage_pct: int\|None`, `is_stale`, `stale_days`, `routed_to`) |
| `backend/app/main.py` (registration) | `coverage_router` included at `/api/v1/coverage` | ✓ VERIFIED | `grep` confirms line 34 import + line 323 `include_router` |
| `backend/app/connectors/intune_sync.py` | corrected `SyncLog`/tenant-scoped Asset upsert | ✓ VERIFIED | `connector_config_id` fully removed; `connector_id=connector_config.id`, `tenant_id=connector_config.tenant_id`, uppercase `RUNNING`/`SUCCESS`/`FAILED`; both `Asset` selects + constructor tenant-scoped |
| `backend/tests/test_coverage.py` | 16 behavior tests (COV-01/02/03) | ✓ VERIFIED | 16/16 pass live (`pytest tests/test_coverage.py -q`) |
| `backend/tests/test_intune_sync.py` | 4 tests incl. DB-integration test | ✓ VERIFIED | 4/4 pass live |
| `frontend/.../dashboard/coverage/page.tsx` | full state-branch page, drill panel, RBAC gate | ✓ VERIFIED | 244+ lines; 6-branch WR-13 machine (error/loading/no-inventory/scanner-absent/all-covered/populated); `DrillPanel idKey="asset"`; `canRouteToOwner` gate wired to row action + drill footer |
| `frontend/.../coverage-connector-card.tsx` | per-connector card, 3-tier color, stale pill | ✓ VERIFIED | 8/8 component tests pass live |
| `frontend/.../coverage-asset-drill-content.tsx` | DrillPanel slot content, idKey="asset" | ✓ VERIFIED | 3-region shape (header/body/sticky footer), `!asset` loading branch, footer Route-to-owner button gated by `canRouteToOwner` |
| `frontend/.../route-to-owner-dialog.tsx` | 2-branch confirm dialog | ⚠ VERIFIED (component) / HOLLOW (real wiring) | Component itself correctly implements and tests both branches (5/5 tests pass); in production, both real call sites in `page.tsx` pass a hardcoded `ownerResolved={false}`, so the resolved (D-07) branch is unreachable via the app UI today — see SC3 above |
| `frontend/.../use-route-to-owner.ts` | mutation hook, retry:0, invalidate, toasts | ✓ VERIFIED | 5/5 tests pass live |
| `frontend/src/components/shell/nav-items.ts` | Coverage nav entry (Radar icon) | ✓ VERIFIED | `{ label: 'Coverage', href: '/dashboard/coverage', icon: Radar }` present |
| `frontend/e2e/routes.ts` | `/dashboard/coverage` STATIC_ROUTES entry | ✓ VERIFIED | Present with comment referencing 41-01/COV-01 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `coverage/page.tsx` | `/api/v1/coverage/blind-spots` | `useBlindSpotAssets` | WIRED | Confirmed via passing branch tests + live grep |
| `coverage/page.tsx` | `/api/v1/coverage/summary` | `useCoverageSummary` | WIRED | Confirmed; strip renders above list per D-04 |
| `coverage/service.py` | `app.assets.constants.SCANNER_SOURCES/ENRICHMENT_SOURCES` | import + `.contains()` | WIRED | No literal re-derivation found |
| `main.py` | `app.coverage.router` | `include_router` | WIRED | Confirmed at line 323 |
| `coverage/page.tsx` | `POST /assets/{id}/route-to-owner` | `useRouteToOwner` mutation | WIRED | Confirmed; fires on dialog confirm, toast + invalidate on settle |
| `coverage/page.tsx` | `coverage-asset-drill-content.tsx` | `DrillPanel idKey="asset"` | WIRED | Confirmed via live test: "?asset=a1&open=drill pre-opens the asset DrillPanel with the row content" |
| `coverage/page.tsx` | `canRouteToOwner` (useAuth role check) | prop passed to row action + drill footer | WIRED | Confirmed via live tests: viewer-disabled / analyst-enabled |
| `coverage-connector-card.tsx` | `app.connectors.service._normalize_sync_status` (backend) | import (Pitfall 3) | WIRED | Confirmed on backend side; frontend receives already-normalized status |
| `route-to-owner-dialog.tsx` (`ownerResolved` prop) | real owner-resolution signal | — | **NOT WIRED (by design/scope)** | No data source populates this prop with real data — both real call sites in `page.tsx` hardcode `ownerResolved={false}`. Disclosed limitation, see SC3 / human-verification item. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `RouteToOwnerDialog` | `ownerResolved` / `ownerName` props | Hardcoded literal `false` / absent at both `page.tsx` call sites | No — component supports real data but none is supplied | ⚠ HOLLOW (disclosed) — does not affect the actual server-side routing outcome (audit + notification are still correct); only the pre-confirm copy is a static default |
| `CoverageConnectorCard` (`card` prop) | `summaryQ.data.cards` | `useCoverageSummary()` → `GET /api/v1/coverage/summary` → `get_coverage_summary()` real DB query | Yes | ✓ FLOWING |
| `BlindSpotTable` (`rows` prop) | `q.data.items` | `useBlindSpotAssets()` → `GET /api/v1/coverage/blind-spots` → `list_blind_spot_assets()` real DB query | Yes | ✓ FLOWING |
| `CoverageAssetDrillContent` (`asset` prop) | `selectedAsset` derived from `items.find(...)` | Same real blind-spot list data (no separate fetch) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend coverage module tests (COV-01/02/03, 16 tests) | `pytest tests/test_coverage.py -q` (with ENCRYPTION_KEY/JWT_SECRET_KEY env) | `16 passed, 1 warning in 7.00s` | ✓ PASS |
| Intune sync fix tests (4 tests) | `pytest tests/test_intune_sync.py -q` | `4 passed, 1 warning in 0.34s` | ✓ PASS |
| Coverage page frontend tests (12 tests) | `npx vitest run "src/app/(authed)/dashboard/coverage/page.test.tsx"` | `Test Files 1 passed / Tests 12 passed` | ✓ PASS |
| Coverage component + hook tests (25 tests) | `npx vitest run` over `coverage-connector-card.test.tsx`, `route-to-owner-dialog.test.tsx`, `use-route-to-owner.test.tsx`, `use-blind-spot-assets`/`use-coverage-summary` | `Test Files 3 passed / Tests 25 passed` | ✓ PASS |
| TypeScript compile | `npx tsc --noEmit -p .` | 0 errors project-wide | ✓ PASS |
| `main.py` router registration | `grep coverage_router backend/app/main.py` | import + `include_router(..., prefix="/api/v1/coverage")` present | ✓ PASS |
| `intune_sync.py` defect fix | `grep -c connector_config_id backend/app/connectors/intune_sync.py` | 0 occurrences | ✓ PASS |
| Git commit existence (10 task commits across 5 plans) | `git log --oneline --all \| grep <hash>` for all 10 hashes | All 10 found | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|-------------|--------|----------|
| COV-01 | 41-01, 41-02 | Reconcile authoritative inventory vs. scanner-seen assets; list never-scanned assets | ✓ SATISFIED | `list_blind_spot_assets` + page; Intune sync fix protects the baseline. Marked `[x]` in REQUIREMENTS.md. |
| COV-02 | 41-03 | Per-connector coverage % and stale-source gaps | ✓ SATISFIED | `get_coverage_summary` + `CoverageConnectorCard`. Marked `[x]` in REQUIREMENTS.md. |
| COV-03 | 41-04, 41-05 | Route a newly-discovered unmanaged asset to an owner | ✓ SATISFIED (with disclosed UX caveat) | `route_to_owner` backend + `RouteToOwnerDialog`/`useRouteToOwner` frontend, end-to-end functional. Marked `[x]` in REQUIREMENTS.md. See human-verification item for the pre-confirm copy caveat. |

No orphaned requirements found — REQUIREMENTS.md's Phase 41 section lists exactly COV-01/02/03, all three declared by at least one plan's `requirements:` frontmatter field, all three marked complete.

### Anti-Patterns Found

None blocking. No `TODO`/`FIXME`/`PLACEHOLDER`/"not yet implemented" strings found in any Phase 41 backend or frontend file. The one documented gap (hardcoded `ownerResolved={false}`) is disclosed as a "Known Stub" in `41-05-SUMMARY.md` rather than hidden — treated here as a human-verification item, not a silent anti-pattern.

### Human Verification Required

### 1. Route-to-owner pre-confirm dialog copy accuracy

**Test:** As an analyst, open `/dashboard/coverage`, find (or seed) a blind-spot asset whose `assigned_user` matches a real tenant `User`'s email (or whose Humaans/last-login data would resolve via `get_directory_user`'s precedence). Click "Route to owner" and read the dialog BEFORE confirming.
**Expected:** Decide whether always showing "No owner found for this device — we'll notify your admins and the configured alert channel instead" (even when the backend will, in fact, resolve and directly email a real owner) is acceptable to ship as-is, given the post-confirm toast will report the true `routed_to` value and may contradict the dialog's own pre-confirm claim.
**Why human:** This is a product/UX trust call, not a code-correctness question — the underlying action (resolve → notify → audit) is correct and fully tested; only the client-side pre-confirm branch selection lacks a data signal by explicit scope decision (schema change to `BlindSpotAssetResponse` was out of this phase's reversibility contract). A human should either (a) accept this via a verification override with a documented reason, or (b) request a small follow-up plan to add an owner-preview field/endpoint so the dialog can select the correct branch before confirm.

### Gaps Summary

No functional gaps. All three roadmap success criteria are backed by real, live-tested code: the blind-spot reconciliation query, the per-connector coverage/staleness computation, and the route-to-owner notify-and-audit action all work end-to-end against real data (backend tests exercise a real Postgres test DB; frontend tests exercise the real component tree). The Intune sync defect that would have silently emptied the D-01 baseline for Intune-only tenants was found and fixed in the same phase (41-02), with its own regression test.

The one open item is a disclosed, scoped-out UX limitation on SC3: the `RouteToOwnerDialog`'s owner-resolved/unresolvable copy branches are both implemented and unit-tested, but the two real production call sites in `coverage/page.tsx` never supply a real `ownerResolved` signal (no such field exists on `BlindSpotAssetResponse`, and adding one was explicitly ruled out of this phase's reversibility scope). This does not break the feature — the server-side routing, notification, and audit trail are all correct regardless — but it means the pre-confirm dialog can tell an analyst something that turns out not to be true once the mutation completes. This is surfaced as a human-decision item rather than a blocking gap, because the phase's literal success criterion ("routed to an owner directly from the coverage view") is met by the actual behavior, and the executor disclosed the limitation transparently (`41-05-SUMMARY.md` "Known Stubs") rather than hiding it.

**This looks like an acceptable, well-scoped, disclosed deviation.** If the developer agrees, add the following override so future re-verification treats it as resolved rather than re-flagging it:

```yaml
overrides:
  - must_have: "The confirm dialog has two copy branches — owner-resolved and unresolvable-owner — per the UI-SPEC Copywriting Contract"
    reason: "Both copy branches are implemented and unit-tested in RouteToOwnerDialog, but real call sites in coverage/page.tsx cannot select the resolved branch because BlindSpotAssetResponse carries no owner-preview signal — adding one is a schema change explicitly out of this phase's reversibility scope. The end-to-end routing outcome (resolve/notify/audit) is correct regardless; only the pre-confirm dialog copy is a conservative default. Deferred to a future plan that adds an owner-preview field."
    accepted_by: "{developer name}"
    accepted_at: "{ISO timestamp}"
```

---

*Verified: 2026-08-21T08:39:39Z*
*Verifier: Claude (gsd-verifier)*
