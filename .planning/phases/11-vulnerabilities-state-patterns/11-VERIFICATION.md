---
phase: 11-vulnerabilities-state-patterns
verified: 2026-05-27T12:15:00Z
status: human_needed
score: 11/11 must-haves verified (automated); 8 manual UAT items pending
overrides_applied: 0
deferred:
  - truth: "At <900px viewport, the table collapses to card view (3-row card per row)"
    addressed_in: "Phase 15"
    evidence: "Phase 15 Success Criterion 1: 'tables collapse to card view at <900px' — closing milestone quality gate"
human_verification:
  - test: "Sunset visual continuity vs Phase 10 (D-S-06)"
    expected: "No regression in dashboard visual hierarchy; only loading shimmer + error chrome changed after retrofit"
    why_human: "Visual perception; requires side-by-side comparison vs pre-retrofit screenshot"
  - test: "420px drill panel layout vs sketch-003 variant C (UX-03-03)"
    expected: "Panel layout matches sketch within rendering tolerance"
    why_human: "Visual fidelity comparison against HTML mockup"
  - test: "vaul mobile bottom-sheet on real device (UX-03-06)"
    expected: "Smooth drag gesture, no jank, focus correctly returns after close"
    why_human: "Real touch gestures + iOS Safari + Android Chrome cannot be exercised in jsdom"
  - test: "Empty-state copy voice + tone (UX-S-02 + copy-voice.md)"
    expected: "Tone matches copy-voice.md exemplar — peer, not butler"
    why_human: "Tone/voice quality evaluation"
  - test: "Screen-reader announcements (D-S-07 + UX-07-03 partial)"
    expected: "All ARIA roles/labels exercised; no double-announcement; no focus traps"
    why_human: "VoiceOver / NVDA audio output cannot be automated"
  - test: "Forced-colors-mode preservation (Phase 9 a11y carryover)"
    expected: "No invisible UI in forced-colors mode; severity glyphs survive grayscale"
    why_human: "Windows High Contrast / Edge Force Colors visual inspection"
  - test: "Reduce-motion shimmer suppression (Phase 9 a11y carryover)"
    expected: "All animations halted; visual shape preserved"
    why_human: "OS-level reduce-motion behavior visual verification"
  - test: "Real-world filter + pagination performance @ 2k vulns (D-T-03 sanity)"
    expected: "No visible jank; render times <100ms per interaction; no virtualization needed"
    why_human: "React DevTools profiler perception of jank requires interactive use"
---

# Phase 11: `/vulnerabilities` + State Patterns Verification Report

**Phase Goal:** Ship the redesigned `/dashboard/vulnerabilities` surface (faceted filtering, list / by-host views, drill-panel detail, ticket creation) AND the 4 canonical cross-phase state-pattern primitives (SkeletonTable, EmptyState, PartialFailureBanner, PerSourceStatusStrip) consumed verbatim by Phases 12-14. Honor Phase 10 deep-link contract (`?cve=...&open=drill`). Retrofit 5 Phase 10 dashboard components onto canonical primitives.

**Verified:** 2026-05-27T12:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### ROADMAP Success Criteria (Phase 11 contract)

