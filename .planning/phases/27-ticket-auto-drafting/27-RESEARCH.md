# Phase 27: Ticket Auto-Drafting - Research

**Researched:** 2026-08-01
**Domain:** Client-side composition over existing cached AI outputs + one mirrored backend request-schema override (no new AI call, no new grounding, no DB model change)
**Confidence:** HIGH

## Summary

Phase 27 is unusually low-risk for a v3.0 AI-milestone phase: it adds no new AI call, no new grounding/schema/prompt, and no `Ticket` DB model change. Direct code verification confirms every seam CONTEXT.md/27-UI-SPEC.md assume is real and ready to extend. `backend/app/ticketing/service.py::create_tickets()` builds today's ticket title via one uncontested line (`task_name = f"[{sev}] {cve} on {hostname or 'unknown host'}"`, service.py:202) with **no analyst-supplied override path at all** — this resolves CONTEXT.md's open discretion question ("does a new `title` field belong on the request schema, or can an existing summary path be reused?") definitively: there is no existing path, so a new field is required, mirroring `description`'s already-shipped Phase 25 pattern class-for-class. `dispatch.py`'s `TicketingClient` Protocol (built in Phase 23, D-06/D-07) already normalizes `create(title, body, **kwargs)` across Asana (`name`), Jira (`summary`), and GitHub (`title`) — a title override needs **zero** per-provider code, only one new Pydantic field plus one new fallback expression in `create_tickets()`.

On the frontend, the three GET cache-check hooks the composer needs (`useExplainCache('vuln'|'remediation-guidance'|'prioritization', v.id)`) all key off the exact same `v.id` already resolved in `drill-content.tsx`, and all three response shapes share `ExplainResponseBase.summary` (`backend/app/ai/schemas.py:58`) as the plain-text field to compose from — confirmed directly in the Pydantic schema and in `AiExplanationCitations`'s own rendering (citation coloring is a DOM-only overlay; the underlying `summary` string is always plain text, never HTML). The on-demand gap-fill mechanism this phase needs already exists verbatim as `useExplainStream(resourceType, resourceId).start()` — no new endpoint, no new hook.

Research surfaced five concrete implementation risks that **neither CONTEXT.md nor 27-UI-SPEC.md resolves**, all found via direct code reads (detailed in Common Pitfalls): (1) Jira's externally-enforced 255-character summary limit, combined with `create_tickets()`'s silent per-vulnerability failure path, means an oversized client-composed title (which now includes a potentially multi-host `hostsLine`) can make "Create ticket" appear to succeed while creating nothing; (2) the `description` state Phase 27 auto-composes into is the **same** state the pre-existing (Phase 25) "Copy into ticket description" button in the main Remediation-guidance section overwrites — the interaction between an analyst using that button *before* opening the confirm dialog and Phase 27's new auto-compose is not addressed in either planning document, and depending on interpretation can silently violate either the Title-always-populated guarantee or the Asset-context-always-present guarantee; (3) `DrillContent` has no remount key on vuln id, and the vulnerabilities list's row-click handler does not force-close the panel before opening a different vuln — so a title/description composed for vuln A can silently carry over into a ticket created for vuln B; (4) `AnalyzingIndicator` (the pulsing-dot component the gap-fill row must reuse verbatim per UI-SPEC) is currently a private, unexported function; (5) owner/department data — cited in CONTEXT.md's "Existing Code Insights" as an asset-context source — does not actually exist on the `VulnerabilityDetail` type the drill panel loads, which is exactly why 27-UI-SPEC.md correctly omits it from the composed body.

