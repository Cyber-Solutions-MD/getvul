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
from typing import Literal

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


# ── Natural-Language Query filter contract (NLQ-01/NLQ-02, Phase 44 Plan 01) ──
#
# D-01/Pitfall 2: a flat, NON-union response schema -- deliberately NOT a
# Pydantic discriminated union (`Field(discriminator="entity")`), which
# would emit "oneOf" in JSON Schema (Anthropic's structured-outputs docs
# list anyOf/allOf as supported, not oneOf). Three independently-optional
# filter fields + `recheck_nlq_filter_exclusivity()` (mirroring
# `recheck_business_rules()`'s own "Anthropic strips constraints, recheck
# explicitly" precedent) enforce "exactly one of the three matches
# `entity`" explicitly in Python -- never assumed structurally enforced by
# the model call alone. Verified empirically this session:
# `NlqFilterResponse.model_json_schema()` contains no "oneOf" key and every
# `$ref` resolves to `#/$defs/...` (self-contained, no external $ref).


class VulnFilterInput(BaseModel):
    """The ONLY filter shape a vulnerabilities-entity NLQ answer may take.
    Phase 44 Plan 02 (W2) adds asset_internet_facing/sla_breached, matching
    VulnerabilityFilter.asset_internet_facing/sla_breached exactly (the
    buildNlqDeepLink param contract uses the SAME name --
    "asset_internet_facing", never bare "internet_facing", which is the
    AssetFilterInput/AssetFilter name only). Deliberately NO asset_hostname:
    the vulnerabilities entity is never host-scoped (W3) -- a hostname
    predicate is outside the D-17 vuln deep-link's own param set, so
    allowing one here would let a vulnerabilities answer silently narrow
    past what "Open in Vulnerabilities" can express. Host-scoped questions
    route to the tickets entity instead, where TicketFilterInput.
    asset_hostname IS resolved server-side."""

    model_config = {"extra": "forbid"}

    severity: list[str] | None = None
    cisa_kev: bool | None = None
    exploit_available: bool | None = None
    age_days_min: int | None = None
    status: list[str] | None = None
    asset_internet_facing: bool | None = None
    sla_breached: bool | None = None


class AssetFilterInput(BaseModel):
    """The ONLY filter shape an assets-entity NLQ answer may take. Maps
    EXISTING AssetFilter predicates: device_category (Plan 01) and
    internet_facing (Plan 02, now that AssetFilter itself has the field).
    Deliberately NO hostname (TicketFilterInput is the only *FilterInput
    model carrying one)."""

    model_config = {"extra": "forbid"}

    device_category: str | None = None
    internet_facing: bool | None = None


class TicketFilterInput(BaseModel):
    """The ONLY filter shape a tickets-entity NLQ answer may take.
    `asset_hostname` is the ONLY hostname-carrying field across all three
    *FilterInput models -- resolved server-side to an asset_id; the model
    never sees or invents a UUID (Plan 02's `_resolve_hostname`)."""

    model_config = {"extra": "forbid"}

    status: str | None = None
    asset_hostname: str | None = None


class NlqFilterResponse(BaseModel):
    """Translate-call response (CALL 1, D-01/D-02): the model picks exactly
    ONE entity and fills in ONLY that entity's own filter object. Flat and
    non-union by construction (see module comment above) -- the unsupported
    union keyword Pitfall 2 warns about is not even structurally reachable
    here. `groundable=false` (D-14) is a legitimate, honest refusal, not a
    failure: the caller treats it as a terminal "can't answer that"
    outcome, never a retry target. This schema structurally has NO
    tenant_id field anywhere -- query execution always uses the
    authenticated session's tenant_id (NLQ-02)."""

    model_config = {"extra": "forbid"}

    entity: Literal["vulnerabilities", "assets", "tickets"]
    vulnerability_filter: VulnFilterInput | None = None
    asset_filter: AssetFilterInput | None = None
    ticket_filter: TicketFilterInput | None = None
    groundable: bool = Field(
        ...,
        description="False when the question cannot be honestly mapped to one of the allowed filter fields.",
    )


class NlqAnswerResponse(ExplainResponseBase):
    """The narrate-call response (CALL 2, D-13). No additional fields --
    mirrors every other ExplainResponseBase subclass in this module: the
    narrative lives as prose in `summary`/`business_risk`, grounded ONLY in
    the executed rows + exact count the caller supplies (never a new
    number, never a row not present in the result set)."""


def recheck_nlq_filter_exclusivity(resp: NlqFilterResponse) -> None:
    """Second validation gate for the translate call -- mirrors
    `recheck_business_rules()`'s own "Anthropic strips constraints, recheck
    explicitly" precedent, generalized here to a cross-field structural
    rule rather than a char-budget/allowlist one. Anthropic's structured-
    output schema translator enforces field TYPES but not this
    "exactly one entity's filter is populated, and it matches `entity`"
    constraint -- never assumed enforced by the model call itself.

    Raises BusinessRuleError when:
    - `groundable` is true but the chosen entity's own filter is null (the
      model claimed it could answer, but forgot to actually fill in a
      filter).
    - Any OTHER entity's filter is non-null (more than one filter
      populated) -- regardless of `groundable`.
    A `groundable=false` response with every filter null (the honest,
    D-14 refusal shape) passes this check cleanly -- it is not an error.
    """
    filters = {
        "vulnerabilities": resp.vulnerability_filter,
        "assets": resp.asset_filter,
        "tickets": resp.ticket_filter,
    }
    matching = filters.pop(resp.entity)
    if resp.groundable and matching is None:
        raise BusinessRuleError(f"entity={resp.entity!r} but its own filter is null")
    if any(other is not None for other in filters.values()):
        raise BusinessRuleError("more than one entity's filter is populated")
