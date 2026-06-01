# Phase 13: `/tickets` List + Detail — Context

**Gathered:** 2026-06-01
**Status:** Ready for research + planning

<domain>
## Phase Boundary

An analyst can review remediation work as a list with provider-aware identity chips (Jira / Asana / GitHub gradient marks) and open a two-column detail at `/tickets/[id]` that ties the ticket to its linked vulnerabilities, asset, and people (assignee + reporter + watchers).

**In scope:**
- `/tickets` list page rewrite (chip-bar + 8-column table + side-panel drill + bulk-actions toolbar + List/Board segmented toggle with Board as placeholder)
- `/tickets/[id]` detail page (new route, two-column with sticky 340px right rail)
- `/tickets/rules` split into its own route with full sunset rewrite
- Backend: `ticket_comments` table + `ticket.blocked` + `ticket.blocked_reason` + `ticket.sla_due_at` columns + `ticket_watchers` table + Jira / GitHub connector stubs (OAuth + ticket-create endpoints to match the Asana surface)
- Frontend: Provider gradient-mark primitive, status pill (4 states), SLA pill (4 states), activity timeline component, comment input bound to local `ticket_comments`, watcher avatar stack with `+N` overflow, Asset cross-link card

**Explicitly out of scope (deferred):**
- Asana config + setup + sync-status surface → moves to `/dashboard/connectors` in Phase 14
- Kanban / Board view body → placeholder toggle only in Phase 13; full kanban deferred to UX-D-01
- Real provider logos → locked deferred (UX-05-02 — gradient marks only)
- Status write-back to provider (Open/In progress/Completed remain display-only from sync; only GetVul-internal `Blocked` is interactive)
- Comment write-back to provider → local notes only in Phase 13

</domain>

<decisions>
## Implementation Decisions

### Out-of-scope cleanup (D-S)

- **D-S-01:** **`/tickets/rules` splits into its own route** (`app/(authed)/dashboard/tickets/rules/page.tsx`) with a **full sunset rewrite** in Phase 13. Topnav links to `/tickets/rules` instead of v1's `?tab=rules` query param. Reuses sunset tokens + ChipBar + state primitives (skeleton/empty/error) same as the main list. Adds ~1 plan to Phase 13 but eliminates v1 carryover on that route.

- **D-S-02:** **Asana config + setup + sync-status surface moves to `/dashboard/connectors`** (Phase 14 territory). Phase 13 keeps `/tickets` focused on the work artifact. If the Asana connector isn't configured, the `/tickets` page renders an empty-state with a deep-link to `/dashboard/connectors` (does not block, does not embed config UI).

- **D-S-03:** **Bulk actions retained on `/tickets` list** via Phase 11's `BulkActionBar` pattern (bottom-anchored toolbar that appears when rows are selected). Bulk operations in Phase 13: **Close**, **Mark blocked / Unblock**. Bulk-comment deferred (UX gets unwieldy with multi-target comment threading; revisit in Phase 14 if analysts want it).

### Comment input behavior (D-C)

- **D-C-01:** **Local audit notes** — comment input on `/tickets/[id]` activity timeline writes to GetVul only. Never posts to Jira / Asana / GitHub. No OAuth scope changes, no threading model, no provider rate-limit handling. Activity timeline composes local comments + provider sync events visually (provider events come from existing daily-sync ingest).

- **D-C-02:** **New `ticket_comments` table** (alembic migration). Schema:
  ```sql
  CREATE TABLE ticket_comments (
    id UUID PRIMARY KEY,
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    user_id UUID NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    edited_at TIMESTAMPTZ
  );
  CREATE INDEX ix_ticket_comments_ticket_created ON ticket_comments(ticket_id, created_at);
  ```
  Comments are first-class entities — edit / delete affordances ship later but the schema supports them. Audit log stays for security events; user content lives in this dedicated table (no conflation).

- **D-C-03:** **Comment body validated like Phase 12 BL-01** — Pydantic model with `min_length=1`, `max_length=10000`, and a `field_validator` that strips leading/trailing whitespace. Permissive on content (markdown/plain text both accepted as raw text in v1; rendering is plain-text with newline preservation in P13, markdown rendering is a v2.x decision per sketch 006).

