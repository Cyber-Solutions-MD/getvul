# Phase 14: Remaining Screens — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebuild the four remaining authenticated screens — `/dashboard/cspm`, `/dashboard/connectors`, `/dashboard/users`, `/dashboard/settings` — against the primitives and patterns already shipped in Phases 9–13, so there is zero v1 styling left in the authenticated surface. This is an **integration phase**: it consumes the locked design system + state primitives + chrome and adds only the new tokens/primitives these four screens require.

**In scope:**
- `/dashboard/cspm` — chip-bar + side-panel (inherited from Phase 11) + cloud-segmented control + compliance-frameworks rail + finding cards + bulk status actions
- `/dashboard/connectors` — category-sectioned card grid with provider gradient marks (14 providers) + sync-health status pills + functional add/edit/test/sync/enable-disable/delete
- `/dashboard/users` — people DIRECTORY (Directory + rebuilt Groups segmented toggle) with enrichment-source pills + export-only bulk bar
- `/dashboard/settings` — sidebar-of-categories (Profile / Workspace / SAML-OIDC / Notifications / API tokens / Audit log), replacing v1's tabbed layout
- New tokens/primitives: 11 additional `--gradient-provider-*` tokens, connector card, finding card, settings sidebar shell, per-category save bar, sync status pill

**Backend posture:** FRONTEND-ONLY milestone. All four screens consume existing v1 endpoints as-is. No backend changes. Where a UX element has no backend (API tokens), it ships as an honest placeholder.

**Explicitly out of scope (deferred):**
- Full connector onboarding wizard (provider catalog browse, guided OAuth, permission preview) → UX-D-02
- API token issuance (needs a backend) → future v1.1/v2.x
- CSPM trend charts → UX-D-05 (charts beyond severity-stacked bars deferred)
- Mobile/a11y/perf formal audit → Phase 15 (this phase ships responsive behavior, Phase 15 audits it)
- Self-serve display-name editing (no self endpoint; backend frozen)

</domain>

<decisions>
## Implementation Decisions

### Connectors (D-CONN)

- **D-CONN-01: Gradient marks for all 14 providers.** Add brand-tinted `--gradient-provider-*` CSS tokens for the ~11 non-ticket providers (CrowdStrike, Nessus, Defender, Wiz, Qualys, Rapid7, Google Workspace, Azure Entra, Okta, Jamf, Intune, Humaans) alongside the existing 3 (jira/asana/github). `<ProviderMark>` reads `var(--gradient-provider-{type})`. Hex lives once in `globals.css` per the Phase-13 token discipline.
- **D-CONN-02: New-connector flow is a functional, sunset-restyled form (NOT a thin placeholder).** Add/edit/test/sync/delete stay fully wired to the existing backend, rebuilt with sunset tokens as a simple form. The "multi-step wizard" deferred to UX-D-02 is the *polished guided experience* — basic functionality loses nothing vs v1.
- **D-CONN-03: Category-sectioned card grid.** Keep v1's labeled category sections (Vulnerability scanners / Identity / MDM / Ticketing); each section is a grid of connector cards. Preserves the at-a-glance "what do I have per category" overview.
- **D-CONN-04: Masked + sentinel passthrough for credentials.** Edit form shows secrets masked (sentinel `••••••`); an untouched field sends the sentinel back so the backend keeps the stored secret; typing replaces it. Eye/EyeOff reveal only on fields the user is actively entering. Mirrors the existing SMTP-password contract — no backend change.
- **D-CONN-05: Sync health = 4-state status pill + PerSourceStatusStrip reuse.** Each card carries a status pill reusing the Phase-13 status-color family: ok (green) / failed (red) / never-synced (gray) / running (amber, animated), driven by `last_sync_status`. In-progress "Sync now" reuses Phase 11's `PerSourceStatusStrip` for live feedback. `last_sync_at` + `last_sync_record_count` render as card metadata.
- **D-CONN-06: Disable toggle + guarded delete.** Card exposes an enable/disable toggle (pauses sync, keeps data, via `is_enabled`) AND a delete action behind a `ConfirmModal` warning that synced data may be affected. Delete gated to Owner/Admin. Disable is the low-risk default; delete is the escape hatch.
- **D-CONN-07: Per-category empty-states + inbound deep-link handling.** When a category has no connectors, render a sunset `EmptyState` with an "Add connector" CTA. The page reads an inbound query (e.g., `?provider=asana` from `/tickets` per Phase 13 D-S-02) to pre-open/scroll to the relevant add flow — closes the Phase-13 cross-screen loop.

