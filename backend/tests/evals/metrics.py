"""Non-LLM DeepEval structural metrics -- the AIE-01 keyless eval harness's
core assertions (28-CONTEXT.md D-01/D-06, 28-RESEARCH.md Pattern 1).

Every metric below is PURE PYTHON: no `evaluation_model`, no network call, no
Anthropic/OpenAI API key anywhere in this file -- the keyless-CI guarantee
this phase's whole CI-blocking tier depends on (BYOK/D-01). Two of the five
metrics (`SchemaValidMetric`, `GroundingTraceabilityMetric`) call the REAL
production validation gates (`ExplainResponseBase.model_validate_json()` /
`recheck_business_rules()`, both from `app.ai.schemas`) directly -- they are
never re-implemented here, so this eval can never silently drift from what
production actually enforces (T-28-07).

mypy note (28-RESEARCH.md Pitfall 7): `mypy app/` (ci.yml's own CI-blocking
scope, see `.github/workflows/ci.yml`) never type-checks this `tests/`
directory, but a local/editor `mypy --strict` run against this file still
trips two DeepEval-typing-looseness errors that are not bugs in this file:
`no-untyped-call` (DeepEval's own `BaseMetric.__init_subclass__` hook is
itself untyped internally, firing on every subclass definition below) and
`operator` (`BaseMetric` declares `threshold`/`score` as `Optional[float]`,
so any subclass comparing them with `>=` -- as every `measure()` below does
-- trips on the base class's own looser declared type). Both are narrowly
suppressed FOR THIS FILE ONLY (never project-wide, never a `strict = false`
change) via the per-module directive immediately below.
"""

# mypy: disable-error-code="no-untyped-call, operator"

from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
from pydantic import ValidationError

from app.ai.schemas import (
    BusinessRuleError,
    ExplainHostResponse,
    ExplainPrioritizationResponse,
    ExplainRemediationGuidanceResponse,
    ExplainRemediationResponse,
    ExplainResponseBase,
    ExplainVulnResponse,
    NlqAnswerResponse,
    recheck_business_rules,
)

# Maps a golden fixture's own "schema_name" string (backend/tests/evals/
# goldens/**/*.json) to its real production response class -- the ONLY
# place this string-to-class resolution happens, so a typo'd schema_name
# fails loudly (KeyError) rather than silently validating against the
# wrong shape. `NlqAnswerResponse` (Phase 44 Plan 06) is an
# `ExplainResponseBase` subclass with zero added fields (schemas.py) --
# added here so `test_nlq_golden_evals.py` can reuse `SchemaValidMetric`
# VERBATIM (same class, same code path) rather than re-implementing it.
_RESPONSE_MODELS: dict[str, type[ExplainResponseBase]] = {
    "ExplainVulnResponse": ExplainVulnResponse,
    "ExplainHostResponse": ExplainHostResponse,
    "ExplainRemediationResponse": ExplainRemediationResponse,
    "ExplainRemediationGuidanceResponse": ExplainRemediationGuidanceResponse,
    "ExplainPrioritizationResponse": ExplainPrioritizationResponse,
    "NlqAnswerResponse": NlqAnswerResponse,
}

# The no-rank invariant (SC2/T-26-02): every ExplainResponseBase subclass
# adds ZERO fields (app/ai/schemas.py) -- this is the exact field set
# test_ai_schemas.py::test_prioritization_no_rank_field already asserts for
# the prioritization view alone; here it is asserted for EVERY capability's
# golden fixture, uniformly (they all share the identical base shape).
_EXPECTED_RESPONSE_KEYS: frozenset[str] = frozenset({"summary", "business_risk", "citations", "grounded"})
_FORBIDDEN_RANK_KEYS: frozenset[str] = frozenset({"priority", "rank", "score", "ai_priority", "ai_rank"})

# Defense-in-depth keyword scan (mirrors app.ai.safety.contains_dangerous_
# pattern's own stated reasoning: "a small, known set of ... phrases ... not
# an adversary actively evading a live interceptor" -- GetVul's threat model
# for this class of check is a cheap second net, not an NER/PII-detection
# model). These are the literal owner-PII field NAMES every allowlist in
# prompt_builder.py structurally excludes at the INPUT boundary
# (T-24-32/T-25-01/T-26-01's directory_user/assigned_user/managed_by/
# building/serial_number -- the exact tuple test_ai_prompt_builder_host.py's
# own PII-exclusion test already asserts against). None of these identifiers
# is a plausible legitimate word choice for an "explain this vuln/asset/fix"
# narrative -- if one surfaces verbatim in an already-schema-validated
# response's own prose, that is a strong signal of an unrelated leak path
# (e.g. a raw object repr), not a false positive worth a full PII-detection
# pipeline.
OWNER_PII_SENTINELS: frozenset[str] = frozenset(
    {"directory_user", "assigned_user", "managed_by", "serial_number", "building"}
)


def _require_actual_output(test_case: LLMTestCase) -> str:
    """Every metric in this file needs `actual_output` -- fail loudly (not a
    silent None-shaped false pass) if a test case omits it."""
    if test_case.actual_output is None:
        raise ValueError("test_case.actual_output is required for every structural eval metric")
    return test_case.actual_output


