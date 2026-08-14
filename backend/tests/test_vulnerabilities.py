"""Tests for vulnerability schemas and pagination."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.pagination import PaginatedResponse, PaginationParams
from app.vulnerabilities.schemas import (
    DashboardStats,
    SeverityCount,
    SourceCount,
    VulnerabilityByHost,
    VulnerabilityFilter,
    VulnerabilityResponse,
)


def _minimal_vuln_response(**overrides) -> VulnerabilityResponse:
    """Build a valid VulnerabilityResponse; overrides patch specific fields."""
    now = datetime(2026, 8, 14, tzinfo=UTC)
    base = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        cve_id="CVE-2024-3094",
        vulnerability_name="xz backdoor",
        cvss_v3_score=Decimal("10.0"),
        cvss_v3_vector=None,
        severity="critical",
        epss_score=Decimal("0.9412"),
        exploit_available=True,
        cisa_kev=True,
        asset_id=uuid.uuid4(),
        source="TENABLE",
        source_vuln_id="t-1",
        affected_product="liblzma",
        affected_version="5.6.0",
        fixed_version=None,
        remediation_info=None,
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
        remediated_at=None,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return VulnerabilityResponse(**base)


class TestScoreDecimalSerialization:
    """Regression (2026-08-14): Postgres numeric columns must serialize to JSON
    NUMBERS, not Pydantic v2's default Decimal-as-string. The string form
    (`"10.0"`) silently crashed the frontend drill panel, which calls .toFixed()
    on a `number`-typed field. See ScoreDecimal in schemas.py."""

    def test_detail_scores_serialize_as_json_numbers(self):
        payload = _minimal_vuln_response().model_dump(mode="json")
        assert payload["cvss_v3_score"] == 10.0
        assert isinstance(payload["cvss_v3_score"], float)
        assert isinstance(payload["epss_score"], float)

    def test_none_scores_stay_null(self):
        payload = _minimal_vuln_response(cvss_v3_score=None, epss_score=None).model_dump(mode="json")
        assert payload["cvss_v3_score"] is None
        assert payload["epss_score"] is None

    def test_by_host_top_cvss_serializes_as_number(self):
        payload = VulnerabilityByHost(
            vuln_count=3,
            critical_count=1,
            high_count=1,
            medium_count=1,
            low_count=0,
            top_cvss=Decimal("9.8"),
        ).model_dump(mode="json")
        assert payload["top_cvss"] == 9.8
        assert isinstance(payload["top_cvss"], float)

    def test_python_mode_preserves_decimal(self):
        # when_used="json" — in-process/from_attributes callers still see Decimal.
        payload = _minimal_vuln_response().model_dump()
        assert isinstance(payload["cvss_v3_score"], Decimal)


class TestPagination:
    def test_offset_calculation(self):
        params = PaginationParams(page=1, page_size=50)
        assert params.offset == 0

        params = PaginationParams(page=3, page_size=20)
        assert params.offset == 40

    def test_paginated_response_create(self):
        params = PaginationParams(page=1, page_size=10)
        response = PaginatedResponse.create(items=["a", "b"], total=25, params=params)
        assert response.total == 25
        assert response.page == 1
        assert response.page_size == 10
        assert response.total_pages == 3

    def test_paginated_response_single_page(self):
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse.create(items=[], total=5, params=params)
        assert response.total_pages == 1


class TestVulnerabilityFilter:
    def test_default_filter(self):
        f = VulnerabilityFilter()
        assert f.severity is None
        assert f.source is None
        assert f.search is None

    def test_filter_with_values(self):
        f = VulnerabilityFilter(
            severity=["CRITICAL", "HIGH"],
            source=["CROWDSTRIKE"],
            exploit_available=True,
        )
        assert f.severity == ["CRITICAL", "HIGH"]
        assert f.exploit_available is True


class TestDashboardStats:
    def test_stats_model(self):
        stats = DashboardStats(
            total_vulnerabilities=1000,
            open_vulnerabilities=800,
            by_severity=[
                SeverityCount(severity="CRITICAL", count=50),
                SeverityCount(severity="HIGH", count=200),
            ],
            by_source=[
                SourceCount(source="CROWDSTRIKE", count=600),
            ],
            exploitable_count=75,
            cisa_kev_count=30,
            correlated_cves=142,
            mttr_days=12.5,
        )
        assert stats.total_vulnerabilities == 1000
        assert len(stats.by_severity) == 2
        assert stats.mttr_days == 12.5