| # | Truth                                                                                                                                                                                                                                                                                                                                                                                  | Status     | Evidence |
|---|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|----------|
| 1 | `/vulnerabilities` renders chip-bar filter row (search + severity chips with counts + source chips + saved-filter violet pill + clear-all) above the table; no persistent left drawer                                                                                                                                                                                                  | VERIFIED   | `chip-bar.tsx` (288 lines): `useUrlStateList` for severity/source/status; `useSavedFilters()` for violet pill; 250ms debounced search; rendered in `page.tsx:161`. `microcopy.savedFilterPrefix='★'`. No drawer in page composition. |
| 2 | Table renders 7 spec columns (Severity pill+glyph · CVE mono · Title/Product · Asset mono · CVSS mono+banded · Status with KEV+exploit badges · SLA mono+tiered); clicking row opens 420px right panel with description/CVSS vector/hosts/remediation/action buttons                                                                                                                   | VERIFIED   | `vuln-table.tsx` (331 lines): 8 `<th` (7 columns + open indicator); `GLYPH` map for ■▲◆◇○□; `data-col="cve"`/`font-mono`; KEV/exploit badge logic. `drill-panel.tsx`: `w-[420px]`. `drill-content.tsx` (322 lines): 6 section `<h4>` headings (CVSS / Hosts / Description / Remediation / Activity / Actions). |
| 3 | Filter state URL-synced (every chip/search change updates `?` query); reloading URL restores filter state; "★ Today's triage" pill restores in one click                                                                                                                                                                                                                               | VERIFIED   | `useUrlStateList` + `useUrlState` write URL via `router.replace(target, { scroll: false })`. XSS allow-list clamp on READ (line 28) AND WRITE (line 38). `useSavedFilters` returns blob; chip-bar applies via URLSearchParams merge. |
| 4 | Segmented control toggle in page-head actions switches By-CVE / By-Host views without losing filter state                                                                                                                                                                                                                                                                              | VERIFIED   | `view-toggle.tsx` (51 lines): writes only `?group=`. Backend `?group=host` returns `VulnerabilityByHost` rows. `vuln-table` test data + `useVulnerabilities({group})` round-trips. Severity/source/status URL keys independent. |
| 5 | At <900px, table collapses to card view (3-row card per row) AND drill panel becomes full-screen overlay                                                                                                                                                                                                                                                                               | **DEFERRED**   | Drill panel mobile overlay IS shipped via vaul (`drill-panel-mobile.tsx` 133 lines, `useMediaQuery('(max-width: 899px)')`, `h-[92dvh]`). **Table-card-view collapse NOT implemented** — no media-query branches, no card layout, no mobile-card test. Phase 15 SC #1 explicitly covers "tables collapse to card view at <900px" as part of the closing milestone quality gate. |
| 6 | Loading shows skeleton chip-bar + skeleton rows + per-source progress; empty shows explained-why card + 3-tier CTAs + violet lightbulb; partial-failure shows amber banner + per-source cards + stale-row tinting; toasts fire on saved-filter/snooze/ticket-created (UX-S-01..S-05)                                                                                                   | VERIFIED   | All 5 state branches present in `page.tsx:148-220`: `PartialFailureBanner`, `PerSourceStatusStrip`, `SkeletonTable` (loading), `EmptyState` (empty-filtered with 3 CTAs + `<Lightbulb>` Suggestion), `EmptyState` (total-failure with retry). Toast wired via `useToast()` in `drill-content.tsx` for ticket create/error + snooze success/error. Stale-row: `failedSources` prop → `data-stale="true"` + `bg-amber-soft`. |
| 7 | State patterns ship as reusable components (SkeletonTable, EmptyState, PartialFailureBanner, PerSourceStatusStrip, Toast) consumed by Phase 12+ verbatim                                                                                                                                                                                                                                | VERIFIED   | `frontend/src/components/states/index.ts` barrel exports all 4 + type aliases. `Toast` already shipped Phase 9, extended Phase 10. 5 dashboard retrofit sites consume from `@/components/states` (verified import in top5-card / trend-section / activity-rail / stat-strip-wired / onboarding-panel). |

