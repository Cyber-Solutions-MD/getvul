"""Nessus Professional vulnerability scanner connector."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedVulnerability

logger = structlog.get_logger(__name__)

SEVERITY_MAP = {
    0: "INFO",
    1: "LOW",
    2: "MEDIUM",
    3: "HIGH",
    4: "CRITICAL",
}


class NessusConnector(BaseConnector):
    """Connector for Nessus Professional vulnerability scanner."""

    source_name = "NESSUS"

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._base_url: str = ""

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(
        self,
        credentials: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> bool:
        """Authenticate to the Nessus server using API keys.

        ``credentials`` must contain:
        - ``url``        – base URL, e.g. ``https://nessus.company.com:8834``
        - ``access_key`` – Nessus API access key
        - ``secret_key`` – Nessus API secret key
        """
        config = config or {}

        access_key = credentials.get("access_key", "")
        secret_key = credentials.get("secret_key", "")
        self._base_url = credentials.get("url", "").rstrip("/")

        if not all([access_key, secret_key, self._base_url]):
            logger.error("nessus.authenticate.missing_credentials")
            return False

        headers = {
            "X-ApiKeys": f"accessKey={access_key}; secretKey={secret_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            verify=False,
            timeout=httpx.Timeout(60.0),
        )

        try:
            resp = await self._client.get("/server/status")
            resp.raise_for_status()
            logger.info(
                "nessus.authenticate.success",
                base_url=self._base_url,
                status=resp.json(),
            )
            return True
        except Exception as exc:
            logger.error("nessus.authenticate.failed", error=str(exc))
            await self.close()
            return False

    # ------------------------------------------------------------------
    # Fetch vulnerabilities
    # ------------------------------------------------------------------

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Retrieve vulnerabilities from all completed Nessus scans."""
        if self._client is None:
            raise RuntimeError("Not authenticated – call authenticate() first")

        results: list[NormalizedVulnerability] = []

        # 1. List all scans
        scans = await self._list_completed_scans()
        logger.info("nessus.scans.found", total=len(scans))

        for scan_meta in scans:
            scan_id = scan_meta["id"]
            scan_name = scan_meta.get("name", "")
            logger.info("nessus.scan.processing", scan_id=scan_id, name=scan_name)

            try:
                scan_detail = await self._get_scan(scan_id)
            except Exception as exc:
                logger.warning(
                    "nessus.scan.fetch_failed",
                    scan_id=scan_id,
                    error=str(exc),
                )
                continue

            hosts = scan_detail.get("hosts", [])
            logger.info(
                "nessus.scan.hosts",
                scan_id=scan_id,
                host_count=len(hosts),
            )

            for host in hosts:
                host_id = host.get("host_id")
                if host_id is None:
                    continue

                try:
                    host_detail = await self._get_host(scan_id, host_id)
                except Exception as exc:
                    logger.warning(
                        "nessus.host.fetch_failed",
                        scan_id=scan_id,
                        host_id=host_id,
                        error=str(exc),
                    )
                    continue

                host_info = host_detail.get("info", {})
                host_ip = host_info.get("host-ip", "")
                host_fqdn = host_info.get("host-fqdn", "")
                os_raw = host_info.get("operating-system", "")
                os_name, os_version = _parse_os(os_raw)
                hostname = host_fqdn or host_ip

                vulns = host_detail.get("vulnerabilities", [])
                for vuln in vulns:
                    normalized = _normalize_vuln(
                        vuln,
                        hostname=hostname,
                        host_ip=host_ip,
                        os_name=os_name,
                        os_version=os_version,
                    )
                    results.extend(normalized)

                # Rate-limit: small pause between host requests
                await asyncio.sleep(0.25)

            # Rate-limit: pause between scan requests
            await asyncio.sleep(0.5)

        logger.info("nessus.fetch_vulnerabilities.done", total=len(results))
        return results

    # ------------------------------------------------------------------
    # Internal API helpers
    # ------------------------------------------------------------------

    async def _list_completed_scans(self) -> list[dict[str, Any]]:
        """Return scans that have status 'completed'."""
        assert self._client is not None
        resp = await self._client.get("/scans")
        resp.raise_for_status()
        data = resp.json()
        scans: list[dict[str, Any]] = data.get("scans") or []
        return [s for s in scans if s.get("status") == "completed"]

    async def _get_scan(self, scan_id: int) -> dict[str, Any]:
        """GET /scans/{scan_id} – full scan detail."""
        assert self._client is not None
        resp = await self._client.get(f"/scans/{scan_id}")
        resp.raise_for_status()
        return resp.json()

    async def _get_host(self, scan_id: int, host_id: int) -> dict[str, Any]:
        """GET /scans/{scan_id}/hosts/{host_id} – host-level details."""
        assert self._client is not None
        resp = await self._client.get(f"/scans/{scan_id}/hosts/{host_id}")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("nessus.client.closed")


