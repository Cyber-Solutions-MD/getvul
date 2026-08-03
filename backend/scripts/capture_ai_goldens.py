"""One-time dev-key golden-fixture capture script (AIE-01, 28-CONTEXT.md D-07).

This script is NOT run in CI -- it is a manually-invoked, one-time developer
tool. The golden fixtures it produces under `backend/tests/evals/goldens/`
are consumed KEYLESS by the CI-blocking `deepeval test run
tests/evals/test_golden_evals.py` suite (Plan 28-01) and must never require a
live model call to pass.

Usage (requires a personal dev key -- never committed, never used in CI):

    GETVUL_DEV_ANTHROPIC_KEY=sk-ant-... python scripts/capture_ai_goldens.py

Re-capture procedure: whenever a response schema (`app/ai/schemas.py`), an
allowlist, or a system prompt (`app/ai/prompt_builder.py`) changes in a way
that would change what a genuinely valid captured response looks like,
re-run this script with a personal `GETVUL_DEV_ANTHROPIC_KEY` and re-commit
the regenerated `backend/tests/evals/goldens/**/*.json` files as a normal,
reviewable source diff.

Design notes (28-RESEARCH.md Open Question 3 -- RESOLVED):
  - This is a MINIMAL standalone capture, not the full `_run_explain_stream()`
    streaming/retry engine. It calls `build_explain_*_prompt()` + a single
    non-streaming `AsyncAnthropic.messages.create()` call (using
    `_build_output_config()`'s exact structured-output shape) +
    `response_model.model_validate_json()` + `recheck_business_rules()`
    directly -- the SAME production prompt-builder and SAME production
    validation gates the real engine uses for the part that actually matters
    for a golden fixture (the FINAL validated response), without needing a
    live app/DB/Redis session for a one-time, offline capture.
  - Every grounding_record below is HAND-AUTHORED and synthetic BY
    CONSTRUCTION (synthetic hostnames like "acme-web-01", synthetic CVE IDs)
    -- never captured-then-redacted real tenant data (D-07). This is a
    stronger guarantee than "capture then scrub": real tenant data never
    enters this script's process in the first place.
  - Only a genuinely valid capture (passes BOTH `model_validate_json()` AND
    `recheck_business_rules()` -- exactly the two gates
    `_run_explain_stream()` itself enforces) is ever written to disk; a
    bad/flaky model response never becomes a permanently-committed golden.

Honest scope note (28-01-PLAN.md): `GETVUL_DEV_ANTHROPIC_KEY` was confirmed
ABSENT in the environment where Plan 28-01 executed (STATE.md's Phase 24-01
blocker). The 10 committed fixtures under `backend/tests/evals/goldens/`
were therefore HAND-AUTHORED to pass these exact same two gates rather than
captured by actually running this script -- see each fixture's own
`"capture_method"` field. This script remains the documented, reproducible
mechanism for a future developer who DOES have a dev key to regenerate them
for real; running it will silently overwrite the hand-authored fixtures with
genuinely model-captured ones using the IDENTICAL grounding_records below.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.explain import MAX_TOKENS, _build_output_config, _default_client_factory
from app.ai.prompt_builder import (
    HOST_ALLOWLIST,
    PRIORITIZATION_ALLOWLIST,
    REMEDIATION_ALLOWLIST,
    REMEDIATION_GUIDANCE_ALLOWLIST,
    VULN_ALLOWLIST,
    build_explain_host_prompt,
    build_explain_prioritization_prompt,
    build_explain_remediation_guidance_prompt,
    build_explain_remediation_prompt,
    build_explain_vuln_prompt,
)
from app.ai.schemas import (
    ExplainHostResponse,
    ExplainPrioritizationResponse,
    ExplainRemediationGuidanceResponse,
    ExplainRemediationResponse,
    ExplainResponseBase,
    ExplainVulnResponse,
    recheck_business_rules,
)

GOLDENS_DIR = Path(__file__).resolve().parent.parent / "tests" / "evals" / "goldens"

# D-01: same default model the production engine falls back to when a
# tenant hasn't configured one explicitly (app.ai.explain.DEFAULT_MODEL) --
# this script deliberately does not hit the DB for a per-tenant override,
# since it never runs against a real tenant (RESEARCH Open Question 3).
_CAPTURE_MODEL = "claude-sonnet-5"


@dataclass(frozen=True)
class CaptureRow:
    """One capability x case combination (28-RESEARCH.md's Golden-Fixture
    Capture table) -- everything needed to build the prompt, call the model,
    validate the response through the exact production gates, and write the
    fixture to its own `goldens/<capability>/<case>.json` path."""

    capability: str
    case: str
    build_prompt: Callable[[Any], tuple[str, list[dict[str, str]]]]
    response_model: type[ExplainResponseBase]
    allowed_source_fields: frozenset[str]
    grounding_record: dict[str, Any]


# Every grounding_record's keys are a strict subset of that capability's own
# allowlist (VULN_ALLOWLIST/HOST_ALLOWLIST/REMEDIATION_ALLOWLIST/
# REMEDIATION_GUIDANCE_ALLOWLIST/PRIORITIZATION_ALLOWLIST) -- hand-authored,
# synthetic by construction, mirroring each view's own FEW_SHOT_* exemplars
# in shape (never a real tenant hostname, CVE, or identifier).
CAPTURE_ROWS: tuple[CaptureRow, ...] = (
    CaptureRow(
        capability="vuln",
        case="grounded",
        build_prompt=build_explain_vuln_prompt,
        response_model=ExplainVulnResponse,
        allowed_source_fields=VULN_ALLOWLIST,
        grounding_record={
            "cve_id": "CVE-2025-9101",
            "vulnerability_name": "Acme WebGateway Remote Code Execution",
            "cvss_v3_score": 9.1,
            "cvss_v3_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "severity": "CRITICAL",
            "cisa_kev": True,
            "exploit_available": True,
            "asset_hostname": "acme-web-01",
            "source": "NESSUS",
            "affected_product": "Acme WebGateway",
            "affected_version": "4.2.0",
            "fixed_version": "4.2.3",
            "remediation_info": "Upgrade Acme WebGateway to 4.2.3 or later.",
            "status": "OPEN",
            "first_detected_at": "2026-06-15T00:00:00Z",
            "last_seen_at": "2026-07-30T00:00:00Z",
        },
    ),
    CaptureRow(
        capability="vuln",
        case="insufficient_evidence",
        build_prompt=build_explain_vuln_prompt,
        response_model=ExplainVulnResponse,
        allowed_source_fields=VULN_ALLOWLIST,
        grounding_record={
            "cve_id": None,
            "vulnerability_name": "Unspecified Finding",
            "cvss_v3_score": None,
            "cvss_v3_vector": None,
            "severity": "LOW",
            "cisa_kev": False,
            "exploit_available": False,
            "asset_hostname": "acme-ws-42",
            "source": "QUALYS",
            "affected_product": None,
            "affected_version": None,
            "fixed_version": None,
            "remediation_info": None,
            "status": "OPEN",
            "first_detected_at": "2026-07-01T00:00:00Z",
            "last_seen_at": "2026-07-29T00:00:00Z",
        },
    ),
    CaptureRow(
        capability="host",
        case="grounded",
        build_prompt=build_explain_host_prompt,
        response_model=ExplainHostResponse,
        allowed_source_fields=HOST_ALLOWLIST,
        grounding_record={
            "hostname": "acme-db-02",
            "os_name": "Ubuntu",
            "os_version": "22.04",
            "device_category": "SERVER",
            "risk_score": 91,
            "vuln_counts": {
                "total": 21,
                "critical": 4,
                "high": 7,
                "medium": 8,
                "low": 2,
                "exploitable": 3,
                "kev": 2,
                "sla_breach": 3,
            },
            "tags": ["pci", "internet-facing"],
            "sla_breach": 3,
            "last_checkin_at": "2026-07-30T00:00:00Z",
        },
    ),
    CaptureRow(
        capability="host",
        case="insufficient_evidence",
        build_prompt=build_explain_host_prompt,
        response_model=ExplainHostResponse,
        allowed_source_fields=HOST_ALLOWLIST,
        grounding_record={
            "hostname": "acme-ws-77",
            "os_name": None,
            "os_version": None,
            "device_category": "WORKSTATION",
            "risk_score": 0,
            "vuln_counts": {
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "exploitable": 0,
                "kev": 0,
                "sla_breach": 0,
            },
            "tags": [],
            "sla_breach": 0,
            "last_checkin_at": None,
        },
    ),
    CaptureRow(
        capability="remediation",
        case="grounded",
        build_prompt=build_explain_remediation_prompt,
        response_model=ExplainRemediationResponse,
        allowed_source_fields=REMEDIATION_ALLOWLIST,
        grounding_record={
            "cve": "CVE-2025-9101",
            "fix": "Upgrade Acme WebGateway to 4.2.3 or later.",
            "affected_assets": [
                {
                    "hostname": "acme-web-01",
                    "os_name": "Ubuntu",
                    "os_version": "22.04",
                    "severity": "CRITICAL",
                    "exploit_available": True,
                    "cisa_kev": True,
                },
                {
                    "hostname": "acme-web-02",
                    "os_name": "Ubuntu",
                    "os_version": "22.04",
                    "severity": "CRITICAL",
                    "exploit_available": True,
                    "cisa_kev": True,
                },
            ],
            "priority": "CRITICAL",
        },
    ),
    CaptureRow(
        capability="remediation",
        case="insufficient_evidence",
        build_prompt=build_explain_remediation_prompt,
        response_model=ExplainRemediationResponse,
        allowed_source_fields=REMEDIATION_ALLOWLIST,
        grounding_record={
            "cve": "CVE-2025-1234",
            "fix": None,
            "affected_assets": [
                {
                    "hostname": "acme-ws-13",
                    "os_name": "Windows",
                    "os_version": "11",
                    "severity": "LOW",
                    "exploit_available": False,
                    "cisa_kev": False,
                },
            ],
            "priority": "LOW",
        },
    ),
    CaptureRow(
        capability="remediation_guidance",
        case="grounded",
        build_prompt=build_explain_remediation_guidance_prompt,
        response_model=ExplainRemediationGuidanceResponse,
        allowed_source_fields=REMEDIATION_GUIDANCE_ALLOWLIST,
        grounding_record={
            "cve_id": "CVE-2025-5566",
            "severity": "HIGH",
            "exploit_available": True,
            "cisa_kev": True,
            "remediation_action": "Upgrade OpenSSL to version 3.0.15 or later.",
            "remediation_info": "Vendor advisory: apply the 3.0.15 security update.",
            "affected_product": "OpenSSL",
            "affected_version": "3.0.14",
            "fixed_version": "3.0.15",
            "asset_hostname": "acme-web-01",
            "os_name": "Ubuntu",
            "os_version": "22.04",
        },
    ),
    CaptureRow(
        capability="remediation_guidance",
        case="insufficient_evidence",
        build_prompt=build_explain_remediation_guidance_prompt,
        response_model=ExplainRemediationGuidanceResponse,
        allowed_source_fields=REMEDIATION_GUIDANCE_ALLOWLIST,
        grounding_record={
            "cve_id": "CVE-2025-7788",
            "severity": "MEDIUM",
            "exploit_available": False,
            "cisa_kev": False,
            "remediation_action": "Refer to vendor documentation for applicable configuration changes.",
            "remediation_info": None,
            "affected_product": "Acme Agent",
            "affected_version": "2.4.0",
            "fixed_version": None,
            "asset_hostname": "acme-ws-88",
            "os_name": "Windows",
            "os_version": "11",
        },
    ),
    CaptureRow(
        capability="prioritization",
        case="grounded",
        build_prompt=build_explain_prioritization_prompt,
        response_model=ExplainPrioritizationResponse,
        allowed_source_fields=PRIORITIZATION_ALLOWLIST,
        grounding_record={
            "cve_id": "CVE-2025-9101",
            "cvss_v3_score": 9.1,
            "epss_score": 0.91,
            "exploit_available": True,
            "cisa_kev": True,
            "exploit_status_name": "Weaponized",
            "severity": "CRITICAL",
            "sla_due_at": "2026-07-15T00:00:00Z",
            "sla_breached": True,
            "department": "Engineering",
        },
    ),
    CaptureRow(
        capability="prioritization",
        case="insufficient_evidence",
        build_prompt=build_explain_prioritization_prompt,
        response_model=ExplainPrioritizationResponse,
        allowed_source_fields=PRIORITIZATION_ALLOWLIST,
        grounding_record={
            "cve_id": None,
            "cvss_v3_score": None,
            "epss_score": None,
            "exploit_available": None,
            "cisa_kev": None,
            "exploit_status_name": None,
            "severity": "LOW",
            "sla_due_at": None,
            "sla_breached": False,
            "department": None,
        },
    ),
)


async def _capture_one(row: CaptureRow, *, api_key: str) -> None:
    system_prompt, user_blocks = row.build_prompt(row.grounding_record)
    output_config = _build_output_config(row.response_model, _CAPTURE_MODEL)
    client = _default_client_factory(api_key)
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_blocks}]

    # A plain, single non-streaming call -- the capture only needs the FINAL
    # validated response, never the drill panel's cosmetic streamed-reveal
    # replay (RESEARCH Open Question 3). Same output_config/temperature/
    # max_tokens shape `_run_explain_stream()` itself uses.
    raw_message = await client.messages.create(
        model=_CAPTURE_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0,
        system=system_prompt,
        messages=messages,  # type: ignore[arg-type]
        output_config=output_config,  # type: ignore[arg-type]
    )
    raw_text = "".join(
        getattr(block, "text", "") for block in raw_message.content if getattr(block, "type", None) == "text"
    )

    # The exact two-gate validation chain `_run_explain_stream()` enforces
    # (app/ai/explain.py:392-394) -- only a genuinely valid capture is ever
    # written to disk.
    candidate = row.response_model.model_validate_json(raw_text)
    recheck_business_rules(candidate, allowed_source_fields=row.allowed_source_fields)

    fixture = {
        "grounding_record": row.grounding_record,
        "schema_name": row.response_model.__name__,
        "model_response": candidate.model_dump(mode="json"),
        "model_used": _CAPTURE_MODEL,
        "captured_at": datetime.now(UTC).isoformat(),
        "capture_method": "dev_key_capture",
    }
    out_path = GOLDENS_DIR / row.capability / f"{row.case}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(f"captured {row.capability}/{row.case} -> {out_path}")  # noqa: T201 -- one-time CLI tool, stdout IS the UX


async def _main() -> None:
    api_key = os.environ.get("GETVUL_DEV_ANTHROPIC_KEY")
    if not api_key:
        print(  # noqa: T201
            "GETVUL_DEV_ANTHROPIC_KEY is not set -- this one-time capture script "
            "requires a personal dev key and is NEVER run in CI. See this file's "
            "module docstring for the re-capture procedure.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    failures: list[tuple[str, str, Exception]] = []
    for row in CAPTURE_ROWS:
        try:
            await _capture_one(row, api_key=api_key)
        except Exception as exc:  # noqa: BLE001 -- a bad/flaky capture must never partially write a golden
            failures.append((row.capability, row.case, exc))
            print(f"SKIPPED {row.capability}/{row.case}: {exc}", file=sys.stderr)  # noqa: T201

    if failures:
        print(f"{len(failures)} of {len(CAPTURE_ROWS)} rows failed to capture a valid golden.", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(_main())
