---
phase: 12
name: assets-list-detail
researched: 2026-05-29
status: ready-for-planning
---

# Phase 12 Research — `/assets` List + Detail

**Methodology note:** The autonomous gsd-phase-researcher run timed out at ~70min without producing output. This research was synthesized by Claude via focused codebase exploration of the critical questions identified during /gsd-discuss-phase. CONTEXT.md decisions remain authoritative; this document records reality-check deltas and an implementation-ready plan map.

---

## Reality-Check Deltas (CONTEXT.md vs. Actual Codebase)

These are the gaps between what CONTEXT.md assumed and what the code actually contains. The planner MUST resolve each one explicitly — many of CONTEXT.md's locked decisions depend on the assumed shapes.

### 1. Asset schema is owner-by-string + directory-user-resolve, not owner-by-FK

**CONTEXT.md decision:** D-A-03 — `POST /api/v1/assets/{id}/owner` with body `{ user_id: string }`.

**Actual:**
- [backend/app/assets/schemas.py:11-37](backend/app/assets/schemas.py#L11-L37) — `AssetResponse` has `assigned_user: str | None` (a string identifier, typically email) and `mdm_details: dict | None`. There is **no** `owner_user_id` FK column.
- [backend/app/assets/router.py:20-61](backend/app/assets/router.py#L20-L61) — `_get_directory_user(db, tenant_id, asset)` resolves the owner by matching `humaans_email` / `assigned_user` / `last_login_user` against `User.email`. The detail endpoint returns the resolved `directory_user` dict at [router.py:300](backend/app/assets/router.py#L300).
- `User` model is in `app.tenants.models` and DOES have a `uuid` primary key, `email`, `display_name`, `idp_source`, `role`, `is_active`, `avatar_url`, `department`, `job_title`.

**Planner action:** Decide between
- **(A)** Keep `assigned_user: str` semantics — Reassign endpoint accepts `{ assigned_user_email: str }`, updates the string field, audit-logs `asset.owner_changed`. Directory user resolution is recomputed at read time (already works this way). **Smallest delta, no migration.** Recommended.
- **(B)** Add `owner_user_id: UUID FK -> users.id` column + Alembic migration + backfill from `assigned_user` lookup + update read path to prefer FK over string match. **Larger surface, cleaner long-term.**

CONTEXT.md D-A-03 is consistent with (A) once we rename the body field. **Recommend (A) for Phase 12; defer (B) to a later cleanup phase if owner-by-FK becomes desirable.**

### 2. Reassign data source: `/api/v1/users` is wrong; `/api/v1/users/directory` is correct

**CONTEXT.md decision:** D-A-02 — Data source `/api/v1/users` (platform users only).

**Actual:**
- [backend/app/users/router.py:22-49](backend/app/users/router.py#L22-L49) — `GET /api/v1/users` returns **aggregated user-by-device rollups**, not platform user records. Each item has `user_key` (lowercased email string), not a UUID. It's a "people who own devices" view, derived from Humaans enrichment.
- [backend/app/users/router.py:251-310](backend/app/users/router.py#L251-L310) — `GET /api/v1/users/directory` returns flat `User` records with `id` (UUID), `email`, `display_name`, `idp_source`, `is_active`, `department`, `job_title`. **This is the correct combobox source.** Supports `search`, `status=active`, `department`, `source`, paginated.

**Planner action:** Reassign combobox queries `/api/v1/users/directory?status=active&search=<typed>`. Hook name `useAssignableUsers` (renamed from CONTEXT.md's implied `useUsers`).

### 3. Asset schema is missing several fields the UI assumes

**CONTEXT.md expects:** `tags`, `os_family`, `sla_breaches`, `7_day_delta`, `critical_exposures`.

**Actual:** None of these columns/fields exist on `Asset` or in the response. What DOES exist:
- `os_name` (free string: "Windows 10", "macOS Ventura", "Ubuntu 22.04 LTS") — `os_family` must be derived
- `vuln_counts: { total, critical, high, medium, low, exploitable, kev }` from detail endpoint at [router.py:304-312](backend/app/assets/router.py#L304-L312) — `kev` count exists ✓; `critical_exposures` = `vuln_counts.critical` (rename for the UI)
- `risk_score` exists as a current snapshot integer — **no historical series**, no `7_day_delta`
- `sla_due_at` is on `Vulnerability`, not `Asset` — SLA breaches per asset require an aggregation query (count vulns where `sla_due_at < now AND status IN ('OPEN','IN_PROGRESS')`)
- No `tags` field anywhere in `Asset` schema

**Planner action — pick scope explicitly:**
- **OS family** — derive client-side via a `osFamily(os_name)` helper that maps prefix → `Linux | Windows | macOS | Other`. Reuse in chip-bar filter logic. No backend work.
- **SLA breaches count** — extend the `vuln_counts` aggregation in [assets/router.py:228](backend/app/assets/router.py#L228) to add `sla_breach` count. Small SQL delta. Required for UX-04-03 risk-ring breakdown row 2.
- **CISA KEV count** — already present in `vuln_counts.kev` ✓
- **Critical exposures count** — already present in `vuln_counts.critical` ✓
- **7-day delta** — `risk_score_history` table does NOT exist. **Two options for the planner:**
  - **(C)** Ship Phase 12 with the delta row rendering `—` + "Trend unavailable" microcopy when history is missing; create a follow-up phase for risk_score history persistence.
  - **(D)** Add `risk_score_history` table + write-through on every `compute_risk_scores` run + 7-day lookup query. Adds non-trivial scope to Phase 12.

**Recommend (C)** — keeps Phase 12 scope tight; the delta is one of 4 rows, not the whole risk card; CONTEXT.md D-R-03 already established the "empty / unavailable" pattern. Add a `<deferred>` entry to ROADMAP for the history table.

- **Tags** — Add `tags: ARRAY(String)` Alembic migration on `Asset` + extend `AssetResponse` + extend `AssetSummary`. Empty default. Backfill is a no-op (NULL/empty). UX-04-02 success criterion 5 explicitly requires tags inline with hostname. Required.

### 4. Tickets endpoint has no `asset_id` filter; small extension required

**CONTEXT.md decision:** D-D-02 — Remediation timeline data source = `/api/v1/tickets?asset_id={id}`, ordered by `updated_at desc`.

**Actual:**
- [backend/app/ticketing/router.py:95-105](backend/app/ticketing/router.py#L95-L105) — `list_all_tickets` accepts `provider`, `status`, `page`, `page_size` only.
- [backend/app/ticketing/service.py:598-680](backend/app/ticketing/service.py#L598-L680) — `list_tickets` service already joins `Ticket → Vulnerability → Asset` via `outerjoin(Asset, Vulnerability.asset_id == Asset.id)`. Adding an `asset_id` filter is a 3-line change inside the existing query: filter `Vulnerability.asset_id == asset_id` on the `base_filter` list.

**Planner action:** Add `asset_id: uuid.UUID | None = Query(None)` param to `list_all_tickets`, thread through to `list_tickets(...)`. Adjust base filter inside `list_tickets`. The ordering CONTEXT.md asks for (`updated_at desc`) currently uses `ticket_created_at desc` — keep the existing ordering or add a sort param; **recommend keeping `ticket_created_at desc` since it's more intuitive for the timeline ("when was this remediation kicked off") and is what `list_tickets` already produces.** Document the deviation.

### 5. `useVulnerabilities` does not accept `asset_id`; backend already does

**CONTEXT.md decision:** D-D-01 — `useAssetVulnerabilities(id)` reuses `useVulnerabilities` query factory with `{ asset_id }` filter.

**Actual:**
- [frontend/src/lib/queries/use-vulnerabilities.ts:7-14](frontend/src/lib/queries/use-vulnerabilities.ts#L7-L14) — `VulnerabilitiesFilters` type has `severity / source / status / search / kev_only / exploit_only`. **No `asset_id` field.**
- [frontend/src/lib/queries/use-vulnerabilities.ts:62-85](frontend/src/lib/queries/use-vulnerabilities.ts#L62-L85) — `buildSearchParams` does not append `asset_id`.
- [backend/app/vulnerabilities/router.py:60](backend/app/vulnerabilities/router.py#L60) — **Backend `/api/v1/vulnerabilities` ALREADY accepts `asset_id: uuid.UUID | None = Query(None)`.** No backend work needed.

**Planner action:** Extend `VulnerabilitiesFilters` to add `asset_id?: string` + extend `buildSearchParams` to append `asset_id` when set. The Phase 11 query key already opaquely carries the `filters` object — adding a field doesn't break existing callers (TypeScript will allow undefined). Verify the existing `useVulnerabilities.test.tsx` doesn't pin the filter shape negatively.

### 6. ChipBar is vuln-hardcoded; generic axis support is a real refactor

**CONTEXT.md decision:** D-L-02 — 4 chip-bar filter axes (Category / Risk band / Source / OS) using Phase 11's `useUrlStateList` hook. CONTEXT.md `<code_context>` notes ChipBar "may need a minor refactor to accept arbitrary chip categories vs. its current vuln-specific signature."

**Actual:** [frontend/src/components/vulnerabilities/chip-bar.tsx:19-67](frontend/src/components/vulnerabilities/chip-bar.tsx#L19-L67):
- Hardcoded `const SEVERITIES = ['critical','high','medium','low','info']`
- Hardcoded `const SOURCES = ['QUALYS','TENABLE','RAPID7','CROWDSTRIKE','AWS_INSPECTOR','WIZ','MOCK']`
- Hardcoded `SEVERITY_GLYPH`, `SEVERITY_LABEL`, `SEVERITY_GLYPH_COLOR` maps
- `facets` prop typed `{ severity, source, status? }` only
- The component owns `useUrlStateList('severity', ...)` and `useUrlStateList('source', ...)` internally — keys are hardcoded
- Search-debounce logic is intertwined with chip rendering (single component, ~290 lines)

**This is NOT a minor refactor.** The planner has 3 realistic options:

- **(E)** **Two-tier component split**: extract a generic `<ChipBarShell>` (search input + clear-all + saved-filter pill + slot/render-prop for chip groups) and rebuild today's vuln-specific bar as `<VulnerabilitiesChipBar>` consuming the shell. Phase 12 then builds `<AssetsChipBar>` consuming the same shell with Category / Risk band / Source / OS axes. **Best long-term shape.** Most refactor risk in Phase 11 surface.
- **(F)** **Parameterize via a `<ChipBar>` descriptor prop** — pass `axes: Array<{ key, allowList, glyph?, label, color? }>` + `facets` keyed by axis key. Rebuild the existing call site in `vulnerabilities/page.tsx` to pass the vuln axis descriptor. Backwards-incompatible signature change; one caller migration. **Cleaner API; slightly more typing work upfront.**
- **(G)** **Duplicate** — copy `chip-bar.tsx` → `components/assets/chip-bar.tsx`, swap axes, accept the technical debt. **Fastest to write; worst long-term.** Recommend against unless time-pressed.

**Recommend (F)** — parameterize via descriptor prop. Allows a single chip-bar implementation, exercises Phase 11's `useUrlStateList` generically (it already accepts arbitrary keys + allow-lists), and the migration cost is one file (`vulnerabilities/page.tsx` callsite).

**Note:** The 'status' chip group is currently rendered separately in vulnerabilities — check the rendered call in `vulnerabilities/page.tsx` to confirm the descriptor abstraction covers it.

### 7. Risk-ring SVG: math is established; gradient is already a CSS var

**Sketch 005 variant B markup** (verified):
```html
<svg viewBox="0 0 100 100" style="transform: rotate(-90deg)">
  <circle cx="50" cy="50" r="40" class="ring-bg" />
  <circle cx="50" cy="50" r="40" class="ring-fg"
          stroke="url(#sunset-grad)"
          stroke-dasharray="251.3"
          stroke-dashoffset="35" />
  <defs>
    <linearGradient id="sunset-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#EC4899"/>
      <stop offset="50%"  stop-color="#A78BFA"/>
      <stop offset="100%" stop-color="#F59E0B"/>
    </linearGradient>
  </defs>
</svg>
```

- **Circumference** = 2π × r = 2π × 40 ≈ **251.3**
- **stroke-dashoffset** = circumference × (1 − score/100). Score 100 → offset 0 (full ring); score 0 → offset 251.3 (empty ring).
- **Stroke colors per D-R-01:** the gradient is the **violet/pink/amber sunset** triplet, hard-coded in the sketch. CONTEXT.md D-R-01 says color bands map to sunset semantic tokens (`80–100 → danger`, `50–79 → amber`, `20–49 → pink`, `0–19 → violet/success`). **Two interpretations possible:**
  - **(H)** Single gradient stroke always — ring color is always the sunset gradient; the **score color band only affects the centered number text + breakdown row tints**, not the ring stroke. This matches what the sketch literally shows. **Simpler.**
  - **(I)** Variable stroke color — at score ≥80, ring is solid danger; 50–79 amber gradient; 20–49 pink; 0–19 violet. Requires building 4 separate gradient definitions. **More expressive but diverges from the locked sketch.**

**Recommend (H)** — the sketch is the locked design. The 4-band semantic mapping (D-R-01) drives the **center text color + breakdown row tints**, not the stroke. Matches "the number is the value, not a flourish" (D-R-02).

- **Edge cases** (D-R-03): score 0 → no fg circle rendered + center is em-dash `—` + caption "No exposures"; score 100 → full ring + number in `text-danger`; score null → no fg circle + caption "Risk unavailable".
- **Drop-shadow filter** in the sketch (`filter: drop-shadow(0 0 8px currentColor)`) — keep, but gate behind `motion-safe:` if it triggers reduce-motion concerns. Filters aren't motion strictly speaking — keep unconditionally.

### 8. No existing RiskRing / Breadcrumb / Avatar primitives

Verified — `grep` across `frontend/src/components` returns no matches for `RiskRing`, `Breadcrumb`, or `Avatar`. All three are new primitives in Phase 12.

**Locations (Claude's discretion per CONTEXT.md):**
- `frontend/src/components/ui/RiskRing.tsx` — reusable on `/dashboard` Top-N cards in a future phase
- `frontend/src/components/ui/Breadcrumb.tsx` — Phase 13 `/tickets/[id]` will reuse
- `frontend/src/components/ui/Avatar.tsx` — needed for owner card + topbar user chip + (eventually) directory pages. Renders 40px sunset-gradient circle with initials; props `{ name, email?, size? }`. Sketch shows `var(--gradient-sunset)` background with white text.

---

## Files Modified / Created (Plan-Scope Preview)

### Backend
| File | Change | Plan candidate |
|------|--------|----------------|
| `backend/app/assets/models.py` | Add `tags = Column(ARRAY(String), nullable=True)` | 12-01 |
| `backend/migrations/versions/<NEW>_asset_tags.py` | Alembic: add `tags` column to `assets` | 12-01 |
| `backend/app/assets/schemas.py` | Extend `AssetResponse` + `AssetSummary` with `tags`, `sla_breach` | 12-01 |
| `backend/app/assets/router.py` (list + detail) | Add `sla_breach` to vuln_counts aggregation; surface `tags` | 12-01 |
| `backend/app/assets/router.py` (new endpoint) | `POST /assets/{id}/owner` with `{ assigned_user_email: str }`, audit `asset.owner_changed` | 12-02 |
| `backend/app/assets/router.py` (list filter) | Accept `os_family` query param mapped to ILIKE prefix on `os_name` (or extend `device_category` to support OS family axis) | 12-01 |
| `backend/app/ticketing/router.py` + `service.py` | Add `asset_id` query param + filter on `Vulnerability.asset_id` | 12-02 |
| `backend/tests/...` | Tests for owner update endpoint, asset_id ticket filter, tags filter | 12-01 / 12-02 |

### Frontend — primitives (new)
| File | Purpose | Plan candidate |
|------|---------|----------------|
| `frontend/src/components/ui/RiskRing.tsx` + test | SVG ring + center number + edge cases (0 / 100 / null) | 12-03 |
| `frontend/src/components/ui/Breadcrumb.tsx` + test | `<Breadcrumb><Crumb href>Assets</Crumb><Crumb>prod-db-01</Crumb></Breadcrumb>` | 12-03 |
| `frontend/src/components/ui/Avatar.tsx` + test | Sunset-gradient circle with initials; 24px / 40px / custom | 12-03 |

### Frontend — ChipBar generification
| File | Change | Plan candidate |
|------|--------|----------------|
| `frontend/src/components/vulnerabilities/chip-bar.tsx` | Refactor to descriptor-driven (`axes: ChipAxis[]`); preserve existing API or rename to `<ChipBar>` in `components/ui/` | 12-04 |
| `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` | Pass vuln axis descriptor to refactored ChipBar | 12-04 |
| `frontend/src/components/vulnerabilities/chip-bar.test.tsx` | Update tests for new signature | 12-04 |

### Frontend — assets list
| File | Change | Plan candidate |
|------|--------|----------------|
| `frontend/src/lib/queries/keys.ts` | Add `assets` namespace (`list`, `byId`, `vulnerabilities`, `remediations`, `savedFilters`) | 12-05 |
| `frontend/src/lib/queries/use-assets.ts` + test | `useAssets({ filters, page, sort })` returns list + facets | 12-05 |
| `frontend/src/lib/queries/use-asset-detail.ts` + test | `useAsset(id)` returns asset + directory_user + vuln_counts | 12-05 |
| `frontend/src/lib/queries/use-asset-vulnerabilities.ts` + test | Wraps `useVulnerabilities` with `{ asset_id: id }` after `asset_id` is added to filter type | 12-05 |
| `frontend/src/lib/queries/use-asset-remediations.ts` + test | `/api/v1/tickets?asset_id=<id>` ordered by created_at | 12-05 |
| `frontend/src/lib/queries/use-vulnerabilities.ts` | Add `asset_id` to `VulnerabilitiesFilters` + `buildSearchParams` | 12-05 |
| `frontend/src/components/assets/assets-chip-bar.tsx` + test | Wraps generic ChipBar with Category / Risk band / Source / OS axes | 12-06 |
| `frontend/src/components/assets/assets-table.tsx` + test | 6 columns (Hostname mono · OS · Owner avatar+name · Risk · Tags · Sources); reuses Phase 11 row patterns | 12-06 |
| `frontend/src/app/(authed)/dashboard/assets/page.tsx` | Rewrite using QueryClient hooks; SkeletonTable / EmptyState / PartialFailureBanner | 12-06 |

### Frontend — assets detail
| File | Change | Plan candidate |
|------|--------|----------------|
| `frontend/src/components/assets/risk-card.tsx` + test | RiskRing + 4-row breakdown (critical / SLA breach / KEV / 7d delta with `—` fallback) | 12-07 |
| `frontend/src/components/assets/owner-card.tsx` + test | Avatar + name + role + email + IdP source pill; Reassign action toggles to combobox | 12-07 |
| `frontend/src/components/assets/reassign-combobox.tsx` + test | Searchable input → `useAssignableUsers` → Esc cancels / Enter confirms; optimistic mutation | 12-07 |
| `frontend/src/lib/queries/use-assignable-users.ts` + test | Wraps `/api/v1/users/directory?status=active&search=<q>` | 12-07 |
| `frontend/src/lib/queries/use-reassign-asset.ts` + test | `POST /api/v1/assets/{id}/owner`; invalidates `assets.byId(id)` + `assets.all` | 12-07 |
| `frontend/src/components/assets/severity-ribbon.tsx` + test | ■2 · ▲3 · ◆1 · ○1 ribbon above vulns | 12-08 |
| `frontend/src/components/assets/asset-vulns-list.tsx` + test | Compact rows of `useAssetVulnerabilities` data; clicking opens Phase 11 DrillPanel via `?cve=<id>&open=drill` | 12-08 |
| `frontend/src/components/assets/remediation-timeline.tsx` + test | Provider mark + ticket title + status pill + relative timestamp | 12-08 |
| `frontend/src/components/assets/identity-metadata-rail.tsx` + test | Stacked metadata block (8 fields) | 12-08 |
| `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` | Two-column layout (main + 340px sticky rail); Breadcrumb + tags + page composition | 12-08 |

### Frontend — chrome integration
| File | Change | Plan candidate |
|------|--------|----------------|
| `frontend/src/lib/util/os-family.ts` + test | `osFamily(os_name: string): 'Linux' \| 'Windows' \| 'macOS' \| 'Other'` | 12-03 |

---

## Wave / Dependency Map

```
Wave 1 (backend foundation):
  12-01 — assets schema: tags + sla_breach (migration + endpoints)
  12-02 — owner reassign endpoint + tickets asset_id filter

Wave 2 (frontend primitives + ChipBar refactor):
  12-03 — RiskRing + Breadcrumb + Avatar + os-family helper   [no deps on Wave 1]
  12-04 — ChipBar generification (preserves /vulnerabilities)  [no deps on Wave 1]

Wave 3 (query hooks + list page):
  12-05 — assets query namespace + 5 hooks                     [needs 12-01, 12-02]
  12-06 — /assets list page                                    [needs 12-03, 12-04, 12-05]

Wave 4 (detail page composition):
  12-07 — risk card + owner card + reassign combobox           [needs 12-03, 12-05]
  12-08 — severity ribbon + vulns list + timeline + identity rail + page    [needs 12-05, 12-07]
```

Wave 2 plans (primitives + chip refactor) are independent of Wave 1 (backend) — they can run in parallel if executor parallelism is enabled.

---

## Validation Architecture (Nyquist)

Per REQUIREMENT IDs UX-04-01..05 — each MUST have at least one verifiable test invocation.

### UX-04-01 — `/assets` list with chip-bar
- **Unit:** `use-assets.test.tsx` — buildSearchParams produces stable URL for each filter combo
- **Component:** `assets-chip-bar.test.tsx` — chip click toggles URL key; clear-all resets all 4 axes; saved-filter pill applies first saved filter
- **Component:** `assets-table.test.tsx` — renders 6 columns; loading shows SkeletonTable; empty shows EmptyState; partial failure shows PartialFailureBanner
- **Integration:** `assets/page.test.tsx` — chip click triggers data refetch with new filter; pagination updates URL

### UX-04-02 — `/assets/[id]` two-column detail
- **Component:** `assets/[id]/page.test.tsx` — renders two-column layout above 900px; collapses to single column below 900px
- **Component:** breadcrumb renders above page title; tag list renders inline with hostname
- **Visual:** Playwright snapshot at 1280px and 390px viewports (sketch 005 variant B fidelity check)

### UX-04-03 — Risk score ring with 4-row breakdown
- **Unit:** `RiskRing.test.tsx` — stroke-dashoffset computed correctly for scores 0 / 20 / 50 / 80 / 100 / null
- **Component:** `risk-card.test.tsx` — 4 breakdown rows render with correct icons + counts + color tints; delta row shows `—` + "Trend unavailable" when history missing; score 0 shows em-dash; score 100 tints center text danger
- **a11y:** axe pass on the risk card; SVG has aria-label with score and band

### UX-04-04 — Owner card + Reassign
- **Component:** `owner-card.test.tsx` — renders Avatar + name + role + IdP source pill + email; "Reassign" button toggles to combobox
- **Component:** `reassign-combobox.test.tsx` — Esc cancels (reverts to display); Enter confirms (calls mutation); blur outside cancels; loading state during request; error state on 4xx/5xx
- **Integration:** `assets/[id]/page.test.tsx` — reassign confirms → optimistic UI update → asset.byId cache invalidated → owner card re-renders with new owner
- **Backend:** `test_assets_owner.py` — POST /assets/{id}/owner updates assigned_user, writes audit log entry, returns updated asset; 404 on missing asset; 403 on cross-tenant

### UX-04-05 — Phase 11 state patterns reused (no new variants)
- **Audit:** grep verification — no new `Skeleton*` or `EmptyState*` or `*Banner` components added to `components/states/` during Phase 12
- **Component:** Each Phase 12 page test asserts at least one Phase 11 state primitive rendered in loading/empty/error scenarios
- **Documentation:** `<state_patterns_used>` block in each PLAN.md lists which Phase 11 primitives are imported

### Cross-cutting (success criteria 1–6)
- **E2E (Playwright):** drill flow — `/assets` → click row → DrillPanel opens with correct `?cve=<id>&open=drill` URL → close panel → returns to `/assets` with scroll preserved
- **E2E (Playwright):** detail flow — `/assets` → click hostname → `/assets/[id]` → click vuln row → DrillPanel opens in-context → close → still on `/assets/[id]` at same scroll
- **E2E (Playwright):** reassign flow — `/assets/[id]` → click Reassign → type query → select → Enter → owner card shows new owner without page reload
- **Build:** `pnpm tsc --noEmit` exits 0; `pnpm lint` exits 0
- **Backend tests:** new endpoints have ≥ 1 happy-path + 1 sad-path test

---

## Open Decisions for the Planner

The following items in CONTEXT.md require explicit resolution before plans are finalized — the planner should choose one and document the choice in the plan's `<deviations>` block:

| # | Question | Recommended | Alt |
|---|----------|-------------|-----|
| 1 | Owner FK vs string | (A) keep `assigned_user: str`; rename body field to `assigned_user_email` | (B) add `owner_user_id` FK + migration |
| 2 | 7-day delta | (C) render `—` + "Trend unavailable" + defer history table | (D) ship history table now |
| 3 | Ring stroke color | (H) single sunset gradient stroke always; band affects center text + breakdown tints | (I) variable stroke per band |
| 4 | ChipBar generification | (F) descriptor prop on existing ChipBar; migrate vuln callsite | (E) two-tier shell split / (G) duplicate |
| 5 | OS family axis | Client-side derive from `os_name` prefix in chip-bar + add `os_family` query param to backend list endpoint that maps to `ILIKE` patterns | Backend adds `os_family` enum column |
| 6 | Timeline sort | Keep `ticket_created_at desc` (matches existing `list_tickets`) | Add `updated_at desc` per CONTEXT.md D-D-02 |

---

## Pitfalls to Watch (carried forward from Phase 11)

1. **Search debounce coupling** — when adding chip click handlers to the new AssetsChipBar, flush pending search via the same `buildHref` pattern (chip-bar.tsx:113-121) or chip clicks lose unflushed search text.
2. **`useUrlStateList` allow-list** — every new chip axis MUST have a hardcoded allow-list (XSS clamp). Risk-band values: `['critical','high','medium','low']`. OS family: `['linux','windows','macos','other']`. Category: `['WORKSTATION','SERVER','NETWORK','MOBILE','OTHER']`. Source: live from facets but clamped against the SOURCES list from existing chip-bar.tsx.
3. **`useAssetVulnerabilities` query key** — must NOT collide with `/vulnerabilities` list page cache. The shared `useVulnerabilities` factory keys off `{ filters, group, page, sort, order }`. Setting `filters.asset_id` differentiates the cache entry naturally — verify in the query-key test.
4. **`directory_user` field may be null** — when an asset's `assigned_user` doesn't match a `User` row. Owner card needs an empty state (avatar with `?` or first letter of `assigned_user`, name = `assigned_user` string, role = "Unassigned in directory", IdP pill hidden). Don't crash on null.
5. **Mobile breakpoint** — sketch 005 variant B implies <900px stacks rail below main; matches Phase 11 D-P-03 drill-panel mobile gate. Use the same Tailwind breakpoint (`md:` or custom `@media (min-width: 900px)`).
6. **Tags column wrap** — CONTEXT.md "Claude's Discretion" — prefer wrap (no truncation). Use `flex-wrap` on the tag list; let row height grow.
7. **Audit log for reassign** — must call the existing `audit(...)` helper from `app.audit` (used elsewhere in router.py for `asset.ignore`). Action key: `asset.owner_changed`. Include `{from: <old>, to: <new>, hostname: <h>}` in the metadata.

---

## STRIDE Threat Register (canonical)

This register is the single source of truth for T-12-NN IDs referenced across all Phase 12 plans. IDs MUST be unique; each plan's `<threat_model>` block references these by ID without redefining them.

| ID | STRIDE | Surface | Plan | Disposition |
|----|--------|---------|------|-------------|
| T-12-01 | Tampering | list_assets `os_family` query param | 12-01 | mitigate (hardcoded ILIKE allow-list) |
| T-12-02 | Information Disclosure | tags ARRAY contents | 12-01 | accept (tenant-scoped, operational labels) |
| T-12-03 | Denial of Service | os_family wildcard ILIKE table scan | 12-01 | accept (bounded table, indexable later) |
| T-12-04 | Tampering / XSS | Avatar `name` prop renders to DOM | 12-03, 12-07 | mitigate (text-node only, no innerHTML) |
| T-12-05 | Tampering / XSS | ChipBar axis URL state | 12-04, 12-06 | mitigate (hardcoded `allowList` clamp) |
| T-12-06 | Information Disclosure | useAsset(id) cross-tenant probe | 12-05 | mitigate (backend tenant filter) |
| T-12-07 | Tampering / XSS | AssetsTable cell rendering | 12-06 | mitigate (React text auto-escape) |
| T-12-08 | Elevation of Privilege | mass assignment via reassign body | 12-02, 12-07 | mitigate (Pydantic `_AssetOwnerUpdate` single explicit field) |
| T-12-09 | Repudiation | missing audit row on owner change | 12-02, 12-07 | mitigate (audit() call in same transaction) |
| T-12-10 | Tampering / XSS | DrillPanel URL `?cve=` / `?open=` injection | 12-08 | mitigate (Phase 11 D-P-02 allow-list carries forward) |
| T-12-11 | Tampering | empty / whitespace-only email on reassign | 12-02 | mitigate (`.strip().lower()` + 422 if empty) |
| T-12-12 | Tampering | Breadcrumb `href` prop | 12-03 | accept (Next router serialization) |
| T-12-13 | Tampering | savedFilter.query untrusted | 12-04 | mitigate (useUrlStateList read-side clamp) |
| T-12-14 | Information Disclosure | useAssignableUsers leak | 12-05 | accept (backend already tenant-scoped) |
| T-12-15 | Denial of Service | useAssignableUsers per-keystroke spam | 12-05 | mitigate downstream (combobox debounces in 12-07) |
| T-12-16 | Information Disclosure | URL `?asset_id=` cross-tenant probes | 12-06 | accept (backend-owned) |
| T-12-17 | Denial of Service | combobox per-keystroke spam | 12-07 | mitigate (250ms input debounce) |
| T-12-18 | Tampering / XSS | RemediationTimeline external_ticket_url | 12-08 | mitigate (`rel="noreferrer"`, React attr escape) |
| T-12-19 | Tampering / XSS | asset.tags + asset.hostname rendering | 12-08 | mitigate (React text auto-escape) |
| T-12-20 | Information Disclosure | `update_asset_owner` cross-tenant probe | 12-02 | mitigate (`Asset.tenant_id` filter; 404 not 403) |
| T-12-21 | Information Disclosure | `GET /tickets?asset_id=` cross-tenant leak | 12-02 | mitigate (existing `Ticket.tenant_id` filter unchanged) |

**Block-on threshold:** HIGH severity. No T-12-NN entries are currently rated HIGH-unmitigated. T-12-02 and T-12-03 are accepted-low (operational-label exposure / bounded table scan).

---

## RESEARCH COMPLETE

Ready for planning. The planner should:
1. Resolve the 6 open decisions above (default to the Recommended column)
2. Produce 8 PLANs (12-01 through 12-08) across 4 waves
3. Address all 5 requirement IDs (UX-04-01..05) explicitly in plan `requirements:` frontmatter
4. Honor the schema-push gate by including the Alembic migration step in 12-01 with a [BLOCKING] task that runs `alembic upgrade head` before tests
5. Reference threats from the canonical STRIDE Threat Register above by ID — do NOT re-invent IDs in plan-local tables
