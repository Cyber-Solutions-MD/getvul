# Phase 12: `/assets` List + Detail - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the redesigned `/assets` surfaces:
- **`/assets` list** — chip-bar filtered table (6 columns: Hostname mono · OS · Owner avatar+name · Risk Score · Tags · Sources), reusing Phase 11's drill panel for in-context CVE deep-dives.
- **`/assets/[id]` detail** — two-column layout (sketch 005 variant B winner) with main column (severity-breakdown ribbon + vulnerabilities-on-this-host rows + remediation timeline) and 340px sticky right rail (circular gradient risk ring + owner card + identity/host metadata).
- **Reassign flow** — owner card supports inline reassignment with backend mutation.

State patterns, chip-bar UX, drill-panel behavior, table interactions, and pagination all inherit from Phase 11 verbatim. Phase 12 is a composition phase — minimal new primitive surface, mostly screen-specific composition + the risk-ring SVG primitive.

</domain>

<decisions>
## Implementation Decisions

### Risk-score ring (D-R)
- **D-R-01:** Score color bands map to **sunset semantic tokens** — `80–100 → danger`, `50–79 → amber`, `20–49 → pink`, `0–19 → violet/success`. Reuses the design system's severity language so asset risk reads visually identical to vuln severity. Zero raw palette.
- **D-R-02:** **Static render** — no count-up animation, no stroke-fill animation. Per `copy-voice.md` "peer, not butler"; the number is the value, not a flourish. Also a11y-cleanest (no `motion-safe:` gate needed). Saves a dependency.
- **D-R-03:** Edge case handling:
  - Score `0` → empty ring (no arc stroke), center renders em-dash `—` with caption "No exposures"
  - Score `100` → full closed ring, number rendered in `text-danger` tint (danger-soft background subtlety on the breakdown rows)
  - Score `null` / missing → empty ring + "Risk unavailable" — distinguishable from genuine 0
- **D-R-04:** **4-row breakdown** in the ring card, per UX-04-03 spec verbatim:
  1. Critical exposures (mono count + `Critical` label, danger-tint)
  2. SLA breaches (mono count + `SLA breach` label, amber-tint)
  3. CISA KEV count (mono count + `KEV` label, pink-tint)
  4. 7-day delta (`▲ +12` red = score went UP = bad / `▼ -8` violet/success = score went DOWN = good)
  Delta direction language: ↑ = worse (always tinted danger), ↓ = better (always tinted success).

### Reassign owner flow (D-A)
- **D-A-01:** UX shape — **inline combobox in owner card** (no modal, no vaul sheet). Click "Reassign" → card flips to edit mode with a searchable input. Esc cancels (reverts to display); Enter confirms (POST + optimistic UI); blur outside cancels. Keeps the user on the asset detail page.
- **D-A-02:** Data source — **`/api/v1/users`** (platform users only). Smallest assignable set (~10–100 per tenant), already authenticated, has roles. Avoids the IdP-pool plumbing complexity. Future phase can extend to IdP identities if analysts need it.
- **D-A-03:** Backend endpoint — **`POST /api/v1/assets/{id}/owner`** with body `{ user_id: string }`. Writes an audit log entry (`asset.owner_changed`). Returns the updated asset payload. New endpoint (not a generic PATCH) for clarity, audit specificity, and matching the asset endpoint shape.

### Detail page data flow (D-D)
- **D-D-01:** **Compose 3 parallel TanStack queries client-side**, not a single backend mega-call. Hooks:
  - `useAsset(id)` → asset + owner + metadata
  - `useAssetVulnerabilities(id)` → vulnerabilities on this host (reuses `useVulnerabilities` query factory from Phase 11 with `{ asset_id }` filter)
  - `useAssetRemediations(id)` → tickets associated with this asset's vulns
  Each section degrades independently — if `useAssetRemediations` 503s, the timeline shows `<PartialFailureBanner>` while vuln list + owner card render unaffected. Matches Phase 11 D-D-03 query-key shape; downstream phases can extend without breaking changes.
