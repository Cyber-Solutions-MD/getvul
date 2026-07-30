# Phase 25: Asset-Aware Remediation Guidance - Research

**Researched:** 2026-07-30
**Domain:** Cite-or-refuse LLM output grounding (backend Python/FastAPI/Pydantic) + dangerous-content post-generation gating + a thin frontend pre-fill seam. Extends Phase 24's proven AI scaffold; does not introduce a new stack.
**Confidence:** HIGH (all six research questions resolved by direct codebase reads; one MEDIUM-confidence area — the exact dangerous-pattern list — is inherently a judgment call CONTEXT.md explicitly delegates to plan time)

## Summary

Phase 25 is a narrow, well-precedented extension of Phase 24's AI scaffold, not a new engineering risk surface. Every one of the six research questions resolved to a concrete, code-verified answer. The two genuinely new architectural facts this research surfaces — facts CONTEXT.md left open and the planner needs before writing tasks — are: **(1)** the D-01 "non-generic present" refuse predicate must treat empty string as absent (not just `None`), because `sync.py`'s upsert logic (`getattr(v, "remediation_action", None) or v.remediation_info`) makes `remediation_action` and `remediation_info` byte-identical for 5 of 6 connectors, and Rapid7's own fetch-failure path persists a literal `""`; and **(2)** the D-04 dangerous-pattern gate cannot be implemented as a route-layer filter alone — because `_run_explain_stream()` caches and audits a response as `"ok"` *before* yielding the `done` SSE event, a route-layer-only interception would still leave dangerous content retrievable via the existing GET cache-check endpoint. The gate must be a small, additive, default-`None` optional parameter on `_run_explain_stream()` itself, mirroring exactly how `allowed_source_fields` was pre-built as an extension point in Plan 04 for Plan 08's later use — this is the one place this phase must touch shared Phase 24 code, and it is provably backward-compatible (a no-op for the vuln/host/remediation-posture views).

