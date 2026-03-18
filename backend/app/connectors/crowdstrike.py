"""CrowdStrike Falcon connector — Spotlight vulnerabilities + Configuration Assessment (CSPM)."""

from __future__ import annotations

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability

logger = structlog.get_logger()

CS_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "informational": "INFO",
    "none": "INFO",
}

CS_CSPM_CATEGORY_MAP = {
    "IAM": "IAM",
    "Network": "NETWORK",
    "Encryption": "ENCRYPTION",
    "Logging": "LOGGING",
    "Storage": "STORAGE",
    "Compute": "COMPUTE",
    "Database": "DATABASE",
    "Container": "CONTAINER",
    "Secrets": "SECRETS",
}


class CrowdStrikeConnector(BaseConnector):
    source_name = "CROWDSTRIKE"

    def __init__(self):
        self.base_url: str = "https://api.crowdstrike.com"
        self.access_token: str | None = None
        self.client: httpx.AsyncClient | None = None
        # Cache device details to avoid repeated lookups
        self._device_cache: dict[str, dict] = {}

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        self.base_url = config.get("base_url", credentials.get("base_url", self.base_url))
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30)

        try:
            resp = await self.client.post(
                "/oauth2/token",
                data={
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
            )
            if resp.status_code == 201:
                self.access_token = resp.json().get("access_token")
                logger.info("crowdstrike_auth_success")
                return True
            else:
                logger.error("crowdstrike_auth_failed", status=resp.status_code, body=resp.text[:500])
                return False
        except Exception as e:
            logger.error("crowdstrike_auth_error", error=str(e))
            return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    # ── Device resolution ──

    async def _get_device_details(self, device_id: str) -> dict:
        """Fetch device details from the Hosts API. Caches results."""
        if device_id in self._device_cache:
            return self._device_cache[device_id]

        if not device_id or not self.client:
            return {}

        try:
            resp = await self.client.get(
                "/devices/entities/devices/v2",
                headers=self._headers(),
                params={"ids": device_id},
            )
            if resp.status_code == 200:
                resources = resp.json().get("resources", [])
                if resources:
                    device = resources[0]
                    self._device_cache[device_id] = device
                    return device
        except Exception as e:
            logger.warning("crowdstrike_device_fetch_error", device_id=device_id, error=str(e))

        return {}

    # ── Vulnerability ingestion (Spotlight) ──

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Fetch vulnerabilities from CrowdStrike Spotlight.

        Uses GET /spotlight/combined/vulnerabilities/v1
        Scope required: Vulnerabilities (spotlight-vulnerabilities) — Read
        Also uses: Hosts (hosts) — Read for device details
        """
        if not self.client or not self.access_token:
            return []

        all_vulns: list[NormalizedVulnerability] = []
        after = None
        page = 0

        while True:
            params: dict = {
                "filter": "status:'open'",
                "limit": 400,
            }
            if after:
                params["after"] = after

            try:
                resp = await self.client.get(
                    "/spotlight/combined/vulnerabilities/v1",
                    headers=self._headers(),
                    params=params,
                )

                # Handle 403 (scope not granted) gracefully
                if resp.status_code == 403:
                    logger.warning("crowdstrike_spotlight_no_access", detail="Vulnerabilities scope (Read) may not be granted")
                    break
                if resp.status_code == 429:
                    logger.warning("crowdstrike_rate_limited", page=page)
                    break

                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("crowdstrike_vuln_fetch_error", page=page, error=str(e))
                break

            resources = data.get("resources", [])
            if not resources:
                break

            for item in resources:
                vuln = await self._normalize_spotlight_vuln(item)
                if vuln:
                    all_vulns.append(vuln)

            meta = data.get("meta", {}).get("pagination", {})
            after = meta.get("after")
            if not after or len(resources) < 400:
                break
            page += 1

        logger.info("crowdstrike_vulns_fetched", count=len(all_vulns))
        return all_vulns

    async def _normalize_spotlight_vuln(self, item: dict) -> NormalizedVulnerability | None:
        """Normalize a single Spotlight vulnerability resource."""
        cve = item.get("cve", {})
        cve_id = cve.get("id") if isinstance(cve, dict) else None

        # Some items have cve as a string directly
        if isinstance(cve, str):
            cve_id = cve
            cve = {}

        # Severity
        severity_raw = ""
        if isinstance(cve, dict):
            severity_raw = (cve.get("base_score_severity") or "").lower()
        severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")

        # Host info — try multiple field paths
        host_info = item.get("host_info", {}) or {}
        aid = item.get("aid") or host_info.get("aid") or ""

        hostname = host_info.get("hostname", "")
        local_ip = host_info.get("local_ip", "")
        os_version = host_info.get("os_version", "")
        platform = host_info.get("platform_name") or host_info.get("platform", "")

        # If hostname is missing, try to resolve via Hosts API using the AID
        if not hostname and aid:
            device = await self._get_device_details(aid)
            hostname = device.get("hostname", "")
            local_ip = local_ip or device.get("local_ip", "")
            os_version = os_version or device.get("os_version", "")
            platform = platform or device.get("platform_name", "")

        if not hostname:
            hostname = local_ip or aid or "unknown"

        # App info
        app = item.get("app", {}) or {}
        product = app.get("product_name_version") or app.get("product_name", "")

        # Remediation
        remediation = item.get("remediation", {}) or {}
        remediation_text = remediation.get("action", "")

        # Exploit status
        exploit_status = 0
        if isinstance(cve, dict):
            exploit_status = cve.get("exploit_status", 0)

        # CVSS score
        cvss_score = None
        if isinstance(cve, dict):
            cvss_score = cve.get("base_score")

        return NormalizedVulnerability(
            cve_id=cve_id,
            vulnerability_name=(cve.get("description", "") or "")[:500] if isinstance(cve, dict) else None,
            cvss_v3_score=cvss_score,
            severity=severity,
            exploit_available=bool(exploit_status),
            source_vuln_id=str(item.get("id", "")),
            affected_product=product[:300] if product else None,
            hostname=hostname.lower().strip(),
            ip_addresses=[local_ip] if local_ip else [],
            os_name=platform or os_version,
            os_version=os_version,
            remediation_info=remediation_text[:2000] if remediation_text else None,
        )

    # ── CSPM ingestion (Configuration Assessment) ──

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        """Fetch CSPM findings from CrowdStrike Configuration Assessment.

        Uses GET /configuration-assessment/combined/assessments/v1
        Scope required: Configuration Assessment — Read

        Falls back to CSPM Registration endpoints if Configuration Assessment is not available.
        """
        if not self.client or not self.access_token:
            return []

        # Try Configuration Assessment API first
        findings = await self._fetch_configuration_assessments()
        if findings:
            return findings

        # Fallback: try CSPM registration-based endpoints
        findings = await self._fetch_cspm_iom()
        return findings

    async def _fetch_configuration_assessments(self) -> list[NormalizedMisconfiguration]:
        """Fetch from Configuration Assessment API (requires Configuration Assessment scope)."""
        all_findings: list[NormalizedMisconfiguration] = []
        after = None
        page = 0

        while True:
            params: dict = {
                "filter": "status:'fail'",
                "limit": 500,
            }
            if after:
                params["after"] = after

            try:
                resp = await self.client.get(
                    "/configuration-assessment/combined/assessments/v1",
                    headers=self._headers(),
                    params=params,
                )

                if resp.status_code == 403:
                    logger.info("crowdstrike_config_assessment_no_access",
                                detail="Configuration Assessment scope (Read) not granted. Trying fallback.")
                    return []
                if resp.status_code == 404:
                    logger.info("crowdstrike_config_assessment_not_available")
                    return []

                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError:
                return []
            except Exception as e:
                logger.error("crowdstrike_config_assessment_error", page=page, error=str(e))
                break

            resources = data.get("resources", [])
            if not resources:
                break

            for item in resources:
                finding = self._normalize_config_assessment(item)
                if finding:
                    all_findings.append(finding)

            meta = data.get("meta", {}).get("pagination", {})
            after = meta.get("after")
            if not after or len(resources) < 500:
                break
            page += 1

        logger.info("crowdstrike_config_assessments_fetched", count=len(all_findings))
        return all_findings

    def _normalize_config_assessment(self, item: dict) -> NormalizedMisconfiguration | None:
        """Normalize a Configuration Assessment resource."""
        rule = item.get("rule", {}) or {}
        resource = item.get("resource", {}) or {}

        rule_id = rule.get("id") or item.get("rule_id") or item.get("id", "")
        rule_name = rule.get("name") or rule.get("description") or item.get("rule_name", "Unknown")
        rule_desc = rule.get("description") or rule.get("rationale", "")

        severity_raw = (rule.get("severity") or item.get("severity", "medium")).lower()
        severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")

        # Category mapping
        category_raw = rule.get("category") or item.get("category", "Other")
        category = CS_CSPM_CATEGORY_MAP.get(category_raw, "OTHER")

        # Frameworks / benchmarks
        benchmarks = rule.get("benchmarks") or item.get("benchmarks") or []
        if isinstance(benchmarks, list):
            frameworks = [b.get("name", str(b)) if isinstance(b, dict) else str(b) for b in benchmarks]
        else:
            frameworks = []

        # Cloud info
        cloud = (resource.get("cloud_provider") or item.get("cloud_provider", "")).upper()
        if cloud not in ("AWS", "AZURE", "GCP"):
            cloud = None

        resource_id = resource.get("id") or item.get("resource_id", "")
        resource_name = resource.get("name") or item.get("resource_name")
        resource_type = resource.get("type") or item.get("resource_type")
        region = resource.get("region") or item.get("region")
        account_id = resource.get("account_id") or item.get("account_id")

        return NormalizedMisconfiguration(
            rule_id=str(rule_id),
            rule_name=str(rule_name)[:500],
            rule_description=str(rule_desc)[:2000] if rule_desc else None,
            category=category,
            severity=severity,
            frameworks=frameworks,
            resource_id=str(resource_id),
            resource_name=str(resource_name)[:300] if resource_name else None,
            resource_type=str(resource_type)[:100] if resource_type else None,
            resource_region=str(region)[:50] if region else None,
            cloud_provider=cloud,
            cloud_account_id=str(account_id)[:100] if account_id else None,
            source_finding_id=str(item.get("id", "")),
            remediation_info=(rule.get("remediation") or item.get("remediation", ""))[:2000] or None,
        )

    async def _fetch_cspm_iom(self) -> list[NormalizedMisconfiguration]:
        """Fallback: Fetch from CSPM registration / IoM endpoints.

        Uses CSPM registration scope (cspm-registration) — Read
        """
        all_findings: list[NormalizedMisconfiguration] = []

        # Try multiple possible CSPM endpoints
        cspm_endpoints = [
            "/cloud-connect-cspm-aws/entities/iom/v2",
            "/detects/entities/iom/v2",
        ]

        for endpoint in cspm_endpoints:
            try:
                resp = await self.client.get(
                    endpoint,
                    headers=self._headers(),
                    params={"limit": 500, "filter": "status:'fail'"},
                )

                if resp.status_code in (403, 404):
                    continue

                resp.raise_for_status()
                data = resp.json()
                resources = data.get("resources", [])

                for item in resources:
                    severity_raw = (item.get("severity") or "medium").lower()
                    severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")
                    category_raw = item.get("policy_type") or item.get("category", "Other")
                    category = CS_CSPM_CATEGORY_MAP.get(category_raw, "OTHER")
                    cloud = (item.get("cloud_provider") or "").upper()
                    if cloud not in ("AWS", "AZURE", "GCP"):
                        cloud = None

                    finding = NormalizedMisconfiguration(
                        rule_id=str(item.get("policy_id", item.get("id", ""))),
                        rule_name=str(item.get("policy_statement", item.get("title", "Unknown")))[:500],
                        rule_description=item.get("policy_description"),
                        category=category,
                        severity=severity,
                        frameworks=item.get("benchmark", []),
                        resource_id=str(item.get("resource_id", "")),
                        resource_name=item.get("resource_name"),
                        resource_type=item.get("resource_type"),
                        resource_region=item.get("region"),
                        cloud_provider=cloud,
                        cloud_account_id=item.get("cloud_account_id"),
                        source_finding_id=str(item.get("id", "")),
                        remediation_info=item.get("remediation"),
                    )
                    all_findings.append(finding)

                if all_findings:
                    logger.info("crowdstrike_cspm_iom_fetched", endpoint=endpoint, count=len(all_findings))
                    break

            except Exception as e:
                logger.warning("crowdstrike_cspm_endpoint_error", endpoint=endpoint, error=str(e))
                continue

        if not all_findings:
            logger.info("crowdstrike_cspm_no_data",
                        detail="No CSPM data found. Ensure 'Configuration Assessment' or 'CSPM registration' scope is enabled.")

        return all_findings

    async def close(self):
        if self.client:
            await self.client.aclose()
