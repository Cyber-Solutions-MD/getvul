---
phase: 12
slug: assets-list-detail
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-29
last_updated: 2026-05-29
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Filled by gsd-planner before plans are finalized.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 7.x (backend/) |
| **Frontend framework** | vitest + @testing-library/react (frontend/) + Playwright (frontend/e2e) |
| **Config file** | backend/pyproject.toml (pytest config); frontend/vitest.config.ts; frontend/playwright.config.ts |
| **Quick run command (frontend)** | `pnpm --filter frontend test --run` |
| **Quick run command (backend)** | `cd backend && pytest -x -q` |
| **Full suite command** | `pnpm --filter frontend test --run && pnpm --filter frontend tsc --noEmit && cd backend && pytest && cd ../frontend && pnpm test:e2e` |
| **Estimated runtime** | ~90 seconds (unit + tsc); ~3 min including e2e |

---

## Sampling Rate

- **After every task commit:** Run scoped quick command (frontend changes → vitest; backend changes → pytest of touched module)
- **After every plan wave:** Run full unit suite (frontend vitest + backend pytest)
- **Before `/gsd-verify-work`:** Full suite + tsc + lint + playwright must be green
- **Max feedback latency:** 30 seconds for unit; 180 seconds for full

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-T1 | 12-01 | 1 | UX-04-02 | T-12-02 | tags ARRAY scoped per-tenant via existing query filter | unit (smoke import) | `cd backend && python -c "from app.assets.models import Asset; from app.assets.schemas import AssetResponse, AssetSummary; print('OK')"` | yes | ⬜ pending |
| 12-01-T2 | 12-01 | 1 | UX-04-01, UX-04-02 | T-12-01 | os_family ILIKE patterns hardcoded; allow-list clamp | unit (smoke import) | `cd backend && python -c "from app.assets.router import router; print('OK')"` | yes | ⬜ pending |
| 12-01-T3 | 12-01 | 1 | UX-04-02 | — | migration applied in transaction | integration | `cd backend && alembic current 2>&1 \| grep -c "025_add_asset_tags"` | yes | ⬜ pending |
| 12-01-T4 | 12-01 | 1 | UX-04-01, UX-04-02 | T-12-01, T-12-02 | end-to-end behavior verified | integration (pytest) | `cd backend && pytest -x tests/test_assets_tags_and_os_family.py -q` | yes | ⬜ pending |
| 12-02-T1 | 12-02 | 1 | UX-04-04 | T-12-20, T-12-08, T-12-09 | tenant scope on update + audit row + mass-assignment guard | unit (smoke import) | `cd backend && python -c "from app.assets.router import update_asset_owner; print('OK')"` | yes | ⬜ pending |
| 12-02-T2 | 12-02 | 1 | UX-04-02 | T-12-21 | asset_id filter scoped by Ticket.tenant_id | unit (smoke import) | `cd backend && python -c "from app.ticketing.router import list_all_tickets; from app.ticketing.service import list_tickets; print('OK')"` | yes | ⬜ pending |
| 12-02-T3 | 12-02 | 1 | UX-04-04 | T-12-20, T-12-08, T-12-09, T-12-11 | reassign happy + 404 + cross-tenant + 422 + audit row | integration (pytest) | `cd backend && pytest -x tests/test_asset_owner_reassign.py -q` | yes | ⬜ pending |
| 12-02-T4 | 12-02 | 1 | UX-04-02 | T-12-21 | tickets asset_id filter | integration (pytest) | `cd backend && pytest -x tests/test_tickets_asset_id_filter.py -q` | yes | ⬜ pending |
| 12-03-T1 | 12-03 | 2 | UX-04-03 | — | SVG math + edge cases + single sunset gradient invariant | unit (vitest) | `cd frontend && pnpm test --run src/components/ui/RiskRing` | yes | ⬜ pending |
| 12-03-T2 | 12-03 | 2 | UX-04-02, UX-04-04, UX-04-01 | T-12-04, T-12-12 | Avatar XSS guard + Breadcrumb a11y + osFamily parity | unit (vitest) | `cd frontend && pnpm test --run src/components/ui/Breadcrumb src/components/ui/Avatar src/lib/util/os-family` | yes | ⬜ pending |
| 12-04-T1 | 12-04 | 2 | UX-04-01 | T-12-05 | each axis carries hardcoded allowList → useUrlStateList clamp | unit (vitest) | `cd frontend && pnpm test --run src/components/ui/ChipBar` | yes | ⬜ pending |
| 12-04-T2 | 12-04 | 2 | UX-04-01 | T-12-05, T-12-13 | Phase 11 contract preserved 1:1 | regression (vitest) | `cd frontend && pnpm test --run src/components/vulnerabilities/chip-bar src/components/ui/ChipBar` | yes | ⬜ pending |
| 12-05-T1 | 12-05 | 3 | UX-04-01, UX-04-02 | — | queryKeys namespace + asset_id filter wired | type check | `cd frontend && pnpm tsc --noEmit` | yes | ⬜ pending |
| 12-05-T2 | 12-05 | 3 | UX-04-01, UX-04-02 | T-12-06 | useAssets buildSearchParams URL shape + useAsset enabled gate | unit (vitest) | `cd frontend && pnpm test --run src/lib/queries/use-assets src/lib/queries/use-asset-detail` | yes | ⬜ pending |
| 12-05-T3 | 12-05 | 3 | UX-04-01, UX-04-02 | T-12-14, T-12-15 | cache key isolation + correct endpoint paths | unit (vitest) | `cd frontend && pnpm test --run src/lib/queries/use-asset-vulnerabilities src/lib/queries/use-asset-remediations src/lib/queries/use-assignable-users` | yes | ⬜ pending |
| 12-06-T1 | 12-06 | 3 | UX-04-01 | T-12-05 | 4 axes with hardcoded allow-lists | unit (vitest) | `cd frontend && pnpm test --run src/components/assets/assets-chip-bar` | yes | ⬜ pending |
| 12-06-T2 | 12-06 | 3 | UX-04-01 | T-12-07 | text-only cell rendering (no innerHTML); keyboard nav | unit (vitest) | `cd frontend && pnpm test --run src/components/assets/assets-table` | yes | ⬜ pending |
| 12-06-T3 | 12-06 | 3 | UX-04-01, UX-04-05 | T-12-16 | page composes Phase 11 state primitives; no new variants | integration (vitest) | `cd frontend && pnpm test --run "src/app/(authed)/dashboard/assets/page" "src/components/assets"` | yes | ⬜ pending |
| 12-07-T1 | 12-07 | 4 | UX-04-03, UX-04-04 | — | mutation invalidates correct cache keys | unit (vitest) | `cd frontend && pnpm test --run src/lib/queries/use-reassign-asset src/components/assets/risk-card` | yes | ⬜ pending |
| 12-07-T2 | 12-07 | 4 | UX-04-04 | T-12-04, T-12-08, T-12-09, T-12-17 | Esc/Enter/blur contract + click-outside cancel + 250ms debounce | unit (vitest) | `cd frontend && pnpm test --run src/components/assets/owner-card src/components/assets/reassign-combobox` | yes | ⬜ pending |
| 12-08-T1 | 12-08 | 4 | UX-04-02 | — | severity ribbon merged text node + vuln row keyboard nav | unit (vitest) | `cd frontend && pnpm test --run src/components/assets/severity-ribbon src/components/assets/asset-vulns-list` | yes | ⬜ pending |
| 12-08-T2 | 12-08 | 4 | UX-04-02 | T-12-18 | provider mark + rel=noreferrer + relative timestamp + null-row skip | unit (vitest) | `cd frontend && pnpm test --run src/components/assets/remediation-timeline src/components/assets/identity-metadata-rail` | yes | ⬜ pending |
| 12-08-T3 | 12-08 | 4 | UX-04-02, UX-04-05 | T-12-10, T-12-19 | DrillPanel reuse via ?cve+open=drill; state primitives only | integration (vitest) | `cd frontend && pnpm test --run "src/app/(authed)/dashboard/assets/[id]/page"` | yes | ⬜ pending |

