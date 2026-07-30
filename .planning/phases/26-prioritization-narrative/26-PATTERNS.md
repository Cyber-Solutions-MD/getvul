# Phase 26: Prioritization Narrative - Pattern Map

**Mapped:** 2026-07-30
**Files analyzed:** 11 new/modified backend files + 1 new backend migration + 6 new/extended backend tests + 3 modified frontend files + 2 extended frontend tests
**Analogs found:** 20 / 23 exact or role-match; 3 flagged (batch.py is a composite of three existing shapes, not one file; the scheduler→Redis access seam has no analog at all; the no-rank CI grep has no file-shaped analog)

This map corroborates 26-RESEARCH.md's seams against a direct re-read of every cited file this session (not a re-statement of RESEARCH.md's own prose) and adds line-precise citations RESEARCH.md's Patterns left at the "mirrors X" level. Phase 26 is dominated by the SAME self-analog reality Phase 25 established: `grounding.py`/`schemas.py`/`prompt_builder.py`/`api/v1/ai/__init__.py` each already hold 3-4 sibling "view" blocks, so the closest analog for the 5th (`prioritization`) is almost always a block 100-300 lines away in the identical file — most recently the `remediation-guidance` quadruplet Phase 25 shipped, which is now itself live, current-generation code (not just a research recommendation) and is consistently the *closest* analog, closer than the older `vuln`/`host` blocks RESEARCH.md's Pattern 7 table sometimes cited instead.

