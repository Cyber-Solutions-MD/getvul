"""The batch submitter + single-pass result validator (AIP-02, Phase 26
Plan 07) -- the nightly Message Batches API pre-warm job. A composite new
module: no single existing file plays this whole role, so its three
functions each borrow a different existing shape (26-PATTERNS.md):
`validate_and_cache_batch_result()` mirrors `explain.py::_run_explain_stream()`'s
SUCCESS-path validation chain minus the retry loop (there is no live
conversation to retry within for a completed batch item);
`run_batch_prewarm()` mirrors `scheduler.py::_run_single_sync()`'s
own-session background-task shape plus the SLA-check block's active-tenant
loop; the budget-skip path mirrors
`explain_remediation_guidance.py::_refuse_ungroundable()`'s audit-only,
zero-dispatch refusal shape.

Two Critical properties enforced here, mirroring explain.py's own module
docstring:

1. **Per-tenant BYOK client, never shared (T-24-19/D-05/SC3).**
   `run_batch_prewarm()` takes NO externally-injected shared client. Inside
   EVERY tenant loop iteration, a FRESH `AsyncAnthropic` is built from
   THAT tenant's own resolved key via `(anthropic_client_factory or
   _default_client_factory)(key)` -- the identical per-tenant-fresh-client
   contract `explain.py` already enforces. A tenant's key can never sign
   another tenant's batch; there is no shared/fallback key, and
   `anthropic_client_factory` exists ONLY as a test seam (mirrors
   `_run_explain_stream()`'s own seam).
2. **Fail-closed budget, never a silent partial (D-07).** The batch's cost
   is pre-estimated and checked against the tenant's cap BEFORE
   `client.messages.batches.create()` ever runs. A would-breach batch is
   skipped + admin-alerted + audited `batch_skipped_budget_exceeded` --
   never submitted, never partially submitted.

The 50% batch discount (RESEARCH Pitfall 4) is applied at BOTH cost sites:
`estimate_batch_cost_usd()`'s pre-submission estimate, and
`validate_and_cache_batch_result()`'s actual-cost audit write. Forgetting
either one would make `check_tenant_budget()`'s month-to-date SUM
systematically over-count real spend by 2x.

Nothing in this module is wired into the scheduler yet (Plan 08) --
`run_batch_prewarm()`/`validate_and_cache_batch_result()` are directly
test-invoked here, with a fake Anthropic client injected via the
`anthropic_client_factory` seam.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import redis.asyncio as redis
from anthropic import AsyncAnthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.audit import audit_log_ai_call
from app.ai.budget import notify_admins_budget_exceeded, would_exceed_budget_for_batch
from app.ai.cache import build_cache_key, get_cached, record_hash, set_cached
from app.ai.explain import (
    _DEFAULT_PRICING_PER_MTOK_USD,
    _PRICING_PER_MTOK_USD,
    MAX_TOKENS,
    _build_output_config,
    _contains_leak_marker,
    _default_client_factory,
    _estimate_cost_usd,
    _extract_scanner_data,
    get_model_and_budget,
)
from app.ai.grounding import get_prioritization_context
from app.ai.models import AiBatchJob
from app.ai.prompt_builder import (
    PRIORITIZATION_ALLOWLIST,
    SYSTEM_PROMPT_PRIORITIZATION,
    build_explain_prioritization_prompt,
    prioritization_prompt_version,
)
from app.ai.schemas import BusinessRuleError, ExplainPrioritizationResponse, recheck_business_rules
from app.ai.tenant_keys import get_tenant_anthropic_key
from app.db.session import async_session_factory
from app.redis_client import get_redis_client
from app.tenants.models import Tenant
from app.vulnerabilities.service import get_top_findings_for_ai_batch

_logger = logging.getLogger(__name__)

# Zero-token usage sentinel for an audit row where no model call was ever
# dispatched (the budget-skip path) -- mirrors explain.py's own _ZERO_USAGE
# shape exactly. `audit_log_ai_call()` unconditionally reads
# `usage.input_tokens`/`usage.output_tokens`; passing a bare `None` raises
# AttributeError (Rule 1 fix -- see 26-07-SUMMARY.md Deviations).
_ZERO_USAGE = SimpleNamespace(input_tokens=0, output_tokens=0)


async def estimate_batch_cost_usd(
    client: AsyncAnthropic,
    model: str,
    requests: list[Request],
) -> float:
    """Pre-submission cost estimate for a Message Batch (D-07, RESEARCH
    Pattern 6): sums each request's real `count_tokens()` input-token count
    plus a worst-case output ceiling (`len(requests) * MAX_TOKENS`) at the
    model's per-token rate, then applies the Message Batches API's flat 50%
    discount (RESEARCH Pitfall 4) -- a batch of K identical requests costs
    exactly half its interactive equivalent.

    `requests` are the SAME `Request`/`MessageCreateParamsNonStreaming`
    objects `run_batch_prewarm()` is about to hand to
    `client.messages.batches.create()`. Both are read via DICT-style access
    (`req["params"]["system"]`), NOT attribute access. This is a deliberate
    correction (Rule 1 -- see 26-07-SUMMARY.md Deviations), not a stylistic
    choice: direct introspection of the installed `anthropic==0.120.2` SDK
    confirms `Request`/`MessageCreateParamsNonStreaming` are `TypedDict`
    subclasses, which construct plain nested `dict`s at runtime --
    `type(Request(custom_id="x", params=...))` is exactly `dict`, so
    `req.params` raises `AttributeError`. This is unlike the Pydantic
    `BaseModel` RESPONSE objects (`MessageBatch`,
    `MessageBatchIndividualResponse`) the poller (Plan 08) reads on the
    RETRIEVAL side, which genuinely do support attribute access -- the two
    sides of this same API use different runtime shapes.
    """
    input_rate, output_rate = _PRICING_PER_MTOK_USD.get(model, _DEFAULT_PRICING_PER_MTOK_USD)
    total_input_tokens = 0
    for req in requests:
        params = req["params"]
        counted = await client.messages.count_tokens(
            model=model,
            system=params["system"],
            messages=params["messages"],
        )
        total_input_tokens += counted.input_tokens
    worst_case_output_tokens = len(requests) * MAX_TOKENS
    input_cost = (total_input_tokens / 1_000_000) * input_rate
    output_cost = (worst_case_output_tokens / 1_000_000) * output_rate
    return round((input_cost + output_cost) * 0.5, 6)


async def run_batch_prewarm(
    *,
    limit: int = 50,
    anthropic_client_factory: Callable[[str], AsyncAnthropic] | None = None,
) -> None:
    """Nightly batch-scope submitter (D-01/D-05/D-07, AIP-02). Opens its OWN
    `async with async_session_factory() as db:` and its OWN Redis client
    (via `get_redis_client()`) -- the own-session/own-client shape
    `_run_single_sync()` already establishes, needed because Plan 08
    dispatches this via `asyncio.create_task`, detaching it from the
    scheduler loop's own `db` variable. Loops every active tenant, mirroring
    `scheduler.py`'s SLA-check block.

    T-24-19/D-05/SC3: takes NO externally-injected shared client.
    `anthropic_client_factory` is ONLY a test seam (mirrors
    `_run_explain_stream()`'s own seam) -- inside EVERY tenant iteration, a
    FRESH per-tenant client is built from THAT tenant's own resolved key:
    `key = await get_tenant_anthropic_key(db, tenant.id)` (skip silently if
    None, D-23), then `client = (anthropic_client_factory or
    _default_client_factory)(key)`. A tenant's key can never sign another
    tenant's batch; there is no shared/fallback key, and no client is ever
    constructed outside this per-tenant scope.

    Per-tenant processing is wrapped in its own try/except (Rule 2 addition
    -- see 26-07-SUMMARY.md Deviations): one tenant's failure (a transient
    Anthropic error, a malformed grounding record) must not silently starve
    every OTHER tenant of their nightly batch. This mirrors T-24-19's own
    per-tenant ISOLATION principle applied at the error-handling layer, not
    just the credentials layer.

    Selects `Tenant.id` (a plain scalar column), NOT the whole `Tenant` ORM
    object (Rule 1 fix -- see 26-07-SUMMARY.md Deviations): `AsyncSession.
    rollback()` expires every object in the session's identity map, so a
    LATER tenant's `Tenant.id` attribute access would need a lazy DB
    reload -- a synchronous ORM operation that raises
    `sqlalchemy.exc.MissingGreenlet` outside an `await` expression. A bare
    `uuid.UUID` scalar has no such lazy-load/expiration behavior, so the
    per-tenant try/except's rollback can never break a later iteration's
    (or even the SAME iteration's own exception-logging) attribute access.
    """
    async with async_session_factory() as db:
        redis_client = get_redis_client()
        tenant_ids = (await db.execute(select(Tenant.id).where(Tenant.is_active.is_(True)))).scalars().all()

        for tenant_id in tenant_ids:
            try:
                key = await get_tenant_anthropic_key(db, tenant_id)
                if key is None:
                    continue  # D-23: no key configured -- inert, skip silently

                client = (anthropic_client_factory or _default_client_factory)(key)
                model, monthly_cap_usd = await get_model_and_budget(db, tenant_id)

                finding_ids = await get_top_findings_for_ai_batch(db, tenant_id, limit)

                requests: list[Request] = []
                custom_id_hash_map: dict[str, str] = {}
                for finding_id in finding_ids:
                    record = await get_prioritization_context(db, tenant_id, finding_id)
                    if record is None:
                        continue

                    system, user_blocks = build_explain_prioritization_prompt(record)
                    allowlisted_fields = _extract_scanner_data(user_blocks)
                    the_hash = record_hash(allowlisted_fields)
                    cache_key = build_cache_key(
                        tenant_id,
                        "prioritization",
                        str(finding_id),
                        the_hash,
                        model,
                        prioritization_prompt_version(),
                    )
                    if await get_cached(redis_client, cache_key) is not None:
                        # Pitfall 5: already fresh -- do not re-pay for it tonight.
                        continue

                    requests.append(
                        Request(
                            custom_id=str(finding_id),
                            params=MessageCreateParamsNonStreaming(
                                model=model,
                                max_tokens=MAX_TOKENS,
                                temperature=0,
                                system=system,
                                messages=[{"role": "user", "content": user_blocks}],  # type: ignore[typeddict-item]
                                output_config=_build_output_config(  # type: ignore[typeddict-item]
                                    ExplainPrioritizationResponse, model
                                ),
                            ),
                        )
                    )
                    custom_id_hash_map[str(finding_id)] = the_hash

                if not requests:
                    # Every top-N finding was already fresh -- nothing to submit
                    # tonight (Pitfall 5's own steady-state: not an error).
                    continue

                est = await estimate_batch_cost_usd(client, model, requests)

                if await would_exceed_budget_for_batch(db, tenant_id, monthly_cap_usd, est):
                    # D-07: fail-closed BEFORE any spend -- never a silent partial.
                    await notify_admins_budget_exceeded(db, tenant_id)
                    await audit_log_ai_call(
                        db,
                        tenant_id=tenant_id,
                        user_email="system:scheduler",
                        model=model,
                        usage=_ZERO_USAGE,
                        resource_type="prioritization",
                        resource_id="batch",
                        status="batch_skipped_budget_exceeded",
                        cost_estimate_usd=0.0,
                    )
                    await db.commit()
                    continue

                batch = await client.messages.batches.create(requests=requests)
                db.add(
                    AiBatchJob(
                        tenant_id=tenant_id,
                        anthropic_batch_id=batch.id,
                        status="in_progress",
                        model=model,
                        prompt_version=prioritization_prompt_version(),
                        custom_id_hash_map=custom_id_hash_map,
                        submitted_at=datetime.now(UTC),
                    )
                )
                await db.commit()  # durable BEFORE moving to the next tenant (Pitfall 2)
            except Exception:
                # Rule 2: one tenant's failure must not abort the whole nightly
                # run for every OTHER tenant. Roll back whatever this tenant's
                # iteration left pending, log, and continue.
                await db.rollback()
                _logger.exception("ai_batch_prewarm_tenant_error", extra={"tenant_id": str(tenant_id)})


async def validate_and_cache_batch_result(
    db: AsyncSession,
    redis_client: redis.Redis,
    *,
    tenant_id: uuid.UUID,
    finding_id: str,
    raw_text: str,
    model: str,
    usage: Any,
    cache_key: str,
) -> str:
    """Single-pass equivalent of `_run_explain_stream()`'s validation gate
    (schema -> `recheck_business_rules` -> grounded -> leak-marker ->
    `set_cached`), minus the retry loop -- there is no live conversation to
    append a corrective turn to for a completed batch item (RESEARCH
    Pattern 8). `errored`/`canceled`/`expired` batch results never reach
    this function at all (Plan 08's poller audits those directly with
    their own distinct status and `cost_estimate_usd=0.0` -- none of the
    three are billed).

    Commits its own audit row immediately (Rule 2 addition -- mirrors
    `explain.py::_audit()`'s wrapper convention: every attempt's audit row
    survives independently, and this durability is what lets a caller
    re-query it in a fresh session, exactly as `AiBatchJob`'s own Pitfall-2
    durability is proven). Returns the audit status string written.
    """
    try:
        candidate = ExplainPrioritizationResponse.model_validate_json(raw_text)
        recheck_business_rules(candidate, allowed_source_fields=PRIORITIZATION_ALLOWLIST)
    except (ValidationError, BusinessRuleError):
        status = "validation_failed"
    else:
        if not candidate.grounded:
            status = "validation_failed"
        elif _contains_leak_marker(candidate, SYSTEM_PROMPT_PRIORITIZATION):
            status = "injection_flagged"
        else:
            payload = candidate.model_dump(mode="json")
            await set_cached(redis_client, cache_key, payload)
            status = "ok"

    # RESEARCH Pitfall 4: the batch 50% discount applied at this actual-cost
    # audit site too, matching estimate_batch_cost_usd()'s pre-submission
    # estimate -- forgetting either one corrupts check_tenant_budget()'s SUM.
    cost = _estimate_cost_usd(model, usage) * 0.5 if status == "ok" else 0.0
    await audit_log_ai_call(
        db,
        tenant_id=tenant_id,
        user_email="system:scheduler",
        model=model,
        usage=usage,
        resource_type="prioritization",
        resource_id=finding_id,
        status=status,
        cost_estimate_usd=cost,
    )
    await db.commit()
    return status
