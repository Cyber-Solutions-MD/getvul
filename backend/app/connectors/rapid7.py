"""
Rapid7 InsightVM vulnerability scanner connector.

Pulls assets, vulnerabilities, and remediation solutions from InsightVM API v3
and normalises them into NormalizedVulnerability records.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.connectors.base import BaseConnector, NormalizedVulnerability

logger = logging.getLogger(__name__)

PAGE_SIZE = 500


class Rapid7Connector(BaseConnector):
    source_name = "RAPID7"

    def __init__(self) -> None:
        super().__init__()
        self.base_url: str = ""
        self.username: str = ""
        self.password: str = ""
        self.verify_tls: bool = True
        self._client: httpx.AsyncClient | None = None
        # Caches
        self._vuln_detail_cache: dict[str, dict] = {}
        self._vuln_solutions_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(
        self,
        credentials: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> bool:
        """Authenticate to the InsightVM Security Console using Basic auth.

        ``credentials`` must contain:
        - ``url``      – InsightVM console URL, e.g. ``https://insightvm.company.com:3780``
        - ``username`` – InsightVM API username
        - ``password`` – InsightVM API password

        ``config`` may contain:
        - ``verify_tls`` – whether to validate the server's TLS certificate (default True).
          On-prem consoles on self-signed/internal-CA certs can opt out explicitly (D-21).
        """
        config = config or {}

        self.base_url = credentials.get("url", "").rstrip("/")
        self.username = credentials.get("username", "")
        self.password = credentials.get("password", "")
        self.verify_tls = config.get("verify_tls", True)

        if not all([self.base_url, self.username, self.password]):
            logger.error("Rapid7: missing base_url/username/password credentials")
            return False

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.username, self.password),
            verify=self.verify_tls,
            timeout=httpx.Timeout(60.0),
        )

        try:
            resp = await self._client.get("/api/3/assets", params={"page": 0, "size": 1})
            resp.raise_for_status()
            logger.info("Rapid7: authenticated successfully (base_url=%s)", self.base_url)
            return True
        except Exception as exc:
            logger.error("Rapid7: authentication failed: %s", exc)
            await self.close()
            return False

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.username, self.password),
                verify=self.verify_tls,
                timeout=httpx.Timeout(60.0),
            )
        return self._client

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        client = self._get_client()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _paginate(self, path: str, extra_params: dict | None = None) -> list[dict]:
        """Fetch all pages for a paginated InsightVM v3 endpoint."""
        results: list[dict] = []
        page = 0
        while True:
            params: dict[str, Any] = {"page": page, "size": PAGE_SIZE}
            if extra_params:
                params.update(extra_params)
            data = await self._get_json(path, params=params)
            resources = data.get("resources", [])
            results.extend(resources)
            total_pages = data.get("page", {}).get("totalPages", 1)
            page += 1
            if page >= total_pages:
                break
        return results

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def _fetch_assets(self) -> list[dict]:
        logger.info("Rapid7: fetching assets …")
        assets = await self._paginate("/api/3/assets")
        logger.info("Rapid7: fetched %d assets", len(assets))
        return assets

    async def _fetch_asset_vulns(self, asset_id: int) -> list[dict]:
        return await self._paginate(f"/api/3/assets/{asset_id}/vulnerabilities")

    async def _fetch_vuln_detail(self, vuln_id: str) -> dict:
        if vuln_id in self._vuln_detail_cache:
            return self._vuln_detail_cache[vuln_id]
        detail = await self._get_json(f"/api/3/vulnerabilities/{vuln_id}")
        self._vuln_detail_cache[vuln_id] = detail
        return detail

    async def _fetch_vuln_solutions(self, vuln_id: str) -> str:
        if vuln_id in self._vuln_solutions_cache:
            return self._vuln_solutions_cache[vuln_id]
        data = await self._get_json(f"/api/3/vulnerabilities/{vuln_id}/solutions")
        solutions = data.get("resources", [])
        summary = "; ".join(s.get("summary", "") for s in solutions if s.get("summary"))
        self._vuln_solutions_cache[vuln_id] = summary
        return summary

    # ------------------------------------------------------------------
    # Severity mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _severity_from_cvss(score: float | None) -> str:
        if score is None:
            return "LOW"
        if score >= 9.0:
            return "CRITICAL"
        if score >= 7.0:
            return "HIGH"
        if score >= 4.0:
            return "MEDIUM"
        return "LOW"

    # ------------------------------------------------------------------
    # Main entry-point
    # ------------------------------------------------------------------

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        results: list[NormalizedVulnerability] = []

        assets = await self._fetch_assets()
        {a["id"]: a for a in assets}

        for idx, asset in enumerate(assets, 1):
            asset_id: int = asset["id"]
            hostname = asset.get("hostName", "")
            ip = asset.get("ip", "")
            os_info = asset.get("os") or {}
            os_name = os_info.get("description", "")
            os_version = os_info.get("version", "")

            logger.info(
                "Rapid7: processing asset %d/%d (id=%s, host=%s)",
                idx,
                len(assets),
                asset_id,
                hostname,
            )

            asset_vulns = await self._fetch_asset_vulns(asset_id)
            logger.info(
                "Rapid7: asset %s has %d vulnerabilities",
                asset_id,
                len(asset_vulns),
            )

            # Batch-fetch unique vuln details for this asset
            unique_vuln_ids = {v["id"] for v in asset_vulns if "id" in v}
            for vid in unique_vuln_ids:
                if vid not in self._vuln_detail_cache:
                    try:
                        await self._fetch_vuln_detail(vid)
                    except httpx.HTTPStatusError as exc:
                        logger.warning(
                            "Rapid7: failed to fetch detail for vuln %s: %s",
                            vid,
                            exc,
                        )

            for vuln_entry in asset_vulns:
                vuln_id: str = vuln_entry.get("id", "")
                if not vuln_id:
                    continue

                detail = self._vuln_detail_cache.get(vuln_id, {})
                title = detail.get("title", vuln_id)

                # CVSS v3
                cvss_block = detail.get("cvss", {})
                v3_block = cvss_block.get("v3", {})
                cvss_score: float | None = v3_block.get("score")

                severity = self._severity_from_cvss(cvss_score)
                exploit_count = detail.get("exploits", 0)
                exploit_available = exploit_count > 0 if isinstance(exploit_count, int) else False

                # ENRICH-03/04 (Phase 31 Plan 04, Pitfall 5): Risk Score is
                # asset-context-dependent -- read from `vuln_entry` (the
                # per-asset AssetVulnerability association entry), NEVER
                # `detail` (the vendor-neutral vulnerability definition,
                # identical for every asset sharing this CVE). Captured
                # BEFORE the per-CVE loop below so every fanout finding for
                # this vuln_entry gets the same value.
                native_priority_score = _get_risk_score(vuln_entry)

                # source_signals (D-07/D-08): built from the RAW vuln_entry
                # dict in this same scope. `status` (InsightVM's per-asset
                # match-confidence enum -- vulnerable/vulnerable-version/
                # vulnerable-potential/not-vulnerable*) is currently entirely
                # discarded by this connector (only vuln_entry["id"] is read
                # above) and is genuinely exploit/confidence-relevant. A
                # derived `status_confirmed` boolean is added alongside it as
                # PROVENANCE ONLY, mirroring crowdstrike.py's own raw-value +
                # derived-guess pair (Phase 31 Plan 03) -- never authoritative
                # for a promoted column. riskScore itself is excluded here --
                # already promoted to native_priority_score, not duplicated
                # (D-08).
                source_signals: dict[str, Any] = {}
                if "status" in vuln_entry:
                    source_signals["status"] = vuln_entry["status"]
                    source_signals["status_confirmed"] = vuln_entry["status"] == "vulnerable"

                # Remediation
                try:
                    remediation_info = await self._fetch_vuln_solutions(vuln_id)
                except httpx.HTTPStatusError:
                    remediation_info = ""

                # CVEs — emit one record per CVE; fall back to vuln id
                cves: list[str] = detail.get("cves", []) or []
                if not cves:
                    cves = [vuln_id]

                for cve_id in cves:
                    results.append(
                        NormalizedVulnerability(
                            cve_id=cve_id,
                            vulnerability_name=title,
                            cvss_v3_score=cvss_score,
                            severity=severity,
                            source_vuln_id=vuln_id,
                            hostname=hostname,
                            ip_addresses=[ip] if ip else [],
                            os_name=os_name,
                            os_version=os_version,
                            remediation_info=remediation_info,
                            exploit_available=exploit_available,
                            # D-06/Pitfall 5: Risk Score is numeric-only --
                            # Rapid7 has no separate vendor-authored
                            # categorical rating -- native_priority_rating
                            # stays explicit None (never omitted, never
                            # invented).
                            native_priority_rating=None,
                            native_priority_score=native_priority_score,
                            source_signals=source_signals,
                        )
                    )

        logger.info("Rapid7: produced %d normalised vulnerability records", len(results))
        return results

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("Rapid7: HTTP client closed")


# ======================================================================
# Normalisation helpers
# ======================================================================


def _get_risk_score(vuln_entry: dict[str, Any]) -> float | None:
    """ENRICH-03/D-05 (Phase 31 Plan 04): defensive Rapid7 Risk Score probe.

    Risk/Active Risk Score (0-1000 scale) is asset-context-dependent, so it
    lives on the per-asset AssetVulnerability ASSOCIATION entry
    (``vuln_entry``, the ``/api/3/assets/{id}/vulnerabilities`` resource),
    NOT the vendor-neutral ``detail`` resource (Pitfall 5). Exact field name
    is unverified this session (31-RESEARCH.md Assumption A2) -- probes the
    leading candidate (``riskScore``) named verbatim in the plan's own
    interfaces block. Soft-nulls (never raises) on absence or a non-numeric
    value.
    """
    raw = vuln_entry.get("riskScore")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