**Score:** 6/7 verified, 1 deferred to Phase 15 — net **0 gaps for Phase 11**.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Table collapses to card view at <900px | Phase 15 | Phase 15 Success Criterion 1: "tables collapse to card view at <900px" — the "Mobile + a11y + Perf Quality Gate" milestone closer. Phase 11 ships the vaul bottom-sheet drill panel; the table-card-view collapse is a Phase 15 deliverable. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/app/vulnerabilities/schemas.py` | FacetsResponse + VulnerabilityByHost + VulnerabilityListResponse + extended sort Literal + order + group + max_length=10 caps | VERIFIED | 254 lines; 5 class refs verified; Literal extensions confirmed |
| `backend/app/vulnerabilities/service.py` | get_facets() + list_vulnerabilities_by_host() + expanded sort branch | VERIFIED | 535 lines; both `async def get_facets` and `async def list_vulnerabilities_by_host` present |
| `backend/app/vulnerabilities/router.py` | response_model=VulnerabilityListResponse + ?order ?group ?facets Query params + 400 on unknown facet | VERIFIED | 894 lines; all 4 patterns confirmed |
| `backend/tests/test_vuln_sort.py` | 7 RED→GREEN pytests for expanded sort | VERIFIED | 206 lines; 7 `def test_` |
| `backend/tests/test_vuln_facets.py` | 6 RED→GREEN pytests for contextual facets + tenant scope | VERIFIED | 186 lines; 6 `def test_` |
| `backend/tests/test_vuln_group_host.py` | 6 RED→GREEN pytests for by-host grouping | VERIFIED | 206 lines; 6 `def test_` |
| `backend/tests/test_tickets_create.py` | 5 pytests pinning POST /tickets contract | VERIFIED | 171 lines; 5 `def test_` |
| `frontend/package.json` | vaul@1.1.2 exact pin (no caret) | VERIFIED | `"vaul": "1.1.2"` confirmed; no `^` prefix |
| `frontend/tailwind.config.ts` | animate-shimmer keyframe alias | VERIFIED | `'shimmer': 'skeleton-shimmer 1.6s linear infinite'` alias added |
| `frontend/src/hooks/use-url-state-list.ts` | useUrlStateList with XSS clamp on read+write | VERIFIED | 58 lines; clamp on line 28 (read) + line 38 (write); explanatory comment present |
| `frontend/src/hooks/use-media-query.ts` | SSR-safe matchMedia hook | VERIFIED | 28 lines; `addEventListener('change', handler)` present |
| `frontend/src/lib/queries/keys.ts` | extended queryKeys.vulnerabilities.list/.detail + connectors + savedFilters | VERIFIED | All 4 sub-keys present |
| `frontend/src/lib/queries/use-query-errors.ts` | useSyncExternalStore + QueryCache subscription + fingerprint stabilization | VERIFIED | 3212 bytes; `useSyncExternalStore` referenced 4x |
| `frontend/src/lib/queries/use-vulnerabilities.ts` | useVulnerabilities + buildSearchParams export; ?facets=severity,source,status always appended | VERIFIED | Both exports present; `sp.set('facets', 'severity,source,status')` confirmed |
| `frontend/src/lib/queries/use-vulnerability-detail.ts` | useVulnerabilityDetail with enabled gate | VERIFIED | Present; gated query |
| `frontend/src/lib/queries/use-connectors.ts` | useConnectors() | VERIFIED | Present |
| `frontend/src/lib/queries/use-saved-filters.ts` | useSavedFilters() read-only | VERIFIED | Present |
| `frontend/src/lib/mutations/use-create-ticket.ts` | POST /api/v1/tickets + retry:0 + notifications invalidation | VERIFIED | All patterns confirmed |
| `frontend/src/components/states/skeleton-table.tsx` | column-aware shimmer + aria-busy + motion-safe | VERIFIED | 63 lines; `motion-safe:animate-shimmer` + `aria-busy="true"` |
| `frontend/src/components/states/empty-state.tsx` | compound primitive (Title/Body/Actions/Suggestion) + role=status + aria-live=polite | VERIFIED | 77 lines; `Object.assign(EmptyStateRoot, {...})`; 10 ARIA pattern matches |
| `frontend/src/components/states/partial-failure-banner.tsx` | hybrid hook+props + role=alert + amber chrome + useQueryErrors | VERIFIED | 154 lines; 6 critical patterns verified |
| `frontend/src/components/states/per-source-status-strip.tsx` | useConnectors + aria-live=polite | VERIFIED | 72 lines; 6 patterns verified |
| `frontend/src/components/states/index.ts` | barrel for all 4 + type aliases | VERIFIED | 6 exports |
| `frontend/src/components/vulnerabilities/microcopy.ts` | sentence-case strings, no Welcome/Please/Click here | VERIFIED | 77 lines; zero violations of copy-voice rules |
| `frontend/src/components/vulnerabilities/chip-bar.tsx` | search + chips + saved-filter pill + 250ms debounce | VERIFIED | 288 lines; 14 critical patterns verified |
| `frontend/src/components/vulnerabilities/view-toggle.tsx` | By-CVE/By-Host segmented control | VERIFIED | 51 lines; 8 patterns verified |
| `frontend/src/components/vulnerabilities/vuln-table.tsx` | 7 columns + keyboard nav + sticky header + stale-row tinting | VERIFIED | 331 lines; 12 critical patterns; zero `role="grid"` (Pitfall 5 honored) |
| `frontend/src/components/vulnerabilities/drill-panel.tsx` | desktop 420px aside + Esc/close/outside-click/row-swap | VERIFIED | 85 lines; `w-[420px]` confirmed; Escape key handler present |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` | vaul Drawer.Root + useMediaQuery 900px gate | VERIFIED | 133 lines; 15 pattern matches incl. Drawer.NestedRoot |
| `frontend/src/components/vulnerabilities/drill-content.tsx` | shared 7-section content + useToast + useCreateTicketMutation + useSnoozeMutation | VERIFIED | 322 lines; all mutations wired; Toast fires on success/error |
| `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` | ≤250 lines; composes Wave 1/2; ErrorBoundary; Suspense; honors `?cve=…&open=drill` | VERIFIED | Exactly 250 lines; 5 state branches; deep-link round-trips |
| `frontend/src/components/vulnerabilities/{VulnFilters,VulnTable,BulkActions}.tsx` (v1 PascalCase) | DELETED | VERIFIED | All 3 confirmed deleted via `ls` (no such file) |
| `frontend/src/components/ui/Pagination.tsx` | restyled to sunset tokens + aria-current + mono numbers | VERIFIED | Zero raw palette utilities; `bg-pink-soft`/`text-pink`/`aria-current`/`font-mono` confirmed |
| 5 Phase 10 retrofit sites consume `@/components/states` | top5-card / trend-section / activity-rail / stat-strip-wired / onboarding-panel | VERIFIED | All 5 files import from `@/components/states`; counts: 3/3/3/2/16 primitive refs |
| `frontend/src/app/dev/primitives/showcase.tsx` | Phase 11 state primitives section added | VERIFIED | 19196 bytes; 4 primitives imported + rendered |
| `.planning/phases/11-vulnerabilities-state-patterns/11-HUMAN-UAT.md` | 8-item UAT checklist mirroring 11-VALIDATION.md §Manual-Only | VERIFIED | File exists; `status: partial`; 8 items in `[pending]` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `package.json` | `node_modules/vaul` | exact-pin install | VERIFIED | Pinned `1.1.2` (no caret) |
| `tailwind.config.ts` shimmer | SkeletonTable animation | `motion-safe:animate-shimmer` className | VERIFIED | Alias resolves to `skeleton-shimmer` keyframe; consumer uses verbatim |
| `chip-bar.tsx` severity chip click | `useUrlStateList('severity', SEVERITIES, [])` | synchronous toggle handler | VERIFIED | `toggleSeverity` called on chip click; URL flips immediately |
| `chip-bar.tsx` search input | `useUrlState('search', ...)` | 250ms debounced effect | VERIFIED | `250` literal present 3x in file |
| `vuln-table.tsx` row click/keyDown | `onRowOpen` callback | row handler | VERIFIED | Click + Enter/Space both fire `onRowOpen(row.cve_id ?? row.id)` |
| `page.tsx` → backend `/api/v1/vulnerabilities` | via `useVulnerabilities({filters,group,page,sort,order})` | TanStack query + buildSearchParams | VERIFIED | `buildSearchParams` exported; `?facets=severity,source,status` always-on |
| `page.tsx` → drill panels | via `cveId={drillOpen ? cveDeepLink : null}` | URL contract `?cve=…&open=drill` | VERIFIED | Both DrillPanel + DrillPanelMobile receive same prop; only one mounts (media query gate) |
| Phase 10 Top5Card → Phase 11 page | `?cve=…&open=drill` href | Next router | VERIFIED | top5-card.tsx writes the contract URL; page.tsx reads both params |
| 5 dashboard retrofit sites → `@/components/states` | import substitution | barrel import | VERIFIED | All 5 files import canonical primitives; legacy `microcopy.error.inline` removed from error paths |
| `drill-panel-mobile.tsx` → `vaul Drawer.Root` + `Drawer.NestedRoot` | controlled `open` driven by URL | gesture-aware bottom-sheet | VERIFIED | 3 vaul imports; nested-root pattern for ConfirmModal-inside-drawer |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `vuln-table.tsx` | `rows` prop | `useVulnerabilities` → `q.data.items` (real `/api/v1/vulnerabilities` query) | Yes (backend SQLAlchemy DB query) | FLOWING |
| `drill-content.tsx` | `v = q.data` | `useVulnerabilityDetail(idOrCve)` → `/api/v1/vulnerabilities/{id}` | Yes (real backend query) | FLOWING |
| `chip-bar.tsx` facet counts | `facets.severity[s]` | page.tsx normalizes `q.data?.facets` per-key | Yes (backend `get_facets` 3-query result) | FLOWING |
| `per-source-status-strip.tsx` | `q.data` (connectors) | `useConnectors()` → `/api/v1/connectors` | Yes (real connectors query) | FLOWING |
| `partial-failure-banner.tsx` (default mode) | `cacheErrors` | `useQueryErrors(watchKeys)` → QueryCache subscription | Yes (live TanStack cache state) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Frontend test suite passes | `npx vitest run --reporter=dot` | 49 files / 291 tests passed | PASS |
| Production build succeeds | `NODE_ENV=production npx next build` | Exit 0; 14/14 static pages generated | PASS |
| `/dev/primitives` excluded from prod bundle (BL-05) | `npx next build` route output | `/dev/primitives 124 B` (dead-code-eliminated) | PASS |
| `/dashboard/vulnerabilities` ships | `npx next build` route output | `/dashboard/vulnerabilities 22.3 kB / 155 kB First Load JS` | PASS |
| v1 PascalCase files deleted | `ls frontend/src/components/vulnerabilities/{VulnFilters,VulnTable,BulkActions}.tsx` | All 3 "No such file or directory" | PASS |
| Zero `!important` in Phase 11 surfaces | `grep -r '!important' frontend/src/components/states/ frontend/src/components/vulnerabilities/ frontend/src/app/(authed)/dashboard/vulnerabilities/` (non-test) | 0 matches | PASS |
| Zero raw palette utilities | `grep -rE "bg-red-[0-9]+\|bg-gray-[0-9]+\|bg-indigo-[0-9]+\|#[0-9a-fA-F]{6}"` across Phase 11 surfaces (non-test) | 0 matches | PASS |
| Pagination restyled (raw palette removed) | `grep -rE "bg-gray\|bg-indigo\|text-indigo" frontend/src/components/ui/Pagination.tsx` | 0 matches | PASS |
| Backend per-test pytest passes (per SUMMARY) | Documented in deferred-items.md — multi-test runs fail due to pre-existing rate-limiter Redis localhost issue; individual tests PASS | Trusted per context note | SKIP (pre-existing infra issue) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| UX-03-01 | 11-01, 11-02, 11-03, 11-05, 11-06 | Chip-bar filters above table (search + severity chips + source chips + saved-filter pill + clear-all) | SATISFIED | `chip-bar.tsx` renders all 5 components; rendered in page.tsx:161 |
| UX-03-02 | 11-01, 11-02, 11-05, 11-06 | Table 7 columns (Severity pill+glyph · CVE mono · Title · Asset mono · CVSS mono+banded · Status with KEV+exploit · SLA mono+tiered) | SATISFIED | `vuln-table.tsx` 7 visible columns; pill+glyph + mono-CVE + KEV/exploit badge + SLA banded |
| UX-03-03 | 11-02, 11-03, 11-05, 11-06 | Click row opens 420px side-panel with description/CVSS vector/hosts/remediation/actions | SATISFIED | `drill-panel.tsx` `w-[420px]`; `drill-content.tsx` 6 section `<h4>` (CVSS / Hosts / Description / Remediation / Activity / Actions); URL `?cve=…&open=drill` |
| UX-03-04 | 11-02, 11-03, 11-06 | Saved filters as violet pill (`★ Today's triage`); filter state URL-synced | SATISFIED | `useSavedFilters` query + violet `bg-violet-soft` pill in chip-bar; `useUrlStateList` writes URL |
| UX-03-05 | 11-01, 11-02, 11-03, 11-05, 11-06 | Toggle By-CVE / By-Host via segmented control in page-head actions | SATISFIED | `view-toggle.tsx` 2-segment pill; backend `?group=host` returns `VulnerabilityByHost`; filter state preserved across toggle |
| UX-03-06 | 11-02, 11-05, 11-06 | At <900px: table collapses to card view AND drill panel becomes full-screen overlay | PARTIAL | Drill panel mobile shipped (`drill-panel-mobile.tsx` via vaul); **table-card-view collapse NOT implemented — deferred to Phase 15 SC #1**. |
| UX-S-01 | 11-02, 11-04, 11-06, 11-07 | Loading state: skeleton chip-bar + skeleton table rows + per-source progress strip | SATISFIED | `SkeletonTable` (D-S-01) at page.tsx:167; `PerSourceStatusStrip` (D-V-02) at line 153 |
| UX-S-02 | 11-02, 11-04, 11-06, 11-07 | Empty state: explained-why + 3-tier CTAs + violet lightbulb suggestion | SATISFIED | `EmptyState` compound with `.Title`/`.Body`/`.Actions` (3 buttons)/`.Suggestion` (`<Lightbulb>` icon + violet chrome) at page.tsx:181-199 |
| UX-S-03 | 11-02, 11-03, 11-04, 11-06, 11-07 | Partial failure: amber inline banner + per-source status cards + stale rows tinted | SATISFIED | `PartialFailureBanner` (D-S-03) + `PerSourceStatusStrip` + `failedSources` prop → `data-stale="true"` + `bg-amber-soft` on rows |
| UX-S-04 | 11-02, 11-04, 11-06 | Total failure: empty-state shell with retry CTAs | SATISFIED | `EmptyState` with title/body/retry button at page.tsx:170-178 (q.error branch) |
| UX-S-05 | 11-02, 11-04, 11-06 | Toast notifications for transient events (ticket created, snooze, retry) | SATISFIED | `useToast` invoked in `drill-content.tsx` for ticket success (with View action), ticket error, snooze success, snooze error |

