"""Tests for vulnerability schemas and pagination."""

from app.pagination import PaginatedResponse, PaginationParams
from app.vulnerabilities.schemas import (
    DashboardStats,
    SeverityCount,
    SourceCount,
    VulnerabilityFilter,
)


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