- **D-D-02:** **Remediation timeline data source = `/api/v1/tickets?asset_id={id}`**, ordered by `updated_at desc`. Each timeline row: provider mark (Jira / Asana / GitHub from existing Phase 13 precursor work) + ticket title + status pill + relative timestamp. Closes the loop visually: triage → ticket → visible on the asset detail. Backend extension: add `asset_id` filter to the existing `/tickets` endpoint (small surface delta).
- **D-D-03:** **Vulnerability row click on detail page opens the Phase 11 `<DrillPanel>` in-context**. URL gets `?cve=...&open=drill` per Phase 11 D-P-02 contract. Closing the panel returns the user to their scroll position on `/assets/[id]`. Same vaul bottom-sheet behavior on mobile (<900px). Reuses Phase 11 verbatim — no new drill primitive.

### List view + chip-bar (D-L)
- **D-L-01:** **Flat list only — no view toggle in Phase 12**. Phase 11's By-CVE/By-Host answered a frequent analyst question ("which hosts have this"); the asset analog ("which owners have these") is less common because owner is already a visible column per row. Add a toggle if/when analyst behavior shows demand. Keeps Phase 12 scope clean.
- **D-L-02:** **4 chip-bar filter axes** ship in Phase 12:
  - **Category** (WORKSTATION / SERVER / NETWORK / MOBILE / OTHER) — direct analog to severity in Phase 11; v1 had this; analysts use it
  - **Risk band** (Critical 80–100 / High 50–79 / Medium 20–49 / Low 0–19) — maps to the same sunset semantic bands as the risk ring (D-R-01)
  - **Source** (live facet, contextual count) — same semantics as Phase 11 D-F-03 (only renders sources the tenant actually has)
  - **OS family** (Linux / Windows / macOS / Other) — lower frequency than category but UX-04 specs OS as a column, so make it filterable too
  All 4 use Phase 11's `useUrlStateList` hook (D-F-05) for multi-value URL sync.
- **D-L-03:** **Search box matches hostname + IP + tags**, 250ms debounce per Phase 11 D-F-01. Tags require backend full-text index check (verify in research). Owner search excluded (owner is also a column; redundancy).
- **D-L-04:** **Saved filters read-only** — same contract as Phase 11 D-F-04. Backend `/api/v1/assets/saved-filters` mirrors `/vulnerabilities/saved-filters`. Violet `★` pill in chip bar applies the user's first saved filter (or hides if none). Save / rename / delete deferred.

### Claude's Discretion
- Risk-ring SVG primitive location: `frontend/src/components/ui/RiskRing.tsx` vs. `frontend/src/components/assets/risk-ring.tsx` — Claude's call during planning. (RiskRing is potentially reusable on `/dashboard` Top-N cards, so `components/ui/` likely wins, but defer to pattern-mapper output.)
- Breadcrumb component: build inline vs. extract a primitive — if not already in `components/ui/`, Claude decides. Phase 13 will reuse it for `/tickets/[id]` breadcrumb.
- Tags overflow handling — when an asset has many tags, the list either wraps below hostname or truncates with `+N` chip. Claude picks during implementation; prefer wrap (no truncation) per `copy-voice.md` "don't hide information."
- Specific mobile breakpoint where two-column collapses to stacked (rail-below) — sketch 005 implies <900px (matches drill-panel mobile gate D-P-03). Confirm at implementation.

### Folded Todos
None — no pending todos matched Phase 12 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 12 scope authorities
- `.planning/REQUIREMENTS-v2.md` §"Asset list + detail (UX-04)" — 5 requirements (UX-04-01..05)
- `.planning/ROADMAP.md` — Phase 12 entry (6 success criteria)
- `.claude/skills/sketch-findings-getvul/sources/005-asset-detail-sunset/README.md` — sketch 005 variant B is the winner; defines layout, ring placement, breakdown rows
- `.claude/skills/sketch-findings-getvul/sources/005-asset-detail-sunset/index.html` — visual reference for variant B