### Settings (D-SET)

- **D-SET-01: Sidebar-of-categories, 6 categories.** Profile · Workspace · SAML/OIDC · Notifications · API tokens · Audit log. No horizontal tabs anywhere (success criterion #5). The right pane fills with the selected category.
- **D-SET-02: API tokens = coming-soon placeholder.** Category stays in the sidebar; its pane renders a sunset `EmptyState` ("Personal API tokens are coming soon"), no create capability — there is no backend endpoint and the milestone is frontend-only. A future phase wires it.
- **D-SET-03: Login-account + RBAC management lives under the Workspace category.** Add user / role change / deactivate via `/tenant/users` (Owner/Admin-gated). `/dashboard/users` stays the people directory (see D-USR-01). This keeps a clean split: Workspace settings = who can log in & their roles; `/dashboard/users` = the people inventory.
- **D-SET-04: Per-category sticky save bar with dirty-state tracking.** Each category pane tracks dirty state; a sticky "Save changes / Discard" bar appears when something changed, with an unsaved-changes guard on category switch. Edits commit via `PATCH /tenant/settings` (Owner-gated) or the relevant endpoint.
- **D-SET-05: RBAC gating hides categories below the current role.** Sidebar lists only the categories the role can access (Profile always; Workspace / SAML-OIDC / Notifications / Audit gated to Admin/Owner). A Viewer sees just Profile. No disabled dead-ends.
- **D-SET-06: Profile pane = identity view + password change.** Read-only identity (name, email, role, tenant, IdP source, last login from `/auth/me`) + a Change Password form (`/change-password`, hidden for SSO-only accounts). Display-name editing is deferred (no self endpoint, backend frozen).
- **D-SET-07: SAML/OIDC pane is provider-first with a gated enforce toggle.** Lead with the IdP provider picker (Google/Azure/LOCAL); the "Enforce SSO" toggle is disabled with an inline explainer until a non-LOCAL provider is set; switching to LOCAL warns that enforcement turns off. Mirrors the backend guards exactly (no enforce without IdP; LOCAL auto-disables enforcement).
- **D-SET-08: Notifications pane = three labeled sub-sections in one scrollable pane.** Email/SMTP · Syslog forwarding · Alert categories — each a card with its own fields, all committed by the shared per-category save bar (D-SET-04). No nested tabs (avoids re-introducing the tab pattern).
- **D-SET-09: Audit log pane = filtered + paginated read-only table.** Rows: actor (email + avatar) + action + target (resource_type/id) + timestamp. Filters for `action`, `resource_type`, `user_email` (actor); server pagination (page_size 50). Full state patterns (skeleton/empty/error). Uses every `/tenant/audit-log` param.
- **D-SET-10: Settings mobile (<900px) = category list → pane drill.** Category list full-width; tapping a category slides to its pane with a back affordance (master-detail drill), consistent with the mobile overlay patterns from Phases 11–13. Phase 15 audits it formally.

### Users directory (D-USR)

- **D-USR-01: `/dashboard/users` stays the people DIRECTORY.** It renders enriched people / asset-owners from `/api/v1/users/directory` (devices, risk score, department, enrichment source) — NOT GetVul login accounts. Pill semantics reinterpret to fit this data: the "source pill" = enrichment source (Humaans / CrowdStrike / Google), and a person's "role" is shown as job-title / department chip (there is no RBAC role on directory people). **REQUIREMENTS note:** UX-06-03's "role pills + IdP-source pills" was written against the accounts model; for the directory those map to job-title/department + enrichment-source. The accounts-model pills live on the Workspace settings accounts list (D-SET-03).
- **D-USR-02: Export-only bulk bar on the directory.** Row selection + a bulk bar whose only action is "Export selected" (CSV) via the existing `ExportButton`/endpoint — honest about the read-only directory. Writable bulk RBAC actions (deactivate / role-change) live on the Workspace settings accounts list, not here.
- **D-USR-03: Keep the Groups tab, rebuilt.** Directory and Groups ship as a sunset segmented toggle (NOT v1 horizontal tabs), Groups list reusing `ChipBar`/state primitives. Backed by `/tenant/groups` + `/groups/export`. No capability lost vs v1.

### CSPM (D-CSPM)

- **D-CSPM-01: Reuse the generalized DrillPanel for finding drill.** Add a CSPM content slot to the Phase-13-generalized `<DrillPanel>` (`idKey='finding'`, URL `?finding=...&open=drill`), exactly as tickets did. Body: cloud resource + compliance-framework mappings + remediation + status/bulk actions. Maximum pattern reuse; one new content component.
- **D-CSPM-02: Cloud segmented control + compliance frameworks rail.** Top: segmented control (All / AWS / Azure / GCP, from `/cspm/stats` `by_cloud_provider`) filtering findings. Compliance frameworks as a compact summary strip/cards above the finding list (pass-rate per framework from `/cspm/compliance`). Finding cards below, chip-bar filtered.
- **D-CSPM-03: Bulk resolve/ignore + rich finding cards.** `BulkActionBar` (Phase 11) exposes the real status transitions the backend allows (Resolve / Ignore / Reopen via `/cspm/bulk-status`). Each finding card shows: cloud provider gradient mark + severity glyph + resource identifier (mono) + title + framework tags + status pill. Full detail/remediation lives in the drill (D-CSPM-01).
- **D-CSPM-04: Defer trend charts (UX-D-05).** Rebuilt CSPM ships cards + frameworks rail + drill; no `/cspm/trends` time-series viz this phase. Stays inside the locked deferral.

### Cross-cutting (D-X)

- **D-X-01: Every screen is state-pattern compliant** (success criterion #6): loading (SkeletonTable + chip-bar skeleton + per-source progress strip where applicable), empty (EmptyState with explained-why + CTAs), partial-failure (PartialFailureBanner), and toast for transient events (useToast/ToastProvider). Reuse the Phase 11 canonical primitives verbatim.
- **D-X-02: snake_case frontend↔backend convention, no transform layer** — per the Phase 13 lesson. New frontend code matches the codebase-wide snake_case field names; no camelCase transform shim.

### Plan sequencing (D-SEQ)

- **D-SEQ-01: Foundation-first, then four parallelizable screens.** Wave 0 lands shared work (11 new provider gradient tokens + new primitives: connector card, finding card, settings sidebar shell, per-category save bar, sync status pill). The four screens then become parallelizable plans consuming those. Exact split left to the planner's goal-backward analysis.

### Claude's Discretion

- Exact primitive APIs and file placement (follow Phase 11–13 conventions + sketch-findings references).
- Whether the connectors category-section also gets a chip-filter (D-CONN-03 picked sections; a complementary filter is at Claude's discretion if the connector count warrants it).
- Notification "Alert categories" field shape — map to whatever the existing tenant-settings payload exposes.
- Skeleton/shimmer specifics per `state-patterns.md`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirements
- `.planning/ROADMAP.md` — Phase 14 "Remaining Screens" section (goal + 6 success criteria)
- `.planning/REQUIREMENTS-v2.md` — UX-06-01..04 (the four screens), UX-S-01..05 (cross-cutting state patterns enforced here), UX-D-02 / UX-D-05 (deferrals this phase honors)

### Design system (auto-loaded per CLAUDE.md, but list explicitly)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — color tokens (where the new `--gradient-provider-*` entries land), typography, spacing
- `.claude/skills/sketch-findings-getvul/references/app-shell.md` — sidebar + topbar chrome the settings sidebar-of-categories echoes
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — list / detail / sidebar-pane patterns
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — mandatory loading/empty/error (D-X-01)
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — severity / status / provider / SLA color language (status pills, gradient marks)
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — drill panel, chip bar, bulk bar
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — empty-state / placeholder / unsaved-changes copy

### Established primitives + patterns to reuse (prior CONTEXT files)
- `.planning/phases/11-vulnerabilities-state-patterns/11-CONTEXT.md` — SkeletonTable / EmptyState / PartialFailureBanner / PerSourceStatusStrip (locked APIs), DrillPanel chrome, ChipBar, BulkActionBar
- `.planning/phases/12-assets-list-detail/12-CONTEXT.md` — two-column detail + sticky rail, generic descriptor-driven ChipBar, inline-edit (reassign) pattern reused for save bars/toggles
- `.planning/phases/13-tickets-list-detail/13-CONTEXT.md` — ProviderMark + `--gradient-provider-*` token discipline (D-PROV-03), status/SLA pill visual contract (D-P-04), generalized DrillPanel `idKey` content-slot (D-D-02), `/tickets`→`/connectors` deep-link (D-S-02), snake_case convention lesson

### Backend endpoints consumed (frozen — read as-is)
- Connectors: `backend/app/connectors/router.py` + `schemas.py` (`is_enabled`, `last_sync_at`, `last_sync_status`, `last_sync_record_count`; add/edit/test/sync/delete)
- Settings: `backend/app/tenants/router.py` — `/me`, `/settings` (GET/PATCH: `sso_enforced`, `idp_provider`, `smtp_config`, `syslog_config`, branding), `/users` (accounts CRUD + role/deactivate), `/audit-log` (action/resource_type/user_email + pagination), `/groups` + `/groups/export`
- Users directory: `backend/app/users/router.py` — `/`, `/directory`, `/stats`
- Profile: `backend/app/auth/router.py` — `/me`, `/change-password`
- CSPM: `backend/app/cspm/router.py` — `/`, `/stats` (by_cloud_provider), `/compliance`, `/resources`, `/{id}`, `/{id}/status`, `/bulk-status`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **State primitives** (Phase 11): `SkeletonTable`, `EmptyState`, `PartialFailureBanner`, `PerSourceStatusStrip` — locked APIs, reuse verbatim across all four screens.
- **DrillPanel** (Phase 11 chrome + Phase 13 `idKey` generalization): add a CSPM `finding` content slot; do NOT build a new panel.
- **ChipBar** (Phase 12 generic descriptor-driven): reuse for CSPM finding filters, users directory filters, audit-log filters.
- **BulkActionBar** (Phase 11): reuse for CSPM bulk-status and the users export-only bulk bar.
- **ProviderMark** (`frontend/src/components/tickets/provider-mark.tsx`): extend the gradient-token map to 14 providers (D-CONN-01).
- **Status/SLA pill color family** (Phase 13 D-P-04): connector sync-health pill (D-CONN-05) and any status pills reuse it.
- **ConfirmModal** + **ToastProvider/useToast**: existing — reuse for delete guards and transient toasts.
- **ExportButton**: existing — backs the users export-only bulk bar (D-USR-02) and groups export.
- **Inline-edit pattern** (Phase 12 reassign combobox): template for save-bar / toggle interactions.

### Established Patterns
- Token discipline: hex lives once in `globals.css`; components consume `var(...)` (Phase 13).
- snake_case field names across the frontend/backend boundary, no transform layer (Phase 13 lesson — D-X-02).
- URL-state for drill/view/filters (`?finding=...&open=drill`, segmented toggles persisted to URL) per Phase 11.
- Vertical-slice milestone: tokens/primitives expand outward per screen need; D-SEQ-01 front-loads the shared set as Wave 0.

### Integration Points
- `globals.css` — 11 new `--gradient-provider-*` tokens (the only token-file edit).
- `provider-mark.tsx` — extend the provider→gradient map (additive).
- DrillPanel content-slot — add `finding` content component (additive, mirrors `ticket`).
- All four routes already exist under `frontend/src/app/(authed)/dashboard/{cspm,connectors,users,settings}/page.tsx` — these are full rewrites onto the new system.

</code_context>

<specifics>
## Specific Ideas

- Connectors page must close the Phase-13 deep-link loop: handle `?provider=<x>` inbound from `/tickets` (D-CONN-07).
- Settings success criterion #5 is a hard gate: `grep -r "tab" frontend/src/app/dashboard/settings/` must return no horizontal-tab pattern usages. The sidebar-of-categories + (where needed) master-detail mobile drill are the only navigation — no nested tabs in any pane (D-SET-08 explicitly avoids sub-tabs).
- "Functional, unstyled-wizard" means the add/edit connector form keeps full backend capability; only the *polished guided wizard* is deferred (D-CONN-02).

</specifics>

<deferred>
## Deferred Ideas

- **Full connector onboarding wizard** — provider catalog browse, guided OAuth, permission preview (UX-D-02).
- **API token issuance** — needs a backend endpoint; ships as a coming-soon placeholder now (D-SET-02), wired in a future v1.1/v2.x phase.
- **CSPM trend charts** — `/cspm/trends` time-series viz deferred per UX-D-05 (D-CSPM-04).
- **Self-serve display-name editing** — no self endpoint; backend frozen this milestone (D-SET-06).
- **Formal mobile/a11y/perf audit** — Phase 15 (this phase ships responsive behavior; Phase 15 audits it).

None — discussion stayed within phase scope (no scope-creep ideas surfaced).

</deferred>

---

*Phase: 14-remaining-screens*
*Context gathered: 2026-06-02*