- **D-C-04:** **Comment ordering on the activity timeline is chronological** (ascending — oldest at top, latest at bottom). Comment input renders below the last activity row (analyst sees what they're responding to). Provider sync events interleave by their `created_at` timestamp.

### Status pill interaction (D-P)

- **D-P-01:** **Mixed model** — `Open` / `In progress` / `Completed` are **display-only** mirrors of `Ticket.external_status` from provider sync. User cannot transition these from GetVul. Provider transitions (Jira board, Asana column, GitHub state) flow back via the existing daily sync. **`Blocked` is GetVul-internal and interactive** — analyst can flag a ticket as blocked without provider write-back. Covers the common "waiting on patch vendor" workflow signal that doesn't have a clean provider equivalent.

- **D-P-02:** **Schema for Blocked flag** — add two columns to existing `tickets` table:
  ```sql
  ALTER TABLE tickets ADD COLUMN blocked BOOLEAN NOT NULL DEFAULT false;
  ALTER TABLE tickets ADD COLUMN blocked_reason TEXT;  -- nullable, max 500 chars
  ```
  Each toggle writes an audit row (`audit_log.action = 'ticket.blocked'` or `'ticket.unblocked'`) with `details.reason` carrying the blocked_reason. Pydantic `field_validator` enforces `len(blocked_reason.strip()) > 0 if blocked_reason else True` (no whitespace-only reasons) and `max_length=500`.

- **D-P-03:** **Where Blocked can be toggled — detail page + bulk action on list:**
  - **Detail page (`/tickets/[id]`):** Toggle lives in the right-rail **Details card**. Clicking the pill opens an inline edit (similar to Phase 12's reassign combobox pattern) — text input for `blocked_reason` + Save / Cancel. Confirms with optimistic UI + audit-then-commit transaction (Phase 12 T-12-09 pattern).
  - **List bulk action:** When multiple rows are selected, BulkActionBar exposes "Mark blocked / Unblock" — opens a modal collecting one shared `blocked_reason` (or empty), applies to all selected. Useful for "vendor X patch slipped — flag all 12 affected tickets at once."

- **D-P-04:** **Visual contract** (locked from UX-05-03):
  | State | Tailwind class | Source |
  |-------|----------------|--------|
  | Open | `border-violet/40 bg-violet-soft text-violet` | provider sync |
  | In progress | `border-amber/40 bg-amber/10 text-amber` | provider sync |
  | Completed | `border-severity-low/40 bg-severity-low/10 text-severity-low` | provider sync |
  | Blocked | `border-severity-critical/40 bg-severity-critical/10 text-severity-critical` | GetVul-internal |

  Each pill has a leading dot (`<span class="size-1.5 rounded-full bg-current">`). When `ticket.blocked` is true, the Blocked pill **renders alongside** the provider-status pill (not replaces it) — analyst sees "Open · Blocked" or "In progress · Blocked" simultaneously.

### Side-panel drill shape (D-D)

- **D-D-01:** **Standard shape (sketch 006 variant A's content)** — clicking a list row opens the Phase 11 `<DrillPanel>` (verbatim primitive reuse, per Phase 11 D-D-03 and Phase 12 D-D-03). Panel content:
  - **Header:** Provider gradient mark + ticket ID (mono) + truncated title + close button
  - **Body:**
    1. Linked vulnerabilities mini-list — top 3 by severity, each row: severity glyph + CVE + CVSS score (compact, ~28px row height). If >3 vulns, show "+N more" with link to detail page.
    2. Description (truncated to ~6 lines with "Show full →" link to `/tickets/[id]`)
    3. Status pill + SLA pill row
  - **Footer (sticky):** Action bar with 3 buttons:
    - **Open in [provider]** — external link (`target="_blank"`, opens provider URL)
    - **Open full detail** — internal link to `/tickets/[id]`
    - **Mark blocked / Unblock** — inline toggle (matches detail-page UX shape via shared `<BlockedToggle>` component)

- **D-D-02:** **DrillPanel slot pattern, not a new TicketDrillPanel** — Phase 11's `<DrillPanel>` is currently vuln-specific in its body content but the chrome (slide-in animation, focus trap, escape-to-close, URL state via `?cve=...&open=drill`) is generic. **Generalize the DrillPanel chrome** in Phase 13 by adding a content slot prop; create a `<TicketDrillContent>` that lives inside the same chrome. URL contract becomes `?ticket=...&open=drill` for ticket drills (mirroring Phase 11's `?cve=...` pattern). The existing vuln drill behavior is preserved; this is an additive refactor.

- **D-D-03:** **Mobile (<900px)** — DrillPanel becomes a full-screen overlay (same as Phase 11's vaul-bound mobile behavior). Footer action bar collapses to "Open in [provider]" primary + overflow kebab for the other 2 actions to fit within the smaller viewport.

### List view + chip-bar (D-L)

- **D-L-01:** **8 columns locked per UX-05-01:** Severity · Provider · ID (mono) · Title (truncated, hover for full) · Vulns (`3 ·2 ·1` format = total · critical · high) · Assignee (avatar + name, truncated) · Status · SLA. Mobile (<900px): columns collapse to a card layout where each card shows Severity · Provider mark · ID · Title (full) · Status pill · SLA pill (vuln count + assignee shown as secondary line).

- **D-L-02:** **Vuln-count column condensed format `T ·C ·H`** (total · critical · high) per UX-05-06. Critical count colored `text-severity-critical`, high count colored `text-severity-high`, total colored `text-text`. Zero values render as `0` (not hidden) — `3 ·0 ·0` reads correctly as "3 mediums-or-below". If total > 99, render as `99+ ·C ·H`. If total is 0 (ticket has no linked vulns), render `—` (em dash).

- **D-L-03:** **List/Board segmented toggle** in the page-head-actions zone (top-right, where Phase 11 view-toggle lives). List view = default. Clicking Board renders the placeholder copy from sketch 006 ("Board view coming in a future update — for now, use the List view with the Status chip filter to organize work by status."). Toggle state persists in URL (`?view=list|board`) per Phase 11 D-P-02 URL-state convention.

- **D-L-04:** **Chip-bar filter axes ship in Phase 13:**
  1. **Status** — Open / In progress / Completed / Blocked (multi-select)
  2. **Provider** — Jira / Asana / GitHub (multi-select; only providers with synced tickets appear)
  3. **Severity** — Critical / High / Medium / Low (multi-select; derived from worst linked vuln)
  4. **SLA** — Overdue / Soon / OK (single-select; SLA = "Soon" defined as within 7 days of `sla_due_at`)
  Search box matches: ticket ID (mono) + title + assignee name. 250ms debounce per Phase 11 D-F-01.

### SLA derivation + storage (D-SLA)

- **D-SLA-01:** **Add `ticket.sla_due_at` column to tickets table** (alembic migration). Single source of truth — derived at ticket-create time, recomputed on linked-vuln changes via a database trigger or service-layer hook.
  ```sql
  ALTER TABLE tickets ADD COLUMN sla_due_at TIMESTAMPTZ;
  CREATE INDEX ix_tickets_tenant_sla ON tickets(tenant_id, sla_due_at);
  ```
  Avoids per-request aggregation across linked vulns. Index supports the "Overdue" SLA chip filter without a join.

- **D-SLA-02:** **Computation rule:** `ticket.sla_due_at = MIN(linked_vuln.sla_due_at)` across all linked vulns (i.e., the soonest-due vuln's SLA wins). If no linked vulns carry `sla_due_at`, leave `ticket.sla_due_at` as `NULL` → UI renders SLA pill as "Unknown" (gray).

- **D-SLA-03:** **Backfill migration** computes `sla_due_at` for all existing tickets via a one-time SQL UPDATE. Subsequent maintenance: a service-layer hook in `ticketing/service.py` recomputes `ticket.sla_due_at` whenever (a) a ticket gains/loses a linked vuln, (b) a linked vuln's `sla_due_at` changes (e.g., snooze ends). Add hooks at the existing vuln-snooze and ticket-create paths.

- **D-SLA-04:** **SLA pill thresholds** (relative to `now()`):
  | State | Condition | Color |
  |-------|-----------|-------|
  | Overdue | `sla_due_at < now()` | severity-critical (red) |
  | Soon | `sla_due_at < now() + 7d` | amber |
  | OK | `sla_due_at >= now() + 7d` | severity-low (green) |
  | Unknown | `sla_due_at IS NULL` | text-text-faint (gray) |

  Computed client-side from `ticket.sla_due_at` so the backend doesn't need a "state" column.

### Provider scope + connector stubs (D-PROV)

- **D-PROV-01:** **Build Jira + GitHub connector stubs in Phase 13** so the gradient-mark contract from UX-05-02 ships with real per-provider data. Phase 13 backend scope expands to include:
  - `backend/app/ticketing/jira_client.py` — OAuth handshake + `create_ticket` + `sync_status` (read-only) implementing the same interface as `asana_client.py`
  - `backend/app/ticketing/github_client.py` — Same shape using GitHub Issues API (OAuth + Issue create + state read)
  - Provider enum extension already exists (`TicketProvider`) — verify Jira and GitHub members are present; add if missing
  - Configuration via existing connector pattern (per-tenant API keys / OAuth tokens, stored encrypted)

- **D-PROV-02:** **Stub depth — auth + ticket-create + read-back state only.** Phase 13 does NOT need Jira / GitHub bidirectional sync at full Asana parity (no daily-sync cron, no comment-pull, no bulk-fetch). Those land later. The stub is enough to:
  1. Create a Jira / GitHub ticket from GetVul's ticket-create flow
  2. Read `external_status` on demand (called from the existing sync-status path or on detail-page render)
  3. Provide gradient-mark + "Open in Jira" / "Open in GitHub" links with real `external_ticket_url` values

- **D-PROV-03:** **Frontend provider type:** `type TicketProvider = 'jira' | 'asana' | 'github'`. Provider gradient-mark component (`<ProviderMark provider={p} />`) renders the correct tint per provider. Marks use **CSS variable-driven gradients** to stay consistent with sunset palette (no inline hex):
  - Jira: `linear-gradient(135deg, var(--color-blue), var(--color-blue-soft))` — cool blue
  - Asana: `linear-gradient(135deg, var(--color-coral), var(--color-pink))` — coral
  - GitHub: `linear-gradient(135deg, var(--color-violet), var(--color-pink))` — violet
  Verify these CSS variables exist in `foundation.md` / `globals.css`; if missing, the planner adds them.

### Watcher avatar stack (D-W)

- **D-W-01:** **Watchers source = union of provider followers + local GetVul subscriptions.** Asana's `followers` field is the closest provider primitive; Jira has explicit `watchers`; GitHub doesn't (uses notifications). Phase 13 reads whichever the provider exposes.

- **D-W-02:** **New `ticket_watchers` table** for local subscriptions:
  ```sql
  CREATE TABLE ticket_watchers (
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticket_id, user_id)
  );
  ```
  Endpoints: `POST /api/v1/tickets/{id}/watch` + `DELETE /api/v1/tickets/{id}/watch` (idempotent — POST is a no-op if already watching, DELETE is a no-op if not watching).

- **D-W-03:** **"Watch" button on `/tickets/[id]` right-rail People card** — toggle between "Watch" (eye-open icon) and "Watching" (eye-closed icon, indicates active). Optimistic UI: button flips immediately on click, API call settles in background. Failure rolls back with toast (Phase 12 mutation pattern).

- **D-W-04:** **Avatar stack render:** First 3 watchers shown by display_name + initials (2-char per Phase 12 WR-09); remainder shown as `+N` chip. Hover/focus on `+N` reveals a popover with the full list (max 50 watchers; pagination beyond that is a future concern). Sorted: assignee first → reporter second → other watchers chronological by `created_at`. If a user appears in multiple roles, dedupe and prefer the strongest role tag.

### Claude's Discretion

- **Mobile breakpoint for two-column → stacked**: use 900px (same as Phase 12 D-D-04, locked there). No new breakpoint needed.
- **Activity timeline date grouping**: group by day ("Today", "Yesterday", "MMM D") above the rows. Standard pattern, no user input needed.
- **DrillPanel close → URL state**: standard `?ticket=...&open=drill` query param matching Phase 11. Esc + X + outside-click all close.
- **Bulk-action confirmation**: "Mark blocked" prompts for shared `blocked_reason` in a modal; "Close" prompts for confirmation only (no input). Standard UX.
- **Connector OAuth flow UX**: out of scope for Phase 13 (lives in Phase 14 connectors UI). The Jira / GitHub stubs land with admin-CLI / manual-DB-write config in P13; full UI in P14.

### Folded Todos

None — `gsd-tools todo match-phase 13` returned zero matches.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 13 scope authorities

- `.planning/REQUIREMENTS-v2.md` §UX-05 (lines 47–54) — UX-05-01 through UX-05-06 acceptance criteria
- `.planning/ROADMAP.md` §Phase 13 (lines 262–274) — Goal + 6 Success Criteria + Plans=TBD
- `.planning/REQUIREMENTS-v2.md` §UX-D (lines 94, 105) — Locked deferrals (UX-D-01 kanban; real-logos prohibited)

### Inherited from Phase 12 (LOAD-BEARING — do not redecide)

- `.planning/phases/12-assets-list-detail/12-CONTEXT.md` §D-D (two-column shape, 340px sticky rail, 900px mobile breakpoint, DrillPanel reuse contract)
- `.planning/phases/12-assets-list-detail/12-CONTEXT.md` §D-A (inline-combobox UX pattern — applied here for Blocked-reason capture)
- `.planning/phases/12-assets-list-detail/12-REVIEW.md` §BL-01 (Pydantic `field_validator` pattern for user-facing string columns — applies to `blocked_reason` and comment `body`)
- `.planning/phases/12-assets-list-detail/12-REVIEW.md` §BL-02 (`uuid.UUID` typing on all path/query params — applies to new `/tickets/{id}/watch` etc.)
- `.planning/phases/12-assets-list-detail/12-REVIEW.md` §WR-09 (2-char Avatar initials — applies to watcher stack)

### Inherited from Phase 11 (LOAD-BEARING)

- `frontend/src/components/vulnerabilities/drill-panel.tsx` — DrillPanel chrome (to be generalized in Phase 13 D-D-02)
- `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` — vaul mobile drawer pattern
- `frontend/src/components/ui/ChipBar.tsx` (Phase 12 generic primitive) — directly consumed for filter chips
- `frontend/src/components/states/*.tsx` — SkeletonTable / EmptyState / PartialFailureBanner / PerSourceStatusStrip (mandatory consumption)

### Design system (auto-load via CLAUDE.md routing)

- `.claude/skills/sketch-findings-getvul/sources/006-tickets-sunset/README.md` — sketch 006 winner contract (A for list, B for detail, C deferred)
- `.claude/skills/sketch-findings-getvul/sources/006-tickets-sunset/index.html` — visual reference for provider gradient marks, status pills, watcher stack
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — color tokens (verify Jira blue / Asana coral / GitHub violet vars; add if missing)
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — provider chip + status pill + SLA pill conventions
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — list page + two-column detail patterns
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — mandatory loading/empty/error coverage
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — drill-down panel chrome + bulk-action bar contract
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — "peer not butler" tone; no generic SaaS copy

### Backend

- `backend/app/ticketing/models.py` — Ticket / TicketRule models to extend (blocked, blocked_reason, sla_due_at columns)
- `backend/app/ticketing/asana_client.py` — interface template for new jira_client.py + github_client.py
- `backend/app/ticketing/service.py` — service-layer hook injection point for sla_due_at recomputation
- `backend/app/ticketing/router.py` — extend with `/tickets/{id}/watch` + `/tickets/{id}/comments` + `/tickets/{id}/blocked` routes
- `backend/alembic/versions/` — current head is `025_add_asset_tags`; Phase 13 needs migrations 026 (ticket_comments), 027 (ticket.blocked + ticket.blocked_reason + ticket.sla_due_at), 028 (ticket_watchers)

### Project-level

- `CLAUDE.md` — Project instructions; UI work routes to `sketch-findings-getvul` skill (auto-loaded by file pattern)
- `.planning/PROJECT.md` — Validated requirements + current milestone state

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (carry forward verbatim)

- **`<ChipBar axes={ChipAxis[]} />`** at `frontend/src/components/ui/ChipBar.tsx` — generic descriptor-driven primitive from Phase 12-04. Phase 13's tickets chip-bar wraps this with a 4-axis configuration (status, provider, severity, SLA).
- **`<DrillPanel>` + `<DrillPanelMobile>`** at `frontend/src/components/vulnerabilities/drill-panel*.tsx` — Phase 11 desktop + vaul mobile drawer. Phase 13 generalizes the chrome (slot pattern) without forking.
- **State primitives** at `frontend/src/components/states/*` — SkeletonTable, EmptyState, PartialFailureBanner mandatory. No new variants.
- **`<Avatar>`** at `frontend/src/components/ui/Avatar.tsx` — 2-char initials (post-WR-09). Used for assignee + reporter + watcher stack.
- **`<Breadcrumb>` + `<Crumb>`** at `frontend/src/components/ui/Breadcrumb.tsx` — used on `/tickets/[id]` header (`Tickets > {ticket.title}`).
- **`<BulkActionBar>` pattern** from Phase 11 — bottom-anchored action toolbar; Phase 13 instantiates with Close + Mark blocked / Unblock actions.
- **TanStack Query hooks pattern** — Phase 12's `use-assets.ts` / `use-asset-detail.ts` are the template for new `use-tickets.ts` / `use-ticket-detail.ts` / `use-ticket-comments.ts` / `use-ticket-watch.ts` / `use-mark-blocked.ts`.
- **`useReassignAsset` cache invalidation pattern** (Phase 12 D-A + WR-01) — applies to mutation hooks here (predicate-based invalidation for cross-prefix cache entries like `vulnerabilities` that include `ticket_id`).
- **`audit()` helper** at `backend/app/audit.py` — Phase 12 T-12-09 pattern (audit + mutation in same transaction, audit failure short-circuits commit). Applies to blocked toggle + watch toggle + comment create.

### Established patterns (cannot deviate)

- **Sunset CSS variables only** — `text-text-faint` / `text-text-muted` / `border-border-subtle` etc. NO `text-text-subtle` (not a token); NO raw hex; NO font substitutions (Inter + JetBrains Mono locked).
- **`field_validator` + `min_length` / `max_length` on every user-facing string** (Phase 12 BL-01) — applies to `blocked_reason` (3–500) and comment `body` (1–10000).
- **`uuid.UUID` on every path/query param** (Phase 12 BL-02) — applies to `ticket_id`, `comment_id`, `user_id` in new routes.
- **Audit-then-commit transaction** (Phase 12 T-12-09) for any mutation that changes Asset / Ticket / User state.
- **Mandatory state coverage** — every screen renders SkeletonTable on loading, EmptyState on no-results, PartialFailureBanner on error (UX-04-05 / UX-05-x bar).

### Integration points

- **Topnav** at `frontend/src/components/shell/sidebar.tsx` — already has `/tickets` link; need to add `/tickets/rules` as a sibling.
- **Search (Cmd+K)** at `frontend/src/app/(authed)/search` — current implementation likely doesn't search ticket comments; out of scope for P13 but note for future.
- **`/dashboard/connectors`** at `frontend/src/app/(authed)/dashboard/connectors/page.tsx` — Asana config relocation lands here in P14; P13 should add a placeholder empty-state link from `/tickets` when no Asana connector is configured.
- **AuditLog** model — `action='ticket.blocked'` / `'ticket.unblocked'` / `'ticket.comment_added'` / `'ticket.watch'` / `'ticket.unwatch'` are the new audit-event types Phase 13 introduces.

</code_context>

<specifics>
## Specific Ideas

- **"Provider gradient marks, not real logos"** — locked legally + brand-coherence-wise. Mark = `<span class="size-4 rounded gradient-{provider}">` with a small inner glyph or initial. Verify zero references to Atlassian/Jira/Asana/GitHub trademark assets in `frontend/public/` post-Phase-13.
- **"3 ·2 ·1" vuln-count format** — total · critical · high. Visually scannable. Total in normal text, critical in `text-severity-critical`, high in `text-severity-high`. Zeros render explicitly, not hidden.
- **"List view / Board view" toggle in page-head-actions** — Board view ships as a placeholder with copy ("Board view coming in a future update — for now…") + a sketch screenshot link. Toggle state persists in URL.
- **Blocked is "waiting on patch vendor"** — the canonical use case for the GetVul-internal Blocked flag. UI should make this read as a workflow signal, not a status override.
- **Phase 12's reassign-combobox UX pattern** is the template for the Blocked-reason inline editor on the right-rail Details card.

</specifics>

<deferred>
## Deferred Ideas

- **Full kanban / Board view body** — `UX-D-01` (drag-and-drop kanban for tickets; sketched in 006 variant C; placeholder toggle ships in UX-05).
- **Comment write-back to provider** — Local-only comments in Phase 13; provider write-back is a future phase if analysts want it.
- **Status interactive transitions to provider** — Open/In progress/Completed remain display-only; analyst-driven transitions to Jira/Asana/GitHub are a future phase.
- **Asana config + setup + sync-status UI** — moves to `/dashboard/connectors` in Phase 14.
- **Edit / delete comments** — schema supports it (`edited_at` column), UI affordances not in P13 scope.
- **Markdown rendering for comments** — plain-text only in v1; markdown is a v2.x decision per sketch 006 open variables.
- **Mine vs All filter persistence across screens** — sketch 006 open variable; topbar-global persistence deferred.
- **Connector OAuth UI** for Jira + GitHub — Phase 13 stubs use admin-CLI config; full UI in Phase 14 connectors.
- **Bulk-comment** — bulk Close + bulk Mark blocked only in P13; bulk-comment deferred to Phase 14 if analysts want it.
- **Drag-to-reorder watchers** / **watcher prioritization** — out of scope.
- **Search ticket comments (Cmd+K)** — comments are searchable in v2 if analysts ask.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 13` returned zero matches.

</deferred>

---

*Phase: 13-tickets-list-detail*
*Context gathered: 2026-06-01*