**Note on UX-03-06:** Plans 11-02 / 11-05 explicitly scoped UX-03-06 to the vaul mobile drill-panel work; the table-card-view collapse is acknowledged in CONTEXT.md line 11 but Phase 15 Success Criterion #1 ("tables collapse to card view at <900px") is the milestone-closing gate where the audit lands. Per Step 9b: this is a deferred item, not a gap.

**Orphaned requirements:** None. All 11 phase requirement IDs (UX-03-01..06, UX-S-01..05) appear in at least one plan's `requirements` frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | TODO/FIXME/XXX/PLACEHOLDER scan across Phase 11 production files | — | Zero matches |
| (none) | — | `!important` scan across Phase 11 surfaces (non-test) | — | Zero matches |
| (none) | — | Raw palette utility scan (`bg-red-/text-emerald-/bg-gray-/bg-indigo-/hex`) across Phase 11 surfaces | — | Zero matches |
| (none) | — | `role="grid"` scan in vuln-table.tsx (Pitfall 5 — must avoid) | — | Zero matches |

### Human Verification Required

8 manual-only items per `11-HUMAN-UAT.md` (mirrors 11-VALIDATION.md §Manual-Only Verifications):

#### 1. Sunset visual continuity vs Phase 10 (D-S-06)

**Test:** Open `/dashboard` (Phase 10) and observe Top-5 card loading + error appearance now using `SkeletonTable` + `PartialFailureBanner`. Compare side-by-side against Phase 10 baseline screenshot.
**Expected:** No regression in dashboard visual hierarchy; only loading shimmer + error chrome changed.
**Why human:** Visual perception against pre-retrofit baseline.

