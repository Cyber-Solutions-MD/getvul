"""The buffer-then-validate-then-replay streaming engine (AI-02/AI-03) --
the phase's core engineering novelty. `_run_explain_stream()` is the SHARED
core, parameterized by `build_prompt` + `response_model` so Plan 08's
host/remediation wrappers reuse it unchanged (D-15/D-16).

Two Critical Failure Modes (AI-SPEC Section 1) are defended here:

1. **Unvalidated output reaching the UI (CFM #5).** The raw Anthropic
   stream is consumed ENTIRELY inside this function via
   `await stream.get_final_message()` -- never a raw passthrough of the
   provider's own SSE bytes. Nothing is ever yielded onto the outbound SSE
   stream before `response_model.model_validate_json()` AND
   `recheck_business_rules()` both pass (the gate is upstream of the first
   outbound byte).
2. **BYOK key leakage across tenants (T-24-19).** `AsyncAnthropic` is
   constructed fresh, per-request, from the Fernet-decrypted key returned
   by `get_tenant_anthropic_key()`. Never a module-level singleton.

Retry/audit contract (D-26, AI-06): on `ValidationError`/`BusinessRuleError`
or a self-reported `grounded=false`, exactly ONE corrective retry runs,
invisible to the analyst. Every attempt is audit-logged with a distinct
`status`:
  - "grounded_retry"    -- attempt 1 self-reported grounded=false (a retry follows)
  - "validation_failed" -- attempt 1 (a retry follows) OR the terminal attempt
                           2 failed schema/business-rule validation OR is
                           still grounded=false with no retries left
  - "injection_flagged" -- schema-valid + grounded=true, but the output
                           tripped the leak-marker/off-task check (W3) --
                           terminal, no retry
  - "rate_limited"      -- a persistent RateLimitError/APIStatusError after
                           the SDK's own Retry-After-aware backoff exhausted
                           (D-25) -- terminal, no retry
  - "budget_exceeded"   -- check_tenant_budget failed BEFORE any dispatch (D-06)
  - "ok"                -- schema-valid, business-rules-valid, grounded=true,
                           no leak marker -- cached and streamed

The engine's typed SSE error `kind` vocabulary is exactly
{busy, grounded_false, budget_exceeded, unknown} (matches the frontend's
ExplainStreamState union, Plan 05) -- a "no key configured" precondition is
a DIFFERENT, non-error event shape (`{"type": "no_key"}`), never an "error"
kind, per D-23 ("never an error").
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from types import SimpleNamespace
from typing import Any, cast

import redis.asyncio as redis
from anthropic import APIStatusError, AsyncAnthropic, RateLimitError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.audit import audit_log_ai_call
from app.ai.budget import check_tenant_budget, notify_admins_budget_exceeded
from app.ai.cache import (
    acquire_inflight,
    build_cache_key,
    record_hash,
    release_inflight,
    set_cached,
)
from app.ai.prompt_builder import prompt_version
from app.ai.schemas import BusinessRuleError, ExplainResponseBase, recheck_business_rules
from app.ai.tenant_keys import get_tenant_anthropic_key
from app.ticketing.models import ConnectorConfig

_logger = logging.getLogger(__name__)

# D-01: default model when a tenant's AI connector hasn't set one explicitly.
DEFAULT_MODEL = "claude-sonnet-5"

# D-07: hard per-call ceiling, independent of the configurable monthly cap
# (D-06) -- always set, never left unbounded.
MAX_TOKENS = 1024

# AI-SPEC Section 4b Pitfall 1 / RESEARCH Open Question 1: Anthropic's live
# `effort` docs (fetched 2026-07-28) do not list claude-haiku-4-5 among
# effort-supporting models. Plan 01's own live smoke-test could not run
# (GETVUL_DEV_ANTHROPIC_KEY was never provisioned -- see
# 24-01-SUMMARY.md "Known Gaps"). Omit `effort` for Haiku specifically until
# live-reverified; every other model gets `effort: "low"` (D-01).
_NO_EFFORT_MODELS: frozenset[str] = frozenset({"claude-haiku-4-5"})

# Standard (non-promotional) per-MTok USD pricing, AI-SPEC Section 4 as of
# 2026-07-28. The Sonnet-5 introductory $2/$10 rate expires 2026-08-31 --
# this table intentionally uses the durable standard rate so a stale
# promotional price doesn't silently under-count spend once the promotion
# lapses. Haiku 4.5's exact published per-token rate was not independently
# re-verified this phase (AI-SPEC only characterizes it as
# "fastest/cheapest"); this is a conservative placeholder for D-06's fail-
# closed monthly cap, not Phase 28's authoritative cost dashboard (AIE-04).
_PRICING_PER_MTOK_USD: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-haiku-4-5": (0.80, 4.0),
}
_DEFAULT_PRICING_PER_MTOK_USD = (3.0, 15.0)  # unrecognized model string -> Sonnet-5 rate

_ZERO_USAGE = SimpleNamespace(input_tokens=0, output_tokens=0)

CORRECTIVE_TURN = (
    "Your previous output was not grounded in the provided data, or failed validation. "
    "Do not invent CVEs, hosts, CVSS scores, or any other detail not present in the "
    "<scanner_data> above. If the data is genuinely insufficient to ground a faithful "
    'explanation, set "grounded": false and explain what is missing.'
)


def _default_client_factory(api_key: str) -> AsyncAnthropic:
    """Construct a fresh AsyncAnthropic client from the tenant's own
    decrypted key -- NEVER a module-level singleton (T-24-19; would leak
    one tenant's key to every request). `max_retries` is explicit so
    "persistent" (D-25) means "the SDK's own Retry-After-aware backoff
    already ran out", not zero attempts."""
    return AsyncAnthropic(api_key=api_key, max_retries=2)


def _sse_event(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode()


def _chunk_for_replay(text: str, size: int = 80) -> list[str]:
    """Split already-validated text into small chunks for the drill panel's
    post-validation streamed-reveal UX (D-12) -- purely cosmetic; every
    chunk here comes from content that has ALREADY passed both validation
    gates, never raw model output."""
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


def _build_output_config(response_model: type[ExplainResponseBase], model: str) -> dict[str, Any]:
    config: dict[str, Any] = {
        "format": {"type": "json_schema", "schema": response_model.model_json_schema()},
    }
    if model not in _NO_EFFORT_MODELS:
        config["effort"] = "low"
    return config


def _extract_scanner_data(user_blocks: list[dict[str, str]]) -> dict[str, Any]:
    """Pull the allowlisted grounding fields back out of the already-built
    prompt's `<scanner_data>` user block, for D-18 cache-key hashing. This
    reads the SAME allowlisted JSON `build_prompt()` already placed into
    the prompt -- never a second, independently-maintained allowlist --
    so D-18 compliance is structural (whatever was actually sent to the
    model is exactly what gets hashed) for every current and future view.
    Mirrors the delimiter-breakout-safe rightmost-close-tag convention
    already proven in Plan 02's prompt-builder tests.
    """
    text = user_blocks[0]["text"]
    start = text.index(">") + 1
    end = text.rindex("</scanner_data>")
    # json.loads() is typed to return Any -- cast() documents the contract
    # (build_prompt() always JSON-encodes a dict here) without silencing a
    # genuinely wrong shape at the call site (mirrors cache.py::get_cached).
    return cast("dict[str, Any]", json.loads(text[start:end]))


def _contains_leak_marker(candidate: ExplainResponseBase, system_prompt: str) -> bool:
    """Cheap leak-marker / off-task check (W3) -- run AFTER schema AND
    business-rule validation both pass. A legitimate grounded explanation
    never needs to quote GetVul's OWN instructions back; if the validated
    output contains a verbatim excerpt of the system prompt actually used
    for THIS call, that's a strong signal the model was steered off-task
    despite passing the structural gate. The schema gate remains the
    primary backstop (W3) -- this is a second, narrower net, and is
    generic across every current/future view since it reads the real
    `system_prompt` in scope for this call rather than a hardcoded string.
    """
    first_line = system_prompt.strip().splitlines()[0] if system_prompt.strip() else ""
    marker = first_line[:40].strip().lower()
    if not marker:
        return False
    haystack = " ".join([candidate.summary, candidate.business_risk, *(c.text for c in candidate.citations)]).lower()
    return marker in haystack


def _estimate_cost_usd(model: str, usage: Any) -> float:
    input_rate, output_rate = _PRICING_PER_MTOK_USD.get(model, _DEFAULT_PRICING_PER_MTOK_USD)
    input_cost = (usage.input_tokens / 1_000_000) * input_rate
    output_cost = (usage.output_tokens / 1_000_000) * output_rate
    # `usage` is typed Any (matches audit_log_ai_call's own Any usage param,
    # decoupling this module from over-constraining the anthropic SDK's
    # Usage shape) -- float() documents the real, always-numeric contract.
    return float(round(input_cost + output_cost, 6))


def _append_corrective_turn(messages: list[dict[str, Any]], previous_raw_text: str) -> list[dict[str, Any]]:
    """Build the retry's message list: the original turn(s), the model's
    own (rejected) prior response as an assistant turn, then a new
    corrective user turn (D-26) -- invisible to the analyst."""
    return [
        *messages,
        {"role": "assistant", "content": [{"type": "text", "text": previous_raw_text}]},
        {"role": "user", "content": [{"type": "text", "text": CORRECTIVE_TURN}]},
    ]


async def get_model_and_budget(db: AsyncSession, tenant_id: uuid.UUID) -> tuple[str, float | None]:
    """Resolve the tenant's configured model + optional monthly budget cap
    from their ANTHROPIC ConnectorConfig.config JSONB (D-01/D-02/D-06) --
    no new schema, mirrors tenant_keys.py's own row lookup (a second,
    cheap indexed query -- deliberately NOT fused with
    get_tenant_anthropic_key's own query, to keep Plan 03's decryption
    logic a single, unduplicated source of truth)."""
    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.tenant_id == tenant_id,
            ConnectorConfig.connector_type == "ANTHROPIC",
        )
    )
    connector = result.scalar_one_or_none()
    config = (connector.config or {}) if connector is not None else {}
    model = config.get("model") or DEFAULT_MODEL
    monthly_cap_usd = config.get("monthly_budget_usd")
    return model, monthly_cap_usd


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
    cost_estimate_usd: float | None = None,
) -> None:
    """Write + durably commit one audit row for a single explain attempt.
    `audit_log_ai_call()` itself deliberately does NOT commit (mirrors
    `rotate_credentials()`) -- this wrapper commits immediately after each
    call so every attempt's audit row survives independently (AI-06: no
    silent unlogged call) even if a later step in the SAME request fails.
    """
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
    )
    await db.commit()


