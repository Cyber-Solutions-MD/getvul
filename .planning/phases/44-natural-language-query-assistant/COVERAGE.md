# Phase 44 — External API Coverage

No external API integration: reuses the shipped v3.0 BYOK Anthropic integration verbatim (the existing pinned AsyncAnthropic client, same key storage/cache/budget/audit scaffold — no new external service, SDK, or key surface); the new usage is Anthropic structured-output calls through that same client, and every "tool-called" read service (list_vulnerabilities / list_assets / list_tickets) is internal.

## Rationale

- The two new model calls (translate, narrate) go through `backend/app/ai/explain.py::_default_client_factory` (fresh per-request `AsyncAnthropic`), imported unchanged — no new client, wrapper, or SDK dependency (`anthropic` 0.122.0 already installed/pinned).
- BYOK key resolution is `tenant_keys.get_tenant_anthropic_key()` reused verbatim; no new secret surface, no shared/fallback key (NLQ-03).
- The "tools" the LLM is given are a Pydantic filter catalog over already-shipped internal read services — not external HTTP APIs.
- No new DB columns/migrations (schema-gate): `asset_internet_facing` reuses an existing `Asset` join; `sla_breached` reuses the existing stored derived-mirror column.

Detector note: the `api-coverage` detector may fire on the word "Anthropic"; this declaration is the reasoned override — the Anthropic integration is pre-existing and reused, not newly added by Phase 44.