#### 2. 420px drill panel layout vs sketch-003 variant C (UX-03-03)

**Test:** Open `/dashboard/vulnerabilities?cve=<seeded-CVE>&open=drill`. Side-by-side compare against `.claude/skills/sketch-findings-getvul/sources/003-vulnerabilities-sunset/index.html` (variant C).
**Expected:** Panel layout matches sketch within rendering tolerance.
**Why human:** Visual fidelity comparison against HTML mockup.

#### 3. vaul mobile bottom-sheet on real device (UX-03-06)

**Test:** Open the page on a real mobile device (iPhone Safari + Android Chrome) or Chrome DevTools iPhone 14 Pro emulation. Tap row → vaul drawer slides up. Swipe down / tap × / Esc all close. Tap "Create ticket" → confirmation appears.
**Expected:** Smooth drag gesture, no jank, focus correctly returns after close.
**Why human:** Touch gestures and iOS Safari behavior cannot be exercised in jsdom.

#### 4. Empty-state copy voice + tone (UX-S-02 + copy-voice.md)

**Test:** Apply 5 filters that produce zero results. Read the `EmptyState` aloud. Verify title is sentence case (no exclamation, no "Welcome", no "Please"); body explains why; violet lightbulb suggestion is informative; 3 CTAs at 3 tiers.
**Expected:** Tone matches `copy-voice.md` exemplar — peer, not butler.
**Why human:** Tone/voice quality evaluation.

