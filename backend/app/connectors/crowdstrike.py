"""CrowdStrike Falcon connector — Spotlight vulns + remediations + exploit/KEV enrichment.

Spotlight combined API fields used:
  - vulnerability_id: CVE ID
  - aid: device agent ID → resolved via Hosts API
  - apps[]: product info + remediation IDs
  - cve.id: CVE ID fallback

Severity: determined by per-severity filtered queries (not in response).
Exploit status: fetched from /spotlight/entities/vulnerabilities/v2
CISA KEV: derived from exploit_status >= 30 or separate KEV enrichment.
Remediation: resolved from apps[].remediation.ids via /spotlight/entities/remediations/v2
"""

from __future__ import annotations

import asyncio
import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability

logger = structlog.get_logger()

SEVERITY_FILTERS = [
    ("CRITICAL", "status:'open'+cve.severity:'CRITICAL'"),
    ("HIGH", "status:'open'+cve.severity:'HIGH'"),
    ("MEDIUM", "status:'open'+cve.severity:'MEDIUM'"),
    ("LOW", "status:'open'+cve.severity:'LOW'"),
]

# CrowdStrike exploit_status codes:
#   0 = Unknown, 10 = Unproven, 20 = Proof of Concept,
#   30 = Functional, 40 = Used in Malware, 50 = Used in the Wild (CISA KEV level)
EXPLOIT_STATUS_NAMES = {
    0: "Unknown",
    10: "Unproven",
    20: "Proof of Concept",
    30: "Functional",
    40: "Used in Malware",
    50: "Used in the Wild",
}

CS_CSPM_CATEGORY_MAP = {
    "IAM": "IAM", "Network": "NETWORK", "Encryption": "ENCRYPTION",
    "Logging": "LOGGING", "Storage": "STORAGE", "Compute": "COMPUTE",
    "Database": "DATABASE", "Container": "CONTAINER", "Secrets": "SECRETS",
}

CS_SEVERITY_MAP = {
    "critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM",
    "low": "LOW", "informational": "INFO", "none": "INFO",
}


