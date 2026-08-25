"""AIE-01's CI-blocking golden-set eval suite (28-CONTEXT.md D-01/D-06).

Parametrized over every committed fixture under `goldens/`, asserting all 5
keyless structural metrics (`metrics.py`) via `assert_test()`. ZERO model
calls anywhere in this file or in `metrics.py` -- the keyless-CI guarantee
this phase's whole CI-blocking tier depends on (BYOK: no GetVul-owned/
shared/fallback Anthropic key, ever, including CI).

CI invocation (never plain `pytest` -- DeepEval's own docs discourage
running LLMTestCases that way; 28-RESEARCH.md Pitfall 1):

    DEEPEVAL_TELEMETRY_OPT_OUT=1 deepeval test run tests/evals/test_golden_evals.py
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from app.ai.prompt_builder import (
    HOST_ALLOWLIST,
    PRIORITIZATION_ALLOWLIST,
    REMEDIATION_ALLOWLIST,
    REMEDIATION_GUIDANCE_ALLOWLIST,
    VULN_ALLOWLIST,
)

from .metrics import (
    CiteOrRefuseMetric,
    GroundingTraceabilityMetric,
    NoOwnerPiiMetric,
    NoRankInvariantMetric,
    SchemaValidMetric,
)

GOLDENS_DIR = pathlib.Path(__file__).parent / "goldens"

_ALLOWLISTS: dict[str, frozenset[str]] = {
    "vuln": VULN_ALLOWLIST,
    "host": HOST_ALLOWLIST,
    "remediation": REMEDIATION_ALLOWLIST,
    "remediation_guidance": REMEDIATION_GUIDANCE_ALLOWLIST,
    "prioritization": PRIORITIZATION_ALLOWLIST,
}


def _load_goldens() -> Iterator[tuple[str, pathlib.Path]]:
    """Yield (capability, fixture_path) for every committed
    `goldens/<capability>/<case>.json` file -- sorted for stable
    parametrize-id ordering across runs/platforms.

    Only iterates capabilities registered in `_ALLOWLISTS` (never a bare
    `GOLDENS_DIR.iterdir()`) -- Phase 44 Plan 06 added SIBLING
    `goldens/nlq_translate/` and `goldens/nlq_narrate/` dirs owned by
    `test_nlq_golden_evals.py` (a different response shape + a dedicated
    filter-correctness metric, not this suite's 5 Explain*-shaped
    structural metrics). Iterating every subdirectory unconditionally
    would KeyError on `_ALLOWLISTS[capability]` for those two -- this
    suite must stay scoped to the capabilities it actually knows how to
    grade."""
    for capability in sorted(_ALLOWLISTS):
        capability_dir = GOLDENS_DIR / capability
        if not capability_dir.is_dir():
            continue
        for fixture_path in sorted(capability_dir.glob("*.json")):
            yield capability, fixture_path


_GOLDEN_CASES = list(_load_goldens())


@pytest.mark.parametrize(
    "capability,fixture_path",
    _GOLDEN_CASES,
    ids=[f"{capability}-{fixture_path.stem}" for capability, fixture_path in _GOLDEN_CASES],
)
def test_golden_eval(capability: str, fixture_path: pathlib.Path) -> None:
    """Every committed golden fixture must pass all 5 keyless structural
    metrics: schema validity, grounding-traceability (calls the REAL
    production `recheck_business_rules` gate), no-rank, no-owner-PII, and
    cite-or-refuse."""
    fixture = json.loads(fixture_path.read_text())
    test_case = LLMTestCase(
        input=json.dumps(fixture["grounding_record"]),
        actual_output=json.dumps(fixture["model_response"]),
    )
    allowlist = _ALLOWLISTS[capability]
    assert_test(
        test_case,
        [
            SchemaValidMetric(response_model=fixture["schema_name"]),
            GroundingTraceabilityMetric(allowed_source_fields=allowlist),
            NoRankInvariantMetric(),
            NoOwnerPiiMetric(),
            CiteOrRefuseMetric(),
        ],
    )