**Coverage:**
- Tasks total: 24 across 8 plans
- Each has an `<automated>` verify command (no MISSING flags)
- No 3 consecutive tasks without automated verification

---

## Wave 0 Requirements

No Wave 0 plan required:

- Backend Alembic migration is created and applied inside Plan 12-01 (Task 3 [BLOCKING]) before any backend tests for the phase run.
- Frontend test fixtures: existing TanStack QueryClient wrapper from Phase 11 tests covers the new mutation + query hooks.

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Mobile rail collapse below 900px | UX-04-02 | Viewport-dependent visual; Playwright snapshot covers basic, but real-device fidelity needs manual check | Resize browser to 768/375; verify rail stacks below main; verify breadcrumb truncates gracefully |
| Risk-ring drop-shadow visual at variable scores | UX-04-03 | The `filter: drop-shadow(0 0 8px currentColor)` effect requires visual inspection | Open `/assets/[id]` for assets with scores 0/20/50/80/100; verify gradient stroke + glow read correctly against dark surface |
| Reassign optimistic UI smoothness | UX-04-04 | Mutation timing is sub-second; needs perceived-snappiness check | Reassign with throttled network (Slow 3G); verify combobox closes immediately and owner card shows new name before request resolves |
| Sketch 005 variant B fidelity | UX-04-02 | Pixel-level adherence to the locked sketch | Open both `/assets/[id]` and `.claude/skills/sketch-findings-getvul/sources/005-asset-detail-sunset/index.html` side-by-side at 1280px; verify layout match |
| Drill panel scroll restoration | UX-04-02 | scroll-to-position is browser-driven; Phase 11 D-P-02 contract | On `/assets/[id]`, scroll halfway down vulns list; click a row; close the panel (×); verify the page is at the same scroll position |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none required — Plan 12-01 inlines the migration)
- [x] No watch-mode flags
- [x] Feedback latency < 30s for quick suite
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready for execution