# ======================================================================
# Pure helper functions
# ======================================================================


def _parse_os(raw: str) -> tuple[str, str]:
    """Best-effort parse of an OS string into (name, version).

    Examples:
        "Microsoft Windows 10 Pro 10.0.19041" -> ("Microsoft Windows 10 Pro", "10.0.19041")
        "Linux Kernel 5.4"                    -> ("Linux Kernel", "5.4")
        ""                                    -> ("", "")
    """
    if not raw:
        return ("", "")

    # Try to split on the last version-looking token
    match = re.search(r"(\d+(?:\.\d+)+)\s*$", raw)
    if match:
        version = match.group(1)
        name = raw[: match.start()].strip()
        return (name or raw, version)

    return (raw, "")


def _check_exploit_available(vuln: dict[str, Any]) -> bool:
    """Heuristic check for exploit availability."""
    # Check plugin attributes if present
    attrs = vuln.get("plugin_attributes", {})
    if isinstance(attrs, dict):
        if attrs.get("exploit_available", "") in ("true", True, "1"):
            return True
        if attrs.get("exploitability_ease", "") not in ("", "No known exploits are available"):
            return True

    # Check the description text
    description = str(vuln.get("description", "")).lower()
    return bool("exploitable" in description or "exploit available" in description)


def _normalize_vuln(
    vuln: dict[str, Any],
    *,
    hostname: str,
    host_ip: str,
    os_name: str,
    os_version: str,
) -> list[NormalizedVulnerability]:
    """Convert a single Nessus vulnerability dict into one or more NormalizedVulnerability."""
    plugin_id = vuln.get("plugin_id", 0)
    plugin_name = vuln.get("plugin_name", "")
    severity_int = vuln.get("severity", 0)
    severity = SEVERITY_MAP.get(severity_int, "INFO")
    cvss3 = vuln.get("cvss3_base_score")
    solution = vuln.get("solution", "")
    plugin_output = vuln.get("plugin_output", "")
    cves: list[str] = vuln.get("cve", []) or []
    exploit_available = _check_exploit_available(vuln)

    # Parse affected product from plugin_output (first line as fallback)
    affected_product = ""
    if plugin_output:
        first_line = plugin_output.strip().split("\n")[0].strip()
        if first_line and len(first_line) < 200:
            affected_product = first_line

    # Convert cvss3 to float if present
    cvss3_score: float | None = None
    if cvss3 is not None:
        try:
            cvss3_score = float(cvss3)
        except (TypeError, ValueError):
            cvss3_score = None

    base = dict(
        vulnerability_name=plugin_name,
        cvss_v3_score=cvss3_score,
        severity=severity,
        source="NESSUS",
        source_vuln_id=str(plugin_id),
        remediation_info=solution or None,
        hostname=hostname or None,
        ip_addresses=[host_ip] if host_ip else [],
        os_name=os_name or None,
        os_version=os_version or None,
        affected_product=affected_product or None,
        exploit_available=exploit_available,
    )

    results: list[NormalizedVulnerability] = []

    if cves:
        for cve in cves:
            results.append(NormalizedVulnerability(cve_id=cve, **base))
    else:
        results.append(NormalizedVulnerability(cve_id=f"NESSUS-{plugin_id}", **base))

    return results