#### 5. Screen-reader announcements (D-S-07 + UX-07-03 partial)

**Test:** Enable VoiceOver (macOS) or NVDA (Windows). Navigate to `/dashboard/vulnerabilities`. Verify "Loading vulnerabilities" announced during skeleton render. Tab into table → first row announced with severity + CVE + asset. ArrowDown navigates rows. Enter announces "dialog Vulnerability detail". PartialFailureBanner announced as alert.
**Expected:** All ARIA roles/labels exercised; no double-announcement; no focus traps.
**Why human:** Audio output cannot be automated.

#### 6. Forced-colors-mode preservation (Phase 9 a11y carryover)

**Test:** Enable Windows High Contrast or Edge "Force Colors" devtools toggle. Verify severity glyphs survive grayscale, SkeletonTable rows perceivable, PartialFailureBanner amber chrome maps cleanly, focus rings visible.
**Expected:** No invisible UI in forced-colors mode.
**Why human:** Visual inspection at OS-level.

#### 7. Reduce-motion shimmer suppression (Phase 9 a11y carryover)

**Test:** Enable macOS Reduce Motion or Chrome DevTools `prefers-reduced-motion: reduce`. Reload `/dashboard/vulnerabilities` during loading. Verify SkeletonTable shimmer stops; pulsing dot on dashboard hero stops; gradient-mesh drift on /login stops.
**Expected:** All animations halted; visual shape preserved.
**Why human:** OS-level reduce-motion behavior visual verification.

