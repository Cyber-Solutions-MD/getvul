# Phase 12: `/assets` List + Detail - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 12-assets-list-detail
**Areas discussed:** Risk-ring rendering, Reassign flow scope, Detail page data flow, List view toggle + chip-bar set

---

## Area 1: Risk-Ring Rendering Details

### Q1: Score color bands

| Option | Description | Selected |
|--------|-------------|----------|
| Sunset semantic bands | 80–100 → danger, 50–79 → amber, 20–49 → pink, 0–19 → violet/success — reuses severity tokens | ✓ |
| Pure gradient, no bands | Smooth violet-soft → danger interpolation; premium feel, loses severity language | |
| Keep v1 thresholds (red/orange/yellow/green) | Backward-compatible v1 colors; breaks sunset palette | |

### Q2: Mount animation

| Option | Description | Selected |
|--------|-------------|----------|
| Static | Renders final score immediately; "peer, not butler"; a11y-cleanest | ✓ |
| 0→score count-up over 600ms | Premium feel; motion-safe gated; adds a dep | |
| Stroke fill animation only (no number count) | Compromise — gradient fills, number stays static | |

### Q3: Score edge cases

| Option | Description | Selected |
|--------|-------------|----------|
| 0 = empty ring + '—' / 100 = full ring + tinted text | Score 0 → no stroke + em-dash + "No exposures"; Score 100 → full danger-tinted | ✓ |
| 0 = thin neutral track / 100 = full danger ring | Score 0 → neutral track; Score 100 → full closed danger ring | |
| No edge handling | Math literal — 0% arc invisible, 100% arc full | |

### Q4: Delta indicator (▲ +12 in 7d)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, as 4th breakdown row | Per UX-04-03 spec verbatim; ▲ red = bad, ▼ green = good | ✓ |
| Yes, but as a separate sub-card below the ring | Cleaner ring card, emphasis on delta | |
| Defer — ship in Phase 13 with trending data | Requires historical risk_score snapshots; reduce scope | |

---

## Area 2: Reassign Flow Scope

### Q1: Reassign UX shape

| Option | Description | Selected |
|--------|-------------|----------|
| Inline combobox in owner card | Card flips to edit mode; Esc cancels, Enter confirms; no modal | ✓ |
| Modal with searchable user list | Full user search + filters; more discoverable, heavier | |
| Vaul bottom sheet on mobile, modal on desktop | Cross-device consistency with drill-panel; reuses vaul | |
| Stub-only — toast 'coming soon' | UI affordance only; backend mutation deferred | |

### Q2: Data source for assignable identities

| Option | Description | Selected |
|--------|-------------|----------|
| /api/v1/users | Platform users only (~10-100/tenant); smallest set; reuses existing endpoint | ✓ |
| /api/v1/connectors/identities (IdP-pulled) | Full IdP identity pool; thousands of results; needs connector enrichment | |
| Both — platform users first, then IdP search-on-demand | Best UX, most plumbing | |

### Q3: Backend mutation

| Option | Description | Selected |
|--------|-------------|----------|
| POST /api/v1/assets/{id}/owner | New explicit endpoint; audit log entry; returns updated asset | ✓ |
| Reuse existing PATCH /api/v1/assets/{id} | Generic update; fewer new routes; less explicit | |
| Defer — frontend only with optimistic UI | Frontend-only stub; audit gap until backend ships | |

---

## Area 3: Detail Page Data Flow

### Q1: Detail page composition

| Option | Description | Selected |
|--------|-------------|----------|
| Compose 3 queries client-side via TanStack | useAsset + useAssetVulnerabilities + useAssetRemediations; each section degrades independently | ✓ |
| Extend GET /assets/{id} to return everything | One round-trip; all-or-nothing failure mode; larger backend surface | |
| Hybrid — asset+owner+metadata in one call, vulns+remediations as separate queries | Identity loads instantly, heavy lists independently | |

### Q2: Remediation timeline data source

| Option | Description | Selected |
|--------|-------------|----------|
| Tickets associated with this asset's vulns | /api/v1/tickets?asset_id={id}; closes triage→ticket loop visibly | ✓ |
| Audit log entries scoped to this asset | Broader event stream; more entries, more noise, more "activity feel" | |
| Stub data — ship UI, defer backend | Frontend with mock data; backend in follow-up | |

### Q3: Vulnerability row click behavior on detail page

| Option | Description | Selected |
|--------|-------------|----------|
| Open Phase 11 drill panel in-context | DrillPanel slides in; URL gets ?cve=...&open=drill; user stays on asset page | ✓ |
| Route to /vulnerabilities?cve=X&open=drill | Navigate away; loses asset context (back button needed) | |
| Both — row click = drill in-context, expand button = full /vulnerabilities | Most flexible; adds an affordance | |

---

## Area 4: List View Toggle + Chip-Bar Set

### Q1: List view toggle

| Option | Description | Selected |
|--------|-------------|----------|
| Flat list only — no toggle in Phase 12 | Owner is already a visible column; By-Owner is low-value | ✓ |
| By-Asset (default) / By-Owner toggle | Symmetric with Phase 11; "who owns the riskiest pile" view | |
| By-Asset (default) / By-Category toggle | Fleet management view; group by classification | |

### Q2: Chip-bar filter axes (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Category | WORKSTATION / SERVER / NETWORK / MOBILE / OTHER — direct severity analog | ✓ |
| Risk band | Critical / High / Medium / Low — maps to sunset semantic bands | ✓ |
| Source | Live facet; contextual count; same as Phase 11 D-F-03 | ✓ |
| OS family | Linux / Windows / macOS / Other — lower frequency than category | ✓ |

### Q3: Search box scope

| Option | Description | Selected |
|--------|-------------|----------|
| Hostname + IP + tags | Substring across 3 fields; 250ms debounce | ✓ |
| Hostname + IP only | Narrower; simpler backend query | |
| Add owner name/email too (4 fields) | Broader; redundancy with owner column | |

### Q4: Saved filters / star pill

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, same D-F-04 read-only contract | Backend mirrors /vulnerabilities/saved-filters; violet ★ applies first saved | ✓ |
| Skip saved filters in Phase 12 | No saved-filters surface; only Phase 11 has them | |
| Yes, plus inline Save action (deviate from Phase 11) | Ships save UX; inconsistent with Phase 11 | |

---

## Claude's Discretion

- Risk-ring SVG primitive location: `components/ui/RiskRing.tsx` vs. `components/assets/risk-ring.tsx` — Claude's call during planning. Likely `components/ui/` (potentially reusable on `/dashboard` Top-N cards).
- Breadcrumb component: build inline vs. extract a primitive — Claude decides; Phase 13 will reuse if extracted.
- Tags overflow handling — wrap vs. `+N` truncation. Prefer wrap per copy-voice "don't hide information."
- Mobile breakpoint where two-column collapses — sketch 005 implies <900px (matches drill-panel D-P-03); confirm at implementation.

## Deferred Ideas

- By-Asset / By-Owner view toggle on `/assets` — not Phase 12; add if usage shows demand
- IdP-pulled identities for Reassign picker — Phase 12 uses `/api/v1/users` only
- Save / rename / delete UX for saved filters — same Phase 11 deferral
- Risk-ring count-up animation — explicitly out; could ship later as motion-safe enhancement
- Audit-log-driven timeline — tickets-only for Phase 12; audit-log is a future enhancement
- OS family as a sort axis — Phase 12 ships OS as a chip filter, not a sortable column
