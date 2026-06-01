# Phase 13: `/tickets` List + Detail - Research

**Researched:** 2026-06-01
**Domain:** Full-stack vertical slice — Next.js 15 list/detail UI + FastAPI/Postgres/Alembic backend + connector stubs
**Confidence:** HIGH (codebase verified by direct read; external API endpoints CITED from official docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

> CONTEXT.md is exhaustive (43 locked decisions). This research does NOT re-litigate WHAT to build — it documents HOW. The constraints below are copied verbatim; the planner MUST honor them.

### Locked Decisions

**Out-of-scope cleanup (D-S):**
- **D-S-01:** `/tickets/rules` splits into its own route (`app/(authed)/dashboard/tickets/rules/page.tsx`) with a full sunset rewrite. Topnav links to `/tickets/rules` instead of v1's `?tab=rules`. Reuses sunset tokens + ChipBar + state primitives.
- **D-S-02:** Asana config/setup/sync-status surface moves to `/dashboard/connectors` (Phase 14). If Asana connector isn't configured, `/tickets` renders an empty-state with deep-link to `/dashboard/connectors` (does not block, does not embed config UI).
- **D-S-03:** Bulk actions retained via Phase 11 `BulkActionBar` pattern. P13 bulk ops: **Close**, **Mark blocked / Unblock**. Bulk-comment deferred.

**Comment input (D-C):**
- **D-C-01:** Local audit notes only — comment input writes to GetVul only, never posts to Jira/Asana/GitHub. Activity timeline composes local comments + provider sync events visually.
- **D-C-02:** New `ticket_comments` table (schema in §Migration 026 below). Comments are first-class; edit/delete affordances ship later but schema (`edited_at`) supports them. Audit log stays for security events; user content lives in dedicated table.
- **D-C-03:** Comment `body` validated like Phase 12 BL-01 — Pydantic `min_length=1`, `max_length=10000`, `field_validator` strips leading/trailing whitespace. Plain-text render with newline preservation; markdown deferred.
- **D-C-04:** Comment ordering chronological ascending (oldest top, latest bottom). Comment input renders below the last activity row. Provider sync events interleave by `created_at`.

**Status pill (D-P):**
- **D-P-01:** Mixed model — Open/In progress/Completed are display-only mirrors of `Ticket.external_status` from provider sync (user cannot transition). **Blocked is GetVul-internal and interactive.**
- **D-P-02:** Blocked schema — `blocked BOOLEAN NOT NULL DEFAULT false` + `blocked_reason TEXT` (nullable, max 500). Each toggle writes audit row (`ticket.blocked` / `ticket.unblocked`) with `details.reason`. Validator: no whitespace-only reasons, `max_length=500`.
- **D-P-03:** Blocked toggled at: detail page right-rail Details card (inline edit, Phase 12 reassign-combobox pattern, optimistic + audit-then-commit), AND list bulk action (modal collecting one shared `blocked_reason`).
- **D-P-04:** Visual contract (Tailwind classes locked — see §Visual Contracts). Leading dot. When `ticket.blocked` true, Blocked pill renders ALONGSIDE provider-status pill ("Open · Blocked").

**Side-panel drill (D-D):**
- **D-D-01:** Standard shape (sketch 006 variant A content). Header: provider mark + ticket ID mono + truncated title + close. Body: linked-vulns mini-list (top 3 by severity, +N more), truncated description (~6 lines + "Show full →"), status+SLA pill row. Footer (sticky): Open in [provider], Open full detail, Mark blocked/Unblock (shared `<BlockedToggle>`).
- **D-D-02:** DrillPanel slot pattern, NOT a new TicketDrillPanel. Generalize chrome with a content-slot prop; create `<TicketDrillContent>` inside same chrome. URL contract becomes `?ticket=...&open=drill`. Existing vuln drill preserved — additive refactor.
- **D-D-03:** Mobile (<900px) — DrillPanel full-screen overlay (vaul). Footer collapses to "Open in [provider]" primary + overflow kebab for other 2.

**List view + chip-bar (D-L):**
- **D-L-01:** 8 columns: Severity · Provider · ID (mono) · Title (truncated, hover full) · Vulns (`T·C·H`) · Assignee (avatar+name) · Status · SLA. Mobile card layout collapse.
- **D-L-02:** Vuln-count `T·C·H` (total·critical·high). Critical `text-severity-critical`, high `text-severity-high`, total `text-text`. Zeros explicit. `>99` → `99+·C·H`. Total 0 → `—`.
- **D-L-03:** List/Board segmented toggle in page-head-actions. List default. Board renders placeholder copy. Toggle persists in URL (`?view=list|board`).
- **D-L-04:** Chip-bar axes: Status (multi), Provider (multi, only providers with synced tickets), Severity (multi, from worst linked vuln), SLA (single: Overdue/Soon/OK; Soon = within 7d). Search matches ID + title + assignee. 250ms debounce.

**SLA (D-SLA):**
- **D-SLA-01:** Add `ticket.sla_due_at TIMESTAMPTZ` + index `ix_tickets_tenant_sla ON tickets(tenant_id, sla_due_at)`. Single source of truth, recomputed via service-layer hook.
- **D-SLA-02:** `ticket.sla_due_at = MIN(linked_vuln.sla_due_at)`. No linked vulns with sla_due_at → NULL → "Unknown" gray.
- **D-SLA-03:** Backfill migration computes for existing tickets. Service-layer hook recomputes when ticket gains/loses linked vuln or linked vuln's sla_due_at changes. Hooks at vuln-snooze + ticket-create paths.
- **D-SLA-04:** SLA pill thresholds computed CLIENT-SIDE from `ticket.sla_due_at`: Overdue (`< now`, red), Soon (`< now+7d`, amber), OK (`>= now+7d`, green), Unknown (NULL, gray).

**Provider stubs (D-PROV):**
- **D-PROV-01:** Build Jira + GitHub connector stubs. `jira_client.py` + `github_client.py` implementing same interface as `asana_client.py`. `TicketProvider` enum already has JIRA/GITHUB/ASANA (VERIFIED — see §Connector Stubs). Config via existing connector pattern (encrypted per-tenant).
- **D-PROV-02:** Stub depth — auth + ticket-create + read-back state only. No daily-sync cron, no comment-pull, no bulk-fetch.
- **D-PROV-03:** Frontend `type TicketProvider = 'jira' | 'asana' | 'github'`. `<ProviderMark provider={p} />` with CSS-variable gradients (see §CSS Gradient Tokens for which exist).

**Watchers (D-W):**
- **D-W-01:** Watchers = union of provider followers + local GetVul subscriptions.
- **D-W-02:** New `ticket_watchers` table (composite PK `(ticket_id, user_id)`). Endpoints `POST/DELETE /api/v1/tickets/{id}/watch` (idempotent).
- **D-W-03:** "Watch" button on right-rail People card, optimistic toggle, rollback-with-toast on failure.
- **D-W-04:** Avatar stack: first 3 by display_name + 2-char initials; remainder `+N` chip with hover popover (max 50). Sort: assignee → reporter → watchers chronological. Dedupe, prefer strongest role.

### Claude's Discretion
- Mobile breakpoint two-column → stacked: 900px (Phase 12 D-D-04).
- Activity timeline date grouping: group by day ("Today", "Yesterday", "MMM D").
- DrillPanel close → URL state: `?ticket=...&open=drill`. Esc + X + outside-click close.
- Bulk-action confirmation: "Mark blocked" prompts shared reason modal; "Close" prompts confirmation only.
- Connector OAuth flow UX: out of scope (Phase 14). Stubs land with admin-CLI / manual-DB-write config.

### Deferred Ideas (OUT OF SCOPE)
- Full kanban Board view body (UX-D-01); comment write-back to provider; status interactive transitions to provider; Asana config UI (Phase 14); edit/delete comments UI; markdown rendering; Mine-vs-All filter persistence; Jira/GitHub connector OAuth UI (Phase 14); bulk-comment; drag-to-reorder watchers; search ticket comments.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-05-01 | `/tickets` list: chip-bar + side-panel pattern; 8 columns (Severity·Provider·ID·Title·Vulns·Assignee·Status·SLA) | `ChipBar` primitive (§Reusable Primitives), `assets/page.tsx` list-page template, new `list_tickets` server query reshape (§Backend Reshape) |
| UX-05-02 | Provider identity = gradient marks + tinted chips, NOT real logos (Jira blue / Asana coral / GitHub violet) | `<ProviderMark>` new primitive; tailwind tokens `provider-jira/asana/github` already exist (§CSS Gradient Tokens) |
| UX-05-03 | Status pills separate color family (Open violet · In progress amber · Completed green · Blocked red) + leading dot | Visual contract locked (§Visual Contracts); `blocked` column + `external_status` mapping |
| UX-05-04 | `/tickets/[id]` two-column inheriting `/assets/[id]`; main: linked vulns + description + activity timeline + comment input + status; rail: Details + People + Asset card | `assets/[id]/page.tsx` two-column template (§Two-Column Detail); new ticket-detail endpoint + comments/watchers tables |
| UX-05-05 | Watcher/contributor avatar stacks with `+N` overflow | `<Avatar>` (2-char initials, verified); `ticket_watchers` table; new avatar-stack component |
| UX-05-06 | Kanban "Board view" placeholder — List/Board segmented toggle, Board deferred | `?view=list\|board` URL state (Phase 11 D-P-02 convention); placeholder copy |
</phase_requirements>

## Summary

Phase 13 is a full vertical slice that reuses an already-mature pattern library. The frontend list page mirrors `frontend/src/app/(authed)/dashboard/assets/page.tsx` (Suspense + ErrorBoundary + ChipBar + SkeletonTable/EmptyState/PartialFailureBanner + Pagination), and the detail page mirrors `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` (two-column `grid-cols-[1fr_340px]` with `min-[900px]` gate + sticky right rail). The drill-panel generalization (D-D-02) is the single architecturally novel piece: the existing `DrillPanel`/`DrillPanelMobile` hardcode `DrillContent` and the `?cve=`/`?open=drill` URL keys, so they need an additive `children`/render-slot prop and a parameterized URL-key set to host a new `<TicketDrillContent>` without forking.

The backend needs three Alembic migrations (026 `ticket_comments`, 027 `ticket.blocked`+`blocked_reason`+`sla_due_at`+backfill+index, 028 `ticket_watchers`) chained off the current head `025_add_asset_tags`. The `TicketProvider` enum **already contains JIRA, GITHUB, ASANA** — no enum change needed. `asana_client.py` is a clean dataclass-result + `httpx.AsyncClient` template that `jira_client.py` and `github_client.py` must match (constructor takes a token, async methods return a normalized result dataclass, 429-retry, structured logging). Note: there is a **schema mismatch the planner must resolve** — the current `Ticket` model is **one row per (vuln, provider)** and `list_tickets` groups by `external_ticket_url` to present "one ticket". The 8-column list and the `/tickets/[id]` detail need a stable per-ticket identity; the cleanest approach is to key the list/detail on `external_ticket_url` (or `first_ticket_id`) exactly as `list_tickets` already does.

**Primary recommendation:** Clone the assets list+detail page structure verbatim, generalize `DrillPanel` chrome with a content slot + URL-key params (preserving vuln behavior via default props), add migrations 026/027/028 following the `025` revision-id convention, and implement `jira_client.py`/`github_client.py` as 1:1 interface clones of `asana_client.py`. Inject the `sla_due_at = MIN(linked_vuln.sla_due_at)` recompute as a shared helper called from `create_tickets`/`create_host_ticket`/`create_remediation_ticket` and from the vuln-snooze path. The single biggest planning risk is the per-vuln-row vs per-ticket identity mismatch — resolve it explicitly before writing detail-page tasks.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ticket list query + 8-col aggregation | API/Backend (`list_tickets`) | DB | Severity/vuln-count/SLA aggregation already lives server-side; reshape there, not in browser |
| Chip-bar filter state | Browser (URL) | API (filter params) | Phase 11/12 convention: filters live in URL via `useUrlStateList`, sent as query params |
| SLA pill tier computation | Browser (client-side) | — | D-SLA-04 explicitly: compute from `sla_due_at` client-side, no backend "state" column |
| `sla_due_at` derivation/storage | API/Backend (service hook) | DB (column+index) | D-SLA-01/03: single source of truth, recomputed at write paths |
| Blocked toggle | API/Backend (audit-then-commit) | Browser (optimistic UI) | D-P-03: mutation + audit on backend; optimistic flip on frontend |
| Comment create/list | API/Backend (`ticket_comments`) | Browser (timeline render) | D-C-01: local-only, no provider write-back |
| Watch/unwatch | API/Backend (idempotent) | Browser (optimistic) | D-W-02/03 |
| Provider ticket-create | API/Backend (connector clients) | External (Jira/GitHub APIs) | D-PROV: clients own the external handshake |
| Provider gradient mark | Browser (CSS) | — | UX-05-02: pure presentational, CSS-variable gradients |
| DrillPanel chrome (focus trap, URL, Esc) | Browser | — | Phase 11 generic chrome, generalized in P13 |

## Standard Stack

All dependencies already in the repo — Phase 13 adds **zero new packages**. Versions confirmed from project conventions (CLAUDE.md) and existing imports.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 15 (App Router) | Routing, RSC, `/tickets` + `/tickets/[id]` + `/tickets/rules` | Project standard [VERIFIED: CLAUDE.md] |
| React | 19 | Components | Project standard [VERIFIED: CLAUDE.md] |
| TypeScript | 5.5 | Types | Project standard [VERIFIED: CLAUDE.md] |
| Tailwind | 3.4 | Styling (sunset tokens) | Project standard [VERIFIED: CLAUDE.md] |
| @tanstack/react-query | (existing) | Server-state hooks, optimistic mutations | Phase 12 pattern [VERIFIED: use-reassign-asset.ts imports] |
| vaul | (existing) | Mobile bottom-sheet drawer | Phase 11 DrillPanelMobile [VERIFIED: drill-panel-mobile.tsx imports `Drawer` from 'vaul'] |
| lucide-react | (existing) | Icons (X, eye, kebab) | [VERIFIED: drill-content.tsx imports `X`] |
| FastAPI | (existing) | API routes | Project standard [VERIFIED: router.py] |
| SQLAlchemy | 2.x (async, `Mapped`/`mapped_column`) | ORM | [VERIFIED: models.py uses `Mapped[...]`] |
| Alembic | (existing) | Migrations | [VERIFIED: versions/ dir] |
| Pydantic | 2.x (`field_validator`, `Field`) | Request validation | [VERIFIED: schemas.py uses `Field(..., min_length=...)`] |
| httpx | (existing) | Async HTTP for connector clients | [VERIFIED: asana_client.py uses `httpx.AsyncClient`] |
| structlog | (existing) | Structured logging in clients | [VERIFIED: asana_client.py] |

### Supporting (existing primitives — reuse verbatim)
| Component | Path | Purpose |
|-----------|------|---------|
| `ChipBar` + `ChipAxis` | `frontend/src/components/ui/ChipBar.tsx` | Descriptor-driven filter bar (wrap with 4-axis ticket config) |
| `DrillPanel` / `DrillPanelMobile` | `frontend/src/components/vulnerabilities/drill-panel*.tsx` | Drill chrome to GENERALIZE (D-D-02) |
| `DrillContent` | `frontend/src/components/vulnerabilities/drill-content.tsx` | Already has a `renderConfirm` render-slot — proves slot pattern is feasible |
| `SkeletonTable`/`EmptyState`/`PartialFailureBanner`/`PerSourceStatusStrip` | `frontend/src/components/states/` | Mandatory state coverage |
| `Avatar` | `frontend/src/components/ui/Avatar.tsx` | 2-char initials, sunset gradient (watcher stack + assignee) |
| `Breadcrumb` / `Crumb` | `frontend/src/components/ui/Breadcrumb.tsx` | Detail-page header |
| `Pagination` | `frontend/src/components/ui/Pagination.tsx` | List pagination |
| `ToastProvider` / `useToast` | `frontend/src/components/ui/ToastProvider.tsx` | Optimistic rollback toasts |
| `ConfirmModal` | `frontend/src/components/ui/ConfirmModal.tsx` | Bulk-close confirmation |
| `useUrlState` / `useUrlStateList` | `frontend/src/hooks/` | URL filter/view state |
| `useMediaQuery` | `frontend/src/hooks/use-media-query.ts` | 900px mobile gate |
| `audit()` | `backend/app/audit.py` | Audit-then-commit (fail-closed) |
| `get_decrypted_credentials()` | `backend/app/connectors/service.py` | Decrypt per-tenant connector creds |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Generalizing `DrillPanel` (D-D-02) | A new `TicketDrillPanel` | Forking duplicates focus-trap/Esc/clickaway/URL logic; CONTEXT.md D-D-02 explicitly forbids forking. Use slot. |
| Client-side SLA tier | Backend `sla_state` column | D-SLA-04 locked client-side (avoids stale-state column, thresholds are `now()`-relative) |
| New `ticket_comments` table | Reuse `audit_logs` | D-C-02 locked: user content ≠ security events; no conflation |

**Installation:** None — no new packages.

**Version verification:** Skipped npm registry checks because Phase 13 introduces no new dependencies. All libraries are confirmed present via direct import in the files cited above.

## Architecture Patterns

### System Architecture Diagram

```
                            ┌─────────────────────────────────────────────┐
  Analyst browser           │  /tickets  (list page)                       │
  ─────────────────────────▶│  ┌──────────┐  ┌─────────────────────────┐   │
  URL: ?status=&provider=   │  │ ChipBar  │  │ List/Board toggle (?view)│  │
       &severity=&sla=      │  │ (4 axes) │  └─────────────────────────┘   │
       &search=&view=list   │  └────┬─────┘                                 │
       &ticket=&open=drill  │       │ filters→query params                  │
                            │       ▼                                       │
                            │  useTickets() ──▶ GET /api/v1/tickets ───┐    │
                            │  8-col table (T·C·H, provider mark, pills)│   │
                            │       │ row click → ?ticket=&open=drill   │   │
                            │       ▼                                   │   │
                            │  DrillPanel[generalized] ── TicketDrillContent│
                            │   (Open in provider / full detail / Blocked)  │
                            └───────────────────────────────────────────┼──┘
                                                                         │
  /tickets/[id] (detail, two-column 1fr_340px, sticky rail @900px)      │
   main: linked vulns · description · activity timeline + comment input │
   rail: Details(Blocked toggle) · People(watchers stack) · Asset card  │
        │ useTicketDetail / useTicketComments / useTicketWatch          │
        │ mutations: useMarkBlocked / useTicketWatch (optimistic+rollback)
        ▼                                                                ▼
  ┌──────────────────────────── FastAPI: app/ticketing/router.py ──────────┐
  │ GET  /tickets                  → list_tickets() [reshape: blocked,sla] │
  │ GET  /tickets/{id}             → ticket detail (NEW)                    │
  │ GET  /tickets/{id}/comments    → list comments (NEW)                   │
  │ POST /tickets/{id}/comments    → add comment (NEW, audit)              │
  │ POST /tickets/{id}/blocked     → toggle blocked (NEW, audit-then-commit)│
  │ POST/DELETE /tickets/{id}/watch→ idempotent watch (NEW, audit)         │
  │ POST /tickets/bulk-action      → extend: blocked/unblock               │
  └───────┬──────────────────────────────────────────────────────────────┘
          │ service.py (sla recompute hook)        connector clients
          ▼                                          ▼
  ┌─────────────── Postgres ──────────────┐   ┌──── External APIs ────┐
  │ tickets (+blocked,+blocked_reason,    │   │ asana_client (exists)  │
  │          +sla_due_at, +ix_tenant_sla) │   │ jira_client  (NEW stub)│
  │ ticket_comments (NEW)                 │   │ github_client(NEW stub)│
  │ ticket_watchers (NEW)                 │   └────────────────────────┘
  │ audit_logs (ticket.blocked/comment/...)│
  │ vulnerabilities.sla_due_at (source)   │
  └───────────────────────────────────────┘
```

### Recommended Project Structure
```
frontend/src/
├── app/(authed)/dashboard/tickets/
│   ├── page.tsx                       # list (clone assets/page.tsx)
│   ├── [id]/page.tsx                  # detail (clone assets/[id]/page.tsx)
│   └── rules/page.tsx                 # sunset rewrite of rules (D-S-01)
├── components/tickets/
│   ├── tickets-chip-bar.tsx           # wraps ChipBar w/ 4 ticket axes
│   ├── tickets-table.tsx              # 8-col table
│   ├── ticket-drill-content.tsx       # slot content for generalized DrillPanel
│   ├── provider-mark.tsx              # <ProviderMark provider=...>
│   ├── status-pill.tsx                # 4-state (Open/InProg/Completed/Blocked)
│   ├── sla-pill.tsx                   # client-side tier compute
│   ├── vuln-count.tsx                 # T·C·H format
│   ├── blocked-toggle.tsx             # shared by drill + detail rail
│   ├── activity-timeline.tsx          # comments + sync events, day-grouped
│   ├── comment-input.tsx              # local notes
│   ├── watcher-stack.tsx              # +N avatar overflow
│   ├── ticket-asset-card.tsx          # rail cross-link card
│   ├── ticket-bulk-bar.tsx            # Close + Mark blocked
│   └── microcopy.ts                   # copy-voice strings
├── lib/queries/
│   ├── use-tickets.ts                 # list (clone use-assets.ts)
│   ├── use-ticket-detail.ts           # detail (clone use-asset-detail.ts)
│   ├── use-ticket-comments.ts
│   └── keys.ts                        # ADD tickets.* keys
└── lib/mutations/ (or queries/)
    ├── use-ticket-watch.ts            # clone use-reassign-asset.ts optimistic pattern
    ├── use-mark-blocked.ts
    └── use-add-comment.ts

backend/app/ticketing/
├── jira_client.py                     # NEW — interface clone of asana_client
├── github_client.py                   # NEW — interface clone
├── models.py                          # +Ticket cols, +TicketComment, +TicketWatcher
├── schemas.py                         # +Comment/Blocked/Watch request models
├── service.py                         # +recompute_ticket_sla() hook
└── router.py                          # +comment/blocked/watch routes
backend/alembic/versions/
├── 026_add_ticket_comments.py
├── 027_add_ticket_blocked_sla.py      # cols + backfill UPDATE + index
└── 028_add_ticket_watchers.py
```

### Pattern 1: List page composition (clone assets/page.tsx)
**What:** `ErrorBoundary > Suspense > Inner` with mutually-exclusive state branches (error → loading → empty → data). Filters read from URL via `useUrlStateList`, memoized into a `filters` object, passed to a `useTickets` query.
**When to use:** `/tickets/page.tsx` and `/tickets/rules/page.tsx`.
**Source:** `frontend/src/app/(authed)/dashboard/assets/page.tsx` (verbatim structure). Critical detail (WR-13): state branches MUST be mutually exclusive — `q.error ? ... : isLoading ? ... : items.length===0 ? ... : <Table/>` — never stack error + empty.

### Pattern 2: Two-column detail (clone assets/[id]/page.tsx)
**What:** `grid grid-cols-1 gap-6 p-6 min-[900px]:grid-cols-[1fr_340px]` with a `<section>` main and a sticky `<aside className="min-[900px]:sticky min-[900px]:top-4 min-[900px]:self-start">` rail. Each rail card + main section degrades independently (own loading/empty/error). Avoid nesting a second `<main>` (axe landmark-no-duplicate-main, BL-03) — use `<section aria-label>`.
**When to use:** `/tickets/[id]/page.tsx`.
**Source:** `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx`.

### Pattern 3: DrillPanel slot generalization (D-D-02 — the novel piece)
**Current contract (VERIFIED by read):**
- `DrillPanel({ cveId, originRowRef })` — desktop `<aside w-[420px]>`. Open gate: `params.get('open')==='drill' && cveId!==null`. `close()` deletes `open` + `cve` keys. Renders `<DrillContent idOrCve={cveId} onClose={close} />`.
- `DrillPanelMobile({ cveId })` — vaul `Drawer`, gated `isMobile && params.get('open')==='drill'`. Same close() deleting `open`+`cve`.
- The chrome (slide-in, Esc, mousedown-outside-close, focus return) is fully generic; only the URL keys (`cve`) and the body component (`DrillContent`) are vuln-specific.
- `DrillContent` ALREADY accepts a `renderConfirm` render-prop — precedent that slot injection works.

**Cleanest additive refactor (recommended):**
1. Add optional props to `DrillPanel`/`DrillPanelMobile`:
   - `idKey?: string` (default `'cve'`) — the URL param holding the entity id.
   - `id?: string | null` (alias for the entity id; keep `cveId` as a back-compat alias defaulting into `id`).
   - `children?: React.ReactNode` OR `renderContent?: (args:{id,onClose}) => ReactNode` — when provided, render instead of `<DrillContent>`.
   - `ariaLabel?: string` (default `'Vulnerability detail'`).
2. `close()` deletes `open` + `idKey` (so it removes `ticket` instead of `cve` when `idKey='ticket'`).
3. Existing vuln callers pass nothing new → behavior preserved (default `idKey='cve'`, default content = `DrillContent`). **This is the regression-safety contract — the existing vuln drill tests must stay green unchanged.**
4. Ticket list passes `idKey="ticket"`, `id={ticketId}`, `renderContent={({id,onClose}) => <TicketDrillContent ticketId={id} onClose={onClose}/>}`, `ariaLabel="Ticket detail"`. URL becomes `?ticket=...&open=drill`.

**Source:** `drill-panel.tsx`, `drill-panel-mobile.tsx`, `drill-content.tsx` (renderConfirm slot precedent).

### Pattern 4: Optimistic mutation + rollback (clone use-reassign-asset.ts)
**What:** `useMutation` with `onMutate` (cancel queries, snapshot cache, optimistic patch), `onError` (restore snapshot + error toast), `onSuccess` (invalidate keys + success toast), `retry: 0`. Send ONLY the minimal body (mass-assignment guard). Use predicate-based invalidation for cross-prefix entries.
**When to use:** `use-mark-blocked.ts`, `use-ticket-watch.ts`, `use-add-comment.ts`.
**Source:** `frontend/src/lib/queries/use-reassign-asset.ts` (full optimistic+rollback+predicate-invalidation reference).

```ts
// Source: use-reassign-asset.ts onSuccess (predicate invalidation for cross-prefix keys)
qc.invalidateQueries({
  predicate: (q) =>
    Array.isArray(q.queryKey) &&
    q.queryKey[0] === 'vulnerabilities' &&
    JSON.stringify(q.queryKey).includes(`"asset_id":"${assetId}"`),
});
```
For tickets: marking blocked / adding a comment must invalidate `queryKeys.tickets.byId(id)` AND `queryKeys.tickets.all` (list); blocked also affects the asset remediation rail if it includes ticket state — use the same predicate technique against `['assets', id, 'remediations']`.

### Pattern 5: Audit-then-commit (backend mutation)
**What:** `await audit(db, user, "ticket.blocked", "ticket", str(ticket_id), {"reason": reason}); await db.commit()`. `audit()` is **fail-closed** — if the audit row fails, the exception propagates and the commit is skipped (the mutation rolls back). Do mutation `db.add`/field-set BEFORE the audit call, commit AFTER.
**When to use:** blocked toggle, comment create, watch/unwatch, bulk blocked.
**Source:** `backend/app/audit.py` (AUDIT-01 fail-closed contract) + `router.py:182-185` (existing `ticket.create` example).
New audit actions to introduce: `ticket.blocked`, `ticket.unblocked`, `ticket.comment_added`, `ticket.watch`, `ticket.unwatch`. (Note: `AuditLog.action` is `String(50)` — all fit.)

### Pattern 6: Connector client interface (clone asana_client.py)
**Template shape (VERIFIED):** constructor `__init__(self, access_token: str)` builds an `httpx.AsyncClient(base_url, timeout=30, headers={Authorization: Bearer ...})`. Methods are `async`, return a normalized `@dataclass` result (e.g. `AsanaTask`) or `None` on failure, log failures via `structlog`, handle HTTP 429 with `Retry-After` sleep+retry, and expose `async def close()` calling `aclose()`.
**Required methods for `jira_client.py` / `github_client.py`** (to match the Asana surface used by `service.py` + D-PROV-02):
- `test_connection() -> dict` (auth probe; returns `{success, message, ...}`)
- `create_ticket(...)` / `create_task(...)` → normalized result dataclass with `gid/id`, `name`, `url`, `assignee`, `completed/state`, `due_on`
- `get_task(id) -> dict | None` (read-back `external_status` — D-PROV-02 item 2)
- `close()`
Out of scope per D-PROV-02: `add_comment`, `list_projects`, `update_task`, bulk sync.
**Source:** `backend/app/ticketing/asana_client.py`.

### Anti-Patterns to Avoid
- **Forking DrillPanel** — D-D-02 forbids it. Slot, don't fork.
- **Per-row "ticket"** — `Ticket` is one row per (vuln, provider). Do NOT present each row as a ticket on the new list; group by `external_ticket_url` like `list_tickets` already does (see §Backend Reshape).
- **Stacking error + empty states** — WR-13 (mutually exclusive branches).
- **Slicing `err.message`** — WR-10/WR-15: pass full message to `PartialFailureBanner`, which truncates visually.
- **Freehand hex / `text-text-subtle` / non-Inter fonts** — CLAUDE.md forbids; use sunset CSS vars + `text-text-faint`/`text-text-muted`.
- **Spreading arbitrary form data into mutation bodies** — T-12-08 mass-assignment; send only the minimal field (`{blocked, blocked_reason}` / `{}` for watch).
- **Backend "SLA state" column** — D-SLA-04 computes tier client-side.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Filter chip bar | New chip component | `ChipBar` + `ChipAxis` descriptors | XSS allow-list clamp, debounce, URL-batch flush all solved (T-12-05) |
| Drill chrome | New panel | Generalized `DrillPanel`/`DrillPanelMobile` | Focus trap, Esc, clickaway, vaul mobile, URL state already correct |
| Optimistic mutation | Manual setState rollback | `useReassignAsset` pattern | Cancel/snapshot/rollback/predicate-invalidate is subtle |
| Avatar initials | Custom initials logic | `Avatar` | 2-char rule + XSS-safe text node (T-12-04) |
| Loading/empty/error | Inline spinners | `SkeletonTable`/`EmptyState`/`PartialFailureBanner` | Mandatory, accessibility baked in |
| Audit + mutation atomicity | Separate audit call | `audit()` then `commit()` | Fail-closed AUDIT-01 contract |
| Credential decryption | Read `credentials_secret_arn` raw | `get_decrypted_credentials(connector)` | Fernet/JSON decode handled |
| Connector HTTP client | Raw `requests`/fetch | `httpx.AsyncClient` per asana_client | 429 retry, async, structured logging template |
| SLA pill color | New tier logic per surface | One `<SlaPill due={...}/>` client component | D-SLA-04 thresholds in one place |

**Key insight:** Phase 13 is ~90% composition of existing Phase 11/12 primitives. The genuinely new code is: 3 migrations, 2 connector stubs, ~6 small presentational components, ~5 query/mutation hooks, the DrillPanel slot props, and the `list_tickets` reshape. Anything you'd "build from scratch" almost certainly already exists.

## Backend Reshape (per-vuln-row → per-ticket identity)

**CRITICAL planning input.** `backend/app/ticketing/models.py` `Ticket` is **one row per (vulnerability_id, provider)** with a unique `(tenant_id, external_ticket_id, provider)`. The host/remediation flows create MANY ticket rows sharing one `external_ticket_url`/`external_ticket_id` prefix (`f"{task.gid}:{v.id}"`). `list_tickets` already groups by `external_ticket_url` to present "one ticket" (returns `id` = `first_ticket_id`).

Implications for Phase 13:
- **Identity:** The list/detail "ticket id" should be `external_ticket_url` (stable) or `first_ticket_id`. New routes `/tickets/{id}/...` take `id: uuid.UUID` (BL-02) → resolve to the row group. The planner must pick ONE canonical identity and use it for comments/watchers/blocked FKs.
- **New columns (`blocked`, `blocked_reason`, `sla_due_at`)** live on `tickets` — but since a logical ticket = many rows, the toggle/recompute must update ALL rows in the group (`WHERE external_ticket_url = ...`), OR the planner introduces a parent ticket concept. **Recommendation:** apply to the group (mirror `close_ticket`, which already updates all rows for a URL). Document this in the plan so the migration backfill and the toggle agree.
- **`ticket_comments.ticket_id` / `ticket_watchers.ticket_id`** FK to `tickets(id)` per CONTEXT schema — but with the group model, choose the canonical row id (`first_ticket_id`) consistently, or FK to the group. **Open question O1 below.**
- **8-column list aggregation** (`max_severity`, `critical_count`, `high_count`, `vuln_count`) is ALREADY computed in `list_tickets` detail_q — extend that query to also surface `min(blocked)`/`bool_or(blocked)`, `min(blocked_reason)`, `min(sla_due_at)` per group, plus `external_status` (already present) for the Status pill.

## Migrations (chain off `025_add_asset_tags`)

**Convention (VERIFIED from 024/025):** `revision = "NNN_descriptive_name"` string, `down_revision = "<prev>"`, `branch_labels`/`depends_on` optional (025 omits them; 020 sets `= None`). Use `op.add_column`/`op.create_index`/`op.create_table`. `UUID` PKs use `server_default` `gen_random_uuid()` (see `audit.py` AuditLog) or `UUIDPrimaryKeyMixin` in ORM. Timestamps `sa.DateTime(timezone=True)`. Index naming `ix_<table>_<cols>`.

### Migration 026 — `026_add_ticket_comments`
```python
revision = "026_add_ticket_comments"
down_revision = "025_add_asset_tags"

def upgrade():
    op.create_table(
        "ticket_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ticket_comments_ticket_created", "ticket_comments",
                    ["ticket_id", "created_at"])

def downgrade():
    op.drop_index("ix_ticket_comments_ticket_created", table_name="ticket_comments")
    op.drop_table("ticket_comments")
```

### Migration 027 — `027_add_ticket_blocked_sla` (cols + backfill + index)
```python
revision = "027_add_ticket_blocked_sla"
down_revision = "026_add_ticket_comments"

def upgrade():
    op.add_column("tickets", sa.Column("blocked", sa.Boolean, nullable=False,
                  server_default=sa.text("false")))
    op.add_column("tickets", sa.Column("blocked_reason", sa.Text, nullable=True))
    op.add_column("tickets", sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
    # D-SLA-03 backfill: ticket.sla_due_at = MIN(linked vuln.sla_due_at)
    op.execute("""
        UPDATE tickets t
        SET sla_due_at = v.sla_due_at
        FROM vulnerabilities v
        WHERE t.vulnerability_id = v.id
          AND v.sla_due_at IS NOT NULL
    """)
    # (1:1 vulnerability_id FK → MIN is the row's own value. If a logical
    #  ticket spans many rows, recompute the group MIN in the service hook
    #  on next write; the per-row backfill is correct per-row.)
    op.create_index("ix_tickets_tenant_sla", "tickets", ["tenant_id", "sla_due_at"])

def downgrade():
    op.drop_index("ix_tickets_tenant_sla", table_name="tickets")
    op.drop_column("tickets", "sla_due_at")
    op.drop_column("tickets", "blocked_reason")
    op.drop_column("tickets", "blocked")
```
**Backfill nuance:** Because `Ticket.vulnerability_id` is a 1:1 FK, each ticket ROW maps to exactly one vuln, so the per-row backfill `= v.sla_due_at` IS the per-row MIN. The "group MIN across linked vulns" only matters if the logical ticket (group of rows) needs ONE displayed SLA — `list_tickets` already takes `func.min(...)` per `external_ticket_url` group, so the group MIN can be computed at read time OR materialized identically per row (each row's value is its vuln's value; `MIN` over the group then yields the soonest). **The backfill as written is correct.**

### Migration 028 — `028_add_ticket_watchers`
```python
revision = "028_add_ticket_watchers"
down_revision = "027_add_ticket_blocked_sla"

def upgrade():
    op.create_table(
        "ticket_watchers",
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("ticket_id", "user_id"),
    )

def downgrade():
    op.drop_table("ticket_watchers")
```

## SLA Recompute Hook (D-SLA-03)

**Inject point (VERIFIED `service.py` call sites):**
- `create_tickets` (line 143 `ticket = Ticket(...)`), `create_host_ticket` (line 393), `create_remediation_ticket` (line 567) — all construct `Ticket(...)` then `db.flush()`. Set `sla_due_at=vuln.sla_due_at` at construction (each row's vuln), OR call a shared helper after flush.
- **Recommended:** add `async def recompute_ticket_sla(db, ticket_or_url)` that recomputes the group MIN over linked vulns and updates the row(s). Call it from the three create paths and from the **vuln-snooze path**.
- **Vuln-snooze path:** NOT in `ticketing/service.py` — it lives under `app/vulnerabilities/` (the snooze mutation that changes `vulnerability.sla_due_at`). [ASSUMED — see A1] The planner must locate the snooze service function (frontend hook is `use-snooze.ts` → backend vuln route) and add a post-snooze call to `recompute_ticket_sla` for any tickets linked to the snoozed vuln. Search `grep -rn "def.*snooze\|sla_due_at =" backend/app/vulnerabilities/`.

## Connector Stubs (D-PROV)

**Enum (VERIFIED):** `TicketProvider` in `models.py:14` ALREADY has `JIRA="JIRA"`, `GITHUB="GITHUB"`, `ASANA="ASANA"`. **No enum migration needed.** `TicketCreateRequest.provider` already validates `pattern="^(ASANA|JIRA|GITHUB)$"`.

**Credential storage (VERIFIED):** `ConnectorConfig` (per-tenant, encrypted `credentials_secret_arn`, `config` JSONB). `get_decrypted_credentials(connector)` returns `dict[str,str]`. Jira/GitHub configs would be new `connector_type` rows — BUT `ConnectorType` enum (`CROWDSTRIKE/NESSUS/DEFENDER/WIZ`) does NOT include JIRA/GITHUB, and Asana is fetched by `connector_type == "ASANA"` (a string not in the enum either). [ASSUMED — A2] Connector rows are looked up by string `connector_type`, so Jira/GitHub configs can be stored as `connector_type="JIRA"`/`"GITHUB"` without an enum change (matching how "ASANA" is already used as a free string in `router.py:_get_asana_client`). Planner should confirm there's no DB CHECK constraint on `connector_configs.connector_type`.

### Jira Cloud REST API (CITED)
- **Create issue:** `POST https://<domain>.atlassian.net/rest/api/3/issue` → 201 with `{id, key, self}`. v3 uses Atlassian Document Format (ADF) for `description`. [CITED: developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/]
- **Read issue/state:** `GET /rest/api/3/issue/{issueIdOrKey}` → `fields.status.name` for `external_status`.
- **Auth:** Basic auth `email:api_token` (base64) or OAuth 2.0 (3LO). For the admin-CLI stub (Claude's Discretion — OAuth UI deferred to P14), an API token + email is simplest. Store `{email, api_token, base_url, project_key}` in connector config/creds.
- **Ticket URL for "Open in Jira":** `https://<domain>.atlassian.net/browse/<key>`.

### GitHub Issues REST API (CITED)
- **Create issue:** `POST /repos/{owner}/{repo}/issues` → 201 with `{number, html_url, state, ...}`. [CITED: docs.github.com/en/rest/issues]
- **Read issue/state:** `GET /repos/{owner}/{repo}/issues/{number}` → `state` (`open`/`closed`) for `external_status`.
- **Auth:** `Authorization: Bearer <token>` + `Accept: application/vnd.github+json`. PAT or GitHub App token. Store `{token, owner, repo}` in connector config/creds. [CITED: docs.github.com/rest/guides/getting-started-with-the-rest-api]
- **Watchers (D-W-01):** GitHub has no per-issue watchers primitive (uses notifications/subscriptions) — stub returns empty provider-followers; rely on local `ticket_watchers`. Jira has explicit watchers (`GET /rest/api/3/issue/{key}/watchers`) but pulling them is OUT of P13 stub scope (D-PROV-02 — no bulk-fetch); local watchers only for P13.

## CSS Gradient Tokens (D-PROV-03)

**VERIFIED state:**
- `frontend/tailwind.config.*` ALREADY defines: `provider-jira: '#5C9CFF'`, `provider-asana: '#FF8AA0'`, `provider-github: 'var(--color-violet)'` (lines 54-56).
- `globals.css` has `--color-pink` and `--color-violet` referenced (verified usage) and foundation.md defines `--color-pink #EC4899`, `--color-violet #A78BFA`, `--color-amber #F59E0B`. The `-soft` variants exist ("+ matching -soft variants at 18% alpha").
- **MISSING:** D-PROV-03 names `--color-blue`, `--color-blue-soft`, `--color-coral`. These are NOT in foundation.md (no `--color-blue`/`--color-coral`). visual-language.md instead specifies provider gradients with literal hex: Jira `linear-gradient(135deg, #5C9CFF, #2684FF)`, Asana `linear-gradient(135deg, #FF8AA0, #F1506E)`, GitHub `linear-gradient(135deg, #C7BAFF, #A78BFA)`.

**Recommendation for planner:** Reconcile the conflict — D-PROV-03 wants CSS-variable gradients with `--color-blue`/`--color-coral`/etc., but the design system (visual-language.md) defines providers with specific hex stops and the tailwind config already has `provider-jira/asana/github` color tokens. **Cleanest path:** add three gradient utilities (e.g. `--gradient-provider-jira/asana/github`) to `globals.css` using the visual-language.md hex stops, and have `<ProviderMark>` consume those. This honors "no inline hex in components" (the hex lives once in the token file) AND matches the locked visual-language.md marks. CONTEXT.md D-PROV-03 explicitly allows: "Verify these CSS variables exist...; if missing, the planner adds them."

## Visual Contracts (locked)

**Status pill (D-P-04 / UX-05-03)** — leading dot `<span class="size-1.5 rounded-full bg-current">`:
| State | Tailwind | Source |
|-------|----------|--------|
| Open | `border-violet/40 bg-violet-soft text-violet` | provider sync |
| In progress | `border-amber/40 bg-amber/10 text-amber` | provider sync |
| Completed | `border-severity-low/40 bg-severity-low/10 text-severity-low` | provider sync |
| Blocked | `border-severity-critical/40 bg-severity-critical/10 text-severity-critical` | GetVul-internal |

Blocked renders ALONGSIDE provider pill ("Open · Blocked"). Maps `external_status` (`open`/`completed`/...) → pill; note current data uses lowercase `"open"`/`"completed"` (service.py sets these literally).

**SLA pill (D-SLA-04, client-side):** Overdue (`<now`, severity-critical) · Soon (`<now+7d`, amber) · OK (`>=now+7d`, severity-low) · Unknown (NULL, text-text-faint). Mono font, right-aligned (visual-language.md `.sla-pill`).

**Vuln-count `T·C·H` (D-L-02):** total `text-text`, critical `text-severity-critical`, high `text-severity-high`. Zeros explicit. `>99`→`99+`. Total 0 → `—`.

**Severity glyphs (visual-language.md):** Critical `■`, High `▲`, Medium `◆`, Low `○`, Info `□`.

**Provider marks (visual-language.md):** Jira blue 4-square, Asana coral 3-dots, GitHub violet issue-circle; `.provider-mark` 14px rounded-3px gradient square.

## Common Pitfalls

### Pitfall 1: Forking instead of slotting DrillPanel
**What goes wrong:** A `TicketDrillPanel` copy drifts from the vuln panel; focus-trap/Esc bugs fixed in one don't propagate.
**How to avoid:** Add slot props to the existing components; default behavior unchanged. Keep existing vuln drill tests green as the regression gate.
**Warning sign:** A new file importing `vaul` `Drawer` directly.

### Pitfall 2: Treating each Ticket row as a ticket
**What goes wrong:** Host/remediation tickets create N rows per logical ticket; a naive `SELECT * FROM tickets` list shows duplicates and the detail page can't pick an id.
**How to avoid:** Mirror `list_tickets` grouping by `external_ticket_url`; pick ONE canonical identity for comment/watcher/blocked operations and apply blocked/sla to the whole group (like `close_ticket`).
**Warning sign:** Comment/watcher FK points at a single arbitrary row id while the list shows the group.

### Pitfall 3: `min-[900px]` vs Tailwind `md:`
**What goes wrong:** Using `md:` (768px) splits the two-column rail before the drill switches to mobile sheet (899px), causing a broken in-between layout.
**How to avoid:** Use `min-[900px]:` arbitrary variant everywhere (assets/[id] W7 note). DrillPanelMobile gates at `max-width:899px`.

### Pitfall 4: Audit not fail-closed
**What goes wrong:** Calling `commit()` before `audit()`, or swallowing audit errors → mutation lands without audit row (AUDIT-01 regulatory hazard).
**How to avoid:** mutation `db.add`/set → `audit(...)` → `commit()`. Never wrap `audit()` in try/except that suppresses.

### Pitfall 5: SLA tier drift between surfaces
**What goes wrong:** Different `now()+7d` logic on list vs detail vs drill.
**How to avoid:** One `<SlaPill due={...}/>` client component; thresholds defined once.

### Pitfall 6: Optimistic watch toggle missing snapshot
**What goes wrong:** Watch button flips, API 500s, UI stuck "Watching".
**How to avoid:** Clone `use-reassign-asset` onMutate snapshot + onError rollback + toast exactly.

### Pitfall 7: vaul nested confirm Esc cascade (mobile blocked-reason)
**What goes wrong:** Esc on the blocked-reason input inside the mobile drawer closes the whole drawer.
**How to avoid:** Use `Drawer.NestedRoot` (drill-panel-mobile.tsx `renderConfirm` precedent).

## Code Examples

### Adding tickets cache keys
```ts
// Source: keys.ts (add alongside assets.*)
tickets: {
  all: ['tickets'] as const,
  list: (opts: { filters: object; page: number; sort: string; order: string }) =>
    ['tickets', 'list', opts] as const,
  byId: (id: string) => ['tickets', 'detail', id] as const,
  comments: (id: string) => ['tickets', id, 'comments'] as const,
  watchers: (id: string) => ['tickets', id, 'watchers'] as const,
},
```

### Comment / blocked request schemas (Phase 12 BL-01 validator)
```python
# Source: schemas.py pattern + D-C-03 / D-P-02
from pydantic import BaseModel, Field, field_validator

class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)
    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Comment body cannot be blank")
        return s

class BlockedUpdate(BaseModel):
    blocked: bool
    blocked_reason: str | None = Field(None, max_length=500)
    @field_validator("blocked_reason")
    @classmethod
    def _no_ws_only(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None
```

### Route id typing (BL-02)
```python
# Source: router.py BL-02 — uuid.UUID on path params → 422 not 500
@router.post("/{ticket_id}/blocked")
async def set_blocked(ticket_id: uuid.UUID, body: BlockedUpdate,
                      db: AsyncSession = Depends(get_db),
                      user: CurrentUser = Depends(require_analyst)):
    ...  # update group rows, audit("ticket.blocked"/"ticket.unblocked"), commit
```

## State of the Art

| Old (v1 tickets page) | Current (P13) | Impact |
|--------------------|------------------|--------|
| 1186-line `page.tsx`, raw `apiFetch`, freehand hex (`bg-red-500/20`), `useState` data | Suspense+ErrorBoundary+TanStack hooks, sunset tokens, state primitives | Full rewrite — v1 page is the anti-pattern reference |
| `?tab=rules` query param | `/tickets/rules` route | D-S-01 |
| Asana-only, inline config modal | Provider-agnostic, config moved to /connectors (P14) | D-S-02 |
| Status select All/Open/Resolved | 4-axis chip-bar | D-L-04 |

**Deprecated/outdated:** The entire current `frontend/src/app/(authed)/dashboard/tickets/page.tsx` is v1 — do NOT reuse its components (`TicketBulkActions`, `AsanaSetupModal`, `RulesPanel`, `CommentModal`). Salvage only domain logic understanding (the rules CRUD endpoints still exist and are reused by the rewritten `/tickets/rules`).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Vuln-snooze service path lives under `app/vulnerabilities/` (not ticketing); planner must grep to find exact function to hook | SLA Recompute Hook | If hook placed wrong, snoozing a vuln won't recompute linked ticket SLA → stale SLA pill |
| A2 | `connector_configs.connector_type` is a free string (no DB CHECK constraint), so `"JIRA"`/`"GITHUB"` rows work without enum migration (mirrors existing `"ASANA"` usage) | Connector Stubs | If a CHECK constraint exists, an extra migration is needed to allow JIRA/GITHUB |
| A3 | Logical-ticket identity should be `external_ticket_url`/`first_ticket_id` group; blocked/sla apply to the whole group like `close_ticket` | Backend Reshape | If detail/comments key off a single row id, group operations become inconsistent |
| A4 | `--color-blue`/`--color-coral` do not exist; planner adds provider gradient tokens from visual-language.md hex stops | CSS Gradient Tokens | Wrong token names → ProviderMark renders wrong/blank gradient |

## Open Questions

1. **Canonical ticket identity for FKs (comments/watchers/blocked).**
   - What we know: `Ticket` is per-(vuln,provider); `list_tickets` groups by `external_ticket_url`; `close_ticket` updates all rows for a URL.
   - What's unclear: whether to FK comments/watchers to `first_ticket_id` (one arbitrary row) or introduce a parent. CONTEXT D-C-02/D-W-02 say FK to `tickets(id)`.
   - Recommendation: FK to `tickets(id)` using the deterministic `first_ticket_id` (the MIN id in the group, exactly what `list_tickets` returns as `id`), and resolve detail/comment/watch routes by mapping `{id}` → its `external_ticket_url` group. Document in plan.

2. **Vuln-snooze recompute call site (A1).**
   - Recommendation: grep `backend/app/vulnerabilities/` for the snooze mutation; add `await recompute_ticket_sla(...)` for tickets linked to the snoozed vuln before commit. Confirm during planning.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres | migrations 026/027/028, queries | ✓ (project standard) | — | none needed |
| Alembic | migrations | ✓ | — | — |
| Jira Cloud API | jira_client stub create/read | ✗ at dev time (no creds) | — | Stub testable with mocked httpx; real creds via admin-CLI (P14 OAuth UI) |
| GitHub API | github_client stub | ✗ at dev time | — | Same — unit-test against mocked httpx responses |

**Missing with fallback:** Jira/GitHub live credentials — the stubs are unit-tested against mocked `httpx` responses (matching how `asana_client` failures are handled); live verification deferred to Phase 14 connector UI. No blocker for Phase 13 (D-PROV-02 stub depth).

## Validation Architecture

> nyquist_validation not disabled in config.json (`workflow` has only `_auto_chain_active`) → section INCLUDED.

### Test Framework
| Property | Value |
|----------|-------|
| Framework (frontend) | Vitest + React Testing Library (`.test.tsx` co-located; e.g. `assets/page.test.tsx`, `ChipBar.test.tsx`) |
| Framework (backend) | pytest (async) [ASSUMED — confirm `backend/` test layout] |
| Config file | frontend: vitest config (existing); backend: pytest config |
| Quick run (frontend) | `cd frontend && npx vitest run <file>` |
| Full suite | frontend `npx vitest run`; backend `pytest` |

### Phase Requirements → Test Map
| Req | Behavior (observable) | Test Type | Command | File Exists? |
|-----|----------------------|-----------|---------|-------------|
| UX-05-01 | List renders 8 cols; row click sets `?ticket=&open=drill` | unit (RTL) | `npx vitest run tickets/page.test.tsx` | ❌ Wave 0 |
| UX-05-01 | `list_tickets` reshape returns blocked/sla/external_status per group | unit (pytest) | `pytest tests/ticketing/test_list_tickets.py` | ❌ Wave 0 |
| UX-05-02 | `<ProviderMark provider>` renders gradient class per provider; no `<img>`/logo asset | unit (RTL) | `npx vitest run tickets/provider-mark.test.tsx` | ❌ Wave 0 |
| UX-05-02 | No trademark assets in `frontend/public/` | smoke | `ls frontend/public \| grep -iE 'jira\|asana\|github\|atlassian'` (expect empty) | ❌ Wave 0 |
| UX-05-03 | Status pill maps external_status→class; Blocked renders alongside | unit (RTL) | `npx vitest run tickets/status-pill.test.tsx` | ❌ Wave 0 |
| UX-05-04 | Detail two-column; comment POST appends to timeline; blocked toggle optimistic+rollback | unit (RTL) | `npx vitest run tickets/[id]/page.test.tsx` | ❌ Wave 0 |
| UX-05-04 | `POST /tickets/{id}/comments` validates body 1..10000, writes audit | unit (pytest) | `pytest tests/ticketing/test_comments.py` | ❌ Wave 0 |
| UX-05-04 | `POST /tickets/{id}/blocked` audit-then-commit, validator rejects ws-only reason | unit (pytest) | `pytest tests/ticketing/test_blocked.py` | ❌ Wave 0 |
| UX-05-05 | Watcher stack shows 3 + `+N`; watch toggle idempotent | unit (RTL + pytest) | `npx vitest run tickets/watcher-stack.test.tsx`; `pytest tests/ticketing/test_watch.py` | ❌ Wave 0 |
| UX-05-06 | List/Board toggle persists `?view`; Board shows placeholder copy | unit (RTL) | `npx vitest run tickets/page.test.tsx` | ❌ Wave 0 |
| D-D-02 (regress) | Existing vuln DrillPanel tests still green after slot refactor | unit (RTL) | `npx vitest run vulnerabilities/drill-panel*.test.tsx` | ✅ exists |
| D-SLA | migration 027 backfill sets sla_due_at; SlaPill tier client-side | unit (pytest + RTL) | `pytest tests/migrations/...`; `npx vitest run tickets/sla-pill.test.tsx` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `npx vitest run <touched file>` (frontend) / `pytest <touched test> -x` (backend).
- **Per wave merge:** `npx vitest run` (frontend full) + `pytest` (ticketing module).
- **Phase gate:** full suite green + the D-D-02 vuln-drill regression suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `frontend/src/app/(authed)/dashboard/tickets/page.test.tsx` — UX-05-01/05/06
- [ ] `frontend/src/app/(authed)/dashboard/tickets/[id]/page.test.tsx` — UX-05-04
- [ ] `frontend/src/components/tickets/*.test.tsx` (provider-mark, status-pill, sla-pill, watcher-stack, vuln-count)
- [ ] `backend/tests/ticketing/test_comments.py`, `test_blocked.py`, `test_watch.py`, `test_list_tickets.py`
- [ ] Migration smoke test for 027 backfill
- [ ] Confirm backend pytest layout/fixtures (A: `conftest.py` location)

## Security Domain

> `security_enforcement` not set to false in config → INCLUDED.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `Depends(get_current_user)` / `require_analyst` on every route (existing) |
| V3 Session Management | no (handled by auth layer, unchanged) | — |
| V4 Access Control | yes | Tenant scoping (`Ticket.tenant_id == user.tenant_id`) on ALL new queries; `require_analyst` for mutations |
| V5 Input Validation | yes | Pydantic `field_validator` + `min/max_length` (body 1..10000, reason ..500); `uuid.UUID` path params (BL-02); ChipBar `allowList` clamp (T-12-05) |
| V6 Cryptography | yes (connector creds) | `get_decrypted_credentials` (Fernet) — never store provider tokens in plaintext / config JSONB |
| V7 Error Handling/Logging | yes | `audit()` fail-closed; structured logging in connector clients |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant ticket/comment access via crafted id | Info Disclosure / Elevation | `tenant_id` filter on every query; resolve `{id}` within tenant before mutating |
| Mass assignment on blocked/comment | Tampering | Send only minimal fields; Pydantic models reject extras (T-12-08) |
| Stored XSS via comment body / assignee / watcher name | Tampering | Render as React text node (escaped); plain-text comment render (D-C-03); Avatar text-node only (T-12-04) |
| Audit-trail loss on blocked/comment | Repudiation | `audit()` before `commit()`, fail-closed (AUDIT-01) |
| Reflected XSS via chip URL params | Tampering | ChipBar `allowList` clamp on read+write (T-12-05) |
| Provider token leakage | Info Disclosure | Encrypted at rest (`credentials_secret_arn`); never log tokens; never return in API responses |
| SSRF via provider base_url (Jira domain) | — | Validate/allow-list Jira domain format if user-supplied; admin-CLI config in P13 limits exposure |

## Sources

### Primary (HIGH confidence — direct codebase read)
- `backend/app/ticketing/{asana_client,models,service,router,schemas}.py` — interfaces, enum, call sites
- `backend/app/audit.py` — audit fail-closed contract + AuditLog schema
- `backend/alembic/versions/{020,024,025}*.py` — migration conventions
- `frontend/src/components/vulnerabilities/{drill-panel,drill-panel-mobile,drill-content}.tsx` — drill chrome + slot precedent
- `frontend/src/components/ui/{ChipBar,Avatar}.tsx` — primitives
- `frontend/src/app/(authed)/dashboard/assets/{page,[id]/page}.tsx` — list+detail templates
- `frontend/src/lib/queries/{use-assets,use-asset-detail,use-reassign-asset,keys}.ts` — hook/optimistic patterns
- `frontend/tailwind.config.*` — provider-jira/asana/github tokens
- `.claude/skills/sketch-findings-getvul/references/{foundation,visual-language}.md` — design tokens + visual contracts
- `.planning/phases/13-tickets-list-detail/13-CONTEXT.md`, `.planning/ROADMAP.md` §13, `.planning/REQUIREMENTS-v2.md` §UX-05

### Secondary (MEDIUM-HIGH — official docs)
- [Jira Cloud REST API v3 — Issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)
- [Jira Cloud REST API v3 intro](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [GitHub REST API — Issues](https://docs.github.com/en/rest/issues)
- [GitHub REST API — Getting started/auth](https://docs.github.com/rest/guides/getting-started-with-the-rest-api)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all deps verified via direct import; zero new packages.
- Architecture (templates, DrillPanel slot, migrations): HIGH — patterns read verbatim from existing code.
- Backend reshape / identity model: MEDIUM — the per-vuln-row vs per-ticket mismatch is real and needs an explicit planning decision (O1/A3).
- External API endpoints (Jira/GitHub): HIGH (CITED official docs) for endpoints; MEDIUM for exact auth wiring (admin-CLI config shape is Claude's Discretion in P13).
- Pitfalls: HIGH — derived from Phase 11/12 documented WR-* fixes and verified code comments.

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (codebase patterns stable; recheck Jira/GitHub API only if stubs go to live integration in P14)

Sources:
- [Jira Cloud REST API v3 — Issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)
- [GitHub REST API — Issues](https://docs.github.com/en/rest/issues)
- [GitHub REST API — Getting started](https://docs.github.com/rest/guides/getting-started-with-the-rest-api)
