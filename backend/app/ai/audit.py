"""AI call audit writer (AI-06) — every 'explain this vuln' attempt writes
exactly one AuditLog row, success or failure.

Constructs `AuditLog` DIRECTLY, mirroring `encryption.py::rotate_credentials`
(lines 256-276) — this module NEVER calls the shared `app.audit.audit`
helper. That helper's nil-tenant fallback (`uuid.UUID(int=0)` when its
`user` parameter is None) exists for genuinely userless call sites, but for
a scheduler-originated AI call it would silently bucket a real, tenant-
billed call under a fake tenant — invisible to "all AI audit rows for
tenant X" queries (AI-SPEC Section 4b Pitfall 4 / RESEARCH Pattern 5).
`tenant_id` here is always the caller's own explicit, known tenant context
— interactive or scheduler-originated — never derived from a nullable user.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditLog


async def audit_log_ai_call(
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
    action_prefix: str = "explain",
) -> None:
    """Write one AI-call audit row.

    `tenant_id` is a REQUIRED, keyword-only parameter (no default) — it must
    always come from the caller's own known tenant context. `user_email` is
    either the analyst's email (interactive call) or the literal string
    "system:scheduler" (scheduler-originated call) — symmetric, no
    nil-tenant branch for either path. `usage` is an Anthropic
    `Message.usage`-shaped object (or any object/test-double exposing
    `.input_tokens` / `.output_tokens`); this module deliberately does not
    import the `anthropic` SDK to construct it.

    `status` is one of "ok" | "validation_failed" | "grounded_retry" |
    "budget_exceeded" | "injection_flagged" (AI-SPEC Section 4 State
    Management). Every call site — including a validation_failed attempt —
    must call this exactly once per attempt (AI-06: no silent unlogged call).

    `action_prefix` (Phase 44 Plan 01, additive) — defaults to "explain" so
    every existing call site (`explain.py::_run_explain_stream`, every
    `explain_*.py` route that transitively calls it) is unaffected byte-
    for-byte. `query_assistant.py`'s NLQ orchestrator passes
    `action_prefix="query"` so its rows land as `ai.query.*`, never
    silently mislabeled `ai.explain.*` (D-16 audit vocabulary, NLQ-02).

    Does NOT commit — mirrors `rotate_credentials()`'s pattern of adding to
    the session and letting the caller's own transaction boundary commit.
    """
    log = AuditLog(
        tenant_id=tenant_id,
        user_id=None,
        user_email=user_email,
        action=f"ai.{action_prefix}.{resource_type}",
        resource_type=resource_type,
        resource_id=resource_id,
        details={
            "model": model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_estimate_usd": cost_estimate_usd,
            "status": status,
        },
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db.add(log)
