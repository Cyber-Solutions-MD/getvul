# Phase 27: Ticket Auto-Drafting - Pattern Map

**Mapped:** 2026-08-01
**Files analyzed:** 11 new/modified files (2 backend + 9 frontend, including 4 test files)
**Corroboration files (read-only, zero/near-zero code change expected):** 5 (`dispatch.py`, `jira_client.py`, `asana_client.py`, `github_client.py`, `drill-panel.tsx`)
**Analogs found:** 9/11 exact same-file sibling analogs; 2 partial/novel (the optional `compose-ticket-draft.ts` pure-fn module + its test)

This phase is, even more than Phase 25, dominated by **same-file self-analogs**: almost every backend and frontend change is "add a `title` sibling next to the already-shipped `description`, in the same file, a few lines away." This map extends `25-PATTERNS.md` directly — where Phase 25 mapped `description`, this phase maps `title` onto the identical seam. Every RESEARCH.md claim below was independently re-verified against a direct `Read` in this session (not re-trusted blindly); line numbers are current as of 2026-08-01 and match RESEARCH.md's citations exactly except where noted.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/ticketing/schemas.py` (add `title: str \| None` field + validator to `TicketCreateRequest`) | model / schema | CRUD | same file, `description` field + validator, lines 70-80 | exact (same class, sibling field — deviates only in `max_length`, see below) |
| `backend/app/ticketing/service.py` (`create_tickets()`'s `task_name` fallback, line 202) | service | CRUD | same file, same function, `notes` fallback, lines 226-230 | exact (same file, same function, sibling assignment) |
| `backend/tests/test_ticketing_dispatch.py` (extend) | test | — | same file, `description` schema tests lines 122-147 + dispatch tests lines 246-287 + `FakeTicketingClient` lines 45-73 | exact |
| `frontend/src/lib/tickets/compose-ticket-draft.ts` **(NEW, discretionary — RESEARCH Pattern 1)** | utility (pure fn) | transform | `frontend/src/lib/ticketing/providers.ts` (module shape) + `service.py`'s `_build_task_description()` (section-builder voice, lines 128-159) | partial (novel logic, precedented shape) |
| `frontend/src/lib/tickets/compose-ticket-draft.test.ts` **(NEW, discretionary)** | test | — | `frontend/src/lib/queries/keys.test.ts` (whole file — pure-fn, no-DOM test shape) | role-match |
| `frontend/src/components/ai/ai-explanation-section.tsx` (export `AnalyzingIndicator`, line 104) | component | streaming UI | same file, same line — one-keyword change | exact |
| `frontend/src/components/vulnerabilities/drill-content.tsx` (title state, composed-once guard, gap-fill row, Title `Input`, `fireTicket()` threading) | component | UI composition + CRUD | same file's own `description` state (line 94) + `renderConfirm` type (lines 60-74) + `<ConfirmModal>` children block (lines 406-421) + `fireTicket()` (lines 165-196) | exact (same file, sibling state/threading to extend) |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` (mirror Title `Input` + gap-fill row inside `renderConfirm`) | component | UI composition | same file's own description `Textarea` block, lines 148-168 | exact (same file — but a genuinely separate code path from desktop, confirmed again) |
| `frontend/src/lib/mutations/use-create-ticket.ts` (add `title?: string` to `CreateTicketRequest`) | hook / mutation | CRUD | same file, `description?: string`, line 18 | exact (same file, sibling field, zero mutation-body change needed) |
| `frontend/src/components/vulnerabilities/drill-panel.test.tsx` (extend) | test | — | same file, description-textarea `describe` block, lines 280-339 | exact |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` (extend) | test | — | same file, mobile description-textarea tests, lines 220-276 | exact |
| `backend/app/ticketing/dispatch.py` — **NO CHANGE (confirmed zero-touch)** | service / adapter | CRUD | `TicketingClient.create()` Protocol, whole file | n/a — confirmed |
| `backend/app/ticketing/jira_client.py` — **NO CHANGE** (Pitfall 1 root cause; informs the 255-char cap) | service / http-client | request-response | `create_ticket()`, lines 104-154 | n/a — confirmed |
| `backend/app/ticketing/asana_client.py` — **NO CHANGE** (spot-checked, no hard `name` limit found) | service / http-client | request-response | `create_task()`, lines 105-154 | n/a — confirmed |
| `backend/app/ticketing/github_client.py` — **NO CHANGE** (spot-checked, generous limit, non-issue) | service / http-client | request-response | `create_ticket()`, lines 85-125 | n/a — confirmed |
| `frontend/src/components/vulnerabilities/drill-panel.tsx` — **flagged, no code change expected** (Pitfall 3 root cause) | component | UI composition | `<DrillContent idOrCve={effectiveId} onClose={close} />` mount, line 103, no `key` prop | n/a — corroborated; the fix lives entirely in `drill-content.tsx`'s own guard (Pattern 4), not here |

---

## Pitfall → File Map (quick reference)

All 5 pitfalls RESEARCH.md surfaced were independently re-verified this session by direct `Read`. None required correction — every cited line number matched.

| Pitfall | Exact file(s) / lines it lands on | Verified |
|---|---|---|
| 1. Jira's 255-char summary limit + silent `create_tickets()` failure | `backend/app/ticketing/schemas.py` (new `title` field's `max_length`, NOT 10000) + `backend/app/ticketing/jira_client.py:134-140` (the silent `return None` on non-201) + `backend/app/ticketing/service.py:236-238` (`if url is None: ... continue`) | confirmed — read all three |
| 2. "Copy into ticket description" button vs. auto-compose, same `description` state | `frontend/src/components/ai/ai-explanation-section.tsx:92-102,237-239,290-292` (`CopyToDescriptionButton` + `onCopyToDescription` call sites) + `frontend/src/components/vulnerabilities/drill-content.tsx:94,337` (`description` state + the mount that wires `onCopyToDescription={setDescription}`) | confirmed — read both; also found the exact test that exercises this today (`drill-panel.test.tsx:324-339`, see below) |
| 3. No `DrillContent` remount key → cross-vuln carryover | `frontend/src/components/vulnerabilities/drill-panel.tsx:103` + `drill-panel-mobile.tsx:100-102` (both mount `<DrillContent>` with no `key`) + `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx:116-122` (`handleRowOpen` — sets URL params, never closes first) | confirmed — read `handleRowOpen` directly; grep-confirmed the two mount lines |
| 4. `AnalyzingIndicator` is private | `frontend/src/components/ai/ai-explanation-section.tsx:104` (`function AnalyzingIndicator()`, no `export`) | confirmed — read directly, no `export` keyword present |
| 5. Owner/department not on `VulnerabilityDetail` | `frontend/src/lib/queries/use-vulnerability-detail.ts:12-31` (`VulnerabilityDetail` type — no owner/department field) + `drill-content.tsx:28-52` (`FlexibleDetail` — same absence) | confirmed — read both types in full |

---

## Pattern Assignments

### `backend/app/ticketing/schemas.py` — add `title` override field + validator

**Analog:** the file's own `description` field + validator, lines 70-80 (same class, `TicketCreateRequest`, starting line 53; `model_config = {"extra": "forbid"}` already class-level at line 63)

**Current code to mirror** (verified, lines 63-80):
```python
model_config = {"extra": "forbid"}

vulnerability_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)
provider: str = Field(..., pattern="^(ASANA|JIRA|GITHUB)$")
project_key: str = Field("", description="Asana project GID or Jira project key")
assignee: str | None = Field(None, description="Email or user ID to assign the ticket to")
due_days: int | None = Field(None, ge=1, le=365, description="Days from now for due date")
description: str | None = Field(
    None, max_length=10000, description="Analyst-supplied ticket description (WYSIWYG override)"
)