**Primary recommendation:** mirror Phase 25's `description` override pattern exactly for the new `title` field (one `Field` + one `field_validator`, no new `model_config` since `extra="forbid"` already applies at the class level), thread it through `create_tickets()` with one fallback expression, and extract the composition logic (title format + multi-section description builder) into **one shared, unit-testable pure function** that both `drill-content.tsx` and `drill-panel-mobile.tsx` call identically — closing the "Phase 25 divergence lesson" at its source (a single tested function) rather than relying on careful manual duplication of non-trivial conditional logic across two files.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deterministic title composition | Browser/Client | — | Pure string interpolation over already-loaded `cveLabel`/`sevLabel`/`hostsLine`; zero network calls |
| Multi-section description composition | Browser/Client | — | Reads 3 already-fetched TanStack Query caches (`useExplainCache`) + local vuln fields; no new fetch |
| On-demand gap-fill generation | API/Backend | Browser/Client (trigger only) | The model call/validation/caching is 100% Phase 24/25's existing `_run_explain_stream` engine; the browser only calls the existing `useExplainStream(...).start()` and appends the result to local state |
| `title` request-override validation | API/Backend | — | New Pydantic `Field` + validator on `TicketCreateRequest`, mirroring `description` (schemas.py:70-80) |
| `create_tickets()` title fallback | API/Backend | — | One new expression choosing `request.title` over the existing `task_name` computation (service.py:200-202) |
| Provider-specific field mapping (name/summary/title) | API/Backend | — | Already fully normalized by `dispatch.py`'s `TicketingClient` Protocol (Phase 23, D-06/D-07); no change needed |
| Ticket persistence | Database/Storage | — | Explicitly UNCHANGED (D-05) — no new column, no migration |
| RBAC gating of the gap-fill trigger | API/Backend | Browser/Client | `require_analyst`/`require_viewer` (backend, already enforced on the reused routes) + `useAuth().role` conditional rendering (client, already established in `AiExplanationSection`) |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The draft is composed CLIENT-SIDE from already-cached AI outputs — no new AI call, no new backend risk surface. Sources: Phase 24 explain summary → description body; Phase 25 remediation guidance → remediation section; drill panel's own asset facts → asset-context section; Phase 26 prioritization narrative optionally included. The TITLE is derived DETERMINISTICALLY — not a new AI call. Reversibility: reversible.
- **D-06:** Asset-context and any AI-composed text follow the owner-as-department discipline (D-15) — the AI-sourced portions never carry owner PII (email/name); the analyst edits freely.
- **D-02:** Auto-populate on opening the create flow from whatever cached AI outputs exist (free — no spend; SC1 literal). A missing piece leaves that section blank with a subordinate "Draft with AI" action (Analyst+, D-17) that generates it on demand via the existing per-resource endpoints. No spend on findings the analyst just glances at (D-09). Reversibility: reversible.
- **D-03:** An editable TITLE field + one composed, editable description body. Backend gains a `title: str | None` override on `TicketCreateRequest` (mirroring Phase 25's `description` exactly: `max_length`, `extra="forbid"` mass-assignment defense, whitespace→None, and `create_tickets()` honors it, falling back to the existing server auto-build when absent). The existing description textarea is pre-filled with a composed body (description + remediation + asset-context as clearly-labeled sections; prioritization optional). Reversibility: costly — the `title` request field + `create_tickets()` branch is a new (small) request contract, mirroring D-08/25-06.
- **D-04:** The create flow ALWAYS works and is NEVER blocked by missing AI: pre-fill whichever sections have cached outputs, leave the rest blank/manual (deterministic title fallback); no key configured → the existing fully-manual flow, unchanged (D-23). Nothing is ever auto-submitted — the existing human Create click is the ONLY submit path (SC3); AI pre-fill is a convenience layer, never a dependency or a gate. Do NOT gate the Create button on a complete draft. Reversibility: reversible.
- **D-05:** The ONLY backend change is the `title` request-override + its `create_tickets()` fallback branch (D-03). No new AI endpoint, no new grounding/schema/prompt, no `Ticket` DB model change, no new migration for a draft. The mobile ticket-create path (`drill-panel-mobile.tsx renderConfirm`) must be threaded the same as desktop (the Phase 25 divergence lesson).

### Claude's Discretion

- Exact deterministic title format (D-01) and the composed-body section labels/order (D-03).
- Whether the Phase 26 prioritization narrative is included in the body by default (D-01) — lean: include when cached.
- Placement of the "Draft with AI" gap-fill affordance (D-02) — a UI-SPEC decision.
- Whether title pre-fill needs a `title` field at all vs. reusing the existing summary field path — plan-time confirm against `create_tickets()`. **Resolved by this research: YES, a new field is required — see Summary.**

### Deferred Ideas (OUT OF SCOPE)

- A dedicated 'draft this ticket' AI call / AI-generated title — explicitly OUT (chose compose-from-cache + deterministic title; a new call would add backend risk surface the roadmap forbids).
- Auto-generating missing explain/remediation on dialog open — OUT (spends budget on every open; use the on-demand "Draft with AI" gap-fill instead, D-02/D-09).
- Eval/cost/observability, red-team CI, cost circuit breaker → Phase 28.
- Ticket DB model changes / new draft-persistence table — OUT (drafts are ephemeral client state until Create).
- Non-English drafts → out of milestone scope (D-28).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AID-01 | When creating a Jira/Asana ticket, an analyst gets an AI-drafted title/description/remediation/asset-context that they edit before shipping (never auto-submitted) | Title: `create_tickets()` currently has no override path (service.py:200-202) — confirmed a new `title` field is required, mirroring `description`'s proven Phase 25 pattern (schemas.py:70-80, service.py:222-230). Description/remediation/asset-context: all three cache-check hooks (`useExplainCache`) key off the same `v.id` already resolved in `drill-content.tsx`; `summary` is the shared plain-text field across all three response schemas (`ExplainResponseBase`, `app/ai/schemas.py:58`). Gap-fill reuses `useExplainStream` verbatim, no new endpoint. Provider threading verified zero-touch via `dispatch.py`'s existing Protocol. Never-auto-submit verified: `ConfirmModal`'s only `useEffect` is a focus call, not a submit call (ConfirmModal.tsx:56-60); the confirm button's `onClick={onConfirm}` (line 102) is the sole trigger path. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Frontend stack:** Next.js 15 App Router + React 19 + TypeScript 5.5 + Tailwind 3.4 — unchanged by this phase; no new dependency needed (see Standard Stack).
- **Backend stack:** FastAPI + Postgres + Redis — unchanged by this phase; `title` is a request-schema field only, no new table/column/Redis key.
- **`sketch-findings-getvul` skill (mandatory before UI work):** already consulted — 27-UI-SPEC.md's Copywriting/Color/Typography/Spacing contract is derived from this skill's `references/foundation.md`, `state-patterns.md`, `visual-language.md`, and `copy-voice.md`. This research does not re-derive design tokens; it defers entirely to 27-UI-SPEC.md for anything visual.
- **Locked fonts:** Inter + JetBrains Mono — the new Title `Input`'s text is Body (Inter), never JetBrains Mono, per 27-UI-SPEC.md's explicit call-out (the title is composed prose, not a raw identifier, even though it's seeded from `cveLabel`/`sevLabel`).
- **No freehand hex colors:** the gap-fill row's amber/danger/violet captions must reuse the exact `--color-*` tokens already established by `DegradedCard` (Phase 24/25/26) — 27-UI-SPEC.md already enforces this; no new token needed.
- **Mandatory empty/loading/error states:** already covered by 27-UI-SPEC.md's "UI Considerations" state-coverage table (title/description/gap-fill-row empty/populated/loading/error/zero-one-many all enumerated).
- **No generic SaaS copy:** all new microcopy is pre-written and locked in 27-UI-SPEC.md's Copywriting Contract; this research does not introduce additional copy.

## Standard Stack

### Core

No new dependency is required by this phase — every library it touches is already installed and in use.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tanstack/react-query` | `^5.100.10` [VERIFIED: package.json] | `useExplainCache`'s 3 GET reads (`vuln`/`remediation-guidance`/`prioritization`) | Already the sole data-fetching layer in this codebase; the composer is a pure read of already-populated query caches, not a new query pattern |
| `pydantic` | already in use [VERIFIED: schemas.py imports] | The new `title: str | None` field + validator on `TicketCreateRequest` | Mirrors the exact `description` field shape shipped in Phase 25 (schemas.py:70-80) |
| shadcn `Input` (`components/ui/input.tsx`) | already installed since Phase 9 [VERIFIED: 27-UI-SPEC.md Registry Safety table] | The new Title field | No new `npx shadcn add` — reuses the existing primitive verbatim, restyled to sunset tokens already |
| shadcn `Textarea` (`components/ui/textarea.tsx`) | already installed since Phase 25 [VERIFIED: 25-07-SUMMARY.md] | The composed Description body (unchanged surface/focus styling) | Already restyled to sunset tokens; this phase only changes its pre-fill content, not its chrome |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `lucide-react` | already in use | `AnalyzingIndicator`'s reused pulsing-dot / `AlertTriangle` for amber/danger captions | Only if the gap-fill row's captions need an icon — 27-UI-SPEC.md specifies plain one-line text captions with no icon for the gap-fill states (unlike the full `DegradedCard`), so likely unneeded here |

### Alternatives Considered

Not applicable — this phase introduces no new library choice. The one real "alternatives" question CONTEXT.md left open (does `title` need a new field, or can an existing summary path be reused?) is a code-structure question, not a library question, and is resolved in the Summary/Pattern 1 below: a new field is required.

**Installation:** None. `npm install` / `pip install` are not needed for this phase.

**Version verification:** N/A — no new package.

## Architecture Patterns

### System Architecture Diagram

```
BROWSER (drill-content.tsx desktop / drill-panel-mobile.tsx renderConfirm)
│
│ [Analyst clicks "Create ticket"]
▼
confirmOpen: false → true
│
▼
Composed-once guard: has THIS mount already composed for THIS resourceId?
│                                          │
│ no (first genuine open for this vuln)    │ yes (already composed, or
▼                                          │ analyst has edited) — SKIP
COMPOSE (client-side, zero network calls):  │
  • useExplainCache('vuln', v.id)           │
  • useExplainCache('remediation-guidance', v.id)
  • useExplainCache('prioritization', v.id)
  • local: cveLabel, sevLabel, hostsLine,
    affected_product, cisa_kev, exploit_available
│
▼
setTitle(deterministic "[sev] cve on hosts" format)
setDescription(composed multi-section plain-text body)
│
▼
ConfirmModal / Drawer.NestedRoot renders:
  Title Input ─ gap-fill row (0-2 buttons) ─ Description Textarea
  — all three are ordinary local React state, freely editable
│
├─ [gap-fill button click] ──▶ useExplainStream(resourceType, resourceId).start()
│                                        │
│                                        ▼
│                              POST /api/v1/ai/explain-{type}/{id}
│                              (existing buffer-validate-replay SSE engine,
│                               require_analyst-gated, Phase 24/25 code, UNCHANGED)
│                                        │
│                                        ▼
│                              done/error event → append labeled section to
│                              Description textarea's CURRENT value (local state)
│
▼
[Analyst clicks "Create ticket" — the ONLY submit path; ConfirmModal's sole
 useEffect is a focus() call, never a submit call]
│
▼
createTicket.mutateAsync({ vulnerability_ids: [v.id], provider, title, description })
│
│ POST /api/v1/tickets
▼
BACKEND (FastAPI)
│
router.py::create_new_tickets(body: TicketCreateRequest)  — UNCHANGED, already
  forwards the whole request body through (proven zero-diff in 25-06-SUMMARY.md)
│
▼
service.py::create_tickets()
  task_name = request.title.strip() if request.title else f"[{sev}] {cve} on {hostname}"   ← NEW
  notes     = request.description.strip() if request.description else _build_task_description(...)  ← EXISTING (Phase 25)
│
▼
dispatch.py::TicketingClient.create(task_name, notes, **kwargs)  — UNCHANGED (Phase 23)
  ├─ AsanaAdapter  → create_task(name=task_name, notes=notes, ...)
  ├─ JiraAdapter   → create_ticket(summary=task_name, description=notes, ...)
  └─ GitHubAdapter → create_ticket(title=task_name, body=notes)
│
▼
Ticket row persisted — UNCHANGED model, no new column (D-05)
```

A reader can trace the primary use case (analyst opens Create → sees an AI-composed draft → edits → clicks Create → ticket appears in Jira/Asana/GitHub with that exact title+body) end to end by following the arrows above; every box on the path already exists in the codebase except the two marked `← NEW`.

### Recommended Project Structure

No new directories. This phase is a pure extension of existing files, plus (recommended) one new small pure-function module to eliminate desktop/mobile duplication risk:

| File | Change |
|------|--------|
| `backend/app/ticketing/schemas.py` | Add `title: str | None` Field + `field_validator` on `TicketCreateRequest` (mirrors `description`, lines 70-80) |
| `backend/app/ticketing/service.py` | Add one fallback expression for `task_name` in `create_tickets()` (mirrors the existing `notes` fallback, lines 222-230) |
| `backend/tests/test_ticketing_dispatch.py` | Extend with `title`-mirroring tests (5 schema tests + 2 dispatch tests, mirroring lines 122-147 and 248-287 exactly) |
| `frontend/src/lib/mutations/use-create-ticket.ts` | Add `title?: string` to `CreateTicketRequest` (mirrors `description`, line 18) |
| `frontend/src/lib/tickets/compose-ticket-draft.ts` **(NEW, recommended)** | One pure function: `composeTicketDraft(vuln fields, 3 cache reads) → { title, description }` — see Pattern 1 |
| `frontend/src/components/ai/ai-explanation-section.tsx` | Export `AnalyzingIndicator` (currently private, line 104) so the gap-fill row can reuse it verbatim |
| `frontend/src/components/vulnerabilities/drill-content.tsx` | Add `title`/`setTitle` state, composed-once guard, gap-fill row, Title `Input`; thread `title` into `fireTicket()`'s mutation body |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` | Mirror the identical Title `Input` + gap-fill row inside its own `Drawer.NestedRoot` markup (never imports `ConfirmModal` — a genuinely separate code path, per Pitfall 5 in 25-RESEARCH.md, still true here) |

### Pattern 1: Extract composition logic into one shared pure function — do not duplicate it by hand across desktop/mobile

**What:** Phase 25's precedent for the description Textarea was to duplicate a small, simple JSX snippet (a label + a controlled `<Textarea>`) verbatim across `drill-content.tsx` and `drill-panel-mobile.tsx`. That worked because the JSX was trivial. Phase 27's composition logic is materially more complex: a deterministic title format plus a 4-section conditional description builder (each section present/absent based on 3 independent cache states). Hand-duplicating that logic risks exactly the kind of silent divergence CONTEXT.md calls "the Phase 25 divergence lesson" — except this time in business logic, not just markup.

**When to use:** Any time two structurally-separate render paths (desktop `ConfirmModal` vs. mobile `Drawer.NestedRoot`) need to derive the same non-trivial value from the same inputs.

**Example:**
```typescript
// frontend/src/lib/tickets/compose-ticket-draft.ts (NEW — pure, unit-testable,
// zero React/network dependencies, callable identically from both dialogs)

type CacheSection = { grounded: boolean; summary: string } | null; // null = no usable cache hit

export function composeTicketTitle(params: {
  sevLabel: string; cveLabel: string; hostsLine: string;
}): string {
  // Mirrors service.py:202's server convention exactly, so an unedited
  // draft matches what the server would otherwise auto-build (27-UI-SPEC.md §2).
  return `[${params.sevLabel}] ${params.cveLabel} on ${params.hostsLine}`;
}

export function composeTicketDescription(params: {
  explain: CacheSection;              // useExplainCache('vuln', id)
  remediationGuidance: CacheSection;   // useExplainCache('remediation-guidance', id)
  prioritization: CacheSection;        // useExplainCache('prioritization', id)
  hostsLine: string; affectedProduct: string | null;
  sevLabel: string; cisaKev: boolean; exploitAvailable: boolean;
}): string {
  const sections: string[] = [];
  if (params.explain?.grounded) sections.push(`Description:\n${params.explain.summary}`);
  if (params.remediationGuidance?.grounded) sections.push(`Remediation:\n${params.remediationGuidance.summary}`);
  // Asset context is ALWAYS present (27-UI-SPEC.md §3) — no cache dependency.
  const assetLines = [
    `Host: ${params.hostsLine}`,
    `Product: ${params.affectedProduct ?? '—'}`,
    `Severity: ${params.sevLabel}`,
  ];
  if (params.cisaKev) assetLines.push('CISA KEV: yes');
  if (params.exploitAvailable) assetLines.push('Exploit available: yes');
  sections.push(`Asset context:\n${assetLines.join('\n')}`);
  if (params.prioritization?.grounded) sections.push(`Prioritization:\n${params.prioritization.summary}`);
  return sections.join('\n\n');
}
```
Both `drill-content.tsx` and `drill-panel-mobile.tsx`'s `renderConfirm` call these two functions with the same inputs; neither file re-implements the conditional section logic itself. This is directly testable with plain Vitest (no DOM, no React Testing Library needed) for every cache-state permutation the 27-UI-SPEC.md "partial" state row enumerates.

### Pattern 2: The `title` override mirrors `description` exactly — same field, same validator, same fallback shape

**What:** `TicketCreateRequest` already has `model_config = {"extra": "forbid"}` at the class level (schemas.py:63) — a new field does not need its own mass-assignment guard, it inherits the class-level one automatically. The only genuinely new code is the `Field` declaration, one `field_validator`, and one fallback expression.

**When to use:** Exactly this situation — a WYSIWYG-override request field with an existing sibling precedent in the same schema.

**Example (the exact current code being extended):**
```python
# backend/app/ticketing/schemas.py:53-80 (current, VERIFIED via Read)
class TicketCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    vulnerability_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)
    provider: str = Field(..., pattern="^(ASANA|JIRA|GITHUB)$")
    project_key: str = Field("", description="Asana project GID or Jira project key")
    assignee: str | None = Field(None, description="Email or user ID to assign the ticket to")
    due_days: int | None = Field(None, ge=1, le=365, description="Days from now for due date")
    description: str | None = Field(None, max_length=10000, description="Analyst-supplied ticket description (WYSIWYG override)")

    @field_validator("description")
    @classmethod
    def _no_ws_only(cls, v: str | None) -> str | None:
        if v is None: return None
        s = v.strip()
        return s or None

# RECOMMENDED ADDITION (same class, mirrors the above validator exactly):
    title: str | None = Field(None, max_length=255, description="Analyst-supplied ticket title (WYSIWYG override)")

    @field_validator("title")
    @classmethod
    def _title_no_ws_only(cls, v: str | None) -> str | None:
        if v is None: return None
        s = v.strip()
        return s or None
```
```python
# backend/app/ticketing/service.py:200-234 (current, VERIFIED via Read)
sev = vuln.severity or "MEDIUM"
cve = vuln.cve_id or vuln.vulnerability_name or "Unknown vulnerability"
task_name = f"[{sev}] {cve} on {hostname or 'unknown host'}"   # ← no override path today
...
notes = (
    request.description.strip()
    if request.description and request.description.strip()
    else _build_task_description(vuln, hostname)
)
url = await client.create(task_name, notes, **_provider_create_kwargs(request.provider, assignee, due_on))

# RECOMMENDED CHANGE — one new expression, same shape as the existing `notes` fallback:
task_name = (
    request.title.strip()
    if request.title and request.title.strip()
    else f"[{sev}] {cve} on {hostname or 'unknown host'}"
)
```

### Pattern 3: Provider threading requires zero per-provider changes — verified via `dispatch.py`

**What:** `dispatch.py`'s `TicketingClient` Protocol (`async def create(self, title: str, body: str, **kwargs) -> str | None`) is already the single normalization point across all three providers (built in Phase 23, D-06/D-07, specifically to eliminate scattered per-provider branching).

**When to use:** Any time a new value needs to reach all three ticketing providers — check `dispatch.py` first before writing any `if provider == "JIRA"` branch.

**Example (current code, verified — nothing here changes):**
```python
# backend/app/ticketing/dispatch.py:52-60, 79-86, 107-109
class AsanaAdapter:
    async def create(self, title: str, body: str, **kwargs) -> str | None:
        task = await self._client.create_task(..., name=title, notes=body, **kwargs)
        return task.url if task else None

class JiraAdapter:
    async def create(self, title: str, body: str, **kwargs) -> str | None:
        issue = await self._client.create_ticket(..., summary=title, description=body, **kwargs)
        return issue.url if issue else None

class GitHubAdapter:
    async def create(self, title: str, body: str, **kwargs) -> str | None:
        issue = await self._client.create_ticket(title=title, body=body)
        return issue.url if issue else None
```
`service.py`'s single call site (`await client.create(task_name, notes, **_provider_create_kwargs(...))`, line 234) is the ONLY place `task_name` needs to change — it already flows to `name`/`summary`/`title` correctly for all three providers with no further code.

### Pattern 4: Composed-once guard should be a `ref` keyed to `resourceId`, not a blank-string check

**What:** 27-UI-SPEC.md specifies composition should run "once… only if the Title/Description fields are still in their pristine, never-touched state," explicitly rejecting "a one-shot mount flag." A literal `title === '' && description === ''` check is tempting but has two failure modes discovered in this research (see Pitfalls 2 and 3): it cannot distinguish "never composed" from "analyst deliberately cleared the field," and it does not reset when the underlying vuln (`resourceId`) changes without a full remount.

**When to use:** This exact composed-once-per-entity guard requirement.

**Example:**
```typescript
// Inside DrillContent (and mirrored inside drill-panel-mobile.tsx's renderConfirm
// closure over the same DrillContent instance — no separate state needed there,
// since drill-panel-mobile.tsx renders DrillContent directly and reads its state
// via the renderConfirm args, exactly as description already does today).
const composedForId = useRef<string | null>(null);

useEffect(() => {
  if (!confirmOpen) return;
  const id = v.id ?? idOrCve;
  if (composedForId.current === id) return; // already composed (or reset) for this vuln
  composedForId.current = id;
  setTitle(composeTicketTitle({ sevLabel, cveLabel, hostsLine }));
  setDescription(composeTicketDescription({ /* ...cache reads + local fields */ }));
}, [confirmOpen, v.id, idOrCve]);
```
This single `ref` (not a blank-string check) resolves three distinct problems found in this research with one mechanism: it does not re-fire on a second open of the same vuln (preserving analyst edits, including a deliberately-cleared title), and it DOES re-fire when `resourceId` changes to a different vuln (closing the cross-vuln staleness gap in Pitfall 3), and it composes exactly once regardless of whether `description` already held content from the pre-existing main-panel "Copy into ticket description" button (Pitfall 2) — because the guard is about "have I composed for this id," not "is this field empty."

### Anti-Patterns to Avoid

- **A per-provider `if provider == "JIRA": ...` branch for title mapping** — `dispatch.py` already solved this in Phase 23; adding a new branch would reintroduce the exact class of bug that phase fixed (D-07's "provider:'JIRA' silently created an Asana task" bug).
- **A blank-string pristine check (`title === ''`) as the sole composed-once guard** — conflates "never composed" with "analyst intentionally cleared," and does not reset across a vuln switch. Use Pattern 4 instead.
- **Duplicating the multi-section description-building conditional logic separately in `drill-content.tsx` and `drill-panel-mobile.tsx`** — use Pattern 1's shared pure function instead.
- **Mirroring `description`'s `max_length=10000` verbatim for `title`** — a ticket title/summary is a fundamentally different kind of field than a body; see Common Pitfall 1 for why this specific number matters.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Generating a ticket title/description with AI | A new "draft this ticket" model call / prompt / schema | Compose client-side from the 3 existing cached GET endpoints (`useExplainCache('vuln'|'remediation-guidance'|'prioritization', v.id)`) | D-01/D-05 forbid a new AI call; the 3 outputs already exist, are already schema-validated + cite-or-refuse-guarded, and cost nothing to re-read |
| Mapping a title to Asana/Jira/GitHub's differently-named summary field | Per-provider branching in `service.py` or the frontend | `dispatch.py`'s existing `TicketingClient.create(title, body, **kwargs)` Protocol + 3 adapters | Built in Phase 23 (D-06/D-07) precisely to eliminate this bug class; a title override needs one new fallback expression, zero adapter changes (Pattern 3) |
| An "analyzing" spinner for the new gap-fill buttons | A new loading-spinner component | Export and reuse `AnalyzingIndicator` from `ai-explanation-section.tsx` (currently private — a one-line export change) | D-12 already locked this as the app's one sanctioned pulsing-dot affordance; a second one would be a design-system violation |
| Role/key gating for the gap-fill trigger | A new "can this user spend AI budget" check | Reuse `useAiStatus()` + `useAuth().role` exactly as `AiExplanationSection` already does (`isAnalystOrAbove`) | D-17 RBAC is already fully implemented and tested; re-deriving it risks a subtly different, untested gating rule |
| Mass-assignment defense on the new `title` field | A hand-rolled field-allowlist check | The class-level `model_config = {"extra": "forbid"}` already on `TicketCreateRequest`, plus a `Field(max_length=...)` and a whitespace-coercion validator mirroring `description`'s | The class-level guard already covers any new field added to the model; no per-field allowlist code needed |
| A composed-once-per-vuln guard | An ad hoc boolean flag or blank-string check | A `ref` keyed to `resourceId` (Pattern 4) | Solves 3 distinct discovered edge cases (Pitfalls 2, 3, 4) with one mechanism instead of three separate patches |

**Key insight:** every piece of this phase's plumbing — provider dispatch, RBAC gating, cache reads, the streaming trigger, the mass-assignment defense — was already built and tested in Phases 23-25. The only genuinely new code is (a) one Pydantic field + one fallback expression on the backend, and (b) a client-side composition function on the frontend. Anything larger than that is over-building relative to what D-05 authorizes.

## Common Pitfalls

### Pitfall 1: Jira's hard 255-character summary limit + `create_tickets()`'s silent failure path

**What goes wrong:** `JiraClient.create_ticket()` (jira_client.py:104) sends `summary` straight through to `POST /rest/api/3/issue` with no client-side length check. Jira's own API enforces a hard 255-character limit on the `summary` field [CITED: multiple Atlassian Community + Atlassian Jira issue-tracker threads confirm this is a static, non-configurable server-side limit — see Sources]. If it's exceeded, Jira returns a non-201 response; `JiraClient.create_ticket()` returns `None`; back in `create_tickets()` (service.py:236-238), `if url is None: logger.error(...); continue` — the vulnerability is silently skipped. Because Phase 27's dialog always creates exactly one vulnerability per request (`vulnerability_ids: [v.id]`), this means `created_tickets` ends up empty; `router.py`'s `create_new_tickets()` still returns **HTTP 200** with `{"created": 0, "tickets": []}` (no exception is ever raised). In `fireTicket()` (drill-content.tsx:165-196), `result.tickets?.[0]` is `undefined`, so the `if (first) { toast(...) }` branch never fires — **no success toast, no error toast** — and `setConfirmOpen(false)` still runs unconditionally, closing the dialog as if the ticket had been created.

**Why it happens:** Today's server-built `task_name` (`f"[{sev}] {cve} on {hostname or 'unknown host'}"`) is short and bounded by a single hostname, so this failure mode has likely never been hit in practice. Phase 27's new deterministic client-side title uses `hostsLine`, which is `v.affected_hosts.map(h => h.host ?? h.ip ?? '—').join(', ')` — a comma-joined list that can be arbitrarily long for a vulnerability correlated across many hosts, and the title is also freely analyst-editable, so a manually-lengthened title has the same exposure.

**How to avoid:** Set the new `title` field's `max_length` conservatively — **255** is recommended, matching Jira's own hard ceiling (the strictest of the three providers; GitHub's limit is ~65,536 codepoints [VERIFIED: GitHub Community Discussion], and no hard Asana task-name limit was found in this research — see Assumptions Log). Capping at the Pydantic layer means an over-length title is rejected with a catchable 422 at the mutation boundary (the frontend `api()` helper throws on non-2xx, which `fireTicket()`'s existing `catch` block already surfaces as a toast) — converting a **silent, unrecoverable Jira-side failure** into a visible, retryable client-side validation error.

**Warning signs:** A "Create ticket" click that closes the dialog with no toast at all (neither success nor error) is the signature of this failure — it will not appear in frontend logs, only in the backend's `ticket_creation_failed` log line.

### Pitfall 2: The pre-existing "Copy into ticket description" button and Phase 27's auto-compose write to the SAME `description` state

**What goes wrong:** `drill-content.tsx`'s "Remediation guidance" section (mounted in the main scrollable panel body, *outside* the confirm dialog) already has `onCopyToDescription={setDescription}` wired to its `AiExplanationSection` (line 337) — clicking its "Copy into ticket description" button calls `setDescription(cached.summary)` directly, **replacing** whatever `description` currently holds (`ai-explanation-section.tsx:238,291`). This is the same `description` state Phase 27's confirm-dialog auto-compose will populate. Consider the realistic sequence: analyst opens the drill panel, clicks "Copy into ticket description" in the main panel (a legitimate, already-shipped Phase 25 action) *before* ever opening the Create-ticket dialog, then clicks "Create ticket." At that point `description` already holds non-empty content. Depending on how the composed-once guard is implemented, this creates two possible contradictions with 27-UI-SPEC.md's own stated invariants: if the guard treats "description already non-empty" as "already composed" and skips the whole compose step (including Title), the Title field's own "Always auto-populated… regardless" guarantee (27-UI-SPEC.md §2) breaks. If instead the guard runs per-field independently and skips only Description, the "Asset context: is ALWAYS present" guarantee (27-UI-SPEC.md §3) breaks, since Asset context is generated by the same compose call.

**Why it happens:** Neither CONTEXT.md nor 27-UI-SPEC.md discusses this interaction — 27-UI-SPEC.md's scope note focuses entirely on the confirm dialog and does not revisit the main panel's existing copy-in button's behavior once the dialog gains its own auto-compose.

**How to avoid:** Use Pattern 4's `ref`-keyed-to-`resourceId` guard, which tracks "has THIS mount's confirm dialog already composed for this vuln" independently of the current string value of `description`. On the first genuine open of the confirm dialog for a given vuln, compose unconditionally (overwriting whatever `description` held, including a pre-existing main-panel copy) — this keeps both invariants ("Title always populated," "Asset context always present") true on first open, and still never re-composes over anything the analyst types afterward (inside or outside the dialog) on a second open.

**Warning signs:** A bug report of "the ticket description only has my remediation guidance copy, not the full draft" (or the reverse — "my copied text got wiped") is the fingerprint of this interaction; it will only reproduce when the main-panel copy button is used before the dialog is first opened for that vuln.

### Pitfall 3: `DrillContent` has no remount key — a composed draft can leak from vuln A into a ticket created for vuln B

**What goes wrong:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`'s `handleRowOpen` (lines 116-122) unconditionally sets `?cve=<id>&open=drill` on every row click — it does not close the panel first if one is already open for a different vuln. Neither `DrillPanel` (drill-panel.tsx:103, `<DrillContent idOrCve={effectiveId} onClose={close} />`) nor `DrillPanelMobile` passes a `key={effectiveId}` prop. This means clicking a *different* vulnerability's row while the drill panel is already open for another vulnerability does **not** remount `DrillContent` — React reconciles it as the same component instance, and all of its internal `useState` (`ticketProvider`, `description`, and the new `title`) persists unchanged across the id swap.

**Why it happens:** This characteristic already exists today for `description` (shipped in Phase 25), but its blast radius was small because populating `description` required an explicit, opt-in "Copy into ticket description" click. Phase 27 makes composition **automatic on every open** — so the realistic failure sequence becomes: analyst opens vuln A's drill, opens the Create dialog (title/description auto-compose for A), clicks Cancel (dialog closes, panel stays mounted), clicks a *different* row for vuln B (panel updates in place, no remount), opens Create for vuln B — since `title`/`description` are no longer at their initial blank value (they hold vuln A's composed draft), a guard that checks "already composed" without also checking "for which id" will not recompose, and the analyst can click "Create ticket" and ship **vuln A's title and description on a ticket linked to vuln B**.

**How to avoid:** Pattern 4's `ref` must store the `resourceId` it composed for (not just a boolean), and the effect must compare against the *current* `v.id ?? idOrCve` on every `confirmOpen` transition, recomposing whenever they differ. This closes the gap for both the new `title` field and (as a welcome side effect) the pre-existing `description` field, which has the same latent exposure today.

**Warning signs:** A ticket created for vuln B whose title/CVE-in-text doesn't match its actual `vulnerability_ids` is the fingerprint; this will only reproduce by switching vulns via row-click while the panel stays open, not by closing-and-reopening the panel itself.

### Pitfall 4: `AnalyzingIndicator` is a private, unexported function

**What goes wrong:** `ai-explanation-section.tsx:104` declares `function AnalyzingIndicator()` with no `export` keyword — it is used only internally at line 227. 27-UI-SPEC.md's gap-fill row explicitly requires reusing "the exact `AnalyzingIndicator` pulsing-dot component/copy" (§4, D-12) for its own loading state. Attempting to `import { AnalyzingIndicator } from '@/components/ai/ai-explanation-section'` will fail (or silently import `undefined` depending on bundler/tsconfig strictness) since the symbol isn't exported.

**Why it happens:** `AnalyzingIndicator` was written as a private implementation detail of the one component that needed it (Phase 24); nothing before Phase 27 needed to reuse it from outside that file.

**How to avoid:** Add `export` to the `function AnalyzingIndicator()` declaration (a one-line, zero-risk change — it has no props, no closure over module-private state) and import it directly into wherever the gap-fill row is implemented. This is far preferable to copy-pasting the JSX, which would silently drift the moment either copy is touched in a future phase.

**Warning signs:** A TypeScript/build error on import, or (if caught late) two visually-similar-but-not-identical "Analyzing…" indicators in the same dialog.

### Pitfall 5: Owner/department is not actually available on the drill panel's data — do not invent a field

**What goes wrong:** CONTEXT.md's "Existing Code Insights" section states "the drill panel's own asset facts (owner department, host, product) — the asset-context source, already loaded." This is imprecise: `frontend/src/lib/queries/use-vulnerability-detail.ts`'s `VulnerabilityDetail` type (lines 12-31) has `asset_id`, `asset_hostname`, `affected_product`, `cisa_kev`, `exploit_available` — but **no owner, assigned-user, department, or Humaans-email field at all**. (The backend's `Asset` model does carry `assigned_user`/`mdm_details.humaans_email` — used server-side in `create_tickets()`'s own assignee-resolution logic, service.py:211-220 — but this is never returned by the `/api/v1/vulnerabilities/{id}` endpoint the drill panel queries.)

**Why it happens:** CONTEXT.md was written before the UI-SPEC's checker pass narrowed the composed body's exact fields; 27-UI-SPEC.md's actual "Asset context:" section (§3) correctly lists only `Host` / `Product` / `Severity` / `CISA KEV` / `Exploit available` — no owner/department line at all.

**How to avoid:** Follow 27-UI-SPEC.md exactly (it is the authoritative, more specific contract here) — do not add an owner or department line to the composed body. This is not a D-06 compliance risk to actively manage; it's structurally impossible today since the data isn't loaded, and adding a new fetch to obtain it would be scope creep beyond D-05's "pure consumer" boundary.

**Warning signs:** A plan or implementation that tries to read `v.assigned_user` or similar off `VulnerabilityDetail`/`FlexibleDetail` will hit `undefined` — `FlexibleDetail` (drill-content.tsx:28-52) also has no such field.

### Pitfall 6: The Phase 25 precedent did not centralize its new copy into `microcopy.ts` — minor, but be consistent

**What goes wrong / context:** `frontend/src/components/vulnerabilities/microcopy.ts` states in its header comment "All vulnerabilities-page strings centralized… verified by grep at acceptance," but Phase 25's description-field caption/placeholder strings ("Pre-filled from remediation guidance…", "No remediation guidance yet…") were hardcoded directly and duplicated verbatim in both `drill-content.tsx` (lines 411-412, 418) and `drill-panel-mobile.tsx` (lines 156-159, 165) — not added to `microcopy.ts`.

**Why it happens:** Not a functional bug, just an established (if inconsistent with the file's own header comment) precedent.

**How to avoid:** This is a low-stakes style call, not a correctness risk. Recommend following the actual precedent (hardcode inline, duplicated in both files) for consistency with the immediately-adjacent code this phase extends, since 27-UI-SPEC.md's copy is already locked verbatim and won't need per-string editing later. Centralizing into `microcopy.ts` would be a defensible cleanup but is out of this phase's stated scope (D-05) and would touch more files than necessary.

## Code Examples

### The exact current title-build line being extended (verified, service.py:200-202)
```python
sev = vuln.severity or "MEDIUM"
cve = vuln.cve_id or vuln.vulnerability_name or "Unknown vulnerability"
task_name = f"[{sev}] {cve} on {hostname or 'unknown host'}"
```

### The exact backend test pattern to mirror (verified, test_ticketing_dispatch.py:45-73, 248-287)
```python
# Source: backend/tests/test_ticketing_dispatch.py (existing, Phase 25's description tests)
class FakeTicketingClient:
    async def create(self, title, body, **kwargs):
        self._seq += 1
        self.created.append((title, body, kwargs))  # (title, body, kwargs) tuple — asserted directly
        return f"{_FAKE_URL_BASE[self.provider]}/ref-{self._seq}"

@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ASANA", "JIRA", "GITHUB"])
async def test_create_tickets_uses_request_description_when_supplied(db_session, tenant_a, provider):
    fake = FakeTicketingClient(provider)
    request = TicketCreateRequest(vulnerability_ids=[vuln.id], provider=provider, project_key="PROJ", description=supplied_text)
    await create_tickets(db=db_session, tenant_id=tenant_a, user_id=None, request=request, client=fake)
    assert fake.created[0][1] == supplied_text   # index [1] = body/notes

# RECOMMENDED mirror for title (index [0] = title):
async def test_create_tickets_uses_request_title_when_supplied(db_session, tenant_a, provider):
    fake = FakeTicketingClient(provider)
    request = TicketCreateRequest(vulnerability_ids=[vuln.id], provider=provider, project_key="PROJ", title="Custom title")
    await create_tickets(db=db_session, tenant_id=tenant_a, user_id=None, request=request, client=fake)
    assert fake.created[0][0] == "Custom title"

async def test_create_tickets_falls_back_to_built_title_when_omitted(db_session, tenant_a, provider):
    fake = FakeTicketingClient(provider)
    request = TicketCreateRequest(vulnerability_ids=[vuln.id], provider=provider, project_key="PROJ")
    await create_tickets(db=db_session, tenant_id=tenant_a, user_id=None, request=request, client=fake)
    assert fake.created[0][0] == f"[MEDIUM] {vuln.cve_id} on unknown host"  # matches _build the same way description's fallback test does
```

### The shared response field every cache read composes from (verified, backend/app/ai/schemas.py:44-60)
```python
class ExplainResponseBase(BaseModel):
    summary: str = Field(..., description="Plain-English explanation of the vulnerability")
    business_risk: str = Field(..., description="Business-risk framing for this asset/owner")
    citations: list[Citation] = Field(..., min_length=1, ...)
    grounded: bool = Field(...)
# ExplainVulnResponse, ExplainRemediationGuidanceResponse, ExplainPrioritizationResponse
# all subclass this with NO additional fields — `summary` is universally the field to compose from,
# never `business_risk` (27-UI-SPEC.md §3 explicit instruction, matching the existing
# onCopyToDescription(state.data.summary) convention at ai-explanation-section.tsx:238,291).
```

### The never-auto-submit guarantee (verified, ConfirmModal.tsx:56-60, 100-107)
```typescript
// The ONLY useEffect in the entire component — a focus call, never a submit call:
useEffect(() => {
  if (open && !isMobile) { confirmRef.current?.focus(); }
}, [open, isMobile]);
// ...
<button ref={confirmRef} onClick={onConfirm} disabled={confirmDisabled} ...>
  {confirmLabel}
</button>
// No <form> element wraps the Title/Description inputs, so pressing Enter inside
// either field has no native form-submit side effect to guard against either.
```

## State of the Art

This is an internal, single-project architecture evolution, not an external ecosystem shift — "state of the art" here means how this codebase's own ticket-draft pre-fill capability has evolved phase over phase.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Ticket title: server-only, no override, computed entirely in `create_tickets()` | Ticket title: analyst-editable, client-composed-by-default, with the exact same server fallback preserved | This phase (27) | Analysts get a pre-filled, editable title instead of only seeing it after ticket creation |
| Ticket description: opt-in pre-fill via one explicit "Copy into ticket description" click (Phase 25) | Ticket description: automatic multi-section compose-on-open (explain + remediation + asset-context + optional prioritization), with the same manual copy-in button still present alongside | This phase (27) | Higher-value default (SC1), but see Pitfall 2 for the resulting interaction between the old opt-in button and the new automatic compose |
| Gap-fill: none — a cache miss simply showed a full-section "Explain this"/"Get remediation guidance" button inside the main panel (Phase 24/25) | Gap-fill: an additional compact, dialog-scoped trigger reusing the identical underlying `useExplainStream` mechanism | This phase (27) | Same underlying capability, new compact entry point closer to the point of use (inside the ticket-create dialog itself) |

**Deprecated/outdated:** None — this phase deprecates nothing; the main-panel "Explain this vuln"/"Get remediation guidance"/"Copy into ticket description" affordances all remain exactly as they are.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `title`'s `max_length` should be **255**, matching Jira's hard external limit (the strictest of the three providers) | Common Pitfall 1, Pattern 2 | If the planner instead mirrors `description`'s `max_length=10000` literally, an over-long title (likely from a multi-host `hostsLine`) will pass validation but fail silently at Jira's API boundary per Pitfall 1 — reintroducing the exact silent-failure risk this recommendation exists to close. Low risk of active harm either way since it's a bounds-tightening choice, but 255 is the evidence-backed, safer value. |
| A2 | Asana's task `name` field has no hard character limit strict enough to matter here | Common Pitfall 1 | WebSearch found only a generic, unconfirmed "1024 chars for text fields" reference, not specifically the task-name field — LOW confidence, unverified against Asana's own current API reference. Recommend verifying directly against `developers.asana.com`'s task resource docs at plan time if a title anywhere near that length is expected in practice; otherwise moot since the 255-char Jira-driven cap (A1) is stricter and applies uniformly regardless of provider. |
| A3 | The composed-once guard should key on `resourceId` via a `ref`, not a blank-string check, and should NOT treat the pre-existing main-panel "Copy into ticket description" click as having "already composed" | Pattern 4, Common Pitfalls 2 & 3 | This is this research's own synthesized recommendation, not something either CONTEXT.md or 27-UI-SPEC.md states explicitly. If the planner adopts a simpler blank-string guard instead, the specific cross-vuln (Pitfall 3) and copy-button-interaction (Pitfall 2) failure modes documented above will reproduce. Recommend confirming this approach during planning/discuss-phase rather than treating it as already locked. |

## Open Questions (RESOLVED)

1. **Should the pre-existing main-panel "Copy into ticket description" button change behavior once the confirm dialog auto-composes on open?**
   - What we know: it currently calls `setDescription(text)` (a full replace), sharing state with the new confirm-dialog compose logic (Pitfall 2).
   - What's unclear: whether it should be left exactly as-is (a legitimate "reset to just this" escape hatch, consistent with D-04's "never blocked, always editable" spirit), changed to append instead of replace (for consistency with the gap-fill row's append behavior), or left alone entirely since the composed-once-guard recommendation (Pattern 4/A3) already prevents it from causing data loss on the more common path (composing overwrites it correctly on first genuine dialog open either way).
   - Recommendation: leave its behavior unchanged (simplest, smallest diff, does not touch Phase 25 code) — Pattern 4's `resourceId`-keyed guard already ensures the FIRST open of the confirm dialog composes over whatever `description` held, so the two affordances coexist safely as long as the guard is implemented per Pattern 4, not as a blank-string check.

2. **Exact `title` `max_length` value.**
   - What we know: Jira's hard limit is 255 (well-corroborated externally); GitHub's is far more generous; Asana's specific task-name limit was not conclusively found.
   - What's unclear: whether the planner should lock exactly 255, or a slightly larger bound with a separate pre-submit provider-aware warning (more complex, likely over-engineering relative to D-05's "small" characterization).
   - Recommendation: 255, no per-provider variance — see Assumptions Log A1.

## Environment Availability

No new external dependency is introduced by this phase (no new SDK, no new provider, no new service). The only relevant infrastructure is what Phases 23-26 already established and this phase reuses unchanged.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres (`getvul-postgres-1`) | `Ticket`/`Vulnerability`/`Asset` queries (unchanged) | ✓ [VERIFIED: `docker ps`, 2026-08-01] | healthy, running 22h | — |
| Redis (`getvul-redis-1`) | AI response cache the composer reads from (unchanged, Phase 24) | ✓ [VERIFIED: `docker ps`, 2026-08-01] | healthy, running 22h | — |
| Jira/Asana/GitHub ticketing connectors | `create_tickets()`'s dispatched client (unchanged, Phase 23) | Not independently re-verified this session — inherited from Phase 23/25's proven dispatch tests | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — this phase introduces no new dependency to have a fallback for.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio (`asyncio_mode = "auto"`, session-scoped event loop, `backend/pyproject.toml:73-81`) for backend; Vitest (jsdom) for frontend (`frontend/package.json:10`, `frontend/vitest.config.mts`) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]`; `frontend/vitest.config.mts` (unchanged) |
| Quick run command | Backend: `ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test pytest backend/tests/test_ticketing_dispatch.py -q` (per-file — project memory: do not run the whole `tests/` directory for a quick loop). Frontend: `npx vitest run drill-content` / `drill-panel-mobile` (from `frontend/`) |
| Full suite command | `pytest backend/tests/ -q` + `npm run test` (frontend, from `frontend/`) + `npx tsc --noEmit` + `npm run lint` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AID-01 | `TicketCreateRequest.title` whitespace-only coerces to `None`; over-max-length raises; omitted is valid; extra field still rejected | unit | `pytest backend/tests/test_ticketing_dispatch.py -k title -x` | ❌ Wave 0 (extends existing file) |
| AID-01 | `create_tickets()` uses `request.title` when supplied (all 3 providers), falls back to the built `task_name` when omitted | unit | `pytest backend/tests/test_ticketing_dispatch.py -k create_tickets_uses_request_title -x` | ❌ Wave 0 (extends existing file, mirrors lines 248-287 exactly) |
| AID-01 | `composeTicketTitle`/`composeTicketDescription` produce the correct output for every cache-state permutation (both missing, one missing, all present, prioritization included/excluded) | unit | `npx vitest run compose-ticket-draft` | ❌ Wave 0 (new file, if Pattern 1's extraction is adopted) |
| AID-01 | Desktop + mobile confirm dialogs both auto-populate Title + Description on first open, and do not re-populate over an edit on a second open, and reset when the vuln id changes | component | `npx vitest run drill-content` / `drill-panel-mobile` | ❌ Wave 0 (extends existing `.test.tsx` files) |
| AID-01 | Gap-fill row renders 0-2 buttons per the cache-state matrix, gated by key-configured + Analyst+ role, and appends (never replaces) on success | component | `npx vitest run drill-content` | ❌ Wave 0 (extends existing file) |
| AID-01 | "Create ticket" is never disabled by draft state, only by `!ticketProvider` (unchanged) | component | `npx vitest run drill-content -k confirmDisabled` | ✅ pre-existing assertion pattern, extend with a new negative case |

### Sampling Rate

- **Per task commit:** the touched file's own quick-run command (per-file, per project memory's env-var gotcha).
- **Per wave merge:** `pytest backend/tests/test_ticketing_dispatch.py -q` + `npm run test` for every touched frontend file.
- **Phase gate:** Full backend + frontend suite green, plus `tsc --noEmit` + `eslint`, before `/gsd-verify-work 27`.

### Wave 0 Gaps

- [ ] `backend/tests/test_ticketing_dispatch.py` — extend with the `title` mirror tests (schema validation + dispatch fallback, mirroring the existing `description` tests at lines 122-147 and 248-287)
- [ ] `frontend/src/lib/tickets/compose-ticket-draft.test.ts` — new file, if Pattern 1's extraction is adopted (recommended); covers every cache-state permutation named in 27-UI-SPEC.md's "UI Considerations" partial-state row
- [ ] `frontend/src/components/vulnerabilities/drill-content.test.tsx` (or the file's actual current name, `drill-panel.test.tsx` per 25-07-SUMMARY.md — verify exact filename at plan time) — extend with Title field + gap-fill row + composed-once-guard tests
- [ ] `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — mirror the same new tests for the mobile path
- [ ] No new fixtures/conftest needed — `tenant_a`/`tenant_b`/`db_session` (backend) and the existing `useExplainCache`/`useAiStatus`/`useTicketingProviders` mocks (frontend, already upgraded to `vi.fn()`-backed in 25-07) are reused verbatim

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged — reuses existing JWT/session auth |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | Reuses `require_analyst` (ticket creation, unchanged) and `require_analyst`/`require_viewer` (gap-fill's underlying explain routes, unchanged) verbatim — no new access-control logic introduced |
| V5 Input Validation | Yes | The new `title` field needs its own `max_length` bound (recommended 255, see Assumptions Log A1) and inherits the existing `extra: "forbid"` mass-assignment defense at the class level; whitespace-coercion validator mirrors `description`'s exactly |
| V6 Cryptography | No | No new cryptographic material; BYOK key handling is 100% inherited/unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Mass-assignment via the new `title` field on `TicketCreateRequest` | Tampering | `model_config = {"extra": "forbid"}` (already present at the class level, `app/ticketing/schemas.py:63`) + an explicit `max_length` bound + whitespace-coercion validator (mirrors the `description` precedent, T-25-06) |
| Analyst-editable free text (title/description) reaching a third-party ticketing system verbatim | Tampering / Information Disclosure (in the general sense of "what leaves the system") | Not a new exposure — `description` already crosses this exact trust boundary since Phase 25; the receiving system is the analyst's own already-configured, already-trusted Jira/Asana/GitHub account, and GetVul never renders this text back as HTML anywhere (no XSS-relevant DOM sink for it) |
| Silent per-ticket creation failure masking a data-integrity problem (Pitfall 1) | Not a classic STRIDE category — a reliability/data-integrity concern | Bound `title`'s `max_length` conservatively (255) so an oversized title is rejected as a visible 422 at the mutation boundary instead of failing silently inside `create_tickets()`'s per-vulnerability loop |

## Sources

### Primary (HIGH confidence)
- `backend/app/ticketing/{schemas.py, service.py, dispatch.py, router.py, jira_client.py, asana_client.py, github_client.py}` — direct reads, the entire title-override/dispatch/provider-threading analysis (Patterns 2, 3; Pitfall 1)
- `backend/app/ai/schemas.py` — direct read, the shared `ExplainResponseBase.summary` field confirmation
- `backend/app/api/v1/ai/{explain_vuln.py, explain_remediation_guidance.py, explain_prioritization.py}` — direct reads, confirmed all three route on the same `finding_id`/`v.id` and share the cache-key/allowlist pattern
- `backend/tests/test_ticketing_dispatch.py` — direct read, the exact test pattern to mirror (Code Examples)
- `frontend/src/components/vulnerabilities/{drill-content.tsx, drill-panel-mobile.tsx, ticket-provider-picker.tsx, microcopy.ts}` — direct reads, the desktop/mobile divergence, the `FlexibleDetail` shape, the pre-existing copy-in button interaction (Pitfall 2)
- `frontend/src/lib/mutations/use-create-ticket.ts`, `frontend/src/lib/queries/{use-explain-cache.ts, use-vulnerability-detail.ts, use-ai-status.ts}`, `frontend/src/lib/ai/use-explain-stream.ts` — direct reads, the cache-read/stream-trigger seams and the owner/department absence (Pitfall 5)
- `frontend/src/components/ai/{ai-explanation-section.tsx, ai-explanation-citations.tsx}` — direct reads, the `AnalyzingIndicator` export gap (Pitfall 4) and the plain-text `summary` confirmation
- `frontend/src/components/ui/ConfirmModal.tsx` — direct read, the never-auto-submit confirmation
- `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`, `frontend/src/components/vulnerabilities/drill-panel.tsx` — direct reads, the cross-vuln state-carryover finding (Pitfall 3)
- `.planning/phases/25-asset-aware-remediation-guidance/{25-06-SUMMARY.md, 25-07-SUMMARY.md}` — the exact precedent this phase mirrors, including its own noted deviations/pitfalls
- `.planning/phases/27-ticket-auto-drafting/{27-CONTEXT.md, 27-UI-SPEC.md, 27-DISCUSSION-LOG.md}` — the locked decisions and UI contract this research is scoped against
- `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md` — phase goal/SCs and AID-01 traceability
- `docker ps` (2026-08-01) — Environment Availability verification

### Secondary (MEDIUM confidence)
- [Atlassian Community: "What is the character limit in the JIRA summary field?"](https://community.atlassian.com/forums/Jira-questions/What-is-the-character-limit-in-the-JIRA-summary-field/qaq-p/1937701) and [Atlassian Community: "Summary must be less than 255 characters"](https://community.atlassian.com/forums/Jira-questions/Summary-must-be-less-than-255-characters/qaq-p/989632) and [tenable/integration-jira-cloud#322](https://github.com/tenable/integration-jira-cloud/issues/322) — three independent, corroborating sources confirming Jira's hard 255-character summary limit (Pitfall 1, Assumption A1)
- [GitHub Community Discussion #48785](https://github.com/orgs/community/discussions/48785) and related discussions — corroborate GitHub's issue-title limit is far more generous (tens of thousands of characters), not a practical concern for this phase

### Tertiary (LOW confidence)
- Asana task-name character limit — WebSearch surfaced only a generic, non-task-name-specific "1024 chars for text fields" reference with no primary Asana API documentation page confirming it applies to `name`. Flagged in Assumptions Log A2; not treated as a hard fact anywhere in this document.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new library; every reused piece was read directly in this session
- Architecture: HIGH — every pattern (title mirror, provider dispatch, cache reads, gap-fill trigger, never-auto-submit) was confirmed against actual current source, not inferred from documentation
- Pitfalls: HIGH for 5 of 6 (all directly code-verified); MEDIUM for the exact `title` `max_length` recommendation (externally corroborated but ultimately a judgment call, not a locked spec value)

**Research date:** 2026-08-01
**Valid until:** 2026-08-29 (30 days — this is stable, internal architecture with no fast-moving external dependency; re-verify sooner only if Phases 24-26's ticketing/AI scaffold changes before Phase 27 executes)
