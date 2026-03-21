"""Microsoft Defender for Endpoint connector — machine vulns + recommendations.

Fetches vulnerability findings from Microsoft Defender for Endpoint via:
  - /api/machines — all managed devices
  - /api/vulnerabilities/machinesVulnerabilities — CVE findings per machine
  - /api/recommendations — remediation recommendations mapped by CVE

Authentication uses Azure AD OAuth2 client_credentials flow.
"""

from __future__ import annotations

import asyncio
import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedVulnerability

logger = structlog.get_logger()

TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
API_BASE = "https://api.securitycenter.microsoft.com"
SCOPE = "https://api.securitycenter.microsoft.com/.default"

MAX_RETRIES = 3
RETRY_BACKOFF = 5  # seconds


class DefenderConnector(BaseConnector):
    source_name = "DEFENDER"

    def __init__(self):
        self.access_token: str | None = None
        self.client: httpx.AsyncClient | None = None
        self._machine_cache: dict[str, dict] = {}
        self._recommendation_cache: dict[str, dict] = {}  # cve_id -> recommendation

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        tenant_id = credentials["tenant_id"]
        client_id = credentials["client_id"]
        client_secret = credentials["client_secret"]

        token_url = TOKEN_URL.format(tenant_id=tenant_id)

        self.client = httpx.AsyncClient(base_url=API_BASE, timeout=60)
        try:
            resp = await self.client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": SCOPE,
                },
            )
            if resp.status_code == 200:
                self.access_token = resp.json().get("access_token")
                logger.info("defender_auth_success")
                return True
            logger.error("defender_auth_failed", status=resp.status_code, body=resp.text[:500])
            return False
        except Exception as e:
            logger.error("defender_auth_error", error=str(e))
            return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    # ── OData paginated fetcher ──

    async def _fetch_odata_pages(self, path: str, label: str) -> list[dict]:
        """Fetch all pages of an OData endpoint following @odata.nextLink."""
        if not self.client:
            return []

        all_records: list[dict] = []
        url: str | None = path

        for page in range(500):  # safety cap
            try:
                resp = await self._request_with_retry(url)
                if resp is None:
                    break
                data = resp.json()
            except Exception as e:
                logger.error(f"defender_{label}_page_error", page=page, error=str(e))
                break

            records = data.get("value", [])
            all_records.extend(records)

            next_link = data.get("@odata.nextLink")
            if not next_link or not records:
                break

            # nextLink is a full URL; use it directly
            url = next_link
            if page % 5 == 0 and page > 0:
                logger.info(f"defender_{label}_progress", pages=page, records=len(all_records))

        logger.info(f"defender_{label}_fetched", total=len(all_records))
        return all_records

    async def _request_with_retry(self, url: str) -> httpx.Response | None:
        """GET with retry on 429 rate limits."""
        for attempt in range(MAX_RETRIES):
            try:
                # If it's a full URL (nextLink), use it directly; otherwise treat as relative path
                if url.startswith("https://"):
                    resp = await self.client.request("GET", url, headers=self._headers())
                else:
                    resp = await self.client.get(url, headers=self._headers())

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", RETRY_BACKOFF))
                    logger.warning("defender_rate_limited", retry_after=retry_after, attempt=attempt + 1)
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code == 403:
                    logger.warning("defender_forbidden", url=url)
                    return None

                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError:
                raise
            except Exception as e:
                logger.warning("defender_request_error", url=url, attempt=attempt + 1, error=str(e))
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF)
                    continue
                return None

        logger.error("defender_request_exhausted_retries", url=url)
        return None

    # ── Machine resolution ──

    async def _fetch_machines(self) -> None:
        """Fetch all machines and cache by id."""
        records = await self._fetch_odata_pages("/api/machines", "machines")
        for machine in records:
            machine_id = machine.get("id", "")
            if machine_id:
                self._machine_cache[machine_id] = machine
        logger.info("defender_machines_cached", count=len(self._machine_cache))

    # ── Recommendations resolution ──

    async def _fetch_recommendations(self) -> None:
        """Fetch all recommendations and cache by CVE id."""
        records = await self._fetch_odata_pages("/api/recommendations", "recommendations")
        for rec in records:
            related_cves = rec.get("relatedCves", []) or []
            for cve_id in related_cves:
                # Keep the first recommendation per CVE (or the most relevant)
                if cve_id not in self._recommendation_cache:
                    self._recommendation_cache[cve_id] = rec
        logger.info("defender_recommendations_cached", count=len(self._recommendation_cache))

    # ── Vulnerability fetching ──

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        if not self.client or not self.access_token:
            return []

        # Fetch machines and recommendations in parallel
        logger.info("defender_fetching_machines_and_recommendations")
        await asyncio.gather(
            self._fetch_machines(),
            self._fetch_recommendations(),
        )

        # Fetch vulnerability findings
        logger.info("defender_fetching_vulnerabilities")
        vuln_records = await self._fetch_odata_pages(
            "/api/vulnerabilities/machinesVulnerabilities", "vulns",
        )

        all_vulns: list[NormalizedVulnerability] = []
        for record in vuln_records:
            v = self._normalize_vuln(record)
            if v:
                all_vulns.append(v)

        logger.info("defender_vulns_total", count=len(all_vulns))
        return all_vulns

    def _normalize_vuln(self, record: dict) -> NormalizedVulnerability | None:
        cve_id = record.get("cveId")
        if not cve_id:
            return None

        machine_id = record.get("machineId", "")
        machine = self._machine_cache.get(machine_id, {})

        # Hostname
        hostname = machine.get("computerDnsName", "")
        if not hostname:
            hostname = machine_id[:12] if machine_id else "unknown"

        # IP addresses
        ip_addresses: list[str] = []
        for ip_entry in (machine.get("ipAddresses") or []):
            addr = ip_entry.get("ipAddress", "") if isinstance(ip_entry, dict) else str(ip_entry)
            if addr and addr not in ip_addresses:
                ip_addresses.append(addr)

        # Severity — API returns Critical/High/Medium/Low, uppercase it
        severity = (record.get("severity") or "MEDIUM").upper()
        if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            severity = "MEDIUM"

        # CVSS
        cvss_v3_score = record.get("cvssV3")
        if cvss_v3_score is not None:
            try:
                cvss_v3_score = float(cvss_v3_score)
            except (TypeError, ValueError):
                cvss_v3_score = None

        # Product info
        product_name = record.get("productName", "")
        product_vendor = record.get("productVendor", "")
        product_version = record.get("productVersion", "")

        affected_product = product_name
        if product_vendor and product_name and product_vendor.lower() not in product_name.lower():
            affected_product = f"{product_vendor} {product_name}"

        # Fixed version — from record or recommendation
        fixed_version = record.get("fixedBuild", "")
        recommendation = self._recommendation_cache.get(cve_id, {})
        if not fixed_version and recommendation:
            fixed_version = recommendation.get("recommendedVersion", "")

        # Remediation info from recommendation
        remediation_info = None
        if recommendation:
            rem_type = recommendation.get("remediationType", "")
            rec_version = recommendation.get("recommendedVersion", "")
            rec_product = recommendation.get("productName", "")
            parts = []
            if rem_type:
                parts.append(rem_type)
            if rec_product:
                parts.append(f"product: {rec_product}")
            if rec_version:
                parts.append(f"recommended version: {rec_version}")
            if parts:
                remediation_info = " — ".join(parts)

        # Exploit info
        exploit_available = bool(
            record.get("exploitVerified")
            or record.get("publicExploit")
        )

        # OS info
        os_name = machine.get("osPlatform", "")
        os_version = machine.get("osVersion", "")
        last_seen = machine.get("lastSeen", "")
        health_status = machine.get("healthStatus", "")

        # Machine tags for potential classification
        machine_tags = machine.get("machineTags", []) or []

        return NormalizedVulnerability(
            cve_id=cve_id,
            vulnerability_name=None,
            cvss_v3_score=cvss_v3_score,
            severity=severity,
            exploit_available=exploit_available,
            cisa_kev=False,
            source_vuln_id=str(record.get("id", "")),
            affected_product=affected_product[:300] if affected_product else None,
            affected_version=product_version[:100] if product_version else None,
            fixed_version=fixed_version[:100] if fixed_version else None,
            remediation_info=remediation_info[:2000] if remediation_info else None,
            hostname=hostname.lower().strip(),
            ip_addresses=ip_addresses,
            os_name=os_name,
            os_version=os_version,
            last_seen_at=last_seen or None,
            host_status=health_status or None,
            platform_name=os_name,
        )

    async def close(self):
        if self.client:
            await self.client.aclose()