class CrowdStrikeConnector(BaseConnector):
    source_name = "CROWDSTRIKE"

    def __init__(self):
        self.base_url: str = "https://api.crowdstrike.com"
        self.access_token: str | None = None
        self.client: httpx.AsyncClient | None = None
        self._device_cache: dict[str, dict] = {}
        self._remediation_cache: dict[str, str] = {}
        self._vuln_metadata_cache: dict[str, dict] = {}
        self._eval_logic_cache: dict[str, list[str]] = {}  # eval_id -> [filepaths]

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        self.base_url = config.get("base_url", credentials.get("base_url", self.base_url))
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60)
        try:
            resp = await self.client.post("/oauth2/token", data={
                "client_id": credentials["client_id"],
                "client_secret": credentials["client_secret"],
            })
            if resp.status_code == 201:
                self.access_token = resp.json().get("access_token")
                logger.info("crowdstrike_auth_success")
                return True
            logger.error("crowdstrike_auth_failed", status=resp.status_code)
            return False
        except Exception as e:
            logger.error("crowdstrike_auth_error", error=str(e))
            return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    # ── Device resolution ──

    async def _resolve_devices_batch(self, aids: list[str]) -> None:
        uncached = [a for a in aids if a and a not in self._device_cache]
        if not uncached or not self.client:
            return
        for i in range(0, len(uncached), 100):
            batch = uncached[i:i + 100]
            try:
                resp = await self.client.get(
                    "/devices/entities/devices/v2",
                    headers=self._headers(),
                    params=[("ids", aid) for aid in batch],
                )
                if resp.status_code == 200:
                    for dev in resp.json().get("resources", []):
                        self._device_cache[dev.get("device_id", "")] = dev
                elif resp.status_code == 429:
                    await asyncio.sleep(3)
            except Exception as e:
                logger.warning("crowdstrike_hosts_error", error=str(e))

    # ── Remediation resolution ──

    async def _resolve_remediations_batch(self, remediation_ids: list[str]) -> None:
        """Fetch remediation actions from /spotlight/entities/remediations/v2"""
        uncached = [r for r in remediation_ids if r and r not in self._remediation_cache]
        if not uncached or not self.client:
            return
        for i in range(0, len(uncached), 100):
            batch = uncached[i:i + 100]
            try:
                resp = await self.client.get(
                    "/spotlight/entities/remediations/v2",
                    headers=self._headers(),
                    params=[("ids", rid) for rid in batch],
                )
                if resp.status_code == 200:
                    for rem in resp.json().get("resources", []):
                        rid = rem.get("id", "")
                        action = rem.get("action", "") or rem.get("reference", {}).get("title", "")
                        self._remediation_cache[rid] = action
                elif resp.status_code == 403:
                    logger.info("crowdstrike_remediations_no_access")
                    return
                elif resp.status_code == 429:
                    await asyncio.sleep(3)
            except Exception as e:
                logger.warning("crowdstrike_remediations_error", error=str(e))

    # ── Vulnerability metadata (exploit status) ──

    async def _resolve_vuln_metadata_batch(self, vuln_ids: list[str]) -> None:
        """Fetch exploit status from /spotlight/entities/vulnerabilities/v2"""
        uncached = [v for v in vuln_ids if v and v not in self._vuln_metadata_cache]
        if not uncached or not self.client:
            return
        for i in range(0, len(uncached), 100):
            batch = uncached[i:i + 100]
            try:
                resp = await self.client.get(
                    "/spotlight/entities/vulnerabilities/v2",
                    headers=self._headers(),
                    params=[("ids", vid) for vid in batch],
                )
                if resp.status_code == 200:
                    for vuln in resp.json().get("resources", []):
                        vid = vuln.get("id", "")
                        self._vuln_metadata_cache[vid] = vuln
                elif resp.status_code == 403:
                    logger.info("crowdstrike_vuln_entities_no_access")
                    return
                elif resp.status_code == 429:
                    await asyncio.sleep(3)
            except Exception as e:
                logger.warning("crowdstrike_vuln_metadata_error", error=str(e))

    # ── Evaluation logic (file paths) ──

    async def _resolve_eval_logic_batch(self, eval_ids: list[str]) -> None:
        """Fetch file paths from /spotlight/entities/evaluation-logic/v1"""
        uncached = [e for e in eval_ids if e and e not in self._eval_logic_cache]
        if not uncached or not self.client:
            return
        for i in range(0, len(uncached), 50):
            batch = uncached[i:i + 50]
            try:
                resp = await self.client.get(
                    "/spotlight/entities/evaluation-logic/v1",
                    headers=self._headers(),
                    params=[("ids", eid) for eid in batch],
                )
                if resp.status_code == 200:
                    for el in resp.json().get("resources", []):
                        eid = el.get("id", "")
                        paths = []
                        for logic in el.get("logic", []):
                            for item in logic.get("items", []):
                                fp = item.get("filepath", "")
                                if fp and fp not in paths:
                                    paths.append(fp)
                        self._eval_logic_cache[eid] = paths
                elif resp.status_code in (403, 404):
                    logger.info("crowdstrike_eval_logic_no_access")
                    return
                elif resp.status_code == 429:
                    await asyncio.sleep(3)
            except Exception as e:
                logger.warning("crowdstrike_eval_logic_error", error=str(e))

    # ── Vulnerability fetching ──

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        if not self.client or not self.access_token:
            return []

        all_vulns: list[NormalizedVulnerability] = []
        for severity_label, filter_str in SEVERITY_FILTERS:
            logger.info("crowdstrike_fetching_severity", severity=severity_label)
            vulns = await self._fetch_vulns_by_filter(filter_str, severity_label)
            all_vulns.extend(vulns)
            logger.info("crowdstrike_severity_done", severity=severity_label, count=len(vulns))

        logger.info("crowdstrike_vulns_total", count=len(all_vulns))
        return all_vulns

    async def _fetch_vulns_by_filter(self, filter_str: str, severity: str) -> list[NormalizedVulnerability]:
        vulns: list[NormalizedVulnerability] = []
        after = None

        for page in range(100):
            params: dict = {"filter": filter_str, "limit": 400}
            if after:
                params["after"] = after

            try:
                resp = await self.client.get(
                    "/spotlight/combined/vulnerabilities/v1",
                    headers=self._headers(), params=params,
                )
                if resp.status_code == 403:
                    break
                if resp.status_code == 429:
                    await asyncio.sleep(5)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("crowdstrike_vuln_page_error", page=page, error=str(e))
                break

            resources = data.get("resources") or []
            if not resources:
                break

            # Batch resolve: devices, remediations, vuln metadata
            aids = list({it.get("aid", "") for it in resources if it.get("aid")})
            await self._resolve_devices_batch(aids)

            rem_ids = set()
            vuln_meta_ids = []
            for it in resources:
                for app in (it.get("apps") or []):
                    for rid in (app.get("remediation", {}) or {}).get("ids", []):
                        rem_ids.add(rid)
                vuln_meta_ids.append(it.get("id", ""))

            await self._resolve_remediations_batch(list(rem_ids))
            await self._resolve_vuln_metadata_batch(vuln_meta_ids)

            # Batch resolve evaluation logic for file paths
            eval_ids = set()
            for it in resources:
                for app in (it.get("apps") or []):
                    el = app.get("evaluation_logic", {})
                    if isinstance(el, dict) and el.get("id"):
                        eval_ids.add(el["id"])
            await self._resolve_eval_logic_batch(list(eval_ids))

            for item in resources:
                v = self._normalize_vuln(item, severity)
                if v:
                    vulns.append(v)

            meta = data.get("meta", {}).get("pagination", {})
            after = meta.get("after")
            if not after or len(resources) < 400:
                break

        return vulns

    def _normalize_vuln(self, item: dict, severity: str) -> NormalizedVulnerability | None:
        # CVE
        cve_id = item.get("vulnerability_id")
        if not cve_id:
            cve_obj = item.get("cve", {})
            cve_id = cve_obj.get("id") if isinstance(cve_obj, dict) else None

        # Device
        aid = item.get("aid", "")
        device = self._device_cache.get(aid, {})
        hostname = device.get("hostname", "")
        local_ip = device.get("local_ip", "")
        os_version = device.get("os_version", "")
        platform = device.get("platform_name", "")
        product_type_desc = device.get("product_type_desc", "")
        serial_number = device.get("serial_number", "")
        mac_address = device.get("mac_address", "")
        external_ip = device.get("external_ip", "")
        last_login_user = device.get("last_login_user", "")
        last_login_at = device.get("last_login_timestamp", "")
        last_seen = device.get("last_seen", "")
        host_status = device.get("status", "")
        system_manufacturer = device.get("system_manufacturer", "")
        system_product_name = device.get("system_product_name", "")
        if not hostname:
            hostname = local_ip or aid[:12] or "unknown"

        # App + remediation
        apps = item.get("apps") or []
        product = ""
        vendor = ""
        remediation_id = ""
        remediation_action = ""

        if apps and isinstance(apps, list):
            first_app = apps[0]
            product = first_app.get("product_name_version", "") or first_app.get("product_name_normalized", "")
            vendor = first_app.get("vendor_normalized", "")
            if vendor and product and vendor.lower() not in product.lower():
                product = f"{vendor} {product}"

            # Remediation
            rem_info = first_app.get("remediation", {}) or {}
            rem_ids = rem_info.get("ids", [])
            if rem_ids:
                remediation_id = rem_ids[0]
                remediation_action = self._remediation_cache.get(remediation_id, "")

            # Also check remediation_info for recommended
            rem_info2 = first_app.get("remediation_info", {}) or {}
            if not remediation_id and rem_info2.get("recommended_id"):
                remediation_id = rem_info2["recommended_id"]
                remediation_action = self._remediation_cache.get(remediation_id, "")

        # Exploit status from vuln metadata
        vuln_id = item.get("id", "")
        meta = self._vuln_metadata_cache.get(vuln_id, {})
        exploit_status_id = 0
        cisa_kev = False

        if meta:
            cve_meta = meta.get("cve", {})
            if isinstance(cve_meta, dict):
                exploit_status_id = cve_meta.get("exploit_status", 0) or 0
                # CISA KEV: exploit_status 50 = "Used in the Wild" (CISA KEV level)
                # Also check for explicit CISA KEV flag
                cisa_kev = exploit_status_id >= 50 or bool(cve_meta.get("cisa_kev", False))

        exploit_available = exploit_status_id >= 20  # PoC or higher
        exploit_status_name = EXPLOIT_STATUS_NAMES.get(exploit_status_id, "Unknown")

        # File paths from evaluation logic
        file_paths = None
        if apps and isinstance(apps, list):
            el = apps[0].get("evaluation_logic", {})
            if isinstance(el, dict) and el.get("id"):
                file_paths = self._eval_logic_cache.get(el["id"])

        vuln = NormalizedVulnerability(
            cve_id=cve_id,
            vulnerability_name=None,
            cvss_v3_score=None,
            severity=severity,
            exploit_available=exploit_available,
            cisa_kev=cisa_kev,
            source_vuln_id=str(vuln_id),
            affected_product=product[:300] if product else None,
            hostname=hostname.lower().strip(),
            ip_addresses=[local_ip] if local_ip else [],
            os_name=platform,
            os_version=os_version,
            remediation_info=remediation_action[:2000] if remediation_action else None,
            platform_name=platform,
            product_type_desc=product_type_desc,
            serial_number=serial_number or None,
            mac_address=mac_address or None,
            external_ip=external_ip or None,
            last_login_user=last_login_user or None,
            last_login_at=last_login_at or None,
            last_seen_at=last_seen or None,
            host_status=host_status or None,
            system_manufacturer=system_manufacturer or None,
            system_product_name=system_product_name or None,
            crowdstrike_aid=aid or None,
            file_paths=file_paths,
        )
        # Attach extra fields via ad-hoc attributes
        vuln.remediation_id = remediation_id
        vuln.remediation_action = remediation_action
        vuln.exploit_status_id = exploit_status_id
        vuln.exploit_status_name = exploit_status_name
        return vuln

    # ── CSPM ──

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        if not self.client or not self.access_token:
            return []
        findings = await self._fetch_config_assessments()
        if not findings:
            findings = await self._fetch_cspm_fallback()
        return findings

    async def _fetch_config_assessments(self) -> list[NormalizedMisconfiguration]:
        all_f: list[NormalizedMisconfiguration] = []
        after = None
        for _ in range(50):
            params: dict = {"filter": "status:'fail'", "limit": 500}
            if after:
                params["after"] = after
            try:
                resp = await self.client.get("/configuration-assessment/combined/assessments/v1",
                                              headers=self._headers(), params=params)
                if resp.status_code in (403, 404):
                    return []
                if resp.status_code == 429:
                    await asyncio.sleep(5); continue
                resp.raise_for_status()
                data = resp.json()
            except:
                break
            resources = data.get("resources") or []
            if not resources:
                break
            for it in resources:
                r = it.get("rule", {}) or {}
                res = it.get("resource", {}) or {}
                sev = CS_SEVERITY_MAP.get((r.get("severity") or "medium").lower(), "MEDIUM")
                cat = CS_CSPM_CATEGORY_MAP.get(r.get("category", "Other"), "OTHER")
                cloud = (res.get("cloud_provider") or "").upper()
                if cloud not in ("AWS", "AZURE", "GCP"): cloud = None
                all_f.append(NormalizedMisconfiguration(
                    rule_id=str(r.get("id", it.get("id", ""))),
                    rule_name=str(r.get("name", "Unknown"))[:500],
                    rule_description=str(r.get("description", ""))[:2000] or None,
                    category=cat, severity=sev,
                    frameworks=[b.get("name", str(b)) if isinstance(b, dict) else str(b) for b in (r.get("benchmarks") or [])],
                    resource_id=str(res.get("id", "")), resource_name=str(res.get("name", ""))[:300] or None,
                    resource_type=str(res.get("type", ""))[:100] or None,
                    resource_region=str(res.get("region", ""))[:50] or None,
                    cloud_provider=cloud, cloud_account_id=str(res.get("account_id", ""))[:100] or None,
                    source_finding_id=str(it.get("id", "")),
                    remediation_info=str(r.get("remediation", ""))[:2000] or None,
                ))
            meta = data.get("meta", {}).get("pagination", {})
            after = meta.get("after")
            if not after or len(resources) < 500: break
        logger.info("crowdstrike_cspm_fetched", count=len(all_f))
        return all_f

    async def _fetch_cspm_fallback(self) -> list[NormalizedMisconfiguration]:
        return []

    async def close(self):
        if self.client:
            await self.client.aclose()
