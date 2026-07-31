"""AI response schemas — the schema-validation gate (AI-02, AI-SPEC Section 4b/D1).

Nothing downstream (the SSE replay to the drill panel, the audit log, the
cache) may ever consume raw Anthropic model text. `ExplainVulnResponse.
model_validate_json()` is the backstop: a malformed/incomplete/off-schema
response never reaches the UI. `recheck_business_rules()` is a SECOND gate,
run explicitly after schema validation succeeds, for constraints Anthropic's
structured-output schema translator silently strips when converting a
Pydantic model to the JSON Schema it enforces server-side (`minLength`,
`maxLength`, `minimum`, `maximum`, array constraints beyond `minItems` 0-1 —
AI-SPEC Section 4b Pitfall 4). The API only guarantees STRUCTURAL compliance
(types, required keys, enum membership) — never assume these business rules
are enforced by the model call itself.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CitationSource(str, Enum):
    """Two-tier citation tag (AI-04): whether a claim is copied verbatim
    from a scanner-sourced field, or is Claude's own synthesis/inference. An
    analyst must be able to tell scanner fact from AI reasoning at a glance."""

    SCANNER_VERBATIM = "scanner_verbatim"
    AI_INTERPRETED = "ai_interpreted"


class Citation(BaseModel):
    text: str = Field(..., description="The specific claim being cited")
    source: CitationSource
    source_field: str | None = Field(
        None,
        description=(
            "Which allowlisted source field this was grounded in, e.g. 'cve_id', 'cvss_v3_vector'. "
            "None for an ai_interpreted citation with no single grounding field."
        ),
    )


class ExplainResponseBase(BaseModel):
    """Shape shared by every 'explain' response variant. Host/remediation
    variants (Plan 08) subclass this separately from `ExplainVulnResponse`.

    `citations` is deliberately declared WITHOUT `Field(max_length=...)` on
    `summary`/`business_risk` — those char-budget constraints are re-checked
    explicitly via `recheck_business_rules()` below, not baked into this
    schema, because Anthropic's structured-output schema translator strips
    such constraints before they ever reach the model (Pitfall 4). `citations`
    non-emptiness (`min_length=1`) DOES hold locally regardless of what
    Anthropic enforces upstream: `model_validate_json()` always re-validates
    every field fully, in this process, against this exact schema.
    """

    summary: str = Field(..., description="Plain-English explanation of the vulnerability")
    business_risk: str = Field(..., description="Business-risk framing for this asset/owner")
    citations: list[Citation] = Field(..., min_length=1, description="Two-tier citations backing every claim above")
    grounded: bool = Field(
        ...,
        description=(
            "False if the supplied scanner data was insufficient to ground a faithful explanation "
            "— set instead of inventing a CVE/CVSS/host/owner not present in the record."
        ),
    )


class ExplainVulnResponse(ExplainResponseBase):
    """The 'explain this vuln' response (vuln-specific). No additional
    fields yet — host/remediation variants are added in Plan 08."""


class ExplainHostResponse(ExplainResponseBase):
    """The 'explain this asset' response (D-16 posture-summary view, Plan
    08). No additional fields — the per-host grounding record is already a
    narrow, allowlisted posture summary (HOST_ALLOWLIST); the shared base
    fully covers this view."""


class ExplainRemediationResponse(ExplainResponseBase):
    """The 'explain this fix' response (D-16 Option A: cross-asset CVE
    grouping, decided at the 24-06 TRACER checkpoint — Plan 08). No
    additional fields — the shared base fully covers this view."""


class ExplainRemediationGuidanceResponse(ExplainResponseBase):
    """The 'remediation guidance' response (AIR-01, Phase 25 Plan 02). No
    additional fields — cited remediation steps live as prose inside
    `summary`, exactly as the `ExplainHostResponse`/`ExplainRemediationResponse`
    variants above already prove is sufficient (D-03: cite-verbatim-first is
    a citation-ordering/tagging convention, not a new schema field)."""


class ExplainPrioritizationResponse(ExplainResponseBase):
    """The prioritization-narrative response (AIP-01, Phase 26 Plan 01). No
    additional fields — the narrative lives as prose in `summary`/
    `business_risk`, exactly as `ExplainHostResponse`/`ExplainRemediationResponse`/
    `ExplainRemediationGuidanceResponse` above already prove is sufficient.
    The DELIBERATE absence of any additional numeric field on this class is
    the D-03/Pitfall-7/SC2 augment-never-replace enforcement (threat
    T-26-02): `ExplainResponseBase` has no numeric field anywhere, so a
    competing verdict number has structurally nowhere to live without a
    reviewable diff to this shared base class."""


# ── Business-rule re-check gate (AI-SPEC Section 4b Pitfall 4) ──
#
# Per-field character ceilings and citation source_field allowlist
# membership are NOT expressible as static Field(...) constraints here
# without them being silently stripped from the JSON Schema Anthropic
# actually enforces (`output_config.format`). They are re-checked explicitly,
# in Python, on the ALREADY schema-validated object — never assumed
# enforced by the model call itself.

MAX_SUMMARY_CHARS = 4000
MAX_BUSINESS_RISK_CHARS = 4000


class BusinessRuleError(ValueError):
    """A schema-valid ExplainResponseBase still violates a re-checked
    business rule (char budget or citation source_field allowlist
    membership). Subclasses ValueError — the same exception family Pydantic
    validators themselves raise — so callers can catch validation-shaped
    failures uniformly alongside `pydantic.ValidationError`."""


def recheck_business_rules(
    resp: ExplainResponseBase,
    *,
    allowed_source_fields: frozenset[str] | None = None,
) -> None:
    """Second validation gate — call this AFTER
    `ExplainVulnResponse.model_validate_json()` succeeds, never in place of
    it. Anthropic's structured-output schema translator strips business-rule
    constraints (`maxLength`, citation-field allowlist membership) when
    converting this Pydantic model into the JSON Schema passed to the model
    — the API only guarantees structural compliance (types, required keys,
    enum membership), not these rules. A model response can be perfectly
    schema-valid and still violate a business rule; this function is the
    ONLY place that rule is actually enforced.

    Raises BusinessRuleError on any violation:
    - `summary` / `business_risk` exceed their configured character ceiling.
    - Any `Citation.source_field` (when set) is not a member of
      `allowed_source_fields` (skipped entirely when that param is omitted —
      the caller may not always have an allowlist in scope).
    """
    if len(resp.summary) > MAX_SUMMARY_CHARS:
        raise BusinessRuleError(f"summary exceeds {MAX_SUMMARY_CHARS} chars (got {len(resp.summary)})")
    if len(resp.business_risk) > MAX_BUSINESS_RISK_CHARS:
        raise BusinessRuleError(
            f"business_risk exceeds {MAX_BUSINESS_RISK_CHARS} chars (got {len(resp.business_risk)})"
        )
    if allowed_source_fields is not None:
        for citation in resp.citations:
            if citation.source_field is not None and citation.source_field not in allowed_source_fields:
                raise BusinessRuleError(
                    f"citation.source_field {citation.source_field!r} is not in the allowed source-field set"
                )
