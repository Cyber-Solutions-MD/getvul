"""Tests for app.ai.schemas — the schema-validation gate (AI-02, AI-SPEC D1).

This is the backstop that blocks any off-task, incomplete, or malformed
model output from ever reaching the UI: nothing downstream may consume raw
model text before it survives `ExplainVulnResponse.model_validate_json()`.
`recheck_business_rules()` covers the constraints Anthropic's structured-
output schema translator silently strips (AI-SPEC Section 4b Pitfall 4) —
per-field character budgets and citation source_field allowlist membership
are never assumed enforced by the model call itself.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.schemas import (
    MAX_BUSINESS_RISK_CHARS,
    MAX_SUMMARY_CHARS,
    BusinessRuleError,
    CitationSource,
    ExplainVulnResponse,
    recheck_business_rules,
)


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "summary": "This host runs an outdated OpenSSL affected by CVE-2024-12345.",
        "business_risk": "Internet-facing and CISA KEV-listed — patch this week.",
        "citations": [
            {
                "text": "OpenSSL 1.1.1 is affected by CVE-2024-12345",
                "source": "scanner_verbatim",
                "source_field": "cve_id",
            }
        ],
        "grounded": True,
    }
    payload.update(overrides)
    return payload


# ── Structural gate: well-formed input ──


def test_well_formed_json_validates_with_all_fields() -> None:
    raw = json.dumps(_valid_payload())
    resp = ExplainVulnResponse.model_validate_json(raw)
    assert resp.summary == _valid_payload()["summary"]
    assert resp.business_risk == _valid_payload()["business_risk"]
    assert resp.grounded is True
    assert len(resp.citations) == 1
    assert resp.citations[0].source == CitationSource.SCANNER_VERBATIM
    assert resp.citations[0].source_field == "cve_id"


# ── Structural gate: missing / empty citations ──


def test_missing_citations_raises_validation_error() -> None:
    payload = _valid_payload()
    del payload["citations"]
    with pytest.raises(ValidationError):
        ExplainVulnResponse.model_validate_json(json.dumps(payload))


def test_empty_citations_list_raises_validation_error() -> None:
    raw = json.dumps(_valid_payload(citations=[]))
    with pytest.raises(ValidationError):
        ExplainVulnResponse.model_validate_json(raw)


# ── Structural gate: invalid enum member ──


def test_invalid_source_enum_value_raises_validation_error() -> None:
    payload = _valid_payload()
    payload["citations"][0]["source"] = "scanner"  # not "scanner_verbatim"
    with pytest.raises(ValidationError):
        ExplainVulnResponse.model_validate_json(json.dumps(payload))


# ── Structural gate: malformed / non-JSON ──


def test_malformed_non_json_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ExplainVulnResponse.model_validate_json("{not valid json")


def test_empty_object_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ExplainVulnResponse.model_validate_json("{}")


# ── Structural gate: grounded is a required bool ──


def test_missing_grounded_raises_validation_error() -> None:
    payload = _valid_payload()
    del payload["grounded"]
    with pytest.raises(ValidationError):
        ExplainVulnResponse.model_validate_json(json.dumps(payload))


def test_grounded_must_be_bool() -> None:
    # Pydantic v2's lax bool coercion DOES accept a handful of string
    # sentinels ("yes"/"true"/"1"/...), so use a value outside that
    # accepted set to prove non-bool-shaped input is genuinely rejected.
    payload = _valid_payload(grounded="not-a-boolean-value")
    with pytest.raises(ValidationError):
        ExplainVulnResponse.model_validate_json(json.dumps(payload))


def test_citation_source_field_is_optional() -> None:
    payload = _valid_payload()
    payload["citations"][0]["source_field"] = None
    resp = ExplainVulnResponse.model_validate_json(json.dumps(payload))
    assert resp.citations[0].source_field is None


# ── Business-rule re-check gate (AI-SPEC Pitfall 4): Anthropic's schema
# translator strips per-field char-budget / allowlist-membership constraints
# from the JSON schema it actually enforces server-side — so a schema-valid
# response is not automatically business-rule-valid. recheck_business_rules()
# is the SECOND, explicit gate that must run after model_validate_json(). ──


def test_recheck_business_rules_passes_for_in_budget_response() -> None:
    resp = ExplainVulnResponse.model_validate(_valid_payload())
    recheck_business_rules(resp)  # must not raise


def test_recheck_business_rules_catches_summary_over_char_budget() -> None:
    payload = _valid_payload(summary="x" * (MAX_SUMMARY_CHARS + 1))
    # The schema gate alone passes — there is no Field(max_length=...) on
    # `summary` precisely because that constraint would be silently stripped
    # by Anthropic's structured-output schema translator (Pitfall 4); this
    # over-budget summary is NOT assumed caught by the model call itself.
    resp = ExplainVulnResponse.model_validate(payload)
    with pytest.raises(BusinessRuleError):
        recheck_business_rules(resp)


def test_recheck_business_rules_catches_business_risk_over_char_budget() -> None:
    payload = _valid_payload(business_risk="x" * (MAX_BUSINESS_RISK_CHARS + 1))
    resp = ExplainVulnResponse.model_validate(payload)
    with pytest.raises(BusinessRuleError):
        recheck_business_rules(resp)


def test_recheck_business_rules_catches_source_field_outside_allowlist() -> None:
    payload = _valid_payload()
    payload["citations"][0]["source_field"] = "internal_directory_user_email"
    resp = ExplainVulnResponse.model_validate(payload)
    with pytest.raises(BusinessRuleError):
        recheck_business_rules(resp, allowed_source_fields=frozenset({"cve_id", "cvss_v3_vector"}))


def test_recheck_business_rules_allows_source_field_without_allowlist_param() -> None:
    """When the caller doesn't pass an allowlist, no source_field membership
    check runs — the char-budget checks still apply regardless."""
    resp = ExplainVulnResponse.model_validate(_valid_payload())
    recheck_business_rules(resp)  # must not raise; no allowlist was supplied