def _parse_actual_output(test_case: LLMTestCase) -> dict[str, Any]:
    payload: Any = json.loads(_require_actual_output(test_case))
    if not isinstance(payload, dict):
        raise ValueError(f"actual_output must be a JSON object, got {type(payload).__name__}")
    return payload


class SchemaValidMetric(BaseMetric):
    """A fixture's `model_response` must validate against its OWN named
    Explain*Response class (the fixture's `schema_name`) -- score 1.0 on
    success, 0.0 on any ValidationError. `response_model` is the SCHEMA NAME
    STRING (matching goldens/**/*.json's own `schema_name` field), resolved
    against `_RESPONSE_MODELS` -- never a hardcoded single class, since one
    metric instance is reused across all 5 capabilities' fixtures."""

    def __init__(self, response_model: str, threshold: float = 1.0) -> None:
        self.threshold = threshold
        # NOTE: DeepEval's own `copy_metrics()` (deepeval/metrics/utils.py)
        # reconstructs a fresh instance per test case via
        # `metric_class(**vars(metric))`, filtered to whatever names appear
        # in `__init__`'s OWN signature -- so the stored attribute name MUST
        # be identical to the constructor parameter name (`response_model`,
        # never a renamed `response_model_name`), or reconstruction raises
        # "missing 1 required positional argument" (found via direct
        # execution against deepeval==4.1.5, not assumed from docs).
        self.response_model = response_model

    def measure(self, test_case: LLMTestCase) -> float:
        model_cls = _RESPONSE_MODELS[self.response_model]
        try:
            model_cls.model_validate_json(_require_actual_output(test_case))
            self.score = 1.0
        except ValidationError as exc:
            self.score = 0.0
            self.reason = str(exc)
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Schema Valid"


class GroundingTraceabilityMetric(BaseMetric):
    """Every citation.source_field (when set) must be a member of the
    capability's own allowlist -- this is NOT a re-implementation, it calls
    the REAL production `recheck_business_rules()` gate (app.ai.schemas)
    directly, so this eval can never silently drift from what production
    actually enforces (T-28-07)."""

    def __init__(self, allowed_source_fields: frozenset[str], threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.allowed_source_fields = allowed_source_fields

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            candidate = ExplainResponseBase.model_validate_json(_require_actual_output(test_case))
            recheck_business_rules(candidate, allowed_source_fields=self.allowed_source_fields)
            self.score = 1.0
        except (ValidationError, BusinessRuleError) as exc:
            self.score = 0.0
            self.reason = str(exc)
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Grounding Traceability"


class NoRankInvariantMetric(BaseMetric):
    """A model_response's own JSON keys must be EXACTLY
    `_EXPECTED_RESPONSE_KEYS` -- catches an extra numeric priority/rank/score
    key just as reliably as a missing standard key (mirrors
    test_ai_schemas.py::test_prioritization_no_rank_field's set-equality
    discipline), applied uniformly across every capability's fixture, not
    only prioritization's."""

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        payload = _parse_actual_output(test_case)
        keys = set(payload.keys())
        if keys != _EXPECTED_RESPONSE_KEYS or (keys & _FORBIDDEN_RANK_KEYS):
            self.score = 0.0
            self.reason = (
                f"response keys {sorted(keys)} deviate from the no-rank {sorted(_EXPECTED_RESPONSE_KEYS)} shape"
            )
        else:
            self.score = 1.0
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "No Rank Invariant"


class NoOwnerPiiMetric(BaseMetric):
    """Defense-in-depth keyword scan of the serialized model_response for
    OWNER_PII_SENTINELS. The allowlists in prompt_builder.py already
    structurally exclude owner-PII fields at the INPUT boundary, so this
    metric should never legitimately fire; it exists as a second, cheap net
    against an unrelated leak path (e.g. an accidental raw-object repr)."""

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        haystack = _require_actual_output(test_case).lower()
        hit = next((sentinel for sentinel in OWNER_PII_SENTINELS if sentinel in haystack), None)
        if hit is not None:
            self.score = 0.0
            self.reason = f"owner-PII sentinel {hit!r} found in model_response"
        else:
            self.score = 1.0
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "No Owner PII"


class CiteOrRefuseMetric(BaseMetric):
    """The cite-or-refuse contract (D-01/D-02/D-24): a grounded=true response
    must carry at least one citation; a grounded=false refusal is exempt.
    Operates on the raw parsed JSON, independent of ExplainResponseBase's own
    `citations: Field(..., min_length=1)` constraint -- Anthropic's
    structured-output schema translator can strip array-length constraints
    before they ever reach the model (AI-SPEC Pitfall 4), so this metric
    proves the cite-or-refuse invariant holds on its own terms, not merely
    because local Pydantic re-validation happens to also enforce it today."""

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        payload = _parse_actual_output(test_case)
        grounded = bool(payload.get("grounded"))
        citations = payload.get("citations") or []
        if grounded and len(citations) < 1:
            self.score = 0.0
            self.reason = "grounded=true but zero citations present"
        else:
            self.score = 1.0
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Cite Or Refuse"