Research also surfaces that "OS/package-aware" grounding requires a **brand-new, per-finding grounding query** — neither `get_vulnerability()` (no OS columns) nor `get_remediation_group()` (cross-asset CVE aggregate, the wrong scope for a single finding's drill panel) fits. AIR-02's pre-fill seam is real but currently a dead end: the backend `TicketCreateRequest` schema has no `description` field today, and `create_tickets()` always auto-builds the ticket body server-side — pre-filling a textarea the backend silently discards would ship a UI lie. This requires a small, precise backend schema + service change, not just a frontend textarea.

**Primary recommendation:** Build one new per-finding grounding query (`get_remediation_guidance_context`), one new schema variant (`ExplainRemediationGuidanceResponse`, zero new fields — reuses `summary`/`business_risk`/`citations`/`grounded`), a route-layer-only D-01 pre-generation gate (zero engine changes), a small additive `dangerous_pattern_check` optional parameter on `_run_explain_stream()` for D-04, and a `description: str | None` field threaded through the existing single-vulnerability ticket-create path — replacing (not appending to) the auto-built description when the analyst supplies one.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Remediation grounding-record assembly (finding + asset OS/package join, tenant-scoped) | API / Backend | Database / Storage | New narrow SQLAlchemy query in `grounding.py`, mirrors `get_asset_posture()`'s "SELECT only what's allowlisted" discipline |
| D-01 pre-generation refuse predicate (non-generic-present check) | API / Backend | — | Pure deterministic Python function, no model call, runs in the route before any dispatch |
| Prompt construction (untrusted-content-as-data) | API / Backend | — | New `build_explain_remediation_guidance_prompt()`, same contract as existing builders |
| D-04 post-generation dangerous-pattern gate | API / Backend | — | Regex scan of a validated Pydantic object's text fields, inside the shared engine (must run before cache write) |
| SSE streaming engine | API / Backend | — | `_run_explain_stream()` reused, extended by one optional parameter |
| Cache / budget / audit | API / Backend | Database / Storage (Redis + Postgres) | 100% reused unchanged |
| Draft-ticket description state (copy-in, edit, clear) | Browser / Client | — | New `useState` in `DrillContent`, threaded through `renderConfirm` for mobile |
| Ticket creation with custom description | API / Backend | Browser / Client | New `description` field on `TicketCreateRequest` (backend) + `CreateTicketRequest` (frontend mutation body) |
| Citation rendering (two-tier tinting) | Browser / Client | — | `AiExplanationCitations` reused unchanged, zero new props |
| Feedback capture | API / Backend | Database / Storage | Already fully resourceType-agnostic (verified — see Pattern 4); zero changes |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Grounding source of truth for remediation is the finding's own scanner text: `Vulnerability.remediation_action` (primary) and `remediation_info` (fallback). The refuse predicate is a deterministic pre-generation gate: generate cited steps only when `remediation_action` OR `remediation_info` is present AND non-generic (not empty, not the `"No remediation info available"` placeholder the ticketing layer emits, above a small minimum content length). Otherwise refuse with a typed "insufficient evidence" state — no model call is spent. Belt-and-suspenders with the output-schema `grounded` flag (mirrors Phase 24 D-24). Reversibility: costly.
- **D-02:** The refuse predicate is enforced in two independent layers: (1) the deterministic input gate above, and (2) the response-schema `grounded: false` path the model can still take. A refusal from either layer renders the same honest "not enough vendor guidance to recommend a fix" card, visually distinct from a system error (reuses Phase 24's grounded-false treatment, D-24).
- **D-03:** Cited vendor text is rendered verbatim and visually first (the `scanner_verbatim` tier), with any AI-authored interpretation clearly marked as the `ai_interpreted` tier — reusing Phase 24's inline two-tier citation component (D-13/D-14) unchanged. "Cite before interpret" is the ordering contract for AIR-01 success criterion 1.
- **D-04:** A post-generation dangerous-pattern gate scans the produced steps against a maintained denylist (e.g. `rm -rf`, `DROP TABLE`, disable firewall/EDR, `dd`, `mkfs`, `chmod 777`, `curl … | sh`, and similar destructive/security-disabling patterns — exact list finalized at plan time). On any hit the ENTIRE guidance is refused and a typed safety-refusal state is shown; a partially-dangerous step set is never rendered. The hit is audited (distinct status). Enforced as a code gate (schema-contract + regex), NOT prompt wording. Reversibility: costly.
- **D-05:** The denylist is a maintained constant/module (single source of truth, unit-tested with positive + negative cases incl. obfuscation-resistant matching where cheap), so Phases 26–27 that also surface AI-authored text can reuse it. Exact patterns + case/whitespace normalization are a plan-time detail.
- **D-06:** Remediation guidance is a SEPARATE "Remediation guidance" section/action in the drill panel — its own trigger and its own cite-or-refuse output — distinct from Phase 24's "Explain this vuln" and the Phase-24 per-remediation posture summary (`explain_remediation`/`get_remediation_group`, D-16). Both coexist. Reuses the exact AI section chrome + two-tier citation component built in Phase 24 (no re-styling). Reversibility: costly.
- **D-07:** All Phase 24 UI-state contracts are inherited unchanged for this new section: "Analyzing…" then replay (D-12), no-key state (D-23), 429/busy (D-25), Analyst+ triggers / Viewer cached-only (D-17), thumbs feedback capture (D-21), audit into the existing pane (D-27). No new state vocabulary is invented. (Note: the approved 25-UI-SPEC.md clarifies this as "no new inherited-state mechanism is reinvented" — it separately defines 2 new terminal states, insufficient-evidence-immediate and safety-refusal, layered on top of the inherited mechanism. See Pattern 3/7 below.)
- **D-08:** Guidance populates the description field of the EXISTING drill-panel ticket-create flow (the affordance from Phase 23 / D-14). The analyst reviews and edits the pre-filled description in that same create dialog before anything is created. Nothing is auto-created. Reversibility: reversible.
- **D-09:** Phase 25 pre-fills the description only. Full auto-drafting (AI-authored title + remediation + asset-context, Jira/Asana field mapping, the richer draft surface) is explicitly Phase 27 (AID-01) and must NOT be built here. Reversibility: reversible (scope fence, not code).
- **D-10:** Reuse `_run_explain_stream()` and the Phase 24 grounding/cache/budget/audit/RBAC layers unchanged; Phase 25 adds only a new remediation grounding-record assembler + `ExplainRemediation…`-style response schema variant + prompt builder, following the exact per-view-variant pattern Phase 24 established for host/remediation (24-08). The asset-fact ("OS/package-aware") inputs come from the same allowlisted asset fields Phase 24's `HOST_ALLOWLIST`/`get_asset_posture()` already vet — owner-PII fields stay excluded (Phase 24 D-15 defense-in-depth). Exact field list is a researcher/planner detail. Reversibility: costly.

### Claude's Discretion

- Exact denylist patterns + normalization strategy (D-04/D-05).
- Exact minimum-content-length / generic-placeholder detection for the refuse predicate (D-01).
- The precise OS/package asset-fact field list feeding grounding, within the existing allowlist (D-10).
- Cache TTL window and prompt-version hashing are inherited from Phase 24 conventions (D-18/D-19/D-20) — no new decision.
- Exact drill-panel placement/ordering of the new Remediation section — a UI-SPEC decision (resolved: immediately after the raw "Remediation" section, before "Activity" — see 25-UI-SPEC.md).

### Deferred Ideas (OUT OF SCOPE)

- Full AI ticket auto-drafting (AI-authored title/remediation/asset-context, Jira/Asana field mapping, richer draft surface) → Phase 27 (AID-01). Phase 25 pre-fills the description field only.
- Prioritization narrative ("what to fix first and why") → Phase 26 (AIP).
- AI usage/cost dashboard, eval harness, red-team CI → Phase 28.
- Non-English remediation guidance → out of milestone scope (Phase 24 D-28 English-only carried forward).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AIR-01 | An analyst can get asset-aware remediation guidance that cites the scanner's own solution text and refuses (cites insufficient evidence) rather than inventing an ungrounded fix | Pattern 1 (refuse predicate + connector field reality), Pattern 2 (OS/package allowlist), Pattern 3 (dangerous-pattern gate), Pattern 4 (exact reuse seams) |
| AIR-02 | Remediation guidance can populate a draft ticket description for the analyst to review | Pattern 5 (backend schema gap + frontend wiring seam — the load-bearing finding: today's backend silently discards any client-supplied description) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Directive | Applies to Phase 25 |
|-----------|---------------------|
| Read `sketch-findings-getvul` skill before any frontend work | Already satisfied — 25-UI-SPEC.md (approved) encodes the relevant `state-patterns.md` (refuse/insufficient-evidence/safety states) and `copy-voice.md` (honest refusal copy) guidance. This research does not re-derive it; treat 25-UI-SPEC.md as authoritative for all copy/visual decisions. |
| Don't substitute fonts (Inter + JetBrains Mono locked) | No new typography introduced this phase (25-UI-SPEC.md confirms: identical scale to Phase 24, no new size/weight). |
| Don't pick hex colors freehand | The one new color usage (danger/red for the safety-refusal card) reuses the existing `--color-danger`/`--color-danger-soft` tokens already established in `ticket-provider-picker.tsx`'s error alert — no new hex value. |
| Don't ship a screen without empty/loading/error states | 25-UI-SPEC.md's state-coverage table explicitly covers empty/loading/error/populated/partial/overflow/long-text for both the new section and the new textarea. |
| Backend: FastAPI + Postgres + Redis | No new dependency — Phase 25 adds Python modules/routes only, using the already-provisioned Postgres (AuditLog) and Redis (cache) exactly as Phase 24 established. |
| Frontend: Next.js 15 App Router + React 19 + TS 5.5 + Tailwind 3.4 | No framework change; one new shadcn primitive (`textarea`, official registry, already cleared in 25-UI-SPEC.md's Registry Safety table). |

## Standard Stack

### Core

No new external library is required. Phase 25 is entirely new application code (Python modules/routes, one new schema, one new frontend section, one new shadcn primitive) reusing Phase 24's already-installed `anthropic==0.120.2` SDK, `redis.asyncio`, and `pydantic` — verified via `git diff`-level reads of `backend/app/ai/*` and `backend/pyproject.toml`; no version bump needed for any of these.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.120.2 (already installed) | Model calls via `_run_explain_stream()` | [VERIFIED: codebase — 24-04-SUMMARY.md, `backend/pyproject.toml`] Reused unchanged; Phase 25 never imports the SDK directly |
| pydantic | already installed (v2) | New `ExplainRemediationGuidanceResponse` schema | [VERIFIED: codebase — `backend/app/ai/schemas.py`] Same `BaseModel`/`Field` conventions as every existing schema variant |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `re` (stdlib) | n/a | Dangerous-pattern regex matching (D-04) | New `backend/app/ai/safety.py` module — no third-party pattern-matching library needed for this scope (see Don't Hand-Roll) |
| shadcn `textarea` | official registry | AIR-02 description pre-fill field | `npx shadcn add textarea` — already cleared by 25-UI-SPEC.md's Registry Safety table; [CITED: 25-UI-SPEC.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-written regex denylist (`app/ai/safety.py`) | A dedicated command-safety crate/library (e.g. Rust-based `destructive_command_guard`, AST-based shell parsing per the CARE paper) | Those tools are built to intercept *live, agent-typed shell commands* before execution — a much harder problem (obfuscation via base64/variable-splitting/command substitution) than GetVul's actual need: scanning already-schema-validated LLM *prose* for a small, known set of destructive phrases. Adopting a full command-canonicalization engine here would be substantial unused complexity for a text-content scan. See Pattern 3 and Don't Hand-Roll. |
| A route-layer SSE event filter for D-04 | Extending `_run_explain_stream()` with an optional parameter | A route-layer-only filter cannot prevent the dangerous payload from being cached (the engine calls `set_cached()` and audits `status="ok"` *before* yielding `done`) — the GET cache-check route would still serve it on next page load. This is a hard correctness requirement, not a style preference. See Pattern 3. |

**Installation:** None required — no new backend or frontend package.

**Version verification:** N/A — no new package version to verify. `anthropic==0.120.2` and the installed `pydantic`/`redis` versions were already verified current as of Phase 24 (2026-07-28/29, per 24-01-SUMMARY.md and 24-04-SUMMARY.md); nothing in Phase 25's scope requires re-verification.

## Architecture Patterns

### System Architecture Diagram

```
Analyst clicks "Get remediation guidance" (drill panel, single finding_id)
        |
        v
[Frontend] useExplainStream('remediation-guidance', finding_id)
        |  POST /api/v1/ai/explain-remediation-guidance/{finding_id}
        v
[Route: explain_remediation_guidance.py]
        |
        1. get_remediation_guidance_context(db, tenant_id, finding_id)  -- NEW query
        |     -- joins Vulnerability + Asset, tenant-scoped, narrow SELECT
        |     -- returns None -> 404 (foreign tenant / no such finding)
        v
        2. has_actionable_remediation_text(record)   -- NEW, D-01 pre-generation gate
        |     -- deterministic, zero model calls
        |
        +-- False --> audit(status="ungroundable") --> synthesize ONE SSE frame
        |               {type:"error", kind:"grounded_false"} --> return
        |               (same card as state 8; analyst never knows which layer fired)
        |
        +-- True ---> _run_explain_stream(..., dangerous_pattern_check=contains_dangerous_pattern)
                        |  -- REUSED UNCHANGED except one new optional param (default None,
                        |     no-op for vuln/host/remediation-posture views)
                        v
                      Anthropic call --> schema validate --> business-rule recheck
                        --> grounded check --> leak-marker check (existing, W3)
                        --> dangerous_pattern_check(candidate)   -- NEW, D-04 post-generation gate
                        |
                        +-- Match --> audit(status="unsafe_denylisted") -->
                        |               yield {type:"error", kind:"unsafe"}  -- NEW SSE kind
                        |               (skips set_cached() entirely -- never retrievable)
                        |
                        +-- Clean --> set_cached() --> audit(status="ok") --> stream summary_delta*
                                        --> yield {type:"done", ...}
        |
        v
[Frontend] AiExplanationSection (resourceType='remediation-guidance')
        |  renders via AiExplanationCitations (REUSED, zero new props)
        |  + "Copy into ticket description" button (NEW, local state only)
        v
[Frontend] DrillContent's ticketDescription state --> ConfirmModal / renderConfirm
        |  Textarea (NEW shadcn primitive), pre-filled, freely editable
        v
        Analyst clicks "Create ticket" --> createTicket.mutateAsync({..., description})
        |  POST /api/v1/tickets  (body.description: str | None -- NEW field)
        v
[Backend] create_tickets() --> notes = request.description.strip() or _build_task_description(vuln, hostname)
        |  -- WYSIWYG: analyst-supplied text REPLACES the auto-built description when present
        v
        client.create(task_name, notes, ...)  -- Jira/Asana/GitHub, unchanged
```

### Recommended Project Structure

```
backend/app/ai/
├── grounding.py            # + get_remediation_guidance_context() + has_actionable_remediation_text()
├── schemas.py               # + ExplainRemediationGuidanceResponse (0 new fields)
├── prompt_builder.py         # + REMEDIATION_GUIDANCE_ALLOWLIST + build_explain_remediation_guidance_prompt()
├── explain.py                 # + ONE new optional param on _run_explain_stream() (dangerous_pattern_check)
├── safety.py                   # NEW module: DANGEROUS_PATTERNS + contains_dangerous_pattern()
└── api/v1/ai/
    └── explain_remediation_guidance.py   # NEW thin route, mirrors explain_vuln.py's shape

backend/app/ticketing/
├── schemas.py               # + TicketCreateRequest.description: str | None
└── service.py                 # 1-line change to create_tickets()'s notes= assignment

frontend/src/lib/ai/
└── use-explain-stream.ts     # + 'unsafe' member on ExplainStreamState's error.kind union (additive)

frontend/src/lib/queries/
└── use-explain-cache.ts       # + optional groundable?: boolean on the cached:false branch (additive)

frontend/src/components/vulnerabilities/
└── drill-content.tsx           # + new <section> (Remediation guidance) + description textarea state,
                                   threaded through renderConfirm for drill-panel-mobile.tsx
```

---

### Pattern 1: The D-01 refuse predicate must treat empty string as absent, and remediation_action/remediation_info are identical for 5 of 6 connectors

**What:** The deterministic "non-generic present" gate CONTEXT.md D-01 requires.

**Evidence [VERIFIED: codebase]:**

`backend/app/connectors/schemas.py`'s `NormalizedVulnerability` dataclass has **no declared `remediation_action` field at all** — only `remediation_info: str | None = None`. `remediation_action` is an ad-hoc Python attribute, set on the instance **only by CrowdStrike** (`backend/app/connectors/crowdstrike.py:405`):
```python
vuln.remediation_action = remediation_action or (f"Update {product} to the latest version" if product else "")
```
This can be: real CrowdStrike remediation-cache text, a **synthesized** `"Update {product} to the latest version"` string (not vendor solution text — GetVul's own connector invents it from the product name), or `""`.

The persistence layer (`backend/app/connectors/sync.py:333,355`) is what actually populates the DB column for **every** connector:
```python
existing.remediation_action = getattr(v, "remediation_action", None) or v.remediation_info
```
Since Nessus, Defender, Qualys, Wiz, and Rapid7 never set the ad-hoc `remediation_action` attribute, `getattr(..., None)` returns `None` for all of them, so **`Vulnerability.remediation_action` collapses to `Vulnerability.remediation_info`'s exact value for 5 of the 6 connectors.** Checking `remediation_action OR remediation_info` is therefore only meaningfully different from checking `remediation_info` alone for CrowdStrike rows.

Confirmed empty-string leak: `backend/app/connectors/rapid7.py:230-233`:
```python
try:
    remediation_info = await self._fetch_vuln_solutions(vuln_id)
except httpx.HTTPStatusError:
    remediation_info = ""
```
and `_fetch_vuln_solutions()` itself (`rapid7.py:141-148`) does `"; ".join(s.get("summary", "") for s in solutions if s.get("summary"))`, which is **also `""`** when Rapid7's own solutions endpoint returns zero solutions with a non-empty summary (not rare for low-severity findings). Because `sync.py`'s `or` chain treats `""` as falsy only when the LEFT side is being tested, the persisted value ends up literally `""` — **`is not None` is not sufficient**; a naive check would wrongly treat an empty-string row as "present."

Qualys is defensive by contrast: `_kb_solution()` (`qualys.py:543-552`) only returns a non-`None` value `if val and isinstance(val, str)`, so an empty/missing Qualys `SOLUTION` field already normalizes to `None` before it reaches the DB. Nessus (`nessus.py:287`) does the same (`remediation_info=solution or None`).

The ticketing layer's exact placeholder string is confirmed at `backend/app/ticketing/service.py:135`:
```python
remediation = vuln.remediation_action or vuln.remediation_info or "No remediation info available"
```
— this string is only ever **computed at read time** for a ticket description/title; it is never written back into `Vulnerability.remediation_action`/`remediation_info`, so it cannot leak into the DB column the new grounding query reads. Other ephemeral fallback strings exist in the same file (`"No remediation info"`, `"Unknown"`) but are likewise never persisted.

**Recommendation (concrete, ready to implement):**

```python
# backend/app/ai/grounding.py (or a small shared helper)
_GENERIC_REMEDIATION_PLACEHOLDERS: frozenset[str] = frozenset({
    "no remediation info available",
    "no remediation info",
    "no remediation available",
    "unknown",
    "n/a",
    "none",
})
MIN_REMEDIATION_CHARS = 15  # excludes "Unknown"/"N/A"/"-" but passes a real short fix like "Upgrade to 1.3.2."

def has_actionable_remediation_text(remediation_action: str | None, remediation_info: str | None) -> bool:
    for raw in (remediation_action, remediation_info):
        if raw is None:
            continue
        text = raw.strip()
        if len(text) < MIN_REMEDIATION_CHARS:
            continue
        if text.casefold() in _GENERIC_REMEDIATION_PLACEHOLDERS:
            continue
        return True
    return False
```

**Open judgment call (flagged, not resolved by CONTEXT.md):** should CrowdStrike's synthesized `"Update {product} to the latest version"` count as "actionable" grounding? It contains a real, asset-specific product name (not a vacuous placeholder) but is GetVul's own connector's invention, not the vendor's solution text — arguably in tension with AIR-01's "cites the scanner's own solution text" framing. See Assumptions Log A1.

---

### Pattern 2: "OS/package-aware" requires a new grounding query — no existing Asset field carries installed-package data

**What:** The exact field list for the new remediation-guidance grounding record.

**Evidence [VERIFIED: codebase]:**

`backend/app/assets/models.py` has **no installed-package or software-inventory field** — confirmed by a full field listing (hostname, ip/mac addresses, `os_name`, `os_version`, `asset_type`, `device_category`, risk_score, ownership/MDM fields, tags — no `packages`/`installed_software` column exists anywhere on `Asset`). The closest thing to "package" context in this codebase is **per-finding**, on `Vulnerability`: `affected_product`, `affected_version`, `fixed_version`. So "OS/package-aware" in AIR-01's language resolves concretely to: OS context from `Asset.os_name`/`os_version`, package context from `Vulnerability.affected_product`/`affected_version`/`fixed_version` — a single-finding + single-asset join, not a per-asset software inventory.

Phase 24's existing allowlists don't cover this shape: `HOST_ALLOWLIST` (9 fields: hostname/os_name/os_version/device_category/risk_score/vuln_counts/tags/sla_breach/last_checkin_at) has no product/version fields; `REMEDIATION_ALLOWLIST`'s `AllowlistedAffectedAsset` (hostname/os_name/os_version/severity/exploit_available/cisa_kev) also has no product/version fields. `VULN_ALLOWLIST` has `affected_product`/`affected_version`/`fixed_version` but no `os_name`/`os_version` (the existing `get_vulnerability()` query, reused as-is by `explain_vuln.py`, only outer-joins `Asset.hostname` — confirmed at `backend/app/vulnerabilities/service.py:172-189`, no OS columns selected). **No existing query or allowlist has the exact field set AIR-01 needs — a new one is required**, which is exactly what CONTEXT.md D-10 anticipates ("Exact field list for OS/package context is a researcher/planner detail").

**Recommendation — new `REMEDIATION_GUIDANCE_ALLOWLIST` (12 fields, all already-precedented names, zero new owner-PII exposure):**

| Field | Source | Precedent |
|-------|--------|-----------|
| `cve_id`, `severity`, `exploit_available`, `cisa_kev` | `Vulnerability` | Already in `VULN_ALLOWLIST` verbatim |
| `remediation_action`, `remediation_info` | `Vulnerability` | D-01's grounding source of truth |
| `affected_product`, `affected_version`, `fixed_version` | `Vulnerability` | Already in `VULN_ALLOWLIST` verbatim — the "package" half of OS/package-aware |
| `asset_hostname` | `Asset` (joined) | Already in `VULN_ALLOWLIST` verbatim (named `asset_hostname`, not `hostname`, matching that precedent) |
| `os_name`, `os_version` | `Asset` (joined) | Already in `HOST_ALLOWLIST` verbatim — the "OS" half |

Explicitly **excluded** (Phase 24 D-15 defense-in-depth, owner PII): `assigned_user`, `directory_user`, `managed_by`, `building`, `serial_number`, `department` — none of these are selected by the new query at all (mirroring `get_asset_posture()`'s "never even fetched" discipline, not just a prompt-layer filter).

```python
# backend/app/ai/grounding.py
async def get_remediation_guidance_context(
    db: AsyncSession, tenant_id: uuid.UUID, finding_id: uuid.UUID,
) -> dict[str, Any] | None:
    """New, narrow, tenant-scoped single-finding+asset join -- NOT a reuse of
    get_vulnerability() (missing os_name/os_version) or get_remediation_group()
    (wrong scope: cross-asset CVE aggregate, not this one finding's own
    grounding). Returns None on a foreign-tenant/missing finding_id, matching
    every other grounding function's 404 contract."""
    result = await db.execute(
        select(
            Vulnerability.cve_id, Vulnerability.remediation_action, Vulnerability.remediation_info,
            Vulnerability.affected_product, Vulnerability.affected_version, Vulnerability.fixed_version,
            Vulnerability.severity, Vulnerability.exploit_available, Vulnerability.cisa_kev,
            Asset.hostname, Asset.os_name, Asset.os_version,
        )
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(Vulnerability.id == finding_id, Vulnerability.tenant_id == tenant_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return {
        "cve_id": row.cve_id, "remediation_action": row.remediation_action,
        "remediation_info": row.remediation_info, "affected_product": row.affected_product,
        "affected_version": row.affected_version, "fixed_version": row.fixed_version,
        "severity": row.severity, "exploit_available": row.exploit_available,
        "cisa_kev": row.cisa_kev, "asset_hostname": row.hostname,
        "os_name": row.os_name, "os_version": row.os_version,
    }
```

**Scope decision (recommended, follows directly from D-06):** this grounding is per-finding (single `Vulnerability` row + its one `Asset`), keyed by `finding_id` (UUID) — **not** `cve_id` like Phase 24's cross-asset `explain-remediation` route. Evidence: D-01 says "the finding's own scanner text" (singular); the drill panel operates on one vulnerability (`v.id`); 25-UI-SPEC.md's placement rationale is explicitly "the analyst reads the raw vendor text first [a per-finding section], then requests... the interpretation of exactly that text"; and D-06 explicitly requires this be distinct from `get_remediation_group()`. Route should therefore be `POST/GET /api/v1/ai/explain-remediation-guidance/{finding_id}`, mirroring `explain_vuln.py`'s UUID-keyed shape, not `explain_remediation.py`'s CVE-string-keyed shape.

---

### Pattern 3: The D-04 dangerous-pattern gate requires one small, additive change to `_run_explain_stream()` — a route-layer-only filter is unsafe

**What:** Where the post-generation safety gate must live, and why.

**Evidence [VERIFIED: codebase, `backend/app/ai/explain.py`]:** The engine's SUCCESS path is:
```python
payload = candidate.model_dump(mode="json")
await set_cached(redis_client, cache_key, payload)          # <-- cached HERE
cost = _estimate_cost_usd(model, raw_message.usage)
await _audit(..., status="ok", cost_estimate_usd=cost)        # <-- audited "ok" HERE
for chunk in _chunk_for_replay(candidate.summary):
    yield _sse_event({"type": "summary_delta", "text": chunk})
yield _sse_event({"type": "done", **payload})                 # <-- only THEN streamed
```
Caching and "ok" auditing both happen **before** any byte reaches the SSE stream. A hypothetical route-layer wrapper that inspects/swaps the outgoing `done` event would be too late: the dangerous payload is already sitting in Redis under a real, retrievable cache key, and the existing GET cache-check route (`get_explain_remediation_cache`-style, reused verbatim per D-10) would happily serve it on the next page load — directly violating D-04's "never cached as retrievable content." **This rules out a route-only fix.**

The codebase already has the exact analogous gate to mirror: `_contains_leak_marker(candidate, system_prompt)` (W3), checked in the main flow, in the same place, with the same terminal/no-retry/audited-distinctly treatment:
```python
if _contains_leak_marker(candidate, system_prompt):
    await _audit(..., status="injection_flagged")
    yield _sse_event({"type": "error", "kind": "grounded_false"})
    return
```
This proves the codebase's own convention for "a plain boolean/string-returning check on the validated object, called explicitly in the main flow, terminal, no retry, its own audit status" — exactly the shape D-04 needs, not a new exception-raising mechanism threaded through `recheck_business_rules()`.

**Recommendation:**

```python
# backend/app/ai/safety.py (NEW module -- D-05's "maintained constant/module")
import re

DANGEROUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rm -rf",                  re.compile(r"\brm\s+(-[a-z]*\s+)*-[a-z]*r[a-z]*f[a-z]*\b")),
    ("drop table/database",     re.compile(r"\bdrop\s+(table|database)\b")),
    ("truncate table",          re.compile(r"\btruncate\s+table\b")),
    ("mkfs",                    re.compile(r"\bmkfs\.\w+\b|\bmkfs\s")),
    ("dd to a block device",    re.compile(r"\bdd\s+if=\S+\s+of=/dev/")),
    ("chmod 777 / a+rwx",       re.compile(r"\bchmod\s+(-r\s+)?(777|a\+rwx)\b")),
    ("pipe download to shell",  re.compile(r"\b(curl|wget)\b[^|\n]*\|\s*(sh|bash|zsh)\b")),
    ("disable security control", re.compile(
        r"\bdisable\s+(the\s+)?(firewall|edr|antivirus|selinux|apparmor)\b"
        r"|\bsetenforce\s+0\b|\bufw\s+disable\b|\bstop\b.*\bfirewalld\b"
    )),
)

def contains_dangerous_pattern(candidate: "ExplainResponseBase") -> str | None:
    """Mirrors _contains_leak_marker's exact haystack composition (summary +
    business_risk + every citation.text) and normalization (lowercase +
    whitespace-collapse -- D-05's 'obfuscation-resistant where cheap', NOT
    full command-canonicalization -- see Don't Hand-Roll). Returns the
    matched pattern label for the audit row, or None."""
    haystack = " ".join([candidate.summary, candidate.business_risk, *(c.text for c in candidate.citations)])
    normalized = re.sub(r"\s+", " ", haystack.lower())
    for label, pattern in DANGEROUS_PATTERNS:
        if pattern.search(normalized):
            return label
    return None
```

```python
# backend/app/ai/explain.py -- ONE new optional parameter, default None (no-op
# for vuln/host/remediation-posture views, provably backward-compatible the
# same way Plan 04 proved allowed_source_fields=None is a no-op for the
# original vuln view before Plan 08 gave it a real value).
async def _run_explain_stream(
    db: AsyncSession, *, ..., 
    dangerous_pattern_check: Callable[[ExplainResponseBase], str | None] | None = None,
) -> AsyncIterator[bytes]:
    ...
    if _contains_leak_marker(candidate, system_prompt):
        ...  # unchanged

    if dangerous_pattern_check is not None:
        matched = dangerous_pattern_check(candidate)
        if matched is not None:
            await _audit(db, ..., status="unsafe_denylisted")   # NEW status, free-form JSONB, zero migration
            yield _sse_event({"type": "error", "kind": "unsafe", "matched_pattern": matched})  # NEW kind
            return
    # existing SUCCESS block (set_cached/audit "ok"/replay) unchanged, now unreachable on a hit
```

**This requires one frontend type change**, additive: `use-explain-stream.ts`'s closed union
`kind: 'busy' | 'grounded_false' | 'budget_exceeded' | 'unknown'` needs a 5th member, `'unsafe'` — needed because 25-UI-SPEC.md requires the safety-refusal card to be visually distinct (danger/red) from the insufficient-evidence card (neutral/violet), which the current 4-member closed set cannot express. No other resourceType will ever emit `'unsafe'` (only the new remediation-guidance route passes a real `dangerous_pattern_check`), so this is backward-compatible for vuln/host/remediation-posture.

**Prior art [CITED/MEDIUM confidence — WebSearch, cross-checked across 2 sources]:** A purpose-built tool for this exact class of problem, [Destructive Command Guard (dcg)](https://github.com/Dicklesworthstone/destructive_command_guard), targets the identical example commands CONTEXT.md D-04 lists (`rm -rf`, `git reset --hard`, `DROP TABLE users`) via a SIMD-accelerated dual regex engine with "smart context detection." The academic paper [CARE: Pre-Execution Command Verification for Shell-Executing LLM Agents](https://arxiv.org/html/2607.21642v1) (139 rules across MITRE ATT&CK / GTFOBins / manual categories) uses a much heavier canonicalization pipeline — quoting/escape normalization, bounded base64 decoding, command-substitution unwrapping — to resist obfuscation, but reports it is "weakest on escape/encoding variants" even with that investment, and achieves 0.91–1.82% false-positive rates even with an LLM-judge escalation step. Both tools solve a harder problem than GetVul's (intercepting *live, agent-typed* shell commands before execution, where an attacker actively tries to evade detection) — GetVul is scanning *already schema-validated LLM prose* for a small set of known-destructive phrases, so the proportionate response is the lightweight lowercase+whitespace-normalize regex approach above, not adopting either tool's full architecture. This is the answer to "cite prior art if useful": the prior art confirms GetVul's example patterns are industry-standard starting points, and confirms that even heavy investment in obfuscation resistance has real limits — D-05's "where cheap" qualifier is the right call, not a corner cut.

**Known tension to flag for the planner:** D-04's literal patterns (e.g., bare `rm -rf`) will also match if a legitimate, correctly-scoped vendor cleanup instruction happens to contain that substring (e.g., `rm -rf /opt/old-vulnerable-app-1.2.3/`) even when it appears inside a `scanner_verbatim`-tagged citation. D-04's text ("on any hit the ENTIRE guidance is refused") does not carve out an exception for scanner-sourced text — this is a deliberate, conservative, accepted false-positive tradeoff (the analyst-facing risk of pasting a destructive-looking command into a ticket is the same regardless of provenance), not a bug. Flagged in Assumptions Log A2.

**Testing (D-05 "unit-tested with positive + negative cases"):** mirror the existing `test_ai_prompt_builder.py` parametrized style. Positive: one case per pattern, plus obfuscated variants (mixed case, extra whitespace, split across `summary`/`business_risk`/a citation's `text`). Negative (explicitly proving no over-blocking): `"Remove the old log file with rm oldfile.log"` (no `-rf`), `"Update the firewall rule to allow port 443"` (mentions firewall, doesn't disable it), `"Run chmod 644 to restrict permissions"` (different mode).

---

### Pattern 4: Exact reuse seams — schema, prompt builder, grounding, route, router registration, frontend resourceType

**What:** The precise per-view-variant pattern (24-08) applied to this new view.

**Evidence [VERIFIED: codebase]:** `explain_host.py`/`explain_remediation.py` are ~100-line thin wrappers that do exactly four things: (1) resolve the grounding record (404 if `None`), (2) `StreamingResponse(_run_explain_stream(..., build_prompt=..., response_model=..., allowed_source_fields=..., get_prompt_version=...), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})`, (3) a matching `GET` cache-check that recomputes the exact same cache key via `_allowlisted_hash_fields()` (a route-local mirror of `_extract_scanner_data()`), (4) get registered in `backend/app/api/v1/ai/__init__.py` via `ai_router.include_router(...)`. This is a template, not a novel pattern — Phase 25's new route copies it verbatim with new names.

**Recommendation — exact new symbols:**

| Seam | New symbol | Mirrors |
|------|-----------|---------|
| Schema (`schemas.py`) | `class ExplainRemediationGuidanceResponse(ExplainResponseBase): pass` — **zero new fields** | `ExplainHostResponse`/`ExplainRemediationResponse` (also zero new fields) — confirmed the frontend's `AiExplanationCitations` only ever renders `summary`+`business_risk`+`citations`, so "steps" live as prose inside `summary`, no structured steps array needed |
| Allowlist + prompt builder (`prompt_builder.py`) | `REMEDIATION_GUIDANCE_ALLOWLIST`, `build_explain_remediation_guidance_prompt()`, `SYSTEM_PROMPT_REMEDIATION_GUIDANCE`, `FEW_SHOT_REMEDIATION_GUIDANCE`, `remediation_guidance_prompt_version()` | `HOST_ALLOWLIST`/`build_explain_host_prompt()`/... exactly |
| Grounding (`grounding.py`) | `get_remediation_guidance_context()` + `has_actionable_remediation_text()` (Pattern 1) | `get_asset_posture()`/`get_remediation_group()` |
| Route (`api/v1/ai/`) | New file `explain_remediation_guidance.py`, routes `POST/GET /explain-remediation-guidance/{finding_id}` (UUID-keyed, see Pattern 2's scope decision) | `explain_host.py` (UUID-keyed), not `explain_remediation.py` (CVE-string-keyed) |
| Router registration (`__init__.py`) | `ai_router.include_router(explain_remediation_guidance.router)` | existing 3-line pattern |
| Frontend resourceType | `'remediation-guidance'` (hyphenated — distinct namespace from the existing `'remediation'` posture view in cache keys, audit `action` strings, and the SSE URL `explain-${resourceType}`) | `'vuln'`/`'host'`/`'remediation'` |
| Frontend section mount | `<AiExplanationSection resourceType="remediation-guidance" resourceId={v.id} headingId="drill-remediation-guidance-h" />` in `drill-content.tsx`, between the existing raw "Remediation" `<section>` and "Activity" `<section>` (per 25-UI-SPEC.md) | The existing `resourceType="vuln"` mount three sections above it |

**The D-01 pre-generation gate lives entirely in the new route file, not in the engine** (unlike D-04 — see Pattern 3). The route calls `has_actionable_remediation_text()` on the fetched grounding record **before** calling `_run_explain_stream()` at all; on failure it writes its own audit row and returns a synthetic one-frame SSE response, reusing the engine's private `_sse_event()` helper (already imported across the `app.ai.explain` boundary elsewhere in this codebase — `explain_vuln.py` imports the equally-private `_run_explain_stream`, so this is consistent with existing practice, not a new convention):

```python
# explain_remediation_guidance.py
from app.ai.explain import _run_explain_stream, _sse_event, get_model_and_budget
...
record = await get_remediation_guidance_context(db, user.tenant_id, finding_id)
if record is None:
    raise HTTPException(404, "Finding not found")

if not has_actionable_remediation_text(record["remediation_action"], record["remediation_info"]):
    async def _refuse() -> AsyncIterator[bytes]:
        await audit_log_ai_call(db, tenant_id=user.tenant_id, user_email=user.email, model=..., usage=_ZERO_USAGE,
                                 resource_type="remediation-guidance", resource_id=str(finding_id),
                                 status="ungroundable", cost_estimate_usd=0.0)
        await db.commit()
        yield _sse_event({"type": "error", "kind": "grounded_false"})  # SAME kind as state 8 -- D-02
    return StreamingResponse(_refuse(), media_type="text/event-stream", headers={...})

return StreamingResponse(
    _run_explain_stream(..., dangerous_pattern_check=contains_dangerous_pattern),
    media_type="text/event-stream", headers={...},
)
```

**This means `_run_explain_stream()` needs exactly one change for this whole phase** (the `dangerous_pattern_check` parameter, Pattern 3) — the D-01 gate requires zero engine changes, which is the fullest reading of D-10's "reuse unchanged" that's actually achievable given D-04's hard caching-order constraint.

**The GET cache-check route needs one additive field** to satisfy 25-UI-SPEC.md's state 3 ("deterministic gate finds NO usable grounding → the insufficient-evidence card renders immediately, no button ever shown, **before any click**"). Evidence: today's `ExplainCacheResult` TS type (`use-explain-cache.ts`) is `{ cached: false } | ({ cached: true } & ExplainVulnResponse)` — a closed 2-member union with no signal for "cache miss AND we already know a call would refuse." The GET route must additionally run `has_actionable_remediation_text()` (cheap, no dispatch, matches D-09's existing "cheap lookup" precedent) and return `{"cached": False, "groundable": False}` vs `{"cached": False, "groundable": True}`. **Recommendation:** make the new field `groundable?: boolean` (optional, not required) on the shared TS type — vuln/host/remediation-posture's GET routes don't (and shouldn't) return it, so `AiExplanationSection` must check `groundable === false` explicitly (not just falsy) to avoid misinterpreting `undefined` for the other three resourceTypes.

---

### Pattern 5: AIR-02's pre-fill seam is currently a dead end — the backend has no description override at all

**What:** Exactly what must change for a pre-filled description to survive as far as the created ticket.

**Evidence [VERIFIED: codebase — the single most load-bearing finding for AIR-02]:**

`frontend/src/lib/mutations/use-create-ticket.ts`'s `CreateTicketRequest` type has exactly five fields: `vulnerability_ids`, `provider`, `project_key`, `assignee`, `due_days` — **no `description`**. The backend's `TicketCreateRequest` (`backend/app/ticketing/schemas.py:53-58`) mirrors this exactly — also no `description` field. `create_tickets()` (`backend/app/ticketing/service.py:222`) **always** computes `notes = _build_task_description(vuln, hostname)` — a single, provider-agnostic function (used identically for Asana/Jira/GitHub via `client.create(task_name, notes, ...)`) that builds the description from `vuln.severity`/`cve_id`/`affected_product`/`fixed_version`/`remediation_action or remediation_info` server-side, with **zero seam today for a caller-supplied override**. Pre-filling a textarea that's never actually threaded into this mutation would ship a UI-only lie — the analyst's reviewed, edited text would be silently discarded at ticket-creation time.

**This means AIR-02 requires three small, concrete changes**, not just a frontend textarea:

1. **Backend schema** (`backend/app/ticketing/schemas.py`): add `description: str | None = Field(None, max_length=10000)` to `TicketCreateRequest`.
2. **Backend service** (`backend/app/ticketing/service.py:222`): 
   ```python
   notes = request.description.strip() if request.description and request.description.strip() else _build_task_description(vuln, hostname)
   ```
   **Recommendation (WYSIWYG replace, not append):** when the analyst supplies non-empty text, it becomes the entire ticket description, replacing (not appending to) the auto-generated CVE/host/product/remediation block. Rationale: the textarea is the analyst's reviewed, edited draft — what they see in the box should be exactly what ships, with no hidden server-side content silently appended behind the scenes. This is a judgment call CONTEXT.md/25-UI-SPEC.md don't explicitly resolve — flagged in Assumptions Log A3.
3. **Frontend mutation type** (`use-create-ticket.ts`): add `description?: string` to `CreateTicketRequest`, threaded through `fireTicket()`'s `mutateAsync({ ..., description: ticketDescription || undefined })`.

**The dialog-state seam is more involved than the AI-section mount** because `DrillContent` has **two divergent render paths** for the confirm dialog, not one shared insertion point:

Evidence [VERIFIED: codebase — `drill-content.tsx` + `drill-panel-mobile.tsx`]: `DrillContent`'s `Props.renderConfirm` is an optional callback `(args: {open, onConfirm, onCancel, cveLabel, ticketProvider, onProviderChange}) => ReactNode`. When absent (desktop), `DrillContent` renders its own inline `<ConfirmModal>` directly (lines 337-348). When present (mobile, `drill-panel-mobile.tsx:102-163`), `drill-panel-mobile.tsx` supplies its **own** confirm UI nested inside `Drawer.NestedRoot`, receiving those same named args. **Both branches currently render `<TicketProviderPicker>` independently** — there is no single shared `<ConfirmModal>` component instance the AI section's "one insertion covers both" trick (which worked because `drill-panel-mobile.tsx` renders `DrillContent` directly for the read-only sections) can reuse here.

**Recommendation:** add a `description`/`onDescriptionChange` state pair owned by `DrillContent` (a new `useState<string>('')`), and extend `Props.renderConfirm`'s callback-args type to include `description: string` and `onDescriptionChange: (v: string) => void` — threading it through to `drill-panel-mobile.tsx`'s own render function so BOTH branches render the new `<Textarea>` between `TicketProviderPicker` and the Confirm/Cancel action row (per 25-UI-SPEC.md's Interaction Contract). The "Copy into ticket description" button inside the new Remediation-guidance section calls `onDescriptionChange` (or a prop threaded down to it) with the plain-text-flattened `summary` (not the citation-tinted HTML — citation tinting is a rendering-only concern per 25-UI-SPEC.md point 1).

---

### Pattern 6: Faithfulness / drift testing follows Phase 24's existing pytest-property convention — DeepEval is explicitly out of scope for this phase

**What:** How to verify cited remediation steps don't drift from the scanner source, per research question 6.

**Evidence [VERIFIED: codebase + 24-AI-SPEC.md]:** `24-AI-SPEC.md` Section 5 (Evaluation Strategy) already defines **Dimension D4** for exactly this concern: *"PASS: each citation tagged `scanner_verbatim` only when its `text` is a verbatim substring of the named `source_field`... Measurement: Code (provenance assertion: `scanner_verbatim.text` must be a substring of `record[source_field]`)."* This is stated as the design intent, but a direct grep of the existing test suite (`test_ai_explain_stream.py`, `test_ai_explain_host_remediation.py`) confirms **this exact substring-provenance assertion has not yet been implemented as executable code anywhere** — Phase 24's tests construct citations as opaque test fixtures (mocked model output) and never assert the substring relationship. This is an honest gap, not a contradiction: Phase 24's unit tests mock the model, so there was nothing live to substring-check against; the substring assertion is naturally a property test on a **constructed** `ExplainResponseBase`-shaped fixture, which any phase can add cheaply without a real model call.

Section 5 also explicitly scopes what's **out** of Phase 25: DeepEval golden-set scoring and promptfoo red-team CI are **Phase 28's** job (AIE-01/02) — *"the closing Eval + guardrail gate phase adds the automated 'cite-or-refuse' eval suite and treats it as a milestone-blocking gate, not an advisory check"* (PITFALLS.md, Pitfall 2's "Phase to address"). Phase 25 should not attempt to stand up DeepEval/promptfoo.

**Recommendation — extend, don't reinvent, Phase 24's house style** (mirroring `test_ai_prompt_builder.py`'s existing test names exactly):

```python
def test_scanner_verbatim_citation_is_substring_of_source_field() -> None:
    """D4 (24-AI-SPEC.md Section 5): a scanner_verbatim citation's text must
    actually appear in the grounding record field it claims to cite --
    this is the concrete 'don't drift from the scanner source' check."""
    record = {"remediation_action": "Upgrade OpenSSL to 3.0.14 or later.", ...}
    resp = ExplainRemediationGuidanceResponse(
        summary="Upgrade OpenSSL to 3.0.14 or later.",
        citations=[Citation(text="Upgrade OpenSSL to 3.0.14 or later.",
                             source="scanner_verbatim", source_field="remediation_action")],
        ...
    )
    for c in resp.citations:
        if c.source == "scanner_verbatim" and c.source_field:
            assert c.text in str(record[c.source_field])
```

Also mirror: `test_remediation_guidance_allowlist_excludes_owner_pii_fields` (T-24-32 discipline, both dict- and attribute-object-shaped input, per `test_allowlist_enforcement_on_object_with_extra_attributes`'s existing pattern), `test_injection_isolation`-equivalent for the new prompt builder, and the denylist positive/negative suite from Pattern 3.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dangerous-command detection | A full shell-command AST parser / base64-deobfuscation / command-substitution-unwrapping pipeline (the CARE-paper architecture) | A lightweight lowercase+whitespace-normalize regex scan (Pattern 3) | GetVul is scanning already-schema-validated LLM *prose*, not intercepting live, adversarially-obfuscated shell input from an attacker who controls the exact bytes. The heavier architecture solves a different, harder threat model; D-05 itself says "where cheap." |
| SSE streaming / retry / cache / audit | A second, parallel "explain" engine for this view | `_run_explain_stream()` + one new optional parameter | Every retry/budget/cache/audit invariant Phase 24 already proved would need re-proving in a duplicate ~230-line function — pure maintenance liability with zero benefit. |
| Citation rendering | A new "steps list" renderer | `AiExplanationCitations` (reused, zero new props) | Already handles verbatim-first two-tier tinting exactly as D-03 requires; the new schema variant deliberately has zero new fields so it fits this renderer without modification. |
| Cite-or-refuse validation | A new validation framework | Pydantic schema + `grounded: bool` + `recheck_business_rules()` (existing) | The exact mechanism Phase 24 already built and tested for this precise pattern. |
| Feedback capture for the new section | A new feedback endpoint/table | `POST /api/v1/ai/feedback/{resource_type}/{resource_id}` (existing) | [VERIFIED: `backend/app/api/v1/ai/feedback.py`] `resource_type`/`resource_id` are already untyped free-form path strings with no enum restriction — confirmed zero backend changes needed. |

**Key insight:** every "don't hand-roll" item above is not a hypothetical warning — each one is an existing, already-proven GetVul module that a less-careful implementation could plausibly duplicate under time pressure. The discipline this phase requires is almost entirely about *finding the right seam to extend*, not writing new infrastructure.

## Common Pitfalls

### Pitfall 1: Treating `remediation_action IS NOT NULL` as "present"
**What goes wrong:** The refuse predicate passes on a Rapid7 row where `remediation_info=""` (a real, verified persisted value — Pattern 1), generating a model call and prompt for a finding with zero actual vendor guidance.
**Why it happens:** `is not None` is the natural first instinct; the empty-string case is not visible without reading `rapid7.py`'s exception-handling branch and `_kb_solution`-style connectors' defensiveness varies.
**How to avoid:** `.strip()` and length-check every candidate string, never just `is not None` (Pattern 1's `has_actionable_remediation_text()`).
**Warning signs:** A "grounded" remediation-guidance result for a finding whose raw "Remediation" section (the existing, unstyled display immediately above the new section) visibly shows blank/empty text.

### Pitfall 2: Filtering the SSE `done` event at the route layer instead of gating inside the engine
**What goes wrong:** Dangerous content is swapped out of the outbound stream but remains cached under a real key; a subsequent page load's GET cache-check serves it anyway, silently violating D-04.
**Why it happens:** It looks like the minimal-diff option ("don't touch `explain.py`"), and the caching-before-emission ordering is not obvious without reading the engine's SUCCESS block line-by-line.
**How to avoid:** The dangerous-pattern check must run inside `_run_explain_stream()`, before `set_cached()` (Pattern 3).
**Warning signs:** A test that asserts the SSE stream doesn't contain a dangerous string, but never asserts `set_cached`/the Redis key was never written — a green test that hides the real bug.

### Pitfall 3: Assuming the frontend's closed `ExplainStreamState.error.kind` union already supports a visually distinct safety-refusal card
**What goes wrong:** The engine emits the new `unsafe` kind, but the frontend's TS union (and `AiExplanationSection`'s `if` chain) doesn't have a branch for it, so it silently falls through to the generic/unstyled default — or worse, a TS build error if `noUncheckedIndexedAccess`-style strictness is on.
**Why it happens:** D-07's "no new state vocabulary is invented" reads, out of context, as "don't touch this file" — but 25-UI-SPEC.md's own state list (states 3 and 9) requires exactly this addition, and the more specific, later-approved UI-SPEC document supersedes the more general CONTEXT.md phrasing here.
**How to avoid:** Add the `'unsafe'` member to `ExplainStreamState`'s union (Pattern 3) and a corresponding `DegradedCard variant="danger"` branch in `AiExplanationSection` (25-UI-SPEC.md specifies this is the ONE new color usage this phase introduces).
**Warning signs:** The safety-refusal fixture test renders the SAME card as the insufficient-evidence fixture test.

### Pitfall 4: Pre-filling the ticket description textarea without threading it through the mutation
**What goes wrong:** The analyst edits/reviews a description that is silently discarded — `create_tickets()` always calls `_build_task_description()` regardless of what the client sent, because there is no `description` field on the request schema today (Pattern 5). AIR-02 appears to work in the UI but the created ticket never reflects it.
**Why it happens:** The AI section and the ticket-create dialog are visually adjacent and easy to assume are already wired; the backend gap is invisible without reading `service.py`'s `create_tickets()` body.
**How to avoid:** Verify end-to-end with an integration test asserting the EXTERNAL ticket body (via the mocked `TicketingClient.create()` call args) contains the analyst-supplied text, not just that the textarea renders it.
**Warning signs:** A test only checks the textarea's DOM value, never the `client.create(task_name, notes, ...)` call's `notes` argument.

### Pitfall 5: Assuming the mobile ticket-create dialog gets the new textarea "for free" like the AI section did
**What goes wrong:** The desktop `ConfirmModal` branch gets the new field; `drill-panel-mobile.tsx`'s separate `renderConfirm` implementation does not, because it's a genuinely different code path, not a shared mount point.
**Why it happens:** The AI section's "mobile renders `DrillContent` directly, so one insertion covers both" precedent (confirmed true for read-only sections) doesn't extend to the confirm dialog, which has an explicit `renderConfirm` override specifically because mobile needs `Drawer.NestedRoot` nesting (Pitfall 7 from Phase 23).
**How to avoid:** Extend `Props.renderConfirm`'s callback-args type and verify both the desktop `ConfirmModal` branch AND the mobile `renderConfirm` branch render the textarea (Pattern 5).
**Warning signs:** Desktop drill-panel tests pass; mobile drill-panel tests (`drill-panel-mobile.test.tsx`) never mention a description field at all.

## Code Examples

See Patterns 1–5 above for fully-worked, ready-to-adapt code (grounding query, refuse predicate, dangerous-pattern module + engine extension point, route skeleton, service-layer description override). All are original recommendations synthesized from verified codebase patterns — not copy-pasted from an external source — so none carry a `[CITED: url]` tag; the underlying facts they're built on (query shapes, function signatures, control flow) are tagged `[VERIFIED: codebase]` inline within each pattern.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CrowdStrike's synthesized `"Update {product} to the latest version"` fallback should count as sufficiently "actionable" for the D-01 gate (not added to the generic-placeholder denylist) | Pattern 1 | If wrong: a small fraction of CrowdStrike findings with no real remediation-cache match would generate model-authored "steps" grounded only in a GetVul-invented template sentence, not genuine vendor solution text — arguably a thin violation of "cites the scanner's own solution text." Low blast radius (CrowdStrike-only, and the fallback string does carry a real product name) but worth an explicit plan-time confirmation. |
| A2 | The dangerous-pattern gate should apply uniformly to `scanner_verbatim` and `ai_interpreted` text alike (no exemption for vendor-sourced content) | Pattern 3 | If wrong (i.e., if the intent was to only gate `ai_interpreted` text): the recommended implementation would over-block legitimate vendor remediation text that happens to contain a denylisted phrase, refusing guidance the analyst could have safely used. CONTEXT.md D-04's wording ("on any hit the ENTIRE guidance is refused") does not carve out an exception, so this reading is the more literal one, but it is a real product-behavior tradeoff worth surfacing explicitly rather than silently baking in. |
| A3 | An analyst-supplied ticket description should fully REPLACE the auto-generated description (WYSIWYG), not be appended alongside it | Pattern 5 | If wrong: the recommended one-line service.py change would need to become an append/merge instead, and the frontend's "no character-count UI" framing (25-UI-SPEC.md) would need reconsidering if the two are concatenated with a separator the analyst never previews. Low implementation cost to change either way if flagged before coding. |
| A4 | The D-01 pre-generation refusal should write its own audit row (new status `"ungroundable"`) rather than staying silent like the `no_key` precondition | Pattern 4 | If wrong (i.e., if it should be silent like `no_key`): a trivial one-line removal; no data-model impact either way since `AuditLog.details` is free-form JSONB. Low risk, but affects Phase 28's eventual "grounding-failure rate" flywheel metric completeness if omitted. |

## Open Questions

1. **Exact dangerous-pattern list and threshold for "obfuscation-resistant matching"**
   - What we know: CONTEXT.md D-04 gives explicit example patterns; Pattern 3 above proposes a concrete starter set + lowercase/whitespace normalization, cross-checked against two pieces of external prior art.
   - What's unclear: whether the planner wants a broader category (e.g., explicit credential-rotation-instruction detection, called out in PITFALLS.md but not in CONTEXT.md D-04's own example list) included in the v1 denylist or deferred.
   - Recommendation: ship the concrete starter set in Pattern 3 (already covers every example CONTEXT.md D-04 names), and treat "credential-rotation instructions" as a candidate addition the plan-time denylist review should explicitly accept or defer — it's cheap to add a 9th tuple entry later since D-05 designed this as a single-module, unit-tested, easily-extended list.

2. **Should the new remediation-guidance grounding record surface a "this fix also affects N other assets" note by querying `get_remediation_group()` for the same CVE?**
   - What we know: D-06 requires this new section be structurally distinct from `get_remediation_group()`'s cross-asset posture view; nothing in AIR-01/AIR-02 requires cross-asset awareness.
   - What's unclear: whether a lightweight cross-reference (not full aggregation) would add value without scope creep.
   - Recommendation: out of scope for Phase 25 — the single-finding grounding record (Pattern 2) fully satisfies AIR-01/AIR-02 as written; adding a cross-CVE lookup would duplicate Phase 24's `get_remediation_group()` responsibility inside a "distinct" section, undermining D-06's own separation rationale.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres (`getvul-postgres-1`) | AuditLog writes, Vulnerability/Asset queries | ✓ [VERIFIED: `docker ps`, 2026-07-30] | healthy, running 23h | — |
| Redis (`getvul-redis-1`) | Cache + inflight guard, reused unchanged | ✓ [VERIFIED: `docker ps`, 2026-07-30] | healthy, running 23h | — |
| Backend/Frontend containers | Local dev loop | ✓ [VERIFIED: `docker ps`, 2026-07-30] | `getvul-backend-1` healthy, `getvul-frontend-1` up | — |
| `anthropic` Python SDK | `_run_explain_stream()` (reused, unchanged) | ✓ [VERIFIED: 24-04-SUMMARY.md] `0.120.2` already installed in `backend/.venv` | — |
| Live Anthropic API key (`GETVUL_DEV_ANTHROPIC_KEY`) | End-to-end live smoke test of the new route | ✗ [VERIFIED: `env` check, 2026-07-30 — not set in this shell; also flagged unprovisioned in 24-01/24-04-SUMMARY.md "Known Gaps"] | — | Carry forward Phase 24's exact precedent: unit/integration tests inject a fake Anthropic client via the existing `anthropic_client_factory` test seam; live verification remains a tracked, accepted gap (per the 24-06 "proceed on trust" decision), not a blocker for this phase's plans. |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** Live Anthropic key — mitigated by the existing `anthropic_client_factory` test seam (already proven across every Phase 24 plan); this is inherited, not new, risk.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3 + pytest-asyncio (`asyncio_mode = "auto"`, session-scoped event loop per `backend/pyproject.toml`) for backend; Vitest for frontend (`frontend/package.json`'s `"test": "vitest"`) |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`); frontend Vitest config (existing, unchanged) |
| Quick run command | `pytest backend/tests/test_ai_<new_file>.py -q` (per-file — project memory: `ENCRYPTION_KEY`/`JWT_SECRET_KEY` env vars must be set and the whole `tests/` directory should NOT be run in one pytest invocation for a quick loop, per `getvul-backend-pytest-env` memory) |
| Full suite command | `pytest backend/tests/ -q` (backend wave-merge regression) + `npm run test` (frontend, from `frontend/`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AIR-01 | D-01 refuse predicate: empty/generic/absent remediation text → no model call | unit | `pytest backend/tests/test_ai_grounding_remediation_guidance.py -k has_actionable -x` | ❌ Wave 0 (new file) |
| AIR-01 | REMEDIATION_GUIDANCE_ALLOWLIST excludes owner-PII fields (dict + attribute-object) | unit | `pytest backend/tests/test_ai_prompt_builder_remediation_guidance.py -k pii -x` | ❌ Wave 0 (new file) |
| AIR-01 | Dangerous-pattern gate: positive + negative + obfuscated cases | unit | `pytest backend/tests/test_ai_safety.py -x` | ❌ Wave 0 (new file) |
| AIR-01 | Dangerous-pattern hit skips `set_cached()` (Pitfall 2's backstop) | integration | `pytest backend/tests/test_ai_explain_remediation_guidance.py -k unsafe_not_cached -x` | ❌ Wave 0 (new file) |
| AIR-01 | scanner_verbatim citation substring-of-source-field (Pattern 6) | unit | `pytest backend/tests/test_ai_schemas.py -k substring -x` | ❌ Wave 0 (extends existing file) |
| AIR-02 | `create_tickets()` uses `request.description` when supplied, falls back otherwise | unit | `pytest backend/tests/test_ticketing_service.py -k description_override -x` | ❌ Wave 0 (extends existing file, if present — verify exact filename at plan time) |
| AIR-02 | Desktop + mobile ticket-create dialog both render/thread the textarea | component | `npm run test -- drill-content` / `drill-panel-mobile` | ❌ Wave 0 (extends existing `.test.tsx` files) |

### Sampling Rate
- **Per task commit:** the new file's own quick-run command (per-file, per project memory's env-var gotcha).
- **Per wave merge:** `pytest backend/tests/test_ai_*.py -q` (mirrors Phase 24's own wave-merge convention, currently 117/117 green per 24-08-SUMMARY.md) + `npm run test` for touched frontend files.
- **Phase gate:** Full backend + frontend suite green before `/gsd-verify-work 25`.

### Wave 0 Gaps
- [ ] `backend/tests/test_ai_grounding_remediation_guidance.py` — covers AIR-01's grounding query + D-01 predicate (mirrors `test_ai_explain_host_remediation.py`'s existing structure)
- [ ] `backend/tests/test_ai_prompt_builder_remediation_guidance.py` — covers the new allowlist/prompt-builder (mirrors `test_ai_prompt_builder_host.py`)
- [ ] `backend/tests/test_ai_safety.py` — covers the denylist module in isolation (positive/negative/obfuscated, Pattern 3)
- [ ] `backend/tests/test_ai_explain_remediation_guidance.py` — covers the new route (RBAC matrix, cache-check, cross-tenant 404, groundable flag, unsafe-not-cached backstop — mirrors `test_ai_explain_host_remediation.py`)
- [ ] No new fixtures/conftest needed — `tenant_a`/`tenant_b`/`db_session`/`client_factory` fixtures already exist and are reused verbatim across every `test_ai_*.py` file.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Unchanged — reuses existing JWT/session auth |
| V3 Session Management | No | Unchanged |
| V4 Access Control | Yes | Reuses `require_analyst`/`require_viewer` RBAC dependencies verbatim (D-17) — no new access-control logic introduced |
| V5 Input Validation | Yes | Pydantic schema validation gate (`model_validate_json` + `recheck_business_rules`) is the core mechanism this whole phase extends; the new `TicketCreateRequest.description` field needs its own `max_length` bound (recommended 10000 chars, Pattern 5) and the existing `extra: "forbid"` mass-assignment defense convention |
| V6 Cryptography | No | No new cryptographic material; BYOK key handling is 100% inherited/unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unsafe/destructive AI-generated remediation text reaching an analyst who acts on it directly (this phase's owned Pitfall #2) | Tampering / Elevation of Privilege (via a human executing a destructive instruction) | D-04's post-generation dangerous-pattern gate, enforced as a code gate inside the shared streaming engine (Pattern 3) — never relies on prompt wording alone |
| Fabricated remediation presented as vendor fact | Repudiation / Information Disclosure (false compliance-evidence trail — per 24-AI-SPEC.md's Regulatory/Compliance Context, an AI explanation quoted in a ticket is load-bearing PCI-DSS/SOC 2 evidence) | D-01/D-02's two-layer cite-or-refuse gate + D-03's two-tier citation rendering, inherited unchanged from Phase 24 |
| Mass-assignment via the new `description` field on `TicketCreateRequest` | Tampering | `model_config = {"extra": "forbid"}` (existing project convention, `app/ticketing/schemas.py`'s `CommentCreate`/`BlockedUpdate` precedent) + an explicit `max_length` bound |
| Owner-PII leakage into the new remediation-guidance prompt | Information Disclosure | The new `REMEDIATION_GUIDANCE_ALLOWLIST` (Pattern 2) structurally excludes every owner-PII field at the query layer (never even SELECTed), mirroring `get_asset_posture()`'s defense-in-depth precedent — not just a prompt-builder-layer filter |

## Sources

### Primary (HIGH confidence)
- `backend/app/ai/{explain.py, grounding.py, prompt_builder.py, schemas.py, cache.py, audit.py}` — direct reads, the entire reuse-mechanics and engine-extension-point analysis (Patterns 3, 4)
- `backend/app/api/v1/ai/{explain_vuln.py, explain_host.py, explain_remediation.py, feedback.py, __init__.py}` — direct reads, exact route/registration pattern (Pattern 4)
- `backend/app/connectors/{crowdstrike.py, nessus.py, defender.py, qualys.py, wiz.py, rapid7.py, sync.py, schemas.py}` — direct reads, the connector-field-reality finding (Pattern 1)
- `backend/app/vulnerabilities/models.py`, `backend/app/assets/models.py` — direct reads, confirmed no installed-package field exists (Pattern 2)
- `backend/app/ticketing/{schemas.py, service.py, router.py}` — direct reads, the AIR-02 backend-gap finding (Pattern 5)
- `frontend/src/lib/ai/use-explain-stream.ts`, `frontend/src/components/ai/{ai-explanation-section.tsx, ai-explanation-citations.tsx}`, `frontend/src/lib/queries/use-explain-cache.ts` — direct reads, closed-union and groundable-flag findings (Patterns 3, 4)
- `frontend/src/components/vulnerabilities/{drill-content.tsx, drill-panel-mobile.tsx}`, `frontend/src/lib/mutations/use-create-ticket.ts` — direct reads, the renderConfirm/dialog-divergence finding (Pattern 5)
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-AI-SPEC.md` — Section 5 (Evaluation Strategy, D1-D11) and Section 6 (Guardrails) — Pattern 6's testing recommendation and the "DeepEval is Phase 28's job" scoping
- `.planning/research/PITFALLS.md` Pitfall 2 — the phase's own owned pitfall, direct source for the denylist example list
- `.planning/phases/24-ai-foundation-explain-this-vuln/24-08-SUMMARY.md`, `24-04-SUMMARY.md` — the exact per-view-variant precedent this phase mirrors
- `.planning/phases/25-asset-aware-remediation-guidance/{25-CONTEXT.md, 25-UI-SPEC.md}` — the locked decisions and approved UI contract this research is scoped against
- `docker ps`, `env` (2026-07-30) — Environment Availability verification

### Secondary (MEDIUM confidence)
- [Destructive Command Guard (dcg)](https://github.com/Dicklesworthstone/destructive_command_guard) — corroborates CONTEXT.md D-04's example pattern list against a real, purpose-built tool targeting the same command classes; specific regex source not independently fetched (page content did not expose it)
- [CARE: Pre-Execution Command Verification for Shell-Executing LLM Agents (arXiv 2607.21642v1)](https://arxiv.org/html/2607.21642v1) — corroborates the "normalize + rule-bank" architectural approach and its false-positive/obfuscation-resistance limits, informing the "proportionate, not maximal, investment" recommendation in Pattern 3

### Tertiary (LOW confidence)
- None — every claim in this document is either a direct codebase read or a cross-checked external source; no single-source, unverified WebSearch claims are included.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; every reused symbol verified by direct file read
- Architecture (Patterns 1, 2, 4, 5, 6): HIGH — every seam, gap, and query shape confirmed by direct codebase reads, several revealing concrete bugs-not-yet-hit (empty-string remediation_info, the AIR-02 backend dead-end)
- Architecture (Pattern 3, dangerous-pattern gate mechanics): HIGH for the engine-extension-point argument (derived from verified control-flow facts); MEDIUM for the exact pattern list (CONTEXT.md explicitly delegates this to plan time, and real-world false-positive tuning is inherently iterative)
- Pitfalls: HIGH — five concrete, codebase-specific pitfalls identified, each with a verifiable "warning sign" a reviewer can check for

**Research date:** 2026-07-30
**Valid until:** ~30 days (stable domain — no fast-moving external dependency; re-verify if Phase 26/27 change the shared `ExplainStreamState` union or `_run_explain_stream()` signature before Phase 25 executes)