### Inherited from Phase 11 (LOAD-BEARING — do not redecide)
- `.planning/phases/11-vulnerabilities-state-patterns/11-CONTEXT.md` — Phase 11 decisions; D-F-* / D-P-* / D-T-* / D-V-* / D-S-* all apply to Phase 12
- `.planning/phases/11-vulnerabilities-state-patterns/11-04-SUMMARY.md` — canonical state primitives (SkeletonTable, EmptyState, PartialFailureBanner, PerSourceStatusStrip) consumed verbatim
- `.planning/phases/11-vulnerabilities-state-patterns/11-05-SUMMARY.md` — chip-bar, view-toggle, drill-panel desktop + mobile (vaul), drill-content; Phase 12 inherits ChipBar shape (different axes), inherits DrillPanel verbatim
- `.planning/phases/11-vulnerabilities-state-patterns/11-03-SUMMARY.md` — query-key shape, `useUrlStateList`, `useQueryErrors`, `useCreateTicketMutation` patterns; Phase 12 follows the same hook factory pattern

### Design system (auto-load via CLAUDE.md routing)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — color tokens, typography, spacing, motion (motion-safe gating)
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — list / detail patterns (two-column with rail covered here)
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — severity / status / SLA / providers / CTA (risk-band tokens align with severity tokens here)
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading / empty / partial-failure (mandatory in production)
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — drill-down panel + chip bar canonical patterns (inherited from Phase 11)
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — tone rules ("peer, not butler"); applies to risk-ring labels + reassign flow microcopy

### Backend
- `backend/app/assets/router.py:212` — existing `GET /api/v1/assets/{id}` handler (returns asset + vuln breakdown); Phase 12 will compose this with `useAssetVulnerabilities` + `useAssetRemediations` rather than extend its response
- `backend/app/assets/service.py` — Asset service layer (extend for `update_owner` mutation)
- `backend/app/assets/schemas.py` — Asset response schemas (verify shape includes `owner_user_id`, `tags`, `os_family`)
- `backend/app/tickets/router.py` — extend with `?asset_id` filter for D-D-02

### Project-level
- `.planning/PROJECT.md` — core value, evolution rules, validated requirements
- `CLAUDE.md` — project instructions (sketch-findings-getvul auto-loads on UI work)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (carry forward verbatim)
- **`frontend/src/components/states/*`** — SkeletonTable, EmptyState, PartialFailureBanner, PerSourceStatusStrip. Locked APIs from Phase 11; Phase 12 consumes them.
- **`frontend/src/components/vulnerabilities/chip-bar.tsx`** — ChipBar primitive from Phase 11. Same shape, different chip set (Category / Risk band / Source / OS). May need a minor refactor to accept arbitrary chip categories vs. its current vuln-specific signature.
- **`frontend/src/components/vulnerabilities/drill-panel.tsx`** + `drill-panel-mobile.tsx` + `drill-content.tsx` — Phase 11 drill panel. Consumed verbatim for in-context CVE drill from `/assets/[id]` (D-D-03).
- **`frontend/src/hooks/use-url-state-list.ts`** — multi-value URL chip sync (D-F-05). Used for all 4 Phase 12 chip axes.
- **`frontend/src/lib/queries/keys.ts`** — query key factory. Extend with `keys.assets.{list, byId, vulnerabilities, remediations, savedFilters}` namespace.
- **`frontend/src/lib/queries/use-query-errors.ts`** — partial-failure detection hook. Used by the rail's risk card + owner card when `useAsset` partials.
- **`frontend/src/components/ui/Pagination.tsx`** — sunset-restyled Pagination from Phase 11 D-T-03; reused.