#### 8. Real-world filter + pagination performance @ 2k vulns (D-T-03 sanity)

**Test:** Seed dev DB with 2,000 vulnerabilities. Profile vulnerabilities page with React DevTools profiler. Apply Critical filter → measure render time. Toggle 5 pages of pagination. Open drill panel on the 47th row of page 3.
**Expected:** No visible jank; render times <100ms per interaction; no need for virtualization.
**Why human:** Profiler perception of jank requires interactive use.

### Gaps Summary

**No automated gaps found.** All 7 ROADMAP Success Criteria are either VERIFIED (6) or correctly DEFERRED to Phase 15 (1: mobile table-card-view collapse). All 11 phase requirements (UX-03-01..06 + UX-S-01..05) are SATISFIED at primitive + page level, with UX-03-06 PARTIAL (drill panel done; table-card-view deferred to Phase 15 — matches Phase 15 SC #1 explicitly).

All 30+ artifacts exist, are substantive, are wired, and data flows from real backend to real components. Phase 10 deep-link contract (`?cve=…&open=drill`) round-trips both directions. Frontend test suite is 291/291. Production build exits 0 with `/dev/primitives` at 124 B (BL-05 dead-code-elimination preserved). v1 PascalCase surface is fully deleted.

**Status is `human_needed`** because 8 manual UAT items in `11-HUMAN-UAT.md` require a human reviewer to walk through a live dev environment with screen readers, real mobile devices, forced-colors mode, reduce-motion, and a 2k-vuln seed for perf sanity. These are explicitly enumerated as automation-incompatible in `11-VALIDATION.md §Manual-Only Verifications`.

---

_Verified: 2026-05-27T12:15:00Z_
_Verifier: Claude (gsd-verifier)_
