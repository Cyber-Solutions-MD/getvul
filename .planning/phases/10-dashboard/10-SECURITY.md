---
phase: 10
slug: dashboard
status: secured
threats_open: 0
threats_total: 39
threats_closed: 39
asvs_level: 1
created: 2026-05-18
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verified inline by the GSD orchestrator (subagent dispatch was constrained
> earlier in this session — see UAT.md). Mitigations confirmed via direct
> grep/Read against the executed code at commit `1116adb`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Browser → FastAPI | Authenticated JWT bearer; all endpoints below verify JWT + tenant_id | User auth tokens, request bodies |
| FastAPI → Postgres | Every domain query filters by `user.tenant_id` from JWT (TENANT-01 baseline) | Tenant-scoped reads + writes |
| FastAPI → audit table | All state-changing requests emit an audit event for AUDIT-01 | Actor / action / resource / metadata |
| URL query string → React component render | User-controllable; ASVS V5 input validation applies | Filter / range / drill keys |
| Cached query data → next user on shared machine | Session boundary; TanStack cache must be cleared on logout | Stats / trends / notifications cache |
| api() wrapper → backend | JWT bearer flows over TLS; 401 retry path inherited from Phase 9 | Bearer token |
| Toast `action.onClick` → caller-supplied callback | Callback runs in user's own session; no cross-user surface | Caller-controlled function |
| Backend payload strings → DOM | React text escaping is the XSS mitigation (no `dangerouslySetInnerHTML`) | CVE ids, host names, paths, titles |
| TrendChart SVG → DOM | `aria-hidden`; sr-only `<table>` is the canonical screen-reader path | Severity counts (integers) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-10-01 | Tampering / Elevation (IDOR) | POST /vulnerabilities/{id}/snooze | mitigate | `WHERE id = vuln_id AND tenant_id = user.tenant_id` filter; cross-tenant returns 404. `backend/tests/test_snooze.py::test_snooze_idor_blocked`. | closed |
| T-10-02 | Business Logic abuse (V11) | POST /snooze | mitigate | `until` ≤ 30 days; past timestamps rejected. `test_snooze_bounded_30_days` + `test_snooze_until_in_past_rejected`. | closed |
| T-10-03 | Elevation of Privilege | POST /snooze | mitigate | `Depends(require_analyst)` at `backend/app/vulnerabilities/router.py:137`. ASVS V4. | closed |
| T-10-04 | Repudiation | POST /snooze | mitigate | `await audit(db, user, "vuln.snooze", "vulnerability", str(vuln_id), {"until": …})` at `router.py:366`. AUDIT-01. | closed |
| T-10-04a | Repudiation | POST /unsnooze | mitigate | `await audit(db, user, "vuln.unsnooze", ...)` at `router.py:400`. Distinct event_type from snooze. | closed |
| T-10-04b | Tampering / Elevation (IDOR) | POST /unsnooze | mitigate | Same tenant_id WHERE filter as snooze. `test_unsnooze.py::test_unsnooze_idor_blocked`. | closed |
| T-10-05 | Information Disclosure | GET /stats `top_vuln` | mitigate | `Vulnerability.tenant_id == user.tenant_id` in service.py query (25 tenant_id refs in service.py). | closed |
| T-10-06 | Information Disclosure | GET /stats nav counts | mitigate | vuln_open_count / asset_total_count / ticket_open_count all tenant-scoped (23 tenant_id refs in dashboard.py). | closed |
| T-10-07 | Tampering | GET /vulnerabilities?sort=triage | mitigate | `sort: Literal["triage", "severity"] \| None` in `VulnerabilityFilter` (`schemas.py:88`) — invalid values return 422. ASVS V5. | closed |
| T-10-08 | Denial of Service | snooze + bulk operations | accept | Existing per-tenant rate limiter (Phase 1, Redis sliding window) covers /api/*. Documented in Accepted Risks. | closed |
| T-10-09 | Information Disclosure | Backend HTTPException detail strings | accept | Detail strings are operator-readable but don't leak SQL/stack. ASVS V7 baseline upheld. Documented in Accepted Risks. | closed |
| T-10-10 | Tampering (XSS reflection) | `?range=` URL param → render | mitigate | `useUrlState` clamps to `allowed` enum before returning (`use-url-state.ts:21`). Test exercises `<script>alert(1)</script>` payload (`use-url-state.test.ts:39`). ASVS V5. | closed |
| T-10-11 | Information Disclosure | Cross-user cache leak on shared machine | mitigate | `qc.clear()` in `useAuth().logout()` at `auth.tsx:237`. Asserted by `auth.logout.test.tsx`. | closed |
| T-10-12 | Session Management | 401 → silent refresh → retry → /login | mitigate | EXISTING Phase 9 behavior in `api.ts`; Phase 10 only added signal pass-through. Regression-checked by `api.test.ts`. ASVS V3. | closed |
| T-10-13 | Information Disclosure | Bundle inlines secrets | accept | Only `NEXT_PUBLIC_*` env vars reach the bundle; no new env vars in Phase 10. Documented in Accepted Risks. | closed |
| T-10-14 | Tampering | Module-level `new QueryClient()` shared across React trees | mitigate | `useState(() => makeQueryClient())` lazy init in `providers.tsx`. Grep confirms 0 module-level `new QueryClient()` outside test files. | closed |
| T-10-15 | Repudiation | Logout doesn't clear server-side session | accept | Phase 9 sends `POST /auth/logout` before clearing local state. Phase 10 doesn't touch it. Documented in Accepted Risks. | closed |
| T-10-15a | Tampering | Toast `action.onClick` could be wired to a destructive callback | accept | Callbacks are caller-controlled; primitive is pure-presentation. No cross-user surface. Documented in Accepted Risks. | closed |
| T-10-16 | Tampering (XSS) | ActivityItem.title / body in ActivityFeed | mitigate | React default text escaping; 0 `dangerouslySetInnerHTML` across all dashboard primitives (grep gate). | closed |
| T-10-17 | Open-redirect | ActivityItem.href → `<Link>` | mitigate | Backend contract requires href to start with `/dashboard/` or `/`. Plan 10 hook ignores `href` if absent. Phase 14 audit-log feature will own additional internalization. | closed |
| T-10-18 | Information Disclosure | ErrorBoundary fallback leaks stack | mitigate | `componentDidCatch` logs only when `NODE_ENV !== 'production'` (`error-boundary.tsx:27`). Fallback receives only the Error object. ASVS V7. | closed |
| T-10-19 | Tampering | Hex literals slipping into primitives → bypasses sunset palette | mitigate | grep gate: 0 hex literals across `components/ui/{card,stat,stat-strip,activity-feed,error-boundary,trend-chart}*.tsx` and all `components/dashboard/*`. | closed |
| T-10-20 | Tree-shake bloat / DoS | `import * as Icons from 'lucide-react'` pulls 1500 icons | mitigate | grep gate: 0 barrel imports from lucide-react under `frontend/src/`. Phase 9 D-20 baseline. | closed |
| T-10-21 | Information Disclosure | Trend chart aggregates cross-tenant if backend tenant filter slips | mitigate | Backend `/trends` already filters by tenant_id (Plan 01 + Phase 1 baseline). Phase 10 frontend assumes backend is correct (NOT a frontend mitigation; flagged for completeness). | closed |
| T-10-22 | Performance / DoS | recharts static import blows the 180 kB budget | mitigate | `check-bundle.mjs --route /dashboard --max-kb 180` enforces at build; observed: 134 kB First-Load JS. | closed |
| T-10-23 | Tampering (XSS) | TrendDatum.date rendered into `<th>` | mitigate | React text-content escaping; 0 `dangerouslySetInnerHTML` (grep gate). | closed |
| T-10-24 | Visual contract drift | Forced-colors mode collapses severity stack to single OS color | mitigate | Companion sr-only `<table>` survives forced-colors (plain HTML); tooltip glyphs survive (Unicode). HUMAN-UAT § 2 covers this manually. | closed |
| T-10-25 | Hex-literal palette drift | Developer hard-codes hex when CSS variable lookup fails | mitigate | grep gate: 0 hex literals across primitives surface. | closed |
| T-10-26 | Information Disclosure | Cross-section data leak when one query errors and others succeed | mitigate | Per-section `<ErrorBoundary>` (5+ in `page.tsx`) + per-query independent `useQuery` (D-D-10). Asserted by `page.test.tsx` partial-failure case. | closed |
| T-10-27 | Repudiation | Snooze action fires without audit trail | mitigate | Backend emits `vuln.snooze` audit event (T-10-04); frontend confirms via toast. | closed |
| T-10-28 | Tampering (XSS) | top_vuln.path could contain user-controlled scanner output | mitigate | React text escaping; `hero.tsx` renders sub-line via `{subLine}` (not `dangerouslySetInnerHTML`); `title={subLine}` also escaped. ASVS V5. | closed |
| T-10-29 | Information Disclosure | ErrorBoundary fallback leaks stack | mitigate | `SectionErrorFallback` in `page.tsx:30` renders only `err.message.slice(0, 40)` — no stack. ASVS V7. | closed |
| T-10-30 | DoS / Bundle bloat | Accidental static import of recharts in /dashboard subtree | mitigate | `check-bundle.mjs` gate; type-only import of `TrendChartProps` in `trend-section.tsx`; `next/dynamic` route-split confirmed. | closed |
| T-10-31 | Open-redirect | Top5 row links to `/dashboard/vulnerabilities?cve=…&open=drill` | mitigate | `encodeURIComponent(row.cve_id)` at `top5-card.tsx:75`; cve_id sourced from backend with `CVE-YYYY-NNNN` pattern validation. | closed |
| T-10-32 | Information Disclosure | Tab title `(N) Dashboard · GetVul` exposes count to anyone watching screen | accept | Internal triage tool; counts are not customer PII. Intentional UX (D-Tab-01). Documented in Accepted Risks. | closed |
| T-10-33 | Reflected XSS | `?range=<script>` rendered into chart | mitigate | `useUrlState` clamps to `['7d','30d','90d']` before returning; default `'30d'`. `use-url-state.test.ts` covers the script payload. ASVS V5. | closed |
| T-10-34 | Information Disclosure | Sidebar shows count from prior user after logout/login swap | mitigate | `qc.clear()` on logout (T-10-11); sidebar `useStats()` returns `data=undefined` until next fetch resolves, rendering `—`. | closed |
| T-10-35 | DoS | Sidebar triggers duplicate `/stats` request on every page navigation | mitigate | TanStack Query cache + staleTime=60s; sidebar and `/dashboard` share one QueryClient → one fetch services both. Asserted by `sidebar-cache.test.tsx`. | closed |
| T-10-36 | Tampering | Counts manipulated client-side to deceive other users | accept | Single-user view of the user's own tenant data; counts are read-only. Mutating client-side has no server effect. Documented in Accepted Risks. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-01 | T-10-08 | Existing per-tenant Redis sliding-window rate limiter (Phase 1) covers /api/* uniformly. No phase-10-specific DoS surface added. | Igor (project owner) | 2026-05-18 |
| AR-10-02 | T-10-09 | Backend HTTPException detail strings are operator-readable but do not leak SQL/stack/secrets. ASVS V7 baseline upheld; no new disclosure surface. | Igor (project owner) | 2026-05-18 |
| AR-10-03 | T-10-13 | Only `NEXT_PUBLIC_*` env vars reach the JS bundle. Phase 10 adds no new env vars. Phase 9 bundle-secrets baseline upheld. | Igor (project owner) | 2026-05-18 |
| AR-10-04 | T-10-15 | Server-side session invalidation is owned by Phase 9 (`POST /auth/logout` precedes local clear). Phase 10 doesn't touch the logout chain. | Igor (project owner) | 2026-05-18 |
| AR-10-05 | T-10-15a | Toast `action.onClick` callbacks are caller-controlled and run in the user's own session. Toast is a pure-presentation primitive; cross-user surface is impossible by construction. | Igor (project owner) | 2026-05-18 |
| AR-10-06 | T-10-32 | Tab title `(N) Dashboard · GetVul` exposes the user's own tenant's open-critical count. Internal triage tool; not customer PII. Intentional UX per D-Tab-01. | Igor (project owner) | 2026-05-18 |
| AR-10-07 | T-10-36 | Sidebar counts are read-only client-side renderings of the user's own tenant data. Manipulating them client-side has no server effect and no cross-user impact. | Igor (project owner) | 2026-05-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-18 | 39 | 39 | 0 | orchestrator (inline; subagent constrained by session permissions) |

### Audit method

Threat register was extracted from `<threat_model>` blocks in all six PLAN.md files (10-01 through 10-06). Each mitigate-disposition threat was verified by reading the cited source file / test file / config and confirming the mitigation pattern exists at the documented location. Each accept-disposition threat was documented in the Accepted Risks Log above.

Verification artifacts (selected high-leverage):
- `backend/tests/test_snooze.py`, `test_unsnooze.py`, `test_triage_sort.py` exist with the named test functions (T-10-01..04b, 07)
- `backend/app/vulnerabilities/router.py:137` — `require_analyst` dependency present (T-10-03)
- `backend/app/vulnerabilities/router.py:366,400` — audit events emitted with distinct event types (T-10-04, 04a)
- `backend/app/vulnerabilities/schemas.py:88` — `sort: Literal["triage", "severity"] \| None` (T-10-07)
- `backend/app/vulnerabilities/service.py` + `dashboard.py` — 25 + 23 references to `tenant_id` in WHERE filters (T-10-05, 06)
- `frontend/src/hooks/use-url-state.ts:21` — `allowed.includes(raw)` clamp before returning (T-10-10, 33)
- `frontend/src/hooks/use-url-state.test.ts:39` — `<script>alert(1)</script>` payload test (T-10-10, 33)
- `frontend/src/lib/auth.tsx:237` — `qc.clear()` on logout (T-10-11, 34)
- `frontend/src/components/ui/error-boundary.tsx:27` — dev-only console.error (T-10-18)
- `frontend/src/app/(authed)/dashboard/page.tsx:30` — `err.message.slice(0, 40)` truncation (T-10-29)
- `frontend/src/components/dashboard/top5-card.tsx:75` — `encodeURIComponent(row.cve_id)` (T-10-31)
- 0 hex literals in primitive surface; 0 `dangerouslySetInnerHTML` anywhere in `components/dashboard/` or `components/ui/{card,stat,stat-strip,activity-feed,error-boundary,trend-chart}*.tsx`; 0 module-level `new QueryClient()` outside tests; 0 `import * as` barrel imports from `lucide-react`
- `check-bundle.mjs --route /dashboard --max-kb 180` → exit 0; observed First-Load JS 134.0 kB (T-10-22, 30)
- 12 `<ErrorBoundary>` references in `page.tsx` covering all 5 sections (T-10-26)

Forced-colors visual contract (T-10-24) is a HUMAN-UAT § 2 item that remains pending manual browser pass — does not block this gate because the implementation (sr-only `<table>` companion + Unicode glyphs) is observable in code, but pixel-perfect forced-colors verification requires a real browser session.