Three things this pass found that 26-RESEARCH.md did not fully resolve (flagged inline below, summarized in "Corroboration & Corrections"):
1. **`get_top_findings_for_ai_batch()`'s test home** — RESEARCH.md flagged `test_vulnerabilities_service.py` as unconfirmed. It does not exist. The correct analog is `backend/tests/test_triage_sort.py` (a dedicated DB-integration test file for exactly this kind of tenant-scoped `Vulnerability`+`Asset` ordering query).
2. **The scheduler has literally zero mechanism to obtain a Redis client today** — not just an "unconfirmed factory function" (RESEARCH's Open Question 1) but a confirmed structural gap: `app.state.redis` is constructed in `main.py` lines 118-127, *after* `start_scheduler()` is called at lines 108-110, and no importable Redis-client factory exists anywhere in the codebase (`app/redis_client.py` is 13 lines, a FastAPI dependency taking `request: Request`, nothing else).
3. **Phase 25's own test files now exist and are better analogs than the Phase-24-era files RESEARCH.md's Pattern 7 table cited** — `test_ai_prompt_builder_remediation_guidance.py`, `test_ai_explain_remediation_guidance.py`, `test_ai_grounding_remediation_guidance.py`, and `test_ai_safety.py` are all live, shipped code now (RESEARCH.md was written when some were still forward references).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/ai/grounding.py` (add `get_prioritization_context()`) | service / query assembler | CRUD (read) | `get_remediation_guidance_context()`, same file, lines 264-313 | exact |
| `backend/app/ai/schemas.py` (add `ExplainPrioritizationResponse`) | model / schema | transform | `ExplainRemediationGuidanceResponse`, same file, lines 88-93 | exact |
| `backend/app/ai/prompt_builder.py` (add `PRIORITIZATION_ALLOWLIST` + `AllowlistedPrioritization` + `_to_allowlisted_prioritization()` + `SYSTEM_PROMPT_PRIORITIZATION` + `FEW_SHOT_PRIORITIZATION` + `build_explain_prioritization_prompt()` + `prioritization_prompt_version()`) | service / utility (prompt builder) | transform | `REMEDIATION_GUIDANCE` quadruplet, same file, lines 786-1011 | exact (flat/scalar allowlist, no nested list — same shape as `HOST_ALLOWLIST`/`REMEDIATION_GUIDANCE_ALLOWLIST`, not `REMEDIATION_ALLOWLIST`'s `affected_assets[]`) |
| `backend/app/ai/models.py` (add `AiBatchJob`) | model | CRUD | `AiFeedback`, same file, lines 26-48 | exact |
| `backend/alembic/versions/033_add_ai_batch_job.py` (**new file**) | migration | — | `032_add_ai_feedback.py` (whole file, 65 lines) | exact |
| `backend/app/ai/budget.py` (extract `get_month_to_date_spend()`, add `would_exceed_budget_for_batch()`) | service / utility | CRUD (read) | `check_tenant_budget()`, same file, lines 41-65 | exact (same-file refactor: the SUM query is extracted, not rewritten) |
| `backend/app/ai/batch.py` (**new file**: `estimate_batch_cost_usd()`, `run_batch_prewarm()`, `poll_pending_batches()`, `validate_and_cache_batch_result()`) | service (batch orchestrator) | batch / event-driven | composite — no single exact analog (see Pattern Assignment below) | role-match (structural pieces borrowed from 3 existing files) |
| `backend/app/connectors/scheduler.py` (add 2 new try/except blocks inside `_scheduler_loop()`) | service (scheduler dispatch) | event-driven / batch | SAME file: `trigger_background_sync()` lines 53-62 (dispatch idiom to copy) contrasted with the daily-ticket-sync block lines 152-165 (timing-gate idiom to copy, inline-await idiom to AVOID) | exact (same file, two contrasting sibling blocks) |
| `backend/app/vulnerabilities/service.py` (add `get_top_findings_for_ai_batch()`) | service / query | CRUD (read) | SAME file's `sort="triage"` branch, lines 92-99, **plus** `backend/app/assets/service.py::list_assets()`'s `Asset.risk_score` ordering, line 70 | exact (same-file tiebreak idiom) / role-match (cross-file risk_score-ordering idiom) |
| `backend/app/api/v1/ai/explain_prioritization.py` (**new file**) | route / controller | streaming (POST SSE) + request-response (GET cache-check) | `explain_host.py` (whole file, 103 lines) | exact (UUID-keyed single-record 404, no pre-generation gate, no `dangerous_pattern_check` — closer than `explain_remediation_guidance.py`, which has both) |
| `backend/app/api/v1/ai/__init__.py` (add router registration) | route registration / config | — | Same file, lines 32-47 | exact (same file, 3-line pattern) |
| `backend/tests/test_ai_grounding_prioritization.py` (**new**, recommended — not explicitly named in RESEARCH.md's Wave 0 Gaps but implied by quadruplet-completeness) | test | — | `test_ai_grounding_remediation_guidance.py` (whole file, 190 lines) | exact |
| `backend/tests/test_ai_prompt_builder_prioritization.py` (**new**) | test | — | `test_ai_prompt_builder_remediation_guidance.py` (whole file, 198 lines) | exact |
| `backend/tests/test_ai_explain_prioritization.py` (**new**) | test | — | `test_ai_explain_remediation_guidance.py` (whole file, 355 lines) | exact |
| `backend/tests/test_ai_batch.py` (**new**) | test | — | No exact analog — closest structural pieces: `test_ai_budget.py` (budget-guard unit shape) + `test_ai_audit.py::test_scheduler_audit` (lines 80-103, the `system:scheduler` shape) | partial |
| `backend/tests/test_scheduler_ai_batch.py` (**new**) | test | — | `test_connector_health.py::test_scheduler_path_failure_parity`, lines 182-199 (`from app.connectors import scheduler as scheduler_module; await scheduler_module.<fn>(...)` direct-await calling convention) | exact (calling convention only — this is the first test to assert non-blocking `asyncio.create_task` dispatch specifically, which is new) |
| `backend/tests/test_triage_sort.py` — **CORRECTED target for `get_top_findings_for_ai_batch()`'s test**, not `test_vulnerabilities_service.py` (does not exist) | test | — | Whole file, 95 lines — direct analog (same DB shape: seed `Vulnerability` rows, assert ordering) | exact |
| `frontend/src/components/ai/ai-explanation-section.tsx` (add `isPrioritization` discriminator, `icon` prop on `DegradedCardProps`, new `queued` branch) | component | request-response / streaming UI | SAME file's `isRemediationGuidance` discriminator (lines 164-184) + `groundable === false` branch (lines 278-287) | exact |
| `frontend/src/lib/queries/use-explain-cache.ts` (add `queued?: boolean`) | hook | request-response | SAME file's existing `groundable?: boolean` addition, lines 17-19 | exact |
| `frontend/src/components/vulnerabilities/drill-content.tsx` (new `<section aria-labelledby="drill-prioritization-h">` mount) | component | UI composition | SAME file's `drill-remediation-guidance-h` section mount, lines 307-322 | exact |
| `frontend/src/lib/ai/use-explain-stream.ts` — **no change required** | hook | streaming | n/a — confirmed by direct read (whole file, 143 lines) | n/a (see "No Change Needed" below) |
| `frontend/src/lib/queries/keys.ts` — **no change required** | config | — | n/a — confirmed by direct read (`ai.explain(resourceType, resourceId)`, lines 96-99, already generic) | n/a |
| `frontend/src/components/ai/ai-explanation-section.test.tsx` (extend) | test | — | Existing `isRemediationGuidance`/`groundable` assertions in same file (664 lines) | exact |
| `frontend/src/components/vulnerabilities/drill-panel.test.tsx` / `drill-panel-mobile.test.tsx` (extend) | test | — | Existing AI-section-mount assertions (per 25-PATTERNS.md's own citations) | exact |

---

## Pattern Assignments

### `backend/app/ai/grounding.py` — add `get_prioritization_context()`

**Analog:** `get_remediation_guidance_context()`, same file, lines 264-313 (the most structurally similar existing function: single-row `Vulnerability` outer-joined to `Asset`, keyed on `finding_id`, tenant-scoped, returns `dict[str, Any] | None`).

**Exact shape to copy** (lines 264-298 — SELECT + tenant-scoped-None pattern):
```python
async def get_remediation_guidance_context(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
) -> dict[str, Any] | None:
    result = await db.execute(
        select(
            Vulnerability.cve_id,
            Vulnerability.remediation_action,
            ...
            Asset.hostname,
            Asset.os_name,
            Asset.os_version,
        )
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(Vulnerability.id == finding_id, Vulnerability.tenant_id == tenant_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return {...}
```

`get_prioritization_context(db, tenant_id, finding_id)` swaps the SELECT list to D-04's factor set + `cve_id` (Assumption A4) + `Asset.department` — all 10 columns confirmed to exist verbatim by direct model read this session:
- `Vulnerability.{cve_id, cvss_v3_score, epss_score, exploit_available, cisa_kev, exploit_status_name, severity, sla_due_at, sla_breached}` — `backend/app/vulnerabilities/models.py` lines 51, 53, 56-58, 70-71, 55, 78-79 (all present, confirmed by direct read of the `Vulnerability` class body, lines 46-81).
- `Asset.department` — `backend/app/assets/models.py` line 62 (`department: Mapped[str | None] = mapped_column(String(200))`).

**Owner-PII exclusion — the SAME "never even fetched" discipline this file's docstring already documents for the sibling function** (module docstring, lines 26-37, already states this exact precedent for `get_remediation_guidance_context`): `Asset.assigned_user` (line 64), `Asset.directory_user` (does not exist as a column — confirmed absent from `Asset`; directory identity lives on `User`, never joined here), `Asset.managed_by` (line 65), `Asset.building` (line 63), `Asset.serial_number` (line 60) must never appear in the new SELECT, exactly as `get_remediation_guidance_context()`'s own SELECT (lines 279-292) never names `assigned_user`/`directory_user`/`managed_by`/`building`/`serial_number`/`department` — the new function is the one place in this module that DOES read `department` (deliberately, per D-04), so its docstring should say so explicitly, mirroring how the existing docstring (lines 33-37) is explicit about what it excludes.

**No deterministic pre-generation refuse predicate is needed here** (unlike `has_actionable_remediation_text()`, lines 240-261, which Phase 25 needed because vendor remediation text is frequently empty/placeholder). D-04's factor fields are structured scanner/scoring columns (CVSS/EPSS/exploit/KEV/severity/SLA), not free text — there is no "generic placeholder" failure mode to defend against the way `remediation_action`/`remediation_info` had. The model's own `grounded=false` judgment (already built into `_run_explain_stream()`, reused unchanged) is sufficient, and the UI-SPEC's "insufficient-signal" card confirms this is a defensive backstop, not a deterministic gate like D-01's.

---

### `backend/app/ai/schemas.py` — add `ExplainPrioritizationResponse`

**Analog:** `ExplainRemediationGuidanceResponse`, same file, lines 88-93 — the most recent zero-new-fields subclass.

```python
class ExplainRemediationGuidanceResponse(ExplainResponseBase):
    """The 'remediation guidance' response (AIR-01, Phase 25 Plan 02). No
    additional fields — cited remediation steps live as prose inside
    `summary`..."""
```

`ExplainPrioritizationResponse(ExplainResponseBase): pass` follows verbatim. This is **the literal D-03 "no AI rank" schema enforcement** — confirmed by direct read of `ExplainResponseBase` (lines 44-67): its four fields are `summary: str`, `business_risk: str`, `citations: list[Citation]`, `grounded: bool` — there is no numeric field anywhere in the base class, so there is structurally nowhere for a rank/priority number to live even if a future edit tried to add one without touching this exact base class. `recheck_business_rules()` (lines 117-149) needs zero changes — it already accepts `allowed_source_fields` as a parameter, exactly as every existing route passes its own `*_ALLOWLIST`.

---

### `backend/app/ai/prompt_builder.py` — add the 5th allowlist+prompt-builder quadruplet

**Analog:** the REMEDIATION_GUIDANCE quadruplet, same file, lines 786-1011 (chosen over `HOST_ALLOWLIST`, lines 347-584, because it is the most-recently-shipped sibling AND because CONTEXT.md/RESEARCH.md both frame this view as "like the Phase 25 remediation-guidance section" — though structurally either flat allowlist works, since `PRIORITIZATION_ALLOWLIST` is 10 flat scalar fields with no nested list, matching both `HOST_ALLOWLIST` and `REMEDIATION_GUIDANCE_ALLOWLIST`'s shape, not `REMEDIATION_ALLOWLIST`'s `affected_assets[]`).

**Allowlist declaration** (lines 799-814 to mirror):
```python
REMEDIATION_GUIDANCE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "cve_id",
        "severity",
        "exploit_available",
        "cisa_kev",
        "remediation_action",
        "remediation_info",
        "affected_product",
        "affected_version",
        "fixed_version",
        "asset_hostname",
        "os_name",
        "os_version",
    }
)
```
`PRIORITIZATION_ALLOWLIST` = 10 fields: `{"cve_id", "cvss_v3_score", "epss_score", "exploit_available", "cisa_kev", "exploit_status_name", "severity", "sla_due_at", "sla_breached", "department"}`. Every one of these except `department` is already precedented verbatim in `VULN_ALLOWLIST` (lines 53-72) or this same block; `department` is the one genuinely new field name in this module (Assumption A2 — bare column name, matching `os_name`/`os_version`'s bare-column convention already in this exact allowlist, not an `asset_`-prefixed name).

**Allowlisted Pydantic model + field-by-field constructor** (lines 817-863 to mirror):
```python
class AllowlistedRemediationGuidance(BaseModel):
    model_config = {"extra": "forbid"}
    cve_id: str | None = None
    severity: str | None = None
    ...

def _to_allowlisted_remediation_guidance(record: Any) -> AllowlistedRemediationGuidance:
    return AllowlistedRemediationGuidance(
        cve_id=_get_field(record, "cve_id"),
        severity=_get_field(record, "severity"),
        ...
    )
```
`_get_field()` (lines 109-118) is the shared Mapping-or-attribute reader — reuse unchanged, exactly as every prior constructor does. None of `PRIORITIZATION_ALLOWLIST`'s 10 fields are free text needing `_truncate()` (lines 132-146) — `cve_id`/`severity`/`exploit_status_name`/`department` are all short bounded strings (`String(20)`/`String(10)`/`String(100)`/`String(200)` per the model columns), unlike `remediation_action`/`remediation_info` (`Text`, unbounded) which is why `_to_allowlisted_remediation_guidance()` needed truncation and `AllowlistedPrioritization`'s constructor does not.

**System prompt + few-shot + builder + version functions** (lines 956-1011 to mirror the shape of, not the content):
```python
SYSTEM_PROMPT_REMEDIATION_GUIDANCE = f"""You are GetVul's remediation-guidance assistant.
<untrusted_content_policy>...</untrusted_content_policy>
...
{_render_few_shot(FEW_SHOT_REMEDIATION_GUIDANCE)}
"""

def build_explain_remediation_guidance_prompt(record: Any) -> tuple[str, list[dict[str, str]]]:
    guidance = _to_allowlisted_remediation_guidance(record)
    scanner_data = json.dumps(guidance.model_dump())
    user_block_text = f'<scanner_data source="remediation_guidance">{scanner_data}</scanner_data>'
    return SYSTEM_PROMPT_REMEDIATION_GUIDANCE, [{"type": "text", "text": user_block_text}]

def remediation_guidance_prompt_version() -> str:
    return prompt_version(SYSTEM_PROMPT_REMEDIATION_GUIDANCE, FEW_SHOT_REMEDIATION_GUIDANCE, ExplainRemediationGuidanceResponse)
```
`SYSTEM_PROMPT_PRIORITIZATION` must state D-08's own instruction explicitly in prompt text: explain the deterministic score's drivers (KEV/exploit/SLA/severity/department), **never assert an independent verdict or invent a number** — this is the one place D-03/D-08's product intent becomes prompt text, mirroring how `SYSTEM_PROMPT_REMEDIATION_GUIDANCE` (lines 963-979) states "REFUSE rather than invent a fix... Never recommend a destructive... action" in its own words. `source="prioritization"` on the `<scanner_data>` tag follows the established `source="host_posture"` / `source="remediation_group"` / `source="remediation_guidance"` naming convention. `FEW_SHOT_PRIORITIZATION` needs its own second exemplar demonstrating `grounded: false` on a factor-set that's too sparse to explain (e.g. no CVSS/EPSS/exploit signal at all), consistent with every other view's two-exemplar convention (`FEW_SHOT_HOST` lines 455-538, `FEW_SHOT_REMEDIATION` lines 657-738, `FEW_SHOT_REMEDIATION_GUIDANCE` lines 872-953 all follow this shape).

**The generalized `prompt_version()` hashing function** (lines 317-344) needs zero changes — it already accepts `response_model` as a parameter specifically so each view's own wrapper (`host_prompt_version()`, `remediation_guidance_prompt_version()`, and the new `prioritization_prompt_version()`) reuses it unchanged.

---

### `backend/app/ai/models.py` — add `AiBatchJob`

**Analog:** `AiFeedback`, same file, lines 26-48 — the only prior "new AI-domain table" precedent in this codebase.

```python
class AiFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_feedback"
    __table_args__ = (UniqueConstraint(...),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ...
```
`AiBatchJob` mirrors this shape exactly (per 26-RESEARCH.md Pattern 4's fully-worked model — confirmed viable, no changes needed to the recommendation): `tenant_id` as an explicit indexed FK column (never resolved via a join — same reasoning as `AiFeedback`'s own docstring, lines 9-12: "every query is directly tenant-scoped"), `Base`/`UUIDPrimaryKeyMixin`/`TimestampMixin` reused (`backend/app/db/base.py` lines 15-34, confirmed present), `anthropic_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)`, `status`, `model`/`prompt_version` (frozen at submission time — see Pitfall in RESEARCH.md Pattern 4), `custom_id_hash_map: Mapped[dict] = mapped_column(JSONB, nullable=False)`, `submitted_at`/`ended_at`.

**One import this file currently lacks:** `backend/app/ai/models.py` imports only `String`/`Text`/`ForeignKey`/`UniqueConstraint` from `sqlalchemy` and `UUID` from `sqlalchemy.dialects.postgresql` (lines 19-20) — it has never needed a JSONB column before. The exact import-line precedent to copy is `backend/app/vulnerabilities/models.py` line 9 (`from sqlalchemy.dialects.postgresql import JSONB, UUID`) or `backend/app/assets/models.py` line 7 (same pattern) — either sibling model file's import line is the one to mirror; add `JSONB` to `ai/models.py`'s existing `from sqlalchemy.dialects.postgresql import UUID` line.

**No `Tenant` relationship needed** — confirmed by direct grep: `AiFeedback` has no corresponding `relationship()` declared on `Tenant` (`backend/app/tenants/models.py`), so `AiBatchJob` needs none either; a plain FK column is the established precedent.

**No `conftest.py` registration change needed** — confirmed by direct grep: `backend/tests/conftest.py` explicitly re-imports `app.assets.models`/`app.notifications.models`/`app.tenants.models`/`app.vulnerabilities.models` for side effects (lines 44-48, `# noqa: F401`) but does **not** import `app.ai.models` at all. `AiFeedback` gets registered on `Base.metadata` transitively, via the app's own router-import chain (`app/api/v1/ai/feedback.py` line 31 imports it, and `feedback` is imported by `app/api/v1/ai/__init__.py`, which the test app's own startup imports). `AiBatchJob` will be registered the same way once `batch.py` or the new route imports it — no explicit test-fixture change required, mirroring `AiFeedback`'s own zero-touch precedent exactly.

---

### `backend/alembic/versions/033_add_ai_batch_job.py` (new file)

**Analog:** `032_add_ai_feedback.py` (whole file, 65 lines) — same tenant-FK-table shape, one index, hand-written `op.create_table()` (not autogenerate).

```python
revision = "032_add_ai_feedback"
down_revision = "031_rename_audit_tenant_idx"

def upgrade() -> None:
    op.create_table(
        "ai_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        ...
    )
    op.create_index("ix_ai_feedback_tenant", "ai_feedback", ["tenant_id"])

def downgrade() -> None:
    op.drop_index(...)
    op.drop_table("ai_feedback")
```
`033_add_ai_batch_job.py` sets `revision = "033_add_ai_batch_job"`, `down_revision = "032_add_ai_feedback"`, and creates `ai_batch_jobs` with the same 3-part shape (`op.create_table` → `op.create_index` on `tenant_id` → matching `downgrade()`), plus a second unique index on `anthropic_batch_id` (the poller's lookup key) and the two extra timestamp columns (`submitted_at`, `ended_at` — `DateTime(timezone=True)`, matching `AiFeedback`'s own `created_at`/`updated_at` column style, lines 46-57 of the analog).

**The one new column shape `032` doesn't have a precedent for:** `custom_id_hash_map` (JSONB). The exact migration-level precedent is `backend/alembic/versions/022_add_notifications.py` line 38: `sa.Column("details", postgresql.JSONB, server_default="{}")` — copy this column-definition shape (`postgresql.JSONB`, imported the same way `022`/`032` both already import `from sqlalchemy.dialects import postgresql`) for `custom_id_hash_map`, with `nullable=False` (no default needed — always populated at INSERT time by `run_batch_prewarm()`).

---

### `backend/app/ai/budget.py` — extract `get_month_to_date_spend()`, add `would_exceed_budget_for_batch()`

**Analog:** `check_tenant_budget()`, same file, lines 41-65 — the SUM query to extract.

**Current code (the function to refactor, not rewrite):**
```python
async def check_tenant_budget(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    monthly_cap_usd: float | None,
) -> bool:
    if monthly_cap_usd is None:
        return True
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = (
        await db.execute(
            select(func.sum(AuditLog.details["cost_estimate_usd"].as_float())).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.action.like("ai.%"),
                AuditLog.created_at >= month_start,
            )
        )
    ).scalar_one_or_none() or 0.0
    return spent < monthly_cap_usd
```
**Recommended refactor (RESEARCH.md Pattern 6, confirmed viable — no changes needed):** extract the `month_start`/SUM-query block into a new `get_month_to_date_spend(db, tenant_id) -> float`; `check_tenant_budget()` keeps its exact existing public signature and behavior (calls the new helper, same fail-closed comparison), so **every existing caller (`explain.py::_run_explain_stream()` line 308, and every `explain_*.py` route that transitively calls it) needs zero changes.** Add `would_exceed_budget_for_batch(db, tenant_id, monthly_cap_usd, estimated_batch_cost_usd) -> bool` as a genuinely new function (not a refactor) that adds the pre-estimate to the already-spent figure before comparing to the cap — this is the D-07 pre-submission check `batch.py` calls before `client.messages.batches.create(...)`.

`notify_admins_budget_exceeded()` (lines 68-108) needs **zero changes** — it is already parameterized by `tenant_id` alone, with no request-scoped dependency, so `batch.py`'s skip path calls it verbatim exactly as `explain.py` does today (line 310).

---

### `backend/app/ai/batch.py` (new file) — no single exact analog, three borrowed shapes

**What:** `estimate_batch_cost_usd()`, `run_batch_prewarm()`, `poll_pending_batches()`, `validate_and_cache_batch_result()`. This is the one file in this phase with no single close analog — it is a new orchestration module, and RESEARCH.md's own Pattern 8/System-Architecture-Diagram sections already fully work out its internals. This pattern assignment identifies the THREE existing shapes to borrow from, each for a different piece:

**1. The single-pass validation-gate shape (`validate_and_cache_batch_result()`)** — analog: `_run_explain_stream()`'s SUCCESS-path validation chain, `backend/app/ai/explain.py` lines 392-489 (schema-validate → `recheck_business_rules()` → grounded check → `_contains_leak_marker()` → cache + audit). `validate_and_cache_batch_result()` runs this SAME sequence once, with NO retry loop (there is no live conversation to append a corrective turn to — RESEARCH.md Pattern 8, confirmed correct by direct read: the retry loop lives in the `for attempt_index in range(2):` block, lines 343-489, which is inseparable from the live `client.messages.stream()` call inside it). `_contains_leak_marker` (lines 166-182) is cross-module-importable exactly as `explain_remediation_guidance.py` already imports `contains_dangerous_pattern` from `app.ai.safety` (line 57) — importing a second "private" (`_`-prefixed) helper across the `app.ai.explain` boundary is an already-established convention in this codebase, not a new one.

**2. The own-session background-task shape (`run_batch_prewarm()`/`poll_pending_batches()`)** — analog: `_run_single_sync()`, `backend/app/connectors/scheduler.py` lines 23-50:
```python
async def _run_single_sync(connector_id: str, tenant_id: str) -> None:
    try:
        async with async_session_factory() as db:
            ...
    except Exception as e:
        logger.error(...)
    finally:
        _running_syncs.pop(connector_id, None)
```
Both new functions must open their own `async with async_session_factory() as db:` internally (import target: `from app.db.session import async_session_factory`, confirmed a plain importable callable at `backend/app/db/session.py` line 18, not a FastAPI dependency) — required because once `_scheduler_loop()` wraps their call in `asyncio.create_task(...)`, they are detached from the loop's own `db` variable, exactly as `_run_single_sync()` already is.

**3. The zero-dispatch, audit-only refusal shape (for `errored`/`canceled`/`expired` batch results)** — analog: `_refuse_ungroundable()`, `backend/app/api/v1/ai/explain_remediation_guidance.py` lines 87-111:
```python
async def _refuse_ungroundable(db, *, tenant_id, user_email, finding_id, model) -> AsyncIterator[bytes]:
    await audit_log_ai_call(db, ..., status="ungroundable", cost_estimate_usd=0.0)
    await db.commit()
    yield _sse_event({"type": "error", "kind": "grounded_false"})
```
The poller's own handling of `errored`/`canceled`/`expired` results (RESEARCH.md Pattern 8, lines within the fully-worked `validate_and_cache_batch_result()` recommendation) follows this SAME "audit a distinct status, never touch the cache, cost always `0.0`" shape — these three result types never reach the schema validator at all (there is no payload to validate), mirroring how `_refuse_ungroundable()` never calls `response_model.model_validate_json()` either.

**Reused verbatim, zero changes needed, confirmed by direct read this session:**
- `_estimate_cost_usd(model, usage)` and `_PRICING_PER_MTOK_USD` (`explain.py` lines 98-103, 185-192) — `batch.py` imports both and multiplies by `0.5` at every batch-cost call site (RESEARCH.md Pitfall 4).
- `MAX_TOKENS = 1024` (`explain.py` line 80) — the `worst_case_output_tokens` ceiling for the pre-submission estimate.
- `get_tenant_anthropic_key()` (`tenant_keys.py` lines 31-63) — "skip silently if None" (D-23 parity), same function, same None-means-inert contract.
- `build_cache_key()` / `record_hash()` / `set_cached()` (`cache.py` lines 38-56, 59-71, 87-94) — all pure functions parameterized by an explicit `tenant_id`/`redis_client`, confirmed callable from a non-request context with zero changes (RESEARCH.md Pattern 5).
- `audit_log_ai_call()` (`audit.py` lines 26-74) with `user_email="system:scheduler"` — confirmed already a live, tested contract: `backend/tests/test_ai_audit.py::test_scheduler_audit`, lines 80-103 (reproduced below), already asserts `tenant_id == tenant_a.id` (never the nil-tenant fallback) for exactly this call shape:
```python
async def test_scheduler_audit(db_session, tenant_a):
    await audit_log_ai_call(
        db_session, tenant_id=tenant_a, user_email="system:scheduler",
        model="claude-sonnet-5", usage=_FakeUsage(input_tokens=800, output_tokens=200),
        resource_type="vuln", resource_id=resource_id, status="ok",
    )
    ...
    assert row.user_email == "system:scheduler"
    assert row.tenant_id == tenant_a
    assert row.tenant_id != uuid.UUID(int=0)
```

**The tenant-loop shape (`run_batch_prewarm()`'s "for each active tenant" outer loop)** — analog: the SLA-breach-check block already inside `_scheduler_loop()`, `backend/app/connectors/scheduler.py` lines 136-148:
```python
try:
    async with async_session_factory() as db:
        tenants = (await db.execute(_sel(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
        for t in tenants:
            await backfill_sla_due_dates(db, t.id)
            await check_sla_breaches(db, t.id)
        await db.commit()
except Exception as e:
    logger.error("sla_check_error", error=str(e))
```
This is the exact "SELECT active tenants, loop, per-tenant work, one shared exception boundary" shape `run_batch_prewarm()` should copy for its own per-tenant submission loop (`TenantModel` import: `from app.tenants.models import Tenant as TenantModel`, already the pattern this exact block uses).

---

### `backend/app/connectors/scheduler.py` — add 2 new try/except blocks inside `_scheduler_loop()`

**Analog (the idiom to COPY):** `trigger_background_sync()`, lines 53-62:
```python
def trigger_background_sync(connector_id: str, tenant_id: str) -> bool:
    if connector_id in _running_syncs:
        task = _running_syncs[connector_id]
        if not task.done():
            return False
    task = asyncio.create_task(_run_single_sync(connector_id, tenant_id))
    _running_syncs[connector_id] = task
    return True
```

**Anti-analog (the idiom to AVOID for dispatch, but COPY for the 24h timing gate):** the daily-ticket-sync block, lines 152-165:
```python
global _last_ticket_sync
try:
    now = datetime.now(UTC)
    if _last_ticket_sync is None or (now - _last_ticket_sync).total_seconds() >= 86400:
        async with async_session_factory() as db:
            from app.ticketing.daily_sync import run_daily_ticket_sync
            result = await run_daily_ticket_sync(db)   # <-- INLINE AWAIT: blocks the tick
            ...
        _last_ticket_sync = now
except Exception as e:
    logger.error("daily_ticket_sync_error", error=str(e))
```
D-05 is an explicit hard constraint ("dispatched... via `asyncio.create_task`, never inline in a sync tick") — this block's `await run_daily_ticket_sync(db)` directly inside the `try` is genuinely the WRONG shape to imitate for dispatch, even though its `_last_ticket_sync`-style 24h gate IS exactly the timing-check idiom to copy (a new `_last_ai_batch_prewarm: datetime | None` global, checked the identical way).

**The synthesized new block A (nightly submission — gate-timing from the anti-analog, dispatch-shape from the analog):**
```python
global _last_ai_batch_prewarm
try:
    now = datetime.now(UTC)
    if _last_ai_batch_prewarm is None or (now - _last_ai_batch_prewarm).total_seconds() >= 86400:
        from app.ai.batch import run_batch_prewarm
        asyncio.create_task(run_batch_prewarm())
        _last_ai_batch_prewarm = now
except Exception as e:
    logger.error("ai_batch_prewarm_dispatch_error", error=str(e))
```

**The new block B (every-tick poll — RESEARCH.md Pitfall 3: this ALSO needs `asyncio.create_task`, not just the submission block; there is no existing 24h-gated precedent for this one, since it must run every ~60s tick, not once/day):**
```python
try:
    from app.ai.batch import poll_pending_batches
    asyncio.create_task(poll_pending_batches())
except Exception as e:
    logger.error("ai_batch_poll_dispatch_error", error=str(e))
```
Both blocks slot into `_scheduler_loop()`'s existing one-block-per-concern convention (SLA check lines 136-150, ticket rules lines 114-123, reports lines 125-134, daily ticket sync lines 152-165, daily snapshot lines 167-177, notification alerts lines 179-189 — seven such blocks already exist; these become the 8th and 9th). Global module-level variable declaration goes alongside the existing three (`_running_syncs`, `_scheduler_task`, `_last_ticket_sync`, lines 18-20) — add `_last_ai_batch_prewarm: datetime | None = None` as a 4th.

---

### `backend/app/vulnerabilities/service.py` — add `get_top_findings_for_ai_batch()`

**Analog (the KEV/CVSS/SLA tiebreak idiom):** the `sort="triage"` branch, same file, lines 92-99:
```python
if filters.sort == "triage":
    data_q = data_q.order_by(
        desc(Vulnerability.cisa_kev),
        nulls_last(desc(Vulnerability.cvss_v3_score)),
        nulls_last(asc(Vulnerability.sla_due_at)),
    )
```
`nulls_last`/`desc`/`asc` are already imported at the top of this exact file (line 9: `from sqlalchemy import Select, asc, case, desc, func, nulls_last, or_, select, update`) — the new query should use this SAME function-style `nulls_last(desc(col))` idiom (not `backend/app/assets/service.py`'s method-style `col.desc().nullslast()`, line 70 — a second, different-but-equivalent SQLAlchemy idiom that exists elsewhere in the codebase; staying consistent with the file the new function will actually live in matters more than which idiom is "more correct").

**Analog (the `Asset.risk_score` ordering idiom, since `vulnerabilities/service.py` itself has never sorted by it before):** `backend/app/assets/service.py::list_assets()`, line 70:
```python
.order_by(Asset.risk_score.desc().nullslast(), Asset.hostname.asc())
```
Confirms `Asset.risk_score` (an `Integer | None` column, `backend/app/assets/models.py` line 39) is already an established, live sort key elsewhere in the codebase — the new query's primary sort key is not a novel idea, just a novel join (`Vulnerability` → `Asset`, not `Asset` alone).

**Analog (the `OPEN`+`IN_PROGRESS` status-set convention for "open" findings, confirmed identical in THREE separate existing files, corroborating RESEARCH.md's own recommendation):**
- `backend/app/ai/grounding.py::get_asset_posture()`, lines 109-113 (via `vuln_q`'s `.where(...)`).
- `backend/app/assets/risk_score.py::compute_risk_scores()`, line 119 — `Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])`.
- `backend/app/vulnerabilities/models.py`'s own `VulnStatus` enum, lines 23-28, confirms `OPEN`/`IN_PROGRESS`/`REMEDIATED`/`SUPPRESSED`/`FALSE_POSITIVE` are the only five values — "OPEN" as D-01 uses the word colloquially must mean "not yet resolved" (`OPEN` + `IN_PROGRESS`), not literally `status == "OPEN"` alone, or a finding an analyst has already started triaging would be silently excluded from its own priority batch.

**Recommended new function (RESEARCH.md Pattern 3, confirmed viable — no changes needed to the query shape; Assumption A1 is a plan-time product decision, not a codebase-fact question, see "Corroboration" below):**
```python
async def get_top_findings_for_ai_batch(
    db: AsyncSession, tenant_id: uuid.UUID, limit: int,
) -> list[uuid.UUID]:
    result = await db.execute(
        select(Vulnerability.id)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .order_by(
            nulls_last(desc(Asset.risk_score)),
            desc(Vulnerability.cisa_kev),
            nulls_last(desc(Vulnerability.cvss_v3_score)),
            nulls_last(asc(Vulnerability.sla_due_at)),
        )
        .limit(limit)
    )
    return [row[0] for row in result.all()]
```
This lives in `vulnerabilities/service.py` (a list/sort concern, alongside `list_vulnerabilities()`'s own sort logic) rather than `ai/grounding.py` — the file-placement decision RESEARCH.md's Recommended Project Structure already made and this pass confirms is consistent with how `list_assets()`'s own risk-ordering lives in `assets/service.py`, not in any AI-domain file.

---

### `backend/app/api/v1/ai/explain_prioritization.py` (new file)

**Analog:** `explain_host.py` (whole file, 103 lines) — chosen over `explain_remediation_guidance.py` specifically because Pattern 7 (RESEARCH.md, confirmed by direct read) establishes the on-demand fallback needs **no** `dangerous_pattern_check` kwarg and **no** pre-generation deterministic refuse gate — `explain_host.py` is the simpler, more structurally identical two-route shape (POST dispatch + GET cache-check, UUID-keyed, single 404, no extra control flow), not `explain_remediation_guidance.py` (which has both extra pieces this view doesn't need).

**Full shape to mirror** (lines 37-103 of `explain_host.py`):
```python
def _allowlisted_hash_fields(record: Any) -> dict[str, Any]:
    _system_prompt, user_blocks = build_explain_host_prompt(record)
    text = user_blocks[0]["text"]
    start = text.index(">") + 1
    end = text.rindex("</scanner_data>")
    return json.loads(text[start:end])

@router.post("/explain-host/{asset_id}")
async def explain_host(asset_id, db, user: Depends(require_analyst), redis_client) -> StreamingResponse:
    record = await get_asset_posture(db, user.tenant_id, asset_id)
    if record is None:
        raise HTTPException(404, "Asset not found")
    return StreamingResponse(
        _run_explain_stream(db, tenant_id=..., resource_type="host", resource_id=..., record=record,
                             build_prompt=build_explain_host_prompt, response_model=ExplainHostResponse,
                             redis_client=redis_client, allowed_source_fields=HOST_ALLOWLIST,
                             get_prompt_version=host_prompt_version),
        media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.get("/explain-host/{asset_id}")
async def get_explain_host_cache(asset_id, db, user: Depends(require_viewer), redis_client) -> dict[str, Any]:
    record = await get_asset_posture(db, user.tenant_id, asset_id)
    if record is None:
        raise HTTPException(404, "Asset not found")
    model, _cap = await get_model_and_budget(db, user.tenant_id)
    the_hash = record_hash(_allowlisted_hash_fields(record))
    cache_key = build_cache_key(user.tenant_id, "host", str(asset_id), the_hash, model, host_prompt_version())
    cached = await get_cached(redis_client, cache_key)
    if cached is None:
        return {"cached": False}
    return {"cached": True, **cached}
```
The new file swaps: `get_asset_posture` → `get_prioritization_context`; `build_explain_host_prompt`/`ExplainHostResponse`/`HOST_ALLOWLIST`/`host_prompt_version` → their `prioritization` equivalents; `resource_type="host"` → `"prioritization"`; route path `/explain-prioritization/{finding_id}` (UUID, matching `explain_host.py`'s `asset_id` shape, not `explain_remediation.py`'s CVE-string shape).

**The ONE genuinely new piece this route needs that `explain_host.py`'s GET does NOT have** — the `queued` signal (D-02/UI-SPEC states 3/4). RESEARCH.md's Pattern 4 already specifies the exact query: `SELECT 1 FROM ai_batch_jobs WHERE tenant_id = :t AND status = 'in_progress' AND custom_id_hash_map ? :finding_id` (JSONB containment operator). This is structurally closer to `explain_remediation_guidance.py`'s own precedent for "the GET route returns one additive boolean beyond the universal `{cached: False}` shape" (lines 176-183: `groundable`) than to anything in `explain_host.py` — so while the ROUTE's overall two-function shape mirrors `explain_host.py`, the GET handler's return-value shape for the miss case mirrors `explain_remediation_guidance.py`'s `{"cached": False, "groundable": <bool>}` precedent, substituting `queued` for `groundable`:
```python
    cached = await get_cached(redis_client, cache_key)
    if cached is None:
        queued = await _is_finding_queued(db, user.tenant_id, finding_id)  # new helper, the JSONB containment query
        return {"cached": False, "queued": queued}
    return {"cached": True, **cached}
```

---

### `backend/app/api/v1/ai/__init__.py` — router registration

**Analog:** same file, lines 32-47 (exact, same-file, 3-line pattern already extended once for Phase 25).

```python
from app.api.v1.ai import (
    explain_host,  # noqa: E402
    explain_remediation,  # noqa: E402
    explain_remediation_guidance,  # noqa: E402
    explain_vuln,  # noqa: E402
    feedback,  # noqa: E402
    spike,  # noqa: F401
    status,  # noqa: E402
)

ai_router.include_router(explain_vuln.router)
ai_router.include_router(explain_host.router)
ai_router.include_router(explain_remediation.router)
ai_router.include_router(explain_remediation_guidance.router)
ai_router.include_router(feedback.router)
ai_router.include_router(status.router)
```
Add `explain_prioritization` to the import tuple and one new `ai_router.include_router(explain_prioritization.router)` line. The module-level one-line-per-router comment block (lines 14-31) already documents each sub-router's purpose with a "Plan N's D-xx..." citation style — extend it with a matching entry for the new router, following the exact convention the `explain_remediation_guidance` comment (lines 23-27) already established.

---

### Frontend: `frontend/src/components/ai/ai-explanation-section.tsx`

**Analog:** the file's own `isRemediationGuidance` discriminator + copy-object pattern, lines 164-184, and the `groundable === false` branch, lines 278-287 — this is the SAME shared component Phase 24 built and Phase 25 already extended once for a 4th `resourceType`; Phase 26 adds a 5th.

**1. `isPrioritization` discriminator** (mirrors lines 164-169 exactly):
```typescript
const isRemediationGuidance = resourceType === 'remediation-guidance';
const heading = isRemediationGuidance ? 'Remediation guidance' : 'AI Explanation';
const triggerLabel = isRemediationGuidance ? 'Get remediation guidance' : 'Explain this vuln';
const viewerEmptyText = isRemediationGuidance
  ? 'No remediation guidance generated yet.'
  : 'No AI explanation generated yet.';
```
Needs a 3rd branch per copy variable — either nested ternaries (`isPrioritization ? '...' : isRemediationGuidance ? '...' : '...'`) or a small lookup object; 26-UI-SPEC.md's Copywriting Contract already locks every exact string (`heading: "Prioritization"`, `triggerLabel: "Explain the priority"`, `viewerEmptyText: "No prioritization narrative generated yet."`).

**2. `insufficientEvidenceCopy`** (mirrors lines 176-184) needs its own 3rd branch — UI-SPEC's locked strings: heading `"Not enough signal to explain priority reliably"`, body naming exploit/KEV/SLA/severity signal.

**3. `DegradedCardProps`/`DegradedCard`** (lines 30-74) needs one additive field for the Clock icon, per 26-RESEARCH.md's own Code Examples section (confirmed the correct, minimal shape — `icon?: 'sparkles' | 'clock'`, defaulting to `'sparkles'` so every existing call site is unaffected):
```typescript
type DegradedCardProps = {
  variant: 'neutral' | 'amber' | 'danger';
  heading: string;
  body: string;
  action?: { label: string; onClick?: () => void; href?: string };
};
```
Add `icon?: 'sparkles' | 'clock'` and branch the render (lines 54-58, currently `variant === 'amber' || variant === 'danger' ? <AlertTriangle .../> : <Sparkles .../>`) to check `icon === 'clock'` first when `variant === 'neutral'`.

**4. The new `queued` branch** — placement analog: the `groundable === false` branch, lines 278-287:
```typescript
} else if (cacheQuery.data?.cached === false && cacheQuery.data?.groundable === false) {
  body = <DegradedCard variant="neutral" heading={...} body={...} />;
} else if (isAnalystOrAbove) {
  body = (
    <button type="button" onClick={() => void start()} className={SECONDARY_BTN_CLASS}>
      {triggerLabel}
    </button>
  );
```
The new `cacheQuery.data?.cached === false && cacheQuery.data?.queued === true` branch must be inserted **before** the `isAnalystOrAbove` trigger-button branch, exactly where `groundable === false` sits today — same structural-guarantee reasoning (UI-SPEC state 3/4 "no button ever shown [when queued and Viewer]" must be enforced by branch ORDER, not by a copy choice). Checked `=== true` explicitly (not truthy), mirroring how `groundable` is checked `=== false` explicitly — every OTHER resourceType's GET response never returns `queued` at all, so this new field must not accidentally match on `undefined`.

---

### Frontend: `frontend/src/lib/queries/use-explain-cache.ts` — add `queued?: boolean`

**Analog:** the file's own `groundable?: boolean` addition (whole file is 36 lines; the type is lines 17-19):
```typescript
export type ExplainCacheResult =
  | { cached: false; groundable?: boolean }
  | ({ cached: true } & ExplainVulnResponse);
```
Becomes `{ cached: false; groundable?: boolean; queued?: boolean } | ({ cached: true } & ExplainVulnResponse)`. The hook body (lines 28-36, a plain `useQuery` wrapping `api<ExplainCacheResult>(...)`) needs **zero changes** — `queued` rides along in the already-generic JSON response exactly as `groundable` does, confirmed by direct read.

---

### Frontend: `frontend/src/components/vulnerabilities/drill-content.tsx` — new section mount

**Analog:** the existing `remediation-guidance` section mount, lines 307-322:
```tsx
{/* Phase 25 D-06 placement: "Remediation guidance" sits AFTER the
    raw scanner Remediation text and BEFORE Activity... */}
<section aria-labelledby="drill-remediation-guidance-h">
  <AiExplanationSection
    resourceType="remediation-guidance"
    resourceId={v.id ?? idOrCve}
    headingId="drill-remediation-guidance-h"
    onCopyToDescription={setDescription}
  />
</section>
```
Per 26-UI-SPEC.md's locked placement (Header → CVSS → Affected hosts → Description → **AI Explanation** → **Prioritization (NEW)** → Remediation (raw) → Remediation guidance → Activity → Actions), the new section goes **between** the existing `drill-ai-h` mount (lines 289-295) and `drill-remed-h` (lines 297-305) — NOT after `drill-remediation-guidance-h` like the naive "insert at the bottom" placement would suggest:
```tsx
<section aria-labelledby="drill-ai-h">
  <AiExplanationSection resourceType="vuln" resourceId={v.id ?? idOrCve} />
</section>

{/* NEW: insert here, before drill-remed-h */}
<section aria-labelledby="drill-prioritization-h">
  <AiExplanationSection
    resourceType="prioritization"
    resourceId={v.id ?? idOrCve}
    headingId="drill-prioritization-h"
  />
</section>

<section aria-labelledby="drill-remed-h">
  ...
</section>
```
`headingId` is already a first-class, unique-per-mount prop (`ai-explanation-section.tsx` `Props` type, lines 103-128) specifically so a THIRD mount on the same page never collides on DOM `id` — confirmed no change needed there, mirroring exactly how the `remediation-guidance` mount already passes its own `headingId="drill-remediation-guidance-h"`. **`onCopyToDescription` is deliberately omitted** on this new mount — that prop is scoped specifically to the remediation-guidance view's "pre-fill the ticket description" affordance (D-09 scope fence, confirmed by the `Props` type's own doc comment, lines 117-127: "Omitted by every mount except drill-content.tsx's resourceType='remediation-guidance' mount"); the prioritization view has no ticket-description interaction, so its mount takes only the 3 props the original `resourceType="vuln"` mount takes.

---

### Frontend: `frontend/src/lib/ai/use-explain-stream.ts` — no change needed

Confirmed by direct read of the whole file (143 lines). `resourceType` is already a fully generic string parameter, interpolated into the fetch URL at line 70 (`` `${API_URL}/api/v1/ai/explain-${resourceType}/${resourceId}` ``) — `'prioritization'` flows through unchanged. `ExplainVulnResponse`'s shape (lines 28-33: `summary`/`business_risk`/`citations`/`grounded`) is already exactly what `ExplainPrioritizationResponse` produces (zero new fields, per D-03) — no new TypeScript type is needed for the streamed payload. The error `kind` union (lines 35-39, 46) does **not** need a new member for this phase — confirmed by RESEARCH.md Pattern 7's own finding, corroborated here: prioritization has no `dangerous_pattern_check` gate, so the `'unsafe'` kind (added in Phase 25) is never emitted by this route, and no additional kind is needed either.

### Frontend: `frontend/src/lib/queries/keys.ts` — no change needed

Confirmed by direct read. `queryKeys.ai.explain(resourceType, resourceId)` (lines 96-99) is already fully generic — `resourceType='prioritization'` produces a correctly-namespaced cache key (`['ai', 'explain', 'prioritization', resourceId]`) with zero code changes, exactly as `'remediation-guidance'` required none when Phase 25 shipped.

---

## Shared Patterns

### The allowlist-quadruplet discipline (grounding.py / schemas.py / prompt_builder.py / the new route, together)
**Source:** the VULN/HOST/REMEDIATION/REMEDIATION_GUIDANCE quadruplet across `backend/app/ai/{grounding,schemas,prompt_builder}.py` and `backend/app/api/v1/ai/{explain_vuln,explain_host,explain_remediation,explain_remediation_guidance}.py`.
**Apply to:** every new prioritization file in this phase.
Every existing view follows the identical five-piece shape confirmed by direct read of all four existing instances this session: (1) a `*_ALLOWLIST` frozenset, (2) an `Allowlisted*` Pydantic model with `model_config = {"extra": "forbid"}` and every field `| None = None`, (3) a `_to_allowlisted_*()` field-by-field constructor via the shared `_get_field()`, (4) a `SYSTEM_PROMPT_*` + `FEW_SHOT_*` pair rendered via `_render_few_shot()`, (5) a thin route with a matching POST (dispatch) + GET (cache-check, `require_viewer`) pair. Phase 26 adds a 5th instance; no piece should be reinvented.

### `_run_explain_stream()` engine reuse — zero changes
**Source:** `backend/app/ai/explain.py`, lines 258-518 (whole function, confirmed unchanged since Phase 25 added the `dangerous_pattern_check` parameter at line 272).
**Apply to:** the new on-demand route only — called with `dangerous_pattern_check=None` (the default), exactly as `explain_vuln.py`/`explain_host.py`/`explain_remediation.py` already do (none of the three pass this kwarg).
Cache/budget/audit/RBAC/BYOK-key-resolution/inflight-guard are all already parameterized by `resource_type`/`resource_id`/`tenant_id` and require zero new code for a 5th view — confirmed by direct read, no divergence from RESEARCH.md's claim.

### Tenant-scoped cache key composition — zero changes
**Source:** `backend/app/ai/cache.py`, lines 38-56 (`build_cache_key`), 59-71 (`record_hash`).
**Apply to:** the new route's GET cache-check AND the batch poller's cache write — the SAME function, called from two different call sites (interactive route, scheduler-originated poller), producing the identical key format for the identical `(tenant_id, resource_type, resource_id, hash, model, prompt_version)` tuple regardless of which path generated the narrative — this identity is what makes D-06 ("a batch-warmed narrative is a plain cache hit for the analyst") true with zero extra plumbing.
`resource_type="prioritization"` as the namespace segment — no code change needed in `cache.py` itself, only a new string literal at each of the two call sites (interactive route, batch poller).

### Audit-row-per-attempt discipline
**Source:** `backend/app/ai/audit.py` (whole file) + `explain.py`'s `_audit()` wrapper, lines 226-255.
**Apply to:** every new status this phase introduces — `"batch_skipped_budget_exceeded"`, `"batch_errored"`, `"batch_canceled"`, `"batch_expired"`, plus the existing `"ok"`/`"validation_failed"`/`"injection_flagged"` statuses reused for a batch item's outcome.
`AuditLog.details` is free-form JSONB (`audit.py` lines 64-70) — every new status string needs zero schema/migration change, exactly as the phase-25-added statuses (`"ungroundable"`, `"unsafe_denylisted"`) required none.

### Mass-assignment / model-config discipline on every new Pydantic model
**Source:** every existing `Allowlisted*` model (`AllowlistedFinding`, `AllowlistedHostPosture`, `AllowlistedRemediationGuidance`, all with `model_config = {"extra": "forbid"}`).
**Apply to:** `AllowlistedPrioritization`.
Same defensive shape, zero exceptions — an unexpected extra key can never ride along even if a future caller hands the constructor a raw, PII-bearing row.

### No-Rank enforcement is structural, not a convention to remember
**Source:** `ExplainResponseBase` (`schemas.py` lines 44-67) has no numeric field of any kind.
**Apply to:** `ExplainPrioritizationResponse` — `pass`, zero fields, the base class itself makes a rank field impossible without a directly-reviewable diff to the shared base every other view also depends on. The UI-SPEC's own repo-wide grep check (`priority`/`rank`/`ai_score` touching any table/sort/column definition) is a CI-shaped, not file-shaped, enforcement mechanism — see "No Analog Found" below.

---

## No Analog Found / Flagged Gaps

| Item | Role | Data Flow | Reason |
|---|---|---|---|
| Scheduler-context Redis client access | infrastructure / config | — | **Confirmed structural gap, not just an open question.** `backend/app/redis_client.py` (13 lines, whole file read this session) exposes only `get_redis(request: Request) -> redis.Redis`, a FastAPI dependency requiring a `Request` object. `app.state.redis` is constructed in `backend/app/main.py` lines 118-127 (`redis.Redis(connection_pool=redis.BlockingConnectionPool.from_url(settings.redis_url, decode_responses=True, socket_timeout=2.0, ...))`) — and this happens **after** `start_scheduler()` is called at lines 108-110, confirming the scheduler module has no path to `app.state` even if it wanted one. `async_session_factory` (the DB equivalent) is a plain importable module-level callable (`db/session.py` line 18) with no such problem. **Recommendation for the planner:** either (a) add a small `get_redis_client() -> redis.Redis` factory to `redis_client.py` that both `main.py`'s lifespan and the new `batch.py` call (single construction site, mirrors `async_session_factory()`'s directly-importable shape), or (b) have `batch.py` construct its own `redis.Redis(connection_pool=redis.BlockingConnectionPool.from_url(settings.redis_url, ...))` mirroring `main.py` lines 118-126 verbatim at module scope. Either is a small, additive, low-risk change — flagged here as a genuine gap RESEARCH.md's Open Question 1 correctly flagged but did not confirm this precisely. |
| No-rank repo-wide grep check (UI-SPEC "Executor-facing check" / RESEARCH.md Validation Architecture) | static/CI check | — | No file-shaped analog exists for "a grep assertion wired into CI." RESEARCH.md itself flags the mechanism as undecided ("recommend wiring as a small Vitest test using Node's `fs`, or a documented manual pre-merge check"). Not a blocker — flagged so the planner picks ONE mechanism rather than treating it as an implicit, unowned checklist item. |
| `backend/app/ai/batch.py` as a whole file | service | batch/event-driven | No single existing file plays this role (submit + poll + validate + a durable job registry, dispatched from a scheduler). See the composite Pattern Assignment above — three DIFFERENT existing files each supply one piece of the shape; there is no fourth file to point to for "the whole thing." This mirrors Phase 25's own experience with `safety.py` (a new file whose calling-convention analog and content had to come from different places). |
| `DANGEROUS_PATTERNS`-style content denylist for prioritization | — | — | **Not needed.** Confirmed by direct read of RESEARCH.md Pattern 7's reasoning and cross-checked against the UI-SPEC's own Color table (`--color-danger` has zero reserved usage in this phase): prioritization narratives are explanatory prose about existing structured facts, not actionable remediation steps, so there is no destructive-command risk class to defend against. `contains_dangerous_pattern()` (`safety.py`, unchanged) is not imported by the new route. |

---

## No Change Needed (confirmed by direct read, listed for planner completeness)

| File | Why |
|---|---|
| `frontend/src/lib/ai/use-explain-stream.ts` | Fully generic on `resourceType`; response shape already matches; no new error `kind` needed (see Pattern Assignment above). |
| `frontend/src/lib/queries/keys.ts` | `ai.explain(resourceType, resourceId)` already generic. |
| `frontend/src/components/ai/ai-explanation-citations.tsx` | The two-tier citation renderer is resourceType-agnostic already (takes `ExplainVulnResponse`-shaped `data`, has no view-specific branch anywhere in its 151 lines) — renders the prioritization narrative's citations identically to every other view's, zero changes. |
| `backend/app/ai/cache.py`, `backend/app/ai/tenant_keys.py` | Both already fully parameterized, reused verbatim by the new route AND the new batch code (RESEARCH.md Pattern 5, confirmed). |
| `backend/app/ai/audit.py` | `audit_log_ai_call()`'s free-form JSONB `details` absorbs every new status string with zero schema change. |
| `backend/app/ticketing/router.py`-style "no change required" confidence — n/a this phase (no ticketing files touched) | Phase 26 does not touch the ticketing domain at all (that's Phase 27/AID-01) — noted only to confirm the phase boundary holds; no ticketing file appears in this map. |

---

## Corroboration & Corrections to 26-RESEARCH.md

Direct reads this session either confirmed RESEARCH.md's claims exactly, or sharpened three of them:

1. **Assumption A1 (ASSET-02 is per-asset, not per-finding) — CONFIRMED, unchanged.** Direct read of `backend/app/vulnerabilities/models.py` (whole `Vulnerability` class, lines 46-81) confirms there is no `risk_score` column on `Vulnerability`. Direct read of `backend/app/assets/risk_score.py::compute_risk_scores()` (lines 84-147) confirms `Asset.risk_score` is a per-asset aggregate (SUM of severity×exploit×KEV weights across that asset's open/in-progress vulns, piecewise-normalized 0-100). RESEARCH.md's recommended query (join to `Asset.risk_score` as primary sort, KEV/CVSS/SLA as finding-level tiebreak) is corroborated by this session's read of `backend/app/assets/service.py::list_assets()` line 70, which proves `Asset.risk_score` is ALREADY a live, established sort key elsewhere in the app (just never joined from the `Vulnerability` side before). This remains a plan-time product decision (per-asset-primary-with-tiebreak vs. a pure `sort=triage` per-finding reinterpretation), not a codebase-fact question — the codebase fact (no per-finding column exists) is settled.

2. **The durable-table finding (`AiBatchJob` must be Postgres, not an in-memory dict) — CONFIRMED, unchanged, and sharpened with a concrete zero-touch precedent.** Direct read of `backend/app/connectors/scheduler.py` (whole file) confirms `_running_syncs: dict[str, asyncio.Task]` (line 18) is scoped to connector syncs that finish within one process lifetime — there is no existing precedent in this file for anything that must survive a restart. `AiFeedback` (`backend/app/ai/models.py` lines 26-48) is the correct, sole existing "new AI-domain Postgres table" analog, and this session additionally confirmed `AiFeedback` needed **zero** `conftest.py` registration change (it registers on `Base.metadata` transitively via the router-import chain) — so `AiBatchJob` needs none either, a small but concrete simplification beyond what RESEARCH.md stated.

3. **The 50%-batch-cost-discount finding — CONFIRMED, unchanged.** Direct read of `explain.py::_estimate_cost_usd()` (lines 185-192) and `_PRICING_PER_MTOK_USD` (lines 98-103) confirms both are standard (non-batch) per-token rate tables with no batch-aware branch — every batch-derived cost figure this phase writes must apply `× 0.5` at the call site, exactly as RESEARCH.md's Pitfall 4 states. No existing code anywhere in `backend/app/ai/` currently applies any such discount (confirmed: `grep`-style read of the whole `explain.py` file found no `0.5` multiplier anywhere).

4. **CORRECTED: `get_top_findings_for_ai_batch()`'s test home.** RESEARCH.md's own Validation Architecture table flagged `test_vulnerabilities_service.py` with "❌ Wave 0 (extends existing file — verify exact filename at plan time; no `test_vulnerabilities_service.py` was confirmed to exist this session)." Confirmed this session: **that file does not exist.** `backend/tests/` contains `test_vulnerabilities.py` (70 lines, class-based, covers `TestPagination`/`TestVulnerabilityFilter`/`TestDashboardStats` — schema/pagination-shape tests, not a DB-seeded ordering-query test) and, more usefully, **`test_triage_sort.py`** (95 lines) — a dedicated file that seeds `Vulnerability` rows directly via a `_seed_vuln()` helper and asserts KEV/CVSS/SLA ordering against a live `client`/`db_session`/`tenant_a` fixture set. This is the correct, closest analog for a NEW `get_top_findings_for_ai_batch()` test (which additionally needs `Asset.risk_score` seeded) — either extend `test_triage_sort.py` or create a sibling `test_top_findings_for_ai_batch.py` following its exact `_seed_vuln()`-style helper convention.

5. **CORRECTED/SHARPENED: the test-file analogs for the new prioritization test files are now live code, not forward references.** RESEARCH.md's Pattern 7 table and Wave 0 Gaps both correctly NAME `test_ai_prompt_builder_remediation_guidance.py` and `test_ai_explain_remediation_guidance.py` as the analogs — this session confirms both files exist, are fully shipped, and extracted their exact test-function names for planner precision: `test_ai_prompt_builder_remediation_guidance.py` (198 lines: `test_remediation_guidance_allowlist_has_12_fields_no_owner_pii`, `test_allowlist_enforcement_excludes_owner_pii_from_dict`, `test_allowlist_enforcement_excludes_owner_pii_from_attribute_object`, `test_remediation_guidance_prompt_version_is_stable_and_distinct_from_host`, among others) and `test_ai_explain_remediation_guidance.py` (355 lines: `test_post_as_analyst_groundable_finding_returns_200_sse_with_headers`, `test_post_as_viewer_returns_403`, `test_get_cache_check_miss_groundable_true_no_dispatch`, `test_cross_tenant_finding_id_not_resolvable`, among others). A NEW `test_ai_grounding_prioritization.py` (analog: `test_ai_grounding_remediation_guidance.py`, 190 lines — RESEARCH.md's Wave 0 Gaps table does not explicitly list this file, but the quadruplet-completeness discipline this codebase has followed twice now (Phase 24→25) implies the grounding query gets its own dedicated test file, not just inline assertions inside the prompt-builder or route tests) is recommended as an addition to RESEARCH.md's own gap list.

6. **CONFIRMED: `Asset.department` is a real, actively-synced field, not a placeholder column.** Direct grep across `backend/app/connectors/` confirms `department` is written by THREE separate sync paths — `humaans_sync.py` line 175 (HR), `jamf_sync.py` line 178 (MDM), and read (not written) at `assets/router.py` line 342 for the existing `/assets/[id]` detail endpoint. This corroborates D-04's premise that department is already populated, real data for the narrative to cite — not a field the phase would be introducing alongside its first real writer.

---

## Metadata

**Analog search scope:** `backend/app/ai/` (all 10 files), `backend/app/api/v1/ai/` (all 8 files), `backend/app/connectors/scheduler.py`, `backend/app/vulnerabilities/{models,service}.py`, `backend/app/assets/{models,service,risk_score}.py`, `backend/app/redis_client.py`, `backend/app/main.py` (lifespan section), `backend/app/db/session.py` (spot-check), `backend/app/tenants/models.py` (spot-check), `backend/alembic/versions/{032_add_ai_feedback,022_add_notifications}.py`, `backend/tests/{test_ai_*,test_triage_sort,test_vulnerabilities,test_connector_health}.py` (existence + function-name level), `frontend/src/components/ai/*.tsx`, `frontend/src/components/vulnerabilities/drill-content.tsx`, `frontend/src/lib/{ai/use-explain-stream,queries/use-explain-cache,queries/keys}.ts`

**Files read directly, in full, this session:** 26 backend source files + 2 alembic migrations + 5 backend test files (existence/structure-level) + 5 frontend source files = 38 files, none re-read (all non-overlapping single-pass reads per file).

**Pattern extraction date:** 2026-07-30
**Corroboration method:** Every claim in this document is either re-derived from a direct `Read` of the cited file/line range in this session, or a direct `Bash`/`grep` existence-and-shape check — no pattern here is asserted solely on 26-RESEARCH.md's own prose without an independent re-read. Three corrections are flagged explicitly above (test-file existence for the top-N query; the Redis-access gap's precise mechanics; the now-shipped Phase 25 test files as sharper analogs than the Phase-24-era files RESEARCH.md's Pattern 7 table sometimes cited).