@field_validator("description")
@classmethod
def _no_ws_only(cls, v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None
```

**Recommended addition — mirrors the shape, deviates on ONE value:**
```python
title: str | None = Field(
    None, max_length=255, description="Analyst-supplied ticket title (WYSIWYG override)"
)

@field_validator("title")
@classmethod
def _title_no_ws_only(cls, v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None
```

**Deliberate deviation (do NOT copy `description`'s `max_length=10000` verbatim):** `max_length=255`, matching Jira's hard external summary limit — the strictest of the three providers (see Pitfall 1 corroboration in `jira_client.py` below). Everything else mirrors `description` exactly: `model_config = {"extra": "forbid"}` is already class-level, so the new field inherits mass-assignment defense automatically — no new guard code needed. The validator needs its own method name (`_title_no_ws_only`, not `_no_ws_only`) since Python forbids two methods with the same name in one class.

**Confirmed out of scope:** `HostTicketCreateRequest` (lines 83-88) has no `description`/`title` field at all and is not touched — D-05 scopes this phase's only backend change to `TicketCreateRequest`.

---

### `backend/app/ticketing/service.py` — `create_tickets()`'s `task_name` fallback

**Analog:** the same function's own `notes` fallback, lines 222-230 (11 lines below `task_name`'s current single-line assignment)

**Current code** (verified, lines 199-234):
```python
# Build task
sev = vuln.severity or "MEDIUM"
cve = vuln.cve_id or vuln.vulnerability_name or "Unknown vulnerability"
task_name = f"[{sev}] {cve} on {hostname or 'unknown host'}"
...
# AIR-02 (Phase 25 Plan 06): an analyst-supplied description WYSIWYG-
# replaces the auto-built one (RESEARCH Assumptions A3) — what the
# analyst reviewed/edited in the textarea is exactly what ships, with
# no hidden server-side content silently appended.
notes = (
    request.description.strip()
    if request.description and request.description.strip()
    else _build_task_description(vuln, hostname)
)

# Create via the dispatched provider client (D-07: destination now
# matches request.provider, not always Asana).
url = await client.create(task_name, notes, **_provider_create_kwargs(request.provider, assignee, due_on))

if url is None:
    logger.error("ticket_creation_failed", vuln_id=str(vuln_id), provider=request.provider)
    continue
```

**Recommended replacement of line 202** (same shape as the `notes` fallback above):
```python
task_name = (
    request.title.strip()
    if request.title and request.title.strip()
    else f"[{sev}] {cve} on {hostname or 'unknown host'}"
)
```
The call site at line 234 needs **zero change** — `client.create(task_name, notes, ...)` already takes whatever `task_name` resolves to.

**Confirmed out of scope (contrast, do not touch):** `create_host_ticket()`'s own `task_name` (lines 462-464, `f"[{max_severity}] Remediate {hostname} — ..."`) and `create_remediation_ticket()`'s (line 646, `f"[{max_sev}] {product}: {remediation_action[:80]} — {len(hosts)} hosts"`) are unrelated code paths — their request schemas have no `title`/`description` override field, and CONTEXT.md's phase boundary scopes this change to `create_tickets()` only.

**Pitfall 1's exact silent-failure mechanics** (verified, lines 236-238, corroborating RESEARCH): `if url is None: logger.error(...); continue` — no exception raised, the vulnerability is silently skipped, and since the confirm dialog always sends exactly one `vulnerability_id`, `created_tickets` ends up empty with an HTTP 200. This is why the 255 cap belongs in the Pydantic `Field` (schemas.py), converting a silent backend failure into a visible 422 the frontend's existing `catch` block (drill-content.tsx `fireTicket()`, lines 193-195) already surfaces as a toast.

---

### `backend/app/ticketing/dispatch.py` / `jira_client.py` / `asana_client.py` / `github_client.py` — confirmed zero-touch

**Analog:** `TicketingClient.create(title: str, body: str, **kwargs)` Protocol (dispatch.py, lines 23-41) + the 3 adapters' `create()` methods

**Verified current code (nothing here changes):**
```python
# dispatch.py:52-60
async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
    task = await self._client.create_task(..., name=title, notes=body, **kwargs)
    return task.url if task else None
# dispatch.py:79-86
async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
    issue = await self._client.create_ticket(..., summary=title, description=body, **kwargs)
    return issue.url if issue else None
# dispatch.py:107-109
async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
    issue = await self._client.create_ticket(title=title, body=body)
    return issue.url if issue else None
```
`service.py:234`'s single call site (`await client.create(task_name, notes, **_provider_create_kwargs(...))`) is the ONLY place `task_name` needs to change — it already flows to `name`/`summary`/`title` correctly for all three providers. Confirmed by direct read of all three concrete clients:
- `jira_client.py:104-154` — `create_ticket(project_key, summary, description, assignee_account_id=None)`; `summary` sent straight to `POST /rest/api/3/issue` fields dict (line 118) with no client-side length check; non-201 → `return None` (lines 134-140). **This is Pitfall 1's exact root cause.**
- `asana_client.py:105-154` — `create_task(..., name, notes=None, ...)`; no length check on `name` found (spot-checked, corroborating RESEARCH's Assumption A2 — no hard Asana task-name limit located).
- `github_client.py:85-125` — `create_ticket(title, body)`; no length check on `title` (GitHub's limit is far more generous, non-issue per RESEARCH).

---

### `backend/tests/test_ticketing_dispatch.py` — extend with `title` mirror tests

**Analog:** the file's own `description` tests — `FakeTicketingClient` (lines 45-73), schema validation tests (lines 122-147), dispatch fallback tests (lines 246-287)

**`FakeTicketingClient` — the exact tuple-recording shape to assert against** (verified, lines 45-62):
```python
class FakeTicketingClient:
    def __init__(self, provider: str, get_payload: dict | None = None) -> None:
        self.provider = provider
        self.created: list[tuple[str, str, dict]] = []
        ...

    async def create(self, title, body, **kwargs):
        self._seq += 1
        self.created.append((title, body, kwargs))
        return f"{_FAKE_URL_BASE[self.provider]}/ref-{self._seq}"
```
`fake.created[0][0]` is the `title` argument (index `[1]` is `body`/`notes`, already used by the existing description tests) — the new title tests assert on index `[0]`.

**Schema validation tests to mirror** (verified, lines 122-147 — 5 tests, one function each):
```python
def test_ticket_create_request_description_whitespace_only_coerces_to_none():
    request = TicketCreateRequest(vulnerability_ids=[uuid.uuid4()], provider="ASANA", description="   \n\t  ")
    assert request.description is None

def test_ticket_create_request_description_over_max_length_raises():
    with pytest.raises(ValidationError):
        TicketCreateRequest(vulnerability_ids=[uuid.uuid4()], provider="ASANA", description="x" * 10001)

def test_ticket_create_request_description_omitted_is_valid():
    request = TicketCreateRequest(vulnerability_ids=[uuid.uuid4()], provider="ASANA")
    assert request.description is None

def test_ticket_create_request_description_valid_text_is_kept_verbatim_after_strip():
    request = TicketCreateRequest(vulnerability_ids=[uuid.uuid4()], provider="ASANA", description="  Do the fix  ")
    assert request.description == "Do the fix"

def test_ticket_create_request_description_unknown_field_rejected():
    """extra='forbid' mass-assignment defense (T-25-06, ASVS V5)."""
    with pytest.raises(ValidationError):
        TicketCreateRequest(vulnerability_ids=[uuid.uuid4()], provider="ASANA", not_a_real_field="x")
```
Mirror 4 of these 5 for `title` (the "unknown field rejected" test is class-level and needs no title-specific duplicate) — plus one NEW test the `description` precedent doesn't need: `test_ticket_create_request_title_over_255_raises` using `"x" * 256`, since 255 (not 10000) is the new cap.

**Dispatch fallback tests to mirror** (verified, lines 246-287):
```python
@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ASANA", "JIRA", "GITHUB"])
async def test_create_tickets_uses_request_description_when_supplied(db_session, tenant_a, provider):
    vuln = _seed_vuln(tenant_a)
    db_session.add(vuln)
    await db_session.commit()
    fake = FakeTicketingClient(provider)
    supplied_text = "Patch widget to 2.3.1 on this host by Friday."
    request = TicketCreateRequest(
        vulnerability_ids=[vuln.id], provider=provider, project_key="PROJ", description=supplied_text
    )
    await create_tickets(db=db_session, tenant_id=tenant_a, user_id=None, request=request, client=fake)
    await db_session.commit()
    assert len(fake.created) == 1
    assert fake.created[0][1] == supplied_text

@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ASANA", "JIRA", "GITHUB"])
async def test_create_tickets_falls_back_to_built_description_when_omitted(db_session, tenant_a, provider):
    ...
    assert fake.created[0][1] == _build_task_description(vuln, hostname=None)
```
Mirror both, swapping `description`→`title`, index `[1]`→`[0]`, and the fallback assertion to `f"[MEDIUM] {vuln.cve_id} on unknown host"` (matching `_seed_vuln`'s default severity/no-asset shape).

---

### `frontend/src/lib/tickets/compose-ticket-draft.ts` (NEW, discretionary) — the pure composer functions

**Analog A (module shape):** `frontend/src/lib/ticketing/providers.ts` (whole file, 14 lines) — the closest "small, standalone, zero-React/zero-network pure module living directly under `lib/`" precedent in the codebase:
```typescript
export type TicketProvider = 'ASANA' | 'JIRA' | 'GITHUB';
export const PROVIDER_LABELS: Record<TicketProvider, string> = {
  ASANA: 'Asana', JIRA: 'Jira', GITHUB: 'GitHub',
};
```
Confirmed by directory listing: `frontend/src/lib/tickets/` does not exist yet — this would be a new sibling directory to `frontend/src/lib/ticketing/`, not a naming collision (the plural distinguishes "the draft-composition domain" from "the provider-identifier domain").

**Analog B (section-builder voice to match):** `backend/app/ticketing/service.py::_build_task_description()` (lines 128-159) — the server-side plain-text section builder the composed body's copy should read as a sibling of, not a stranger to:
```python
def _build_task_description(vuln: Vulnerability, hostname: str | None) -> str:
    ...
    lines = [
        f"Vulnerability: {cve}",
        f"  Severity: {sev}",
        f"  Host: {hostname or 'Unknown'}",
        ...
    ]
    lines.append("")
    lines.append(f"Remediation: {remediation}")
    return "\n".join(lines)
```
This confirms RESEARCH's "Title-Case-with-colon" section-label convention (`"Vulnerability:"`, `"Remediation:"`) is real, existing house style — the new client-side `"Description:"`/`"Remediation:"`/`"Asset context:"`/`"Prioritization:"` labels match this voice rather than inventing a new one.

**Alternative (if the extraction is NOT adopted):** the objective's own framing maps the composer directly to "the Phase 25 copy-into-description composition + `useExplainCache` reads" — i.e., if inlined rather than extracted, the closest analog is simply `drill-content.tsx`'s own existing `description`/`setDescription` state plus its `onCopyToDescription={setDescription}` wiring (line 337) and `ai-explanation-section.tsx`'s `cacheQuery.data` shape (which is exactly what `useExplainCache('remediation-guidance', v.id)` already returns). Both `drill-content.tsx` and `drill-panel-mobile.tsx` would then each hand-roll the same 4-section conditional builder — this is the exact duplication risk RESEARCH's Pattern 1 warns against, so the extracted-module path is the stronger recommendation, but both are concretely mapped here per CONTEXT.md leaving this "Claude's Discretion."

**Recommended shape** (RESEARCH Pattern 1, inputs corroborated against real current fields — `cveLabel`/`sevLabel`/`hostsLine` all confirmed at `drill-content.tsx:147,155-163`; `ExplainResponseBase.summary` confirmed as the universal plain-text field at `backend/app/ai/schemas.py`, referenced by `onCopyToDescription(state.data.summary)` at `ai-explanation-section.tsx:238,291`):
```typescript
export function composeTicketTitle(params: {
  sevLabel: string; cveLabel: string; hostsLine: string;
}): string {
  // Mirrors service.py:202's server convention exactly.
  return `[${params.sevLabel}] ${params.cveLabel} on ${params.hostsLine}`;
}

export function composeTicketDescription(params: {
  explain: { grounded: boolean; summary: string } | null;
  remediationGuidance: { grounded: boolean; summary: string } | null;
  prioritization: { grounded: boolean; summary: string } | null;
  hostsLine: string; affectedProduct: string | null;
  sevLabel: string; cisaKev: boolean; exploitAvailable: boolean;
}): string {
  const sections: string[] = [];
  if (params.explain?.grounded) sections.push(`Description:\n${params.explain.summary}`);
  if (params.remediationGuidance?.grounded) sections.push(`Remediation:\n${params.remediationGuidance.summary}`);
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

**Pitfall 5 guardrail (do NOT invent an owner/department field here):** confirmed by direct read of both `VulnerabilityDetail` (`use-vulnerability-detail.ts:12-31`: `asset_id`, `asset_hostname`, `affected_product`, `cisa_kev`, `exploit_available` — no owner/department/assignee field) and `FlexibleDetail` (`drill-content.tsx:28-52`, same absence). The asset-context section above uses only fields that actually exist on these types.

---

### `frontend/src/lib/tickets/compose-ticket-draft.test.ts` (NEW, discretionary)

**Analog:** `frontend/src/lib/queries/keys.test.ts` (whole file) — plain Vitest `describe`/`it`/`expect` directly on a pure function's return value, zero `@testing-library/react` / DOM import:
```typescript
import { describe, it, expect } from 'vitest';
import { queryKeys } from './keys';

describe('queryKeys.tickets namespace', () => {
  it('all is the prefix tuple [tickets]', () => {
    expect(queryKeys.tickets.all).toEqual(['tickets']);
  });
  ...
});
```
This is the closest "no-DOM, pure-function" test shape in the repo — `compose-ticket-draft.test.ts` should mirror this file's import list and `describe`/`it` structure, not the DOM-heavy `drill-panel.test.tsx` style, for every cache-state permutation 27-UI-SPEC.md's "partial" state row enumerates (both missing / one missing / all present / prioritization included-or-excluded).

---

### `frontend/src/components/ai/ai-explanation-section.tsx` — export `AnalyzingIndicator`

**Analog:** same file, same line — the smallest possible same-file change in this entire phase

**Current** (verified, lines 104-113):
```typescript
function AnalyzingIndicator() {
  return (
    <div className="flex items-center gap-2 text-sm text-text-muted">
      <span className="block h-2 w-2 rounded-full bg-violet motion-safe:animate-pulse" aria-hidden="true" />
      <span>Analyzing this finding…</span>
    </div>
  );
}
```
**Change:** add `export` before `function AnalyzingIndicator()`. No props, no closure over module-private state — confirmed safe to export verbatim. Its one existing internal call site (`state.phase === 'analyzing'` branch, line 227: `body = <AnalyzingIndicator />;`) is unaffected.

---

### `frontend/src/components/vulnerabilities/drill-content.tsx` — title state, composed-once guard, gap-fill row, Title `Input`, `fireTicket()` threading

**Analog 1 (state + `renderConfirm` threading + mutation body):** the file's own `description` state (line 94) + `renderConfirm` args type (lines 60-74) + `fireTicket()` (lines 165-196)

**Current code to mirror** (verified):
```tsx
// line 89, 94
const [ticketProvider, setTicketProvider] = useState<TicketProvider | null>(null);
const [description, setDescription] = useState('');

// lines 60-74 (renderConfirm prop type)
renderConfirm?: (args: {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  cveLabel: string;
  ticketProvider: TicketProvider | null;
  onProviderChange: (p: TicketProvider) => void;
  description: string;
  onDescriptionChange: (v: string) => void;
}) => React.ReactNode;

// lines 165-180 (fireTicket's mutation body)
const fireTicket = async () => {
  try {
    const result = (await createTicket.mutateAsync({
      vulnerability_ids: [v.id ?? idOrCve],
      provider: ticketProvider ?? 'ASANA',
      description: description || undefined,
    })) as { tickets?: Array<{ external_ticket_id: string; external_ticket_url: string }> };
    ...
```
Add a sibling `const [title, setTitle] = useState('')`; extend the `renderConfirm` args type with `title: string` + `onTitleChange: (v: string) => void`; thread `title: title || undefined` into the `mutateAsync({...})` call alongside `description`.

**Analog 2 (ConfirmModal children — where the Title `Input` renders):** the existing description `<div className="mt-4">` block, lines 406-421:
```tsx
<TicketProviderPicker value={ticketProvider} onChange={setTicketProvider} />
<div className="mt-4">
  <label htmlFor="ticket-description-textarea" className="mb-1 block text-xs font-medium text-text-muted">
    Pre-filled from remediation guidance — review and edit before creating.
  </label>
  <Textarea
    id="ticket-description-textarea"
    value={description}
    onChange={(e) => setDescription(e.target.value)}
    placeholder="No remediation guidance yet — add a description or leave blank."
    rows={4}
  />
</div>
```
Per 27-UI-SPEC.md §2, the new Title `Input` (imported from `@/components/ui/input`, same import convention as `Textarea` from `@/components/ui/textarea` at line 13) sits directly beneath `TicketProviderPicker` and ABOVE the shared "AI-drafted" caption (which itself supersedes the current label text above per the Copywriting Contract) — a new `<div className="mt-4">` sibling block, same `mt-4` rhythm.

**Analog 3 (composed-once guard — a NEW mechanism, no exact in-repo precedent):** the closest structural analog for "an effect keyed to `idOrCve`" is the existing D-P-06 focus-on-mount effect, lines 103-105:
```tsx
useEffect(() => {
  closeBtnRef.current?.focus();
}, [idOrCve]);
```
Same "effect re-fires when `idOrCve` changes" shape, different purpose (focus vs. compose-guard). RESEARCH's Pattern 4 (`useRef<string | null>(null)` storing the last-composed resource id, compared against `v.id ?? idOrCve` inside a `confirmOpen`-gated effect) is the recommended mechanism — there is no existing ref-keyed-compose-guard in this codebase to copy verbatim; this is genuinely new logic, structurally similar only to the focus effect's dependency-array idiom.

**Analog 4 (gap-fill row chrome + click-to-generate wiring):** `ai-explanation-section.tsx`'s `CopyToDescriptionButton` (lines 92-102, for the subordinate text-button chrome) and the `isAnalystOrAbove` trigger-button branch (lines 343-349, for the click-to-`start()` + role-gate wiring):
```tsx
// CopyToDescriptionButton chrome to reuse verbatim for each gap-fill button
<button
  type="button"
  onClick={onClick}
  className="mt-3 block text-xs font-medium text-text-muted underline-offset-2 hover:text-text hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
>
  Copy into ticket description
</button>

// isAnalystOrAbove trigger-button wiring to reuse for each gap-fill button's onClick
} else if (isAnalystOrAbove) {
  body = (
    <button type="button" onClick={() => void start()} className={SECONDARY_BTN_CLASS}>
      {triggerLabel}
    </button>
  );
```
The gap-fill row calls `useExplainStream('vuln', v.id ?? idOrCve)` / `useExplainStream('remediation-guidance', v.id ?? idOrCve)` directly (imported from `frontend/src/lib/ai/use-explain-stream`, the same hook `AiExplanationSection` already uses internally at line 160) — **bypassing `AiExplanationSection` entirely**, not adding a new callback-up prop to it. This is a deliberate architectural contrast with Phase 25's `onCopyToDescription` prop (which DID add a new prop to `AiExplanationSection`): the gap-fill row is fully local to `drill-content.tsx`/`drill-panel-mobile.tsx`, since it needs its own compact one-line-caption chrome (27-UI-SPEC.md §4), not `AiExplanationSection`'s full-card `DegradedCard` treatment.

**Section placement precedent** (verified, lines 289-339): the file already mounts `AiExplanationSection` twice (`resourceType="vuln"` at 293-295, `resourceType="remediation-guidance"` at 332-339) with distinct `headingId`s — confirms the codebase's established convention of "one shared component, multiple mounts, no id collision," relevant context even though the gap-fill row itself is NOT a third `AiExplanationSection` mount.

---

### `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` — mirror Title `Input` + gap-fill row

**Analog:** the file's own description `Textarea` block inside `Drawer.NestedRoot`, lines 148-168 — confirmed once again a genuinely SEPARATE code path from desktop (never imports `ConfirmModal`; builds its own `role="dialog"` markup)

**Current code to mirror** (verified, lines 142-168):
```tsx
<div className="mt-4">
  <TicketProviderPicker
    value={ticketProvider}
    onChange={onProviderChange}
  />
</div>
{/* Phase 25 (AIR-02): mirrors the desktop ConfirmModal insertion -- same
    relative position (between the provider picker and the action row),
    same LOCKED caption/placeholder. Mobile builds its own Drawer.NestedRoot
    markup (Pitfall 5), never imports ConfirmModal. */}
<div className="mt-4">
  <label
    htmlFor="ticket-description-textarea-mobile"
    className="mb-1 block text-xs font-medium text-text-muted"
  >
    Pre-filled from remediation guidance — review and edit before creating.
  </label>
  <Textarea
    id="ticket-description-textarea-mobile"
    value={description}
    onChange={(e) => onDescriptionChange(e.target.value)}
    placeholder="No remediation guidance yet — add a description or leave blank."
    rows={4}
  />
</div>
```
The `renderConfirm` callback destructuring at lines 103-112 (`{ open: confirmOpen, onConfirm, onCancel, cveLabel, ticketProvider, onProviderChange, description, onDescriptionChange }`) must add `title, onTitleChange` to the destructured args, and a new Title `Input` block renders between the `TicketProviderPicker` div and this description block — same relative position, same `-mobile` id suffix convention (`ticket-title-input-mobile`, mirroring `ticket-description-textarea-mobile`).

---

### `frontend/src/lib/mutations/use-create-ticket.ts` — add `title?: string`

**Analog:** same file, `description?: string`, line 18

**Current** (verified, lines 7-19):
```typescript
export type CreateTicketRequest = {
  vulnerability_ids: string[];
  provider: TicketProvider;
  project_key?: string;
  assignee?: string;
  due_days?: number;
  // Phase 25 (AIR-02, Plan 06 backend contract): analyst-reviewed
  // description, threaded verbatim into TicketCreateRequest.description
  // ...
  description?: string;
};
```
Add `title?: string;` as a sibling. The mutation body (lines 41-58, `useMutation<CreateTicketResponse, Error, CreateTicketRequest>({...})`, `mutationFn` at 44-49) needs **zero change** — `JSON.stringify(body)` already serializes whatever shape `CreateTicketRequest` declares, exactly as it did for `description` in Phase 25.

---

### `frontend/src/components/vulnerabilities/drill-panel.test.tsx` — extend

**Analog:** the file's own `describe('ticket-create dialog description textarea (AIR-02)', ...)` block, lines 280-339 — 4 tests to mirror, PLUS one test whose behavior Phase 27 directly changes:

```tsx
it('renders the Textarea in the confirm dialog with the LOCKED caption + placeholder, starting empty', () => {
  render(<DrillPanel cveId="CVE-2024-3094" />);
  fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
  expect(screen.getByText('Pre-filled from remediation guidance — review and edit before creating.')).toBeInTheDocument();
  const textarea = screen.getByPlaceholderText('No remediation guidance yet — add a description or leave blank.') as HTMLTextAreaElement;
  expect(textarea.value).toBe('');
});

it('typing into the textarea and confirming threads the description into createTicket.mutateAsync body (not only the DOM)', async () => {
  ...
  expect(mockMutateAsync).toHaveBeenCalledWith(expect.objectContaining({ description: 'Patch xz to 5.4.x per vendor advisory.' }));
});
```

**The one existing test Phase 27 directly interacts with (Pitfall 2's exact reproduction path, verified lines 324-339):**
```tsx
it('copying remediation guidance in via "Copy into ticket description" pre-fills the dialog textarea', () => {
  const summary = 'Cited remediation steps, plain text.';
  mockUseExplainCache.mockImplementation((resourceType: string) =>
    resourceType === 'remediation-guidance'
      ? { data: { cached: true, summary, business_risk: 'n/a', citations: [], grounded: true }, ... }
      : { data: { cached: false }, ... },
  );
  render(<DrillPanel cveId="CVE-2024-3094" />);
  fireEvent.click(screen.getByRole('button', { name: 'Copy into ticket description' }));
  fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
  const textarea = screen.getByPlaceholderText(...) as HTMLTextAreaElement;
  expect(textarea.value).toBe(summary);
});
```
This test currently opens the confirm dialog AFTER clicking "Copy into ticket description" in the main panel — once Phase 27's auto-compose exists, this exact sequence becomes the live reproduction of Pitfall 2. Whatever guard mechanism the plan adopts (Pattern 4's `resourceId`-keyed ref, recommended), this test's expected outcome needs an explicit, deliberate assertion updated to match the chosen behavior — it will not silently keep passing if the compose-on-open logic runs unconditionally on first dialog open (which would overwrite `summary` with the full composed body, breaking this test's current expectation of an exact-string match).

**New tests to add** (title field + gap-fill row + composed-once guard + cross-vuln reset), no existing test file has an exact analog for the guard/cross-vuln case since this is new behavior — closest structural sibling is this same file's re-render-on-prop-change pattern used elsewhere in the suite for `idOrCve` changes (verified via the mocked `useVulnerabilityDetail`/`cve_id: 'CVE-2024-1000'` override pattern at line 177, used for a different existing test).

---

### `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` — extend

**Analog:** the file's own description-textarea tests, lines 220-276:
```tsx
it('renders the description Textarea between the TicketProviderPicker and the Cancel/Confirm row, with LOCKED caption + placeholder, starting empty', () => { ... });
it('typing into the mobile textarea and confirming threads the description into createTicket.mutateAsync body', () => { ... });
it('leaving the mobile textarea blank threads description: undefined into the mutation body (mobile mirrors desktop, never a silent skip)', () => { ... });
```
Mirror this same 3-test shape for the Title `Input`, substituting the mobile-suffixed id (`ticket-title-input-mobile`) and asserting on `mockMutateAsync`'s `title` key instead of `description`. The file's existing mock setup (`useProvidersMock`, `mockMutateAsync`, `mockMatchMedia`, lines 60-95) needs no change — same fixtures cover the new field.

---

### `frontend/src/components/vulnerabilities/drill-panel.tsx` / `drill-panel-mobile.tsx` — flagged, no code change expected (Pitfall 3)

**Analog:** the `<DrillContent>` mount sites — `drill-panel.tsx:103` (`{renderContent ? renderContent(...) : <DrillContent idOrCve={effectiveId} onClose={close} />}`) and `drill-panel-mobile.tsx:100-102` (identical shape)

Neither mount passes a `key={effectiveId}` prop, so React reconciles `DrillContent` as the same instance across a vuln switch — confirmed by direct read of both files in full. RESEARCH's recommended fix (Pattern 4) resolves this **entirely inside `drill-content.tsx`**'s own composed-once guard (the `ref` compares the *current* `v.id ?? idOrCve` against what it last composed for, recomposing on mismatch) — no `key` prop change is required at either mount site. This row exists in the classification table purely so the planner is aware of where the underlying condition lives, corroborating RESEARCH.md's Pitfall 3 exactly as described, with no additional code-change recommendation beyond what `drill-content.tsx`'s own pattern assignment above already covers.

**Corroborating source of the cross-vuln trigger** (verified, `page.tsx:116-122`):
```tsx
const handleRowOpen = useCallback((idOrCve: string) => {
  const sp = new URLSearchParams(params?.toString() ?? '');
  sp.set('cve', idOrCve);
  sp.set('open', 'drill');
  const qs = sp.toString();
  router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
}, [router, pathname, params]);
```
Confirms clicking a different row simply flips the `cve` URL param — no close-then-reopen step — exactly the sequence Pitfall 3 describes.

---

## Shared Patterns

### The `title`-mirrors-`description` discipline
**Source:** `backend/app/ticketing/schemas.py:70-80` (field+validator) + `backend/app/ticketing/service.py:222-230` (fallback expression)
**Apply to:** the new `title` field + its `create_tickets()` fallback
Same `Field` + `field_validator` + ternary-fallback shape throughout; the ONLY deliberate deviation anywhere in this discipline is `max_length` (255, not 10000) — every other line is a mechanical copy with names swapped.

### Provider dispatch is already fully normalized — zero per-provider code needed
**Source:** `backend/app/ticketing/dispatch.py:23-41` (Protocol) + the 3 adapters
**Apply to:** nothing new to build; corroborates that `task_name`'s single call site (`service.py:234`) is the only place needing a change
Re-confirmed this session directly against all three concrete clients (`jira_client.py`, `asana_client.py`, `github_client.py`) — no adapter or client file needs to change for `title` to reach `name`/`summary`/`title` correctly.

### RBAC + key-gating for any paid-call trigger
**Source:** `frontend/src/components/ai/ai-explanation-section.tsx:148-163` (`isAnalystOrAbove`, `keyConfigured`) + `:296-309,343-349` (the gating branches)
**Apply to:** the new gap-fill row's two buttons in both `drill-content.tsx` and `drill-panel-mobile.tsx`
Reuse `useAiStatus()` (for `keyConfigured`) and `useAuth().role` (for `isAnalystOrAbove`) exactly as already established — no new "can this user spend AI budget" check should be written from scratch.

### `AnalyzingIndicator` reuse (post-export)
**Source:** `frontend/src/components/ai/ai-explanation-section.tsx:104-113` (post-`export`) + its existing call site at line 227
**Apply to:** the gap-fill row's in-flight state in both dialogs
One sanctioned pulsing-dot affordance app-wide (D-12 lineage) — never a second spinner component.

### Never-auto-submit guarantee
**Source:** `frontend/src/components/ui/ConfirmModal.tsx:56-60` (the ONLY `useEffect`, a `.focus()` call) + line 102 (`onClick={onConfirm}` on the confirm `<button>`)
**Apply to:** confirms that neither the compose-on-open mechanism nor the gap-fill row introduces any new submit path
```tsx
useEffect(() => {
  if (open && !isMobile) { confirmRef.current?.focus(); }
}, [open, isMobile]);
...
<button ref={confirmRef} onClick={onConfirm} disabled={confirmDisabled} ...>
```
No `<form>` wraps the Title `Input`/Description `Textarea`, so Enter-to-submit is structurally impossible in either field — verified directly, matching RESEARCH's claim exactly.

### Mass-assignment defense on new request-body fields
**Source:** `backend/app/ticketing/schemas.py:63` (`model_config = {"extra": "forbid"}`, class-level)
**Apply to:** the new `title` field
Already covers any new field added to `TicketCreateRequest` — no per-field allowlist code needed, confirmed by re-reading the class declaration directly.

---

## No Analog Found / Genuinely Novel Logic

| File / Symbol | Role | Data Flow | Reason |
|---|---|---|---|
| `compose-ticket-draft.ts`'s actual multi-section conditional builder (the CONTENT of `composeTicketDescription`, not its module shape) | utility | transform | No existing module composes a multi-section, conditionally-included plain-text body from 3 independent cache states. The nearest precedent (`_build_task_description`, Python, server-side, unconditional fields) establishes VOICE only, not the conditional-inclusion logic. Use RESEARCH.md Pattern 1's fully-worked function as the starting point rather than searching further. |
| The composed-once-guard mechanism itself (`useRef` keyed to `resourceId`, re-comparing on every `confirmOpen` transition) | component logic | UI composition | No existing effect in this codebase guards "compose once per entity, reset on entity change" — the closest structural sibling (`drill-content.tsx:103-105`'s focus-on-mount effect) shares only the "effect keyed to `idOrCve`" dependency-array idiom, not the compare-and-conditionally-skip logic. This is new, RESEARCH-recommended (Pattern 4), not precedented. |
| The gap-fill row's compact "0-2 buttons, 8px gap, individually replaced by an inline one-line caption on error" layout | component (JSX layout) | UI composition | Every existing per-resource trigger (`ai-explanation-section.tsx`'s own `isAnalystOrAbove` branch, lines 343-349) renders a single full-width button in its own dedicated section — there is no existing "two compact buttons side by side, each independently replaceable" layout to copy verbatim. `CopyToDescriptionButton`'s chrome (text-button styling) is reusable; the two-button row arrangement itself is new. |
| `frontend/src/lib/tickets/` as a directory | — | — | Does not exist yet (confirmed via `ls`) — a new sibling to the existing `frontend/src/lib/ticketing/` (singular "provider identifier" domain vs. plural "draft composition" domain); not a naming collision. |

---

## Metadata

**Analog search scope:** `backend/app/ticketing/` (all 7 files), `backend/tests/test_ticketing_dispatch.py`, `frontend/src/components/vulnerabilities/` (all 8 non-test + 3 test files), `frontend/src/components/ai/` (both non-test files), `frontend/src/components/ui/{input,textarea,ConfirmModal}.tsx`, `frontend/src/lib/mutations/use-create-ticket.ts`, `frontend/src/lib/queries/{use-explain-cache,use-vulnerability-detail,keys}.ts(.test.ts)`, `frontend/src/lib/ai/use-explain-stream.ts`, `frontend/src/lib/ticketing/providers.ts`, `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`

**Files read directly this session:** 24 source files in full (or full relevant function/section) + 2 test files (targeted sections) + 2 planning docs (CONTEXT.md, UI-SPEC.md, full) + RESEARCH.md (full, both halves) + 25-PATTERNS.md (full, the base map extended here)

**Corroboration method:** every RESEARCH.md claim used in this map was independently re-derived from a direct `Read` of the cited file/line range in this session (not re-trusted from RESEARCH.md's own citations) — all 5 pitfalls, all 4 patterns, and the Recommended Project Structure table's file list were checked against actual current source. Zero corrections were needed; every line number RESEARCH.md cited matched exactly what this session's direct reads found.

**Pattern extraction date:** 2026-08-01
