"""NLQ-02's CI-blocking golden-set eval suite (44-06-PLAN.md, EXPANSION 4 --
extends the AIE-01 keyless eval gate additively, never a parallel pipeline).

Two capabilities, each auto-discovered from its own `goldens/nlq_<x>/*.json`
directory (mirroring `test_golden_evals.py::_load_goldens`'s own discovery
pattern, just scoped to these two dirs rather than every registered
capability -- `test_golden_evals.py` deliberately does NOT scan these dirs,
see its own `_load_goldens` docstring):

- `nlq_translate`: the model picks ONE entity + fills ONLY that entity's own
  filter object (`NlqFilterResponse`, D-01/D-02). Graded by a NEW,
  keyless `FilterCorrectnessMetric` (this file) -- schema validity +
  `recheck_nlq_filter_exclusivity` + exact-match against the fixture's own
  hand-authored `expected_filter` for the valid cases, or an asserted
  REJECTION for the deliberately-invalid hallucinated-field/cross-tenant
  cases (`expect_valid: false`).
- `nlq_narrate`: the model narrates already-executed rows/count
  (`NlqAnswerResponse`, D-13). `NlqAnswerResponse` is an `ExplainResponseBase`
  subclass with ZERO added fields (schemas.py) -- graded by the SAME 5
  structural metrics `test_golden_evals.py` already uses, imported and
  applied VERBATIM, no re-implementation.

ZERO model calls anywhere in this file -- the same keyless-CI guarantee
`test_golden_evals.py`'s own module docstring documents (BYOK: no
GetVul-owned/shared/fallback Anthropic key, ever, including CI).

CI invocation (same `ai-evals` job as `test_golden_evals.py`; never plain
`pytest` -- DeepEval's own docs discourage that, 28-RESEARCH.md Pitfall 1):

    DEEPEVAL_TELEMETRY_OPT_OUT=1 deepeval test run tests/evals/test_nlq_golden_evals.py
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator
from typing import Any

import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
from pydantic import ValidationError

from app.ai.schemas import BusinessRuleError, NlqFilterResponse, recheck_nlq_filter_exclusivity

from .metrics import (
    CiteOrRefuseMetric,
    GroundingTraceabilityMetric,
    NoOwnerPiiMetric,
    NoRankInvariantMetric,
    SchemaValidMetric,
)

GOLDENS_DIR = pathlib.Path(__file__).parent / "goldens"

# The nlq_narrate GroundingTraceabilityMetric allowlist -- the union of every
# `source_field` name a narrate citation may legitimately cite across all
# three NLQ entities' row shapes (vulnerabilities/assets/tickets), mirroring
# VULN_ALLOWLIST/HOST_ALLOWLIST's own bounded-identifier discipline
# (prompt_builder.py). "total"/"filter" cover the two grounding-record-level
# citations (e.g. "0 results matched this filter").
NLQ_NARRATE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "cve_id",
        "asset_hostname",
        "hostname",
        "status",
        "severity",
        "cisa_kev",
        "exploit_available",
        "device_category",
        "internet_facing",
        "ticket_id",
        "title",
        "total",
        "filter",
        "rows",
    }
)


def _load_nlq_goldens(capability: str) -> Iterator[pathlib.Path]:
    """Yield every committed `goldens/<capability>/*.json` fixture path,
    sorted for stable parametrize-id ordering -- scoped to ONE of this
    file's two owned dirs (`nlq_translate` / `nlq_narrate`), never a bare
    `GOLDENS_DIR.iterdir()` (that is `test_golden_evals.py`'s own,
    differently-scoped, auto-discovery)."""
    capability_dir = GOLDENS_DIR / capability
    if not capability_dir.is_dir():
        return
    yield from sorted(capability_dir.glob("*.json"))


_TRANSLATE_CASES = list(_load_nlq_goldens("nlq_translate"))
_NARRATE_CASES = list(_load_nlq_goldens("nlq_narrate"))


class FilterCorrectnessMetric(BaseMetric):
    """Keyless structural metric for the nlq_translate capability (D-01/D-02/
    D-14/NLQ-02). Calls the REAL production gates directly
    (`NlqFilterResponse.model_validate_json()` +
    `recheck_nlq_filter_exclusivity()`, both from `app.ai.schemas`) -- never
    re-implemented here, so this eval can never silently drift from what
    production actually enforces (mirrors `GroundingTraceabilityMetric`'s own
    T-28-07 discipline).

    Two modes, selected by the fixture's own `expect_valid` flag:
    - `expect_valid=True` (the ordinary case, incl. the D-14 honest refusal
      shape): the emitted filter must validate + pass exclusivity, AND must
      equal `expected_filter` exactly (the golden's own hand-authored
      ground truth).
    - `expect_valid=False` (T-44-02/T-44-03 hallucinated-field / cross-tenant
      coverage): the emitted filter is DELIBERATELY malformed
      (`extra="forbid"` violation) -- the metric asserts the REJECTION
      itself, not a filter match.
    """

    def __init__(self, expected_filter: dict[str, Any] | None, expect_valid: bool, threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.expected_filter = expected_filter
        self.expect_valid = expect_valid

    def measure(self, test_case: LLMTestCase) -> float:
        if test_case.actual_output is None:
            raise ValueError("test_case.actual_output is required")
        raw = test_case.actual_output
        try:
            candidate = NlqFilterResponse.model_validate_json(raw)
            recheck_nlq_filter_exclusivity(candidate)
            validation_error: Exception | None = None
        except (ValidationError, BusinessRuleError) as exc:
            validation_error = exc

        if self.expect_valid:
            if validation_error is not None:
                self.score = 0.0
                self.reason = f"expected a valid, exclusivity-passing filter but validation failed: {validation_error}"
            else:
                actual_dict = json.loads(raw)
                if actual_dict == self.expected_filter:
                    self.score = 1.0
                else:
                    self.score = 0.0
                    self.reason = f"emitted filter {actual_dict} != golden expected_filter {self.expected_filter}"
        else:
            if validation_error is None:
                self.score = 0.0
                self.reason = "expected this hallucinated/cross-tenant filter to be REJECTED, but it validated cleanly"
            else:
                self.score = 1.0
                self.reason = f"correctly rejected: {validation_error}"

        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Filter Correctness"


@pytest.mark.parametrize(
    "fixture_path",
    _TRANSLATE_CASES,
    ids=[p.stem for p in _TRANSLATE_CASES],
)
def test_nlq_translate_golden(fixture_path: pathlib.Path) -> None:
    """Every committed nlq_translate golden fixture must pass
    `FilterCorrectnessMetric` -- the north-star question + all 4 UI-SPEC
    starter questions map to their EXPECTED filter; the refuse (out-of-scope
    aggregation) case is a valid honest-refusal shape; the hallucinated-field
    and cross-tenant-reach cases must be REJECTED by the real production
    schema (extra="forbid")."""
    fixture = json.loads(fixture_path.read_text())
    test_case = LLMTestCase(
        input=fixture["question"],
        actual_output=json.dumps(fixture["model_response"]),
    )
    assert_test(
        test_case,
        [
            FilterCorrectnessMetric(
                expected_filter=fixture.get("expected_filter"),
                expect_valid=fixture["expect_valid"],
            )
        ],
    )


@pytest.mark.parametrize(
    "fixture_path",
    _NARRATE_CASES,
    ids=[p.stem for p in _NARRATE_CASES],
)
def test_nlq_narrate_golden(fixture_path: pathlib.Path) -> None:
    """Every committed nlq_narrate golden fixture must pass the SAME 5
    keyless structural metrics `test_golden_evals.py` already uses --
    reused VERBATIM (same classes, same import), never re-implemented --
    against `NlqAnswerResponse`-shaped responses (grounded, no fabricated
    numbers, incl. a truthful zero-results case)."""
    fixture = json.loads(fixture_path.read_text())
    test_case = LLMTestCase(
        input=json.dumps(fixture["grounding_record"]),
        actual_output=json.dumps(fixture["model_response"]),
    )
    assert_test(
        test_case,
        [
            SchemaValidMetric(response_model="NlqAnswerResponse"),
            GroundingTraceabilityMetric(allowed_source_fields=NLQ_NARRATE_ALLOWLIST),
            NoRankInvariantMetric(),
            NoOwnerPiiMetric(),
            CiteOrRefuseMetric(),
        ],
    )