### Established patterns (cannot deviate)
- **TanStack Query v5** for all data fetching (Phase 10 D-D-01 — milestone-wide).
- **`useUrlStateList<T>(key, allowed, default)`** for multi-value URL chip sync (Phase 11 D-F-05 — XSS-safe allow-list clamp).
- **Mutation hooks with `onSuccess` invalidation against `queryKeys.{domain}.all`** (Phase 11 use-create-ticket pattern). Reassign mutation follows: invalidates `keys.assets.byId(id)` + `keys.assets.list`.
- **Hybrid hook+props for state primitives** (Phase 11 D-S-03). PartialFailureBanner on the asset rail uses props mode (passes one specific error) vs. hook mode (composes across query set).
- **State primitives MUST be used** for loading / empty / partial-failure / error — no inline-minimal versions (CLAUDE.md non-negotiable).
- **`buildSearchParams` co-located with query hook** so tests can assert URL shape (Phase 11 D-D-03).
- **Compound subcomponent pattern** for primitives (`EmptyState.Title`, `EmptyState.Body`, `EmptyState.Actions`, `EmptyState.Suggestion` — Phase 11 D-S-02). Owner card might follow this pattern if it grows multi-slot.

### Integration points
- **`frontend/src/app/(authed)/dashboard/assets/page.tsx`** (386 lines, v1) — rewrite target. Delete after.
- **`frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx`** (292 lines, v1) — rewrite target. Delete after.
- **Backend `/api/v1/assets/{id}/owner`** — new endpoint. Mounted under existing `backend/app/assets/router.py` router.
- **Backend `/api/v1/tickets?asset_id=`** — filter extension on existing tickets endpoint.
- **`frontend/src/lib/queries/keys.ts`** — add `assets` namespace.
- **Phase 11 `<ChipBar>`** — refactor signature to accept chip-axis descriptors generically (not vuln-hardcoded). This is a Phase 11 → Phase 12 carve-out; if the existing signature is already generic, no refactor needed. Pattern-mapper to verify.
- **Sidebar nav** — `/assets` already exists in the nav (v1). No change.

</code_context>

<specifics>
## Specific Ideas

- **Sketch winner: variant B** — two-column with metadata rail; circular gradient ring; severity-breakdown ribbon on vuln list; full-width timeline below vulns. Anchor visual reference for the build.
- **Sunset semantic bands for risk score** — direct mapping to severity tokens (D-R-01) so asset risk and vuln severity speak the same visual language. An 80–100 asset = a CRITICAL-tinted ring.
- **Static ring** — no count-up. The user explicitly chose "peer, not butler" over premium flourish.
- **Inline combobox for reassign** — fastest analyst workflow; Esc/Enter contract; no modal context-switch.
- **Compose-not-mega-call** — 3 parallel TanStack queries on the detail page. Aligns with Phase 11's per-domain hook pattern and lets sections degrade independently.

</specifics>

<deferred>
## Deferred Ideas

- **By-Asset / By-Owner view toggle on /assets** — not Phase 12. Add if/when analyst usage shows the need.
- **IdP-pulled identities for Reassign picker** — Phase 12 uses `/api/v1/users` only. IdP-pool search is a follow-up if reassignment to non-platform identities is needed.
- **Save / rename / delete UX for saved filters** — same Phase 11 deferred decision (D-F-04). Adds when a user actually asks.
- **Risk-ring count-up animation** — explicitly out for Phase 12. Could ship later as a motion-safe enhancement if usage research shows the static number doesn't read.
- **Audit-log-driven timeline** — D-D-02 went with tickets-only. Audit-log timeline (broader event stream) is a future enhancement when a finer-grained activity view is requested.
- **OS family as a sort axis** — Phase 12 ships OS as a chip filter (D-L-02) but not a sortable column. Sort by OS family is low-value; defer indefinitely.

### Reviewed Todos (not folded)
None — no pending todos surfaced in cross-reference.

</deferred>

---

*Phase: 12-assets-list-detail*
*Context gathered: 2026-05-27*
