"""The Natural-Language Query two-call orchestrator (NLQ-01/NLQ-02/NLQ-03,
Phase 44 Plan 01) — the D-01 tool/filter contract's proof-of-life.

`_run_explain_stream()` (`app.ai.explain`) is fundamentally single-call and
single-record shaped: `build_prompt(record) -> validate -> cache -> audit ->
stream`. NLQ needs "translate a QUESTION into a filter, execute it
deterministically, then narrate the results" — a structurally different,
TWO independent model-call flow with a deterministic DB step in between
(RESEARCH.md Architecture Patterns Pattern 1). `_run_query_stream()` is a
NEW sibling that reuses `explain.py`'s constituent pieces by direct
import — the precondition envelope, the client factory, the SSE helpers,
the budget/cache/audit machinery — rather than parameterizing or
duplicating `_run_explain_stream` itself.

Guarantees proven end-to-end by this module (see 44-01-PLAN.md
`must_haves`):
  - Results-first (D-15): `interpreted` + `results` SSE frames are always
    emitted BEFORE the narrate call even starts.
  - BYOK-inert (NLQ-03): no key configured -> `{"type": "no_key"}`, never
    a 500, never a generic error — identical precondition to
    `_run_explain_stream`.
  - Tenant-scoped (NLQ-02): `list_vulnerabilities` is ALWAYS called with
    the tenant_id this function was invoked with (the authenticated
    session's own) — `NlqFilterResponse` and its `*FilterInput` models
    structurally have NO tenant_id field to supply instead.
  - Deterministic exact count + risk-ranked top-N (D-07): the model never
    computes a count or picks the order; `list_vulnerabilities` does, via
    the SAME `sort="triage"` risk-ranked ORDER BY the rest of the app uses.
  - Single shared inflight acquisition (Pitfall 5): acquired ONCE for the
    whole translate -> execute -> narrate flow, released ONCE in a
    `finally` — never once per model call.
  - Translation-only cache (D-19): only the question -> filter mapping is
    cached; the query itself always executes fresh, and the narrated
    answer is never cached.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import redis.asyncio as redis
from anthropic import APIStatusError, AsyncAnthropic, RateLimitError
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.audit import audit_log_ai_call
from app.ai.budget import check_tenant_budget, notify_admins_budget_exceeded
from app.ai.cache import (
    acquire_inflight,
    build_cache_key,
    get_cached,
    record_hash,
    release_inflight,
    set_cached,
)
from app.ai.explain import (
    _ZERO_USAGE,
    MAX_TOKENS,
    _build_output_config,
    _chunk_for_replay,
    _default_client_factory,
    _estimate_cost_usd,
    _sse_event,
    get_model_and_budget,
)
from app.ai.prompt_builder import (
    build_query_narrate_prompt,
    build_query_translate_prompt,
    query_translate_prompt_version,
)
from app.ai.schemas import (
    AssetFilterInput,
    BusinessRuleError,
    NlqAnswerResponse,
    NlqFilterResponse,
    TicketFilterInput,
    VulnFilterInput,
    recheck_business_rules,
    recheck_nlq_filter_exclusivity,
)
from app.ai.tenant_keys import get_tenant_anthropic_key
from app.assets.schemas import AssetFilter
from app.assets.service import list_assets
from app.pagination import PaginatedResponse, PaginationParams
from app.ticketing.schemas import TicketQueryFilter
from app.ticketing.service import list_tickets
from app.vulnerabilities.schemas import VulnerabilityFilter
from app.vulnerabilities.service import list_vulnerabilities

_logger = logging.getLogger(__name__)

# D-07/RESEARCH Open Question 3 (resolved): matches UI-SPEC's own copy
# precedent ("10 of 47 total") and bounds the narrate call's context size
# regardless of how many rows actually match.
TOP_N_RESULTS = 10

_CORRECTIVE_TURN_QUERY = (
    "Your previous output failed schema validation or violated a required "
    "business rule (for example: more than one entity's filter was "
    "populated, or the chosen entity's own filter was left empty while "
    "groundable=true). Return a corrected response that matches the "
    "schema and every rule exactly."
)


def _append_corrective_turn(messages: list[dict[str, Any]], previous_raw_text: str) -> list[dict[str, Any]]:
    """Mirrors `explain.py::_append_corrective_turn` (§L195-203) --
    duplicated, not imported, because the corrective text itself is
    query-flow-specific (it never mentions `<scanner_data>`, which does not
    exist in either of this module's two prompts)."""
    return [
        *messages,
        {"role": "assistant", "content": [{"type": "text", "text": previous_raw_text}]},
        {"role": "user", "content": [{"type": "text", "text": _CORRECTIVE_TURN_QUERY}]},
    ]


async def _call_structured(
    client: AsyncAnthropic,
    *,
    model: str,
    system_prompt: str,
    user_blocks: list[dict[str, str]],
    response_model: type[BaseModel],
    recheck: Callable[[Any], None] | None = None,
    on_attempt_failed: Callable[[Any], Any] | None = None,
    max_attempts: int = 2,
) -> tuple[Any, Any]:
    """Shared single-call-with-one-corrective-retry loop -- mirrors
    `explain.py::_run_explain_stream`'s inner `for attempt_index in
    range(2)` body (§L343-428), generalized so query_assistant's TWO
    independent structured-output calls (translate/narrate) both reuse it
    (RESEARCH Pattern 1) rather than each hand-rolling their own loop.

    `recheck` is an optional, caller-supplied SECOND validation gate run
    immediately after schema validation succeeds -- mirrors
    `recheck_business_rules`'s own "Anthropic strips constraints, recheck
    explicitly" precedent. A `BusinessRuleError` it raises is treated
    exactly like a `ValidationError`: one corrective retry, then a
    re-raise on the final attempt.

    `on_attempt_failed` (AI-06: "no silent unlogged call") is an optional
    async callback invoked with the failed attempt's `usage` EVERY time a
    `ValidationError`/`BusinessRuleError` is caught -- including the FINAL
    attempt, right before it re-raises. This is what gives every attempt
    (not just the terminal one) its own audit row, mirroring
    `_run_explain_stream`'s own per-attempt `_audit(status="validation_failed")`
    call inside its loop. The caller is expected to NOT audit again in its
    own except-block for `ValidationError`/`BusinessRuleError` -- only for
    `RateLimitError`/`APIStatusError`, which never reach this callback (they
    propagate immediately, before any attempt is made at all).

    Returns `(validated_response, raw_usage)`. Raises `ValidationError` or
    `BusinessRuleError` if the final attempt still fails; raises
    `RateLimitError`/`APIStatusError` unmodified (the SDK's own
    Retry-After-aware backoff has already been exhausted by the time
    either reaches here) for the caller to handle.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_blocks}]
    output_config = _build_output_config(response_model, model)

    for attempt_index in range(max_attempts):
        is_final_attempt = attempt_index == max_attempts - 1

        async with client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=0,
            system=system_prompt,
            messages=messages,  # type: ignore[arg-type]
            output_config=output_config,  # type: ignore[arg-type]
        ) as stream:
            raw_message = await stream.get_final_message()

        raw_text = "".join(
            getattr(block, "text", "") for block in raw_message.content if getattr(block, "type", None) == "text"
        )
        try:
            candidate = response_model.model_validate_json(raw_text)
            if recheck is not None:
                recheck(candidate)
        except (ValidationError, BusinessRuleError):
            if on_attempt_failed is not None:
                await on_attempt_failed(raw_message.usage)
            if is_final_attempt:
                raise
            messages = _append_corrective_turn(messages, raw_text)
            continue

        return candidate, raw_message.usage

    raise AssertionError("unreachable")  # pragma: no cover -- loop always returns or raises


async def _resolve_hostname(db: AsyncSession, tenant_id: uuid.UUID, hostname: str) -> uuid.UUID | None:
    """Deterministic, tenant-scoped hostname -> asset_id resolution --
    NEVER model-side (the model cannot know a tenant's internal UUIDs, and
    D-02 forbids model-side multi-tool composition). Reused by the
    tickets-entity branch ("open tickets for asset X") once it is wired.

    Unresolved -> None, which the caller treats as a zero-results answer
    (D-06's "every question resolves to a filtered list" framing), never a
    D-14 refusal (RESEARCH Pattern 3 / Open Question 2, resolved)."""
    result = await list_assets(db, tenant_id, AssetFilter(hostname=hostname), PaginationParams(page=1, page_size=1))
    return result.items[0].id if result.items else None


async def _audit(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_email: str,
    model: str,
    usage: Any,
    resource_type: str,
    resource_id: str,
    status: str,
    action_prefix: str,
    cost_estimate_usd: float | None = None,
) -> None:
    """Write + durably commit one audit row per attempt (AI-06) -- mirrors
    `explain.py`'s own private `_audit()` (§L226-255), generalized with the
    additive `action_prefix` param (Task 1) so every row this module
    writes lands as `ai.query.*`, never silently mislabeled
    `ai.explain.*`. `action_prefix` is required (no default) at THIS call
    site so it is always explicit, never accidentally inherited."""
    await audit_log_ai_call(
        db,
        tenant_id=tenant_id,
        user_email=user_email,
        model=model,
        usage=usage,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        cost_estimate_usd=cost_estimate_usd,
        action_prefix=action_prefix,
    )
    await db.commit()


def _map_vuln_filter(rows_filter: VulnFilterInput) -> VulnerabilityFilter:
    """Map the model-emitted, allowlisted `VulnFilterInput` onto the REAL
    `VulnerabilityFilter` the existing, tenant-scoped `list_vulnerabilities`
    already knows how to execute (D-01). `sort="triage"` is hardcoded here,
    never model-supplied: it is what makes the top-N deterministic and
    risk-ranked (KEV desc -> CVSS desc -> SLA-due asc), so the narrated
    top-N is stable and matches the shown result set run-to-run (D-07)."""
    return VulnerabilityFilter(
        severity=rows_filter.severity,
        status=rows_filter.status,
        cisa_kev=rows_filter.cisa_kev,
        exploit_available=rows_filter.exploit_available,
        age_days_min=rows_filter.age_days_min,
        # Phase 44 Plan 02 / D-03: the north-star question's two additive
        # predicates.
        asset_internet_facing=rows_filter.asset_internet_facing,
        sla_breached=rows_filter.sla_breached,
        sort="triage",
    )


def _map_asset_filter(rows_filter: AssetFilterInput) -> AssetFilter:
    """Map the model-emitted, allowlisted `AssetFilterInput` onto the REAL
    `AssetFilter` the existing, tenant-scoped `list_assets` already knows
    how to execute (D-01), mirroring `_map_vuln_filter` above."""
    return AssetFilter(
        device_category=rows_filter.device_category,
        internet_facing=rows_filter.internet_facing,
    )


def _map_ticket_filter(rows_filter: TicketFilterInput) -> TicketQueryFilter:
    """Convert the model-emitted `TicketFilterInput` (ai/schemas.py -- what
    the model emits) into `TicketQueryFilter` (ticketing/schemas.py -- the
    ticketing-layer-validated, `extra="forbid"` wrapper `list_tickets` is
    actually called through). This is the single documented type flow (W4)
    -- the two are a producer/consumer pair, never used interchangeably."""
    return TicketQueryFilter(status=rows_filter.status, asset_hostname=rows_filter.asset_hostname)


async def _run_query_stream(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_email: str,
    question: str,
    redis_client: redis.Redis,
    anthropic_client_factory: Callable[[str], AsyncAnthropic] | None = None,
) -> AsyncIterator[bytes]:
    """SHARED orchestrator: question -> translate (CALL 1) -> execute
    deterministically -> results-first SSE -> narrate (CALL 2, grounded) ->
    done. BYOK-gated, tenant-scoped, single-shot (D-10), translation cached
    (D-19).

    `anthropic_client_factory` is the SAME test seam
    `_run_explain_stream` exposes: production callers omit it (the real
    per-request `AsyncAnthropic(api_key=...)` is used); tests inject a fake
    client/transport here instead of monkeypatching module globals.
    """
    model, monthly_cap_usd = await get_model_and_budget(db, tenant_id)

    api_key = await get_tenant_anthropic_key(db, tenant_id)
    if api_key is None:
        # NLQ-03/D-12: inert "configure AI" state -- never an error, never
        # a 500. Deliberately NOT audit-logged: nothing was attempted.
        yield _sse_event({"type": "no_key"})
        return

    if not await check_tenant_budget(db, tenant_id, monthly_cap_usd):
        await notify_admins_budget_exceeded(db, tenant_id)
        await _audit(
            db,
            tenant_id=tenant_id,
            user_email=user_email,
            model=model,
            usage=_ZERO_USAGE,
            resource_type="translate",
            resource_id="pending",
            status="budget_exceeded",
            cost_estimate_usd=0.0,
            action_prefix="query",
        )
        yield _sse_event({"type": "error", "kind": "budget_exceeded"})
        return

    if not await acquire_inflight(redis_client, tenant_id):
        # D-18/Pitfall 5: acquired ONCE for the whole translate->execute->
        # narrate flow -- a queue-clicking analyst's second concurrent
        # question is turned away, never a second call self-blocking
        # behind its own just-released lock.
        yield _sse_event({"type": "error", "kind": "busy"})
        return

    try:
        client = (anthropic_client_factory or _default_client_factory)(api_key)

        # ── CALL 1: TRANSLATE (D-19 cache: question -> filter only) ──
        normalized_question = " ".join(question.strip().lower().split())
        translate_version = query_translate_prompt_version()
        translate_hash = record_hash({"question": normalized_question})
        translate_cache_key = build_cache_key(tenant_id, "query", "translate", translate_hash, model, translate_version)

        async def _on_translate_attempt_failed(usage: Any) -> None:
            # AI-06: audit EVERY failed attempt individually (including the
            # terminal one, right before `_call_structured` re-raises) --
            # mirrors _run_explain_stream's own per-attempt audit inside its
            # retry loop. The entity isn't known yet at this point.
            await _audit(
                db,
                tenant_id=tenant_id,
                user_email=user_email,
                model=model,
                usage=usage,
                resource_type="translate",
                resource_id="pending",
                status="validation_failed",
                action_prefix="query",
            )

        cached_translation = await get_cached(redis_client, translate_cache_key)
        if cached_translation is not None:
            filter_resp = NlqFilterResponse.model_validate(cached_translation)
        else:
            translate_system_prompt, translate_user_blocks = build_query_translate_prompt(question)
            try:
                filter_resp, translate_usage = await _call_structured(
                    client,
                    model=model,
                    system_prompt=translate_system_prompt,
                    user_blocks=translate_user_blocks,
                    response_model=NlqFilterResponse,
                    recheck=recheck_nlq_filter_exclusivity,
                    on_attempt_failed=_on_translate_attempt_failed,
                )
            except (ValidationError, BusinessRuleError):
                # Already audited (once per failed attempt, including this
                # terminal one) by _on_translate_attempt_failed above.
                yield _sse_event({"type": "error", "kind": "grounded_false"})
                return
            except (RateLimitError, APIStatusError):
                await _audit(
                    db,
                    tenant_id=tenant_id,
                    user_email=user_email,
                    model=model,
                    usage=_ZERO_USAGE,
                    resource_type="translate",
                    resource_id="pending",
                    status="rate_limited",
                    action_prefix="query",
                )
                yield _sse_event({"type": "error", "kind": "busy"})
                return

            # D-19: cache the TRANSLATION only -- never the results/answer.
            await set_cached(redis_client, translate_cache_key, filter_resp.model_dump(mode="json"))
            await _audit(
                db,
                tenant_id=tenant_id,
                user_email=user_email,
                model=model,
                usage=translate_usage,
                resource_type="translate",
                resource_id=filter_resp.entity,
                status="ok",
                cost_estimate_usd=_estimate_cost_usd(model, translate_usage),
                action_prefix="query",
            )

        if not filter_resp.groundable:
            # D-14: an honest refusal is the CORRECT terminal outcome, not
            # a failure -- never retried, never an "error" SSE kind.
            yield _sse_event({"type": "refuse"})
            return

        # ── Execute deterministically -- tenant_id ALWAYS from the
        # authenticated session, never from the model's output (NLQ-02) ──
        vuln_filter_input = filter_resp.vulnerability_filter
        asset_filter_input = filter_resp.asset_filter
        ticket_filter_input = filter_resp.ticket_filter
        if filter_resp.entity == "vulnerabilities" and vuln_filter_input is not None:
            vuln_filter = _map_vuln_filter(vuln_filter_input)
            pagination = PaginationParams(page=1, page_size=TOP_N_RESULTS)
            paginated: PaginatedResponse[Any] = await list_vulnerabilities(db, tenant_id, vuln_filter, pagination)
            rows = [item.model_dump(mode="json") for item in paginated.items]
            total = paginated.total
            interpreted_filter = vuln_filter_input.model_dump(mode="json")
        elif filter_resp.entity == "assets" and asset_filter_input is not None:
            asset_filter = _map_asset_filter(asset_filter_input)
            pagination = PaginationParams(page=1, page_size=TOP_N_RESULTS)
            paginated_assets: PaginatedResponse[Any] = await list_assets(db, tenant_id, asset_filter, pagination)
            rows = [item.model_dump(mode="json") for item in paginated_assets.items]
            total = paginated_assets.total
            interpreted_filter = asset_filter_input.model_dump(mode="json")
        elif filter_resp.entity == "tickets" and ticket_filter_input is not None:
            query_filter = _map_ticket_filter(ticket_filter_input)
            interpreted_filter = ticket_filter_input.model_dump(mode="json")
            resolved_asset_id: uuid.UUID | None = None
            if query_filter.asset_hostname is not None:
                resolved_asset_id = await _resolve_hostname(db, tenant_id, query_filter.asset_hostname)
                if resolved_asset_id is None:
                    # RESEARCH Pattern 3 / Open Question 2 (resolved): an
                    # unresolvable "asset X" hostname is a well-formed
                    # zero-results answer, NEVER a D-14 refusal -- the
                    # question was honestly mapped, it simply matched no
                    # asset in this tenant.
                    rows, total = [], 0
                else:
                    ticket_result = await list_tickets(
                        db,
                        tenant_id,
                        status=query_filter.status,
                        asset_id=str(resolved_asset_id),
                        page=1,
                        page_size=TOP_N_RESULTS,
                    )
                    rows = ticket_result["items"]
                    total = ticket_result["total"]
            else:
                ticket_result = await list_tickets(
                    db, tenant_id, status=query_filter.status, page=1, page_size=TOP_N_RESULTS
                )
                rows = ticket_result["items"]
                total = ticket_result["total"]

            # Phase 44 / NLQ-01 / D-17: surface the server-resolved UUID (not
            # just the raw hostname string) in the interpreted filter the
            # frontend receives. Without this, `buildNlqDeepLink` has no way
            # to express "open these in Tickets" -- the tickets list page's
            # `asset_id` URL param needs a UUID, and only this orchestrator
            # (via `_resolve_hostname`) ever resolves one; the model itself
            # never sees or invents a UUID (D-01/D-02). Additive dict key --
            # `interpreted_filter` is a plain dump, not a validated schema,
            # so this can't reintroduce a model-supplied UUID trust issue.
            interpreted_filter["resolved_asset_id"] = (
                str(resolved_asset_id) if resolved_asset_id is not None else None
            )
        else:
            # Every groundable NlqFilterResponse structurally has its own
            # entity's filter populated (recheck_nlq_filter_exclusivity) --
            # this branch is an unreachable defensive backstop, not a
            # scoped-out placeholder.
            yield _sse_event({"type": "refuse"})
            return

        yield _sse_event({"type": "interpreted", "entity": filter_resp.entity, "filter": interpreted_filter})
        yield _sse_event({"type": "results", "rows": rows, "total": total})

        # ── CALL 2: NARRATE, grounded ONLY on the executed rows + count ──
        narrate_system_prompt, narrate_user_blocks = build_query_narrate_prompt(
            question, interpreted_filter, rows, total
        )

        async def _on_narrate_attempt_failed(usage: Any) -> None:
            # AI-06: audit EVERY failed attempt individually -- mirrors the
            # translate-side callback above.
            await _audit(
                db,
                tenant_id=tenant_id,
                user_email=user_email,
                model=model,
                usage=usage,
                resource_type="narrate",
                resource_id=filter_resp.entity,
                status="validation_failed",
                action_prefix="query",
            )

        try:
            answer, narrate_usage = await _call_structured(
                client,
                model=model,
                system_prompt=narrate_system_prompt,
                user_blocks=narrate_user_blocks,
                response_model=NlqAnswerResponse,
                recheck=recheck_business_rules,
                on_attempt_failed=_on_narrate_attempt_failed,
            )
        except (ValidationError, BusinessRuleError):
            # Already audited (once per failed attempt, including this
            # terminal one) by _on_narrate_attempt_failed above.
            yield _sse_event({"type": "error", "kind": "grounded_false"})
            return
        except (RateLimitError, APIStatusError):
            await _audit(
                db,
                tenant_id=tenant_id,
                user_email=user_email,
                model=model,
                usage=_ZERO_USAGE,
                resource_type="narrate",
                resource_id=filter_resp.entity,
                status="rate_limited",
                action_prefix="query",
            )
            yield _sse_event({"type": "error", "kind": "busy"})
            return

        # D-19: the narrate call's OWN output is never cached (only the
        # translation is) -- cache + audit BEFORE any byte reaches the
        # browser, mirroring _run_explain_stream's SUCCESS-block ordering.
        cost = _estimate_cost_usd(model, narrate_usage)
        await _audit(
            db,
            tenant_id=tenant_id,
            user_email=user_email,
            model=model,
            usage=narrate_usage,
            resource_type="narrate",
            resource_id=filter_resp.entity,
            status="ok",
            cost_estimate_usd=cost,
            action_prefix="query",
        )
        for chunk in _chunk_for_replay(answer.summary):
            yield _sse_event({"type": "summary_delta", "text": chunk})
        yield _sse_event({"type": "done", **answer.model_dump(mode="json")})
        return
    except Exception as exc:  # noqa: BLE001 -- deliberate catch-all: any unexpected
        # failure must still surface a typed event, never a raw 500
        # mid-stream, and must still release the inflight guard (handled
        # by `finally` below). GeneratorExit (client abort) is a
        # BaseException, not an Exception, so it is NOT caught here -- it
        # still triggers `finally` and propagates.
        _logger.warning(
            "ai.query.unexpected_error",
            extra={"tenant_id": str(tenant_id), "error_type": type(exc).__name__},
        )
        await _audit(
            db,
            tenant_id=tenant_id,
            user_email=user_email,
            model=model,
            usage=_ZERO_USAGE,
            resource_type="query",
            resource_id="unknown",
            status="unknown",
            cost_estimate_usd=0.0,
            action_prefix="query",
        )
        yield _sse_event({"type": "error", "kind": "unknown"})
    finally:
        await release_inflight(redis_client, tenant_id)