async def _run_explain_stream(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_email: str,
    resource_type: str,
    resource_id: str,
    record: Any,
    build_prompt: Callable[[Any], tuple[str, list[dict[str, str]]]],
    response_model: type[ExplainResponseBase],
    redis_client: redis.Redis,
    allowed_source_fields: frozenset[str] | None = None,
    get_prompt_version: Callable[[], str] = prompt_version,
    anthropic_client_factory: Callable[[str], AsyncAnthropic] | None = None,
    dangerous_pattern_check: Callable[[ExplainResponseBase], str | None] | None = None,
) -> AsyncIterator[bytes]:
    """SHARED buffer-then-validate-then-replay core. Parameterized by
    `build_prompt` + `response_model` (and `allowed_source_fields` /
    `get_prompt_version`) so Plan 08's host/remediation views reuse this
    unchanged (D-15/D-16) -- only the grounding-record assembly and
    response schema vary per view; the engine itself does not.

    `anthropic_client_factory` is the test seam: production callers omit
    it (the real per-request `AsyncAnthropic(api_key=...)` is used);
    tests inject a fake client/transport here instead of monkeypatching
    module globals.

    `dangerous_pattern_check` (Phase 25 D-04/D-05, additive, default None --
    a provable no-op for the vuln/host/remediation-posture views, mirroring
    how `allowed_source_fields=None` was Plan 04's own no-op extension
    point before Plan 08 gave it real teeth) is the post-generation safety
    gate: when supplied and it returns a non-None label for the validated
    `candidate`, the ENTIRE guidance is refused -- audited
    `status="unsafe_denylisted"`, a single `{"type":"error","kind":"unsafe"}`
    SSE frame is yielded, and the function returns BEFORE the SUCCESS
    block's `set_cached()` ever runs (25-RESEARCH.md Pattern 3 / Pitfall 2:
    a route-layer-only filter would leave the dangerous payload sitting in
    a real, GET-retrievable cache key).
    """
    model, monthly_cap_usd = await get_model_and_budget(db, tenant_id)

    api_key = await get_tenant_anthropic_key(db, tenant_id)
    if api_key is None:
        # AI-01/D-23: inert "configure AI" state -- never an error, never a
        # 500. Deliberately NOT audit-logged: no connector/model is even
        # resolved yet, and AI-SPEC's audit status vocabulary has no slot
        # for "not configured" (nothing was attempted).
        yield _sse_event({"type": "no_key"})
        return

    if not await check_tenant_budget(db, tenant_id, monthly_cap_usd):
        # D-06: fail-closed BEFORE any Anthropic dispatch.
        await notify_admins_budget_exceeded(db, tenant_id)
        await _audit(
            db,
            tenant_id=tenant_id,
            user_email=user_email,
            model=model,
            usage=_ZERO_USAGE,
            resource_type=resource_type,
            resource_id=resource_id,
            status="budget_exceeded",
            cost_estimate_usd=0.0,
        )
        yield _sse_event({"type": "error", "kind": "budget_exceeded"})
        return

    if not await acquire_inflight(redis_client, tenant_id):
        # D-25: a queue-clicking analyst's second concurrent request is
        # turned away rather than stampeding the tenant's own key. No
        # audit row -- no model dispatch was attempted, nothing to log.
        yield _sse_event({"type": "error", "kind": "busy"})
        return

    try:
        system_prompt, user_blocks = build_prompt(record)
        allowlisted_fields = _extract_scanner_data(user_blocks)
        version = get_prompt_version()
        the_hash = record_hash(allowlisted_fields)
        cache_key = build_cache_key(tenant_id, resource_type, resource_id, the_hash, model, version)

        client = (anthropic_client_factory or _default_client_factory)(api_key)
        output_config = _build_output_config(response_model, model)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_blocks}]

        for attempt_index in range(2):  # attempt 0 = first try; attempt 1 = the one corrective retry (D-26)
            is_final_attempt = attempt_index == 1

            try:
                # `messages`/`output_config` are intentionally plain
                # dict[str, Any] here (matches AI-SPEC's own locked Entry
                # Point Pattern and prompt_builder.py's return shape) rather
                # than importing the SDK's precise nested TypedDicts, which
                # would need re-deriving per-view again in Plan 08. The
                # runtime shapes are spike-verified against the real
                # installed SDK (see test_ai_explain_stream.py's live
                # MockTransport wire-format test).
                async with client.messages.stream(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    temperature=0,
                    system=system_prompt,
                    messages=messages,  # type: ignore[arg-type]
                    output_config=output_config,  # type: ignore[arg-type]
                ) as stream:
                    raw_message = await stream.get_final_message()
            except (RateLimitError, APIStatusError):
                # D-25: the SDK's own Retry-After-aware backoff (max_retries
                # on the client) has already been exhausted by the time this
                # reaches us -- terminal, no explain.py-level retry, no
                # partial/unvalidated text ever emitted.
                await _audit(
                    db,
                    tenant_id=tenant_id,
                    user_email=user_email,
                    model=model,
                    usage=_ZERO_USAGE,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status="rate_limited",
                    cost_estimate_usd=0.0,
                )
                yield _sse_event({"type": "error", "kind": "busy"})
                return

            # Accumulate ONLY from the fully-buffered final message -- never
            # the raw stream's partial content_block_delta frames (CFM #5).
            # getattr(..., "text", "") (not `block.text`) sidesteps the
            # content-block union's non-text members (tool_use/thinking/...)
            # without a per-member isinstance cascade.
            raw_text = "".join(
                getattr(block, "text", "") for block in raw_message.content if getattr(block, "type", None) == "text"
            )

            try:
                candidate = response_model.model_validate_json(raw_text)
                recheck_business_rules(candidate, allowed_source_fields=allowed_source_fields)
            except (ValidationError, BusinessRuleError):
                await _audit(
                    db,
                    tenant_id=tenant_id,
                    user_email=user_email,
                    model=model,
                    usage=raw_message.usage,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status="validation_failed",
                )
                if is_final_attempt:
                    yield _sse_event({"type": "error", "kind": "grounded_false"})
                    return
                messages = _append_corrective_turn(messages, raw_text)
                continue

            if not candidate.grounded:
                status = "validation_failed" if is_final_attempt else "grounded_retry"
                await _audit(
                    db,
                    tenant_id=tenant_id,
                    user_email=user_email,
                    model=model,
                    usage=raw_message.usage,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status=status,
                )
                if is_final_attempt:
                    yield _sse_event({"type": "error", "kind": "grounded_false"})
                    return
                messages = _append_corrective_turn(messages, raw_text)
                continue

            if _contains_leak_marker(candidate, system_prompt):
                # W3: schema-valid + grounded=true, but content-wise
                # suspicious -- blocked by the gate regardless; audited
                # under its own distinct status (feeds the AI-SPEC Section 7
                # injection-attempt metric), terminal, no retry.
                await _audit(
                    db,
                    tenant_id=tenant_id,
                    user_email=user_email,
                    model=model,
                    usage=raw_message.usage,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status="injection_flagged",
                )
                yield _sse_event({"type": "error", "kind": "grounded_false"})
                return

            if dangerous_pattern_check is not None:
                matched = dangerous_pattern_check(candidate)
                if matched is not None:
                    # D-04: refuse the ENTIRE guidance on any denylist hit --
                    # terminal, no retry, its own audit status. Runs BEFORE
                    # set_cached()/the "ok" audit below, so a dangerous
                    # payload is NEVER written to Redis and NEVER retrievable
                    # via the GET cache-check (T-25-02, Pitfall 2).
                    await _audit(
                        db,
                        tenant_id=tenant_id,
                        user_email=user_email,
                        model=model,
                        usage=raw_message.usage,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        status="unsafe_denylisted",
                    )
                    yield _sse_event({"type": "error", "kind": "unsafe", "matched_pattern": matched})
                    return

            # SUCCESS: schema-valid, business-rules-valid, grounded, no leak
            # marker. Cache + audit BEFORE any byte reaches the browser
            # (AI-05/AI-06), then replay.
            payload = candidate.model_dump(mode="json")
            await set_cached(redis_client, cache_key, payload)
            cost = _estimate_cost_usd(model, raw_message.usage)
            await _audit(
                db,
                tenant_id=tenant_id,
                user_email=user_email,
                model=model,
                usage=raw_message.usage,
                resource_type=resource_type,
                resource_id=resource_id,
                status="ok",
                cost_estimate_usd=cost,
            )
            for chunk in _chunk_for_replay(candidate.summary):
                yield _sse_event({"type": "summary_delta", "text": chunk})
            yield _sse_event({"type": "done", **payload})
            return
    except Exception as exc:  # noqa: BLE001 -- deliberate catch-all: any unexpected
        # failure must still surface a typed event, never a raw 500 mid-stream,
        # and must still release the inflight guard (handled by `finally` below).
        # GeneratorExit (client abort) is a BaseException, not an Exception, so
        # it is NOT caught here -- it still triggers `finally` and propagates,
        # exactly per the abort-releases-the-guard contract.
        _logger.warning(
            "ai.explain.unexpected_error",
            extra={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "tenant_id": str(tenant_id),
                "error_type": type(exc).__name__,
            },
        )
        await _audit(
            db,
            tenant_id=tenant_id,
            user_email=user_email,
            model=model,
            usage=_ZERO_USAGE,
            resource_type=resource_type,
            resource_id=resource_id,
            status="unknown",
            cost_estimate_usd=0.0,
        )
        yield _sse_event({"type": "error", "kind": "unknown"})
    finally:
        await release_inflight(redis_client, tenant_id)
