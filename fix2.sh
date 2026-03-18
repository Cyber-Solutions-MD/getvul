#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fixing CrowdStrike connector with correct field mapping..."

cat > backend/app/connectors/crowdstrike.py << 'FILEEOF'
"""CrowdStrike Falcon connector — Spotlight vulnerabilities + Configuration Assessment (CSPM).

Spotlight combined API response structure (EU-1, as of Mar 2026):
{
  "id": "...",
  "aid": "fd3a5886...",              ← device agent ID (no host_info!)
  "vulnerability_id": "CVE-2025-...", ← CVE ID at top level
  "status": "open",
  "apps": [                           ← array, not "app"
    {
      "product_name_version": "Safari",
      "product_name_normalized": "Safari",
      "vendor_normalized": "Apple",
      ...
    }
  ],
  "cve": {
    "id": "CVE-2025-..."              ← only has "id", NO severity/score
  },
  "confidence": "confirmed",
  "created_timestamp": "...",
  "updated_timestamp": "..."
}

Key insight: severity is NOT in the response. We must query per-severity filter.
Hostname is NOT in the response. We must resolve via Hosts API using aid.
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

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        self.base_url = config.get("base_url", credentials.get("base_url", self.base_url))
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60)

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
                logger.error("crowdstrike_auth_failed", status=resp.status_code)
                return False
        except Exception as e:
            logger.error("crowdstrike_auth_error", error=str(e))
            return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    # ── Device resolution via Hosts API ──

    async def _resolve_devices_batch(self, aids: list[str]) -> None:
        """Batch-resolve device details for multiple AIDs. Fills _device_cache."""
        uncached = [aid for aid in aids if aid and aid not in self._device_cache]
        if not uncached or not self.client:
            return

        # Hosts API accepts up to 100 IDs per call
        for i in range(0, len(uncached), 100):
            batch = uncached[i:i + 100]
            try:
                resp = await self.client.get(
                    "/devices/entities/devices/v2",
                    headers=self._headers(),
                    params=[("ids", aid) for aid in batch],
                )
                if resp.status_code == 200:
                    for device in resp.json().get("resources", []):
                        device_id = device.get("device_id", "")
                        self._device_cache[device_id] = device
                elif resp.status_code == 429:
                    logger.warning("crowdstrike_hosts_rate_limited")
                    await asyncio.sleep(2)
            except Exception as e:
                logger.warning("crowdstrike_hosts_batch_error", error=str(e))

    def _get_device(self, aid: str) -> dict:
        """Get cached device details."""
        return self._device_cache.get(aid, {})

    # ── Vulnerability ingestion (Spotlight) ──

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Fetch vulnerabilities from CrowdStrike Spotlight.

        Strategy: Query each severity level separately since the API response
        does NOT include severity — it can only be determined by the filter used.

        Scopes required:
          - Vulnerabilities (spotlight-vulnerabilities) — Read
          - Hosts (hosts) — Read
        """
        if not self.client or not self.access_token:
            return []

        all_vulns: list[NormalizedVulnerability] = []

        for severity_label, filter_str in SEVERITY_FILTERS:
            logger.info("crowdstrike_fetching_severity", severity=severity_label)
            vulns = await self._fetch_vulns_by_filter(filter_str, severity_label)
            all_vulns.extend(vulns)
            logger.info("crowdstrike_severity_fetched", severity=severity_label, count=len(vulns))

        logger.info("crowdstrike_vulns_total", count=len(all_vulns))
        return all_vulns

    async def _fetch_vulns_by_filter(
        self, filter_str: str, severity: str, max_pages: int = 50,
    ) -> list[NormalizedVulnerability]:
        """Fetch all vulns matching a filter, with pagination."""
        vulns: list[NormalizedVulnerability] = []
        after = None

        for page in range(max_pages):
            params: dict = {
                "filter": filter_str,
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

                if resp.status_code == 403:
                    logger.warning("crowdstrike_spotlight_no_access")
                    break
                if resp.status_code == 429:
                    logger.warning("crowdstrike_rate_limited", page=page)
                    await asyncio.sleep(5)
                    continue

                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("crowdstrike_vuln_fetch_error", page=page, error=str(e))
                break

            resources = data.get("resources") or []
            if not resources:
                break

            # Batch resolve hostnames for all AIDs in this page
            aids = list({item.get("aid", "") for item in resources if item.get("aid")})
            await self._resolve_devices_batch(aids)

            for item in resources:
                vuln = self._normalize_vuln(item, severity)
                if vuln:
                    vulns.append(vuln)

            meta = data.get("meta", {}).get("pagination", {})
            after = meta.get("after")
            if not after or len(resources) < 400:
                break

        return vulns

    def _normalize_vuln(self, item: dict, severity: str) -> NormalizedVulnerability | None:
        """Normalize a Spotlight vulnerability resource."""

        # CVE ID: top-level vulnerability_id or cve.id
        cve_id = item.get("vulnerability_id")
        if not cve_id:
            cve_obj = item.get("cve", {})
            cve_id = cve_obj.get("id") if isinstance(cve_obj, dict) else None

        # Device info via Hosts API
        aid = item.get("aid", "")
        device = self._get_device(aid)
        hostname = device.get("hostname", "")
        local_ip = device.get("local_ip", "")
        os_version = device.get("os_version", "")
        platform = device.get("platform_name", "")

        if not hostname:
            hostname = local_ip or aid[:12] or "unknown"

        # App info: apps is an ARRAY
        apps = item.get("apps") or []
        product = ""
        vendor = ""
        if apps and isinstance(apps, list):
            first_app = apps[0]
            product = first_app.get("product_name_version", "") or first_app.get("product_name_normalized", "")
            vendor = first_app.get("vendor_normalized", "")
            if vendor and product and vendor.lower() not in product.lower():
                product = f"{vendor} {product}"

        # Remediation info from apps
        remediation_text = ""
        if apps and isinstance(apps, list):
            rem = apps[0].get("remediation", {})
            if isinstance(rem, dict):
                remediation_text = rem.get("action", "")

        # Exploit status — check suppression_info and confidence
        exploit_available = False  # Not directly available in this response format

        return NormalizedVulnerability(
            cve_id=cve_id,
            vulnerability_name=None,
            cvss_v3_score=None,  # Not in Spotlight combined response
            severity=severity,   # From our per-severity query
            exploit_available=exploit_available,
            source_vuln_id=str(item.get("id", "")),
            affected_product=product[:300] if product else None,
            hostname=hostname.lower().strip(),
            ip_addresses=[local_ip] if local_ip else [],
            os_name=platform,
            os_version=os_version,
            remediation_info=remediation_text[:2000] if remediation_text else None,
        )

    # ── CSPM ingestion (Configuration Assessment) ──

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        """Fetch CSPM findings.

        Tries Configuration Assessment API first, then CSPM registration fallback.
        Scope required: Configuration Assessment — Read
        """
        if not self.client or not self.access_token:
            return []

        findings = await self._fetch_configuration_assessments()
        if findings:
            return findings

        findings = await self._fetch_cspm_fallback()
        return findings

    async def _fetch_configuration_assessments(self) -> list[NormalizedMisconfiguration]:
        """Configuration Assessment API — requires 'Configuration Assessment' scope."""
        all_findings: list[NormalizedMisconfiguration] = []
        after = None

        for page in range(50):
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
                    logger.info("crowdstrike_config_assessment_403",
                                detail="Add 'Configuration Assessment — Read' scope to your API client")
                    return []
                if resp.status_code == 404:
                    logger.info("crowdstrike_config_assessment_404")
                    return []
                if resp.status_code == 429:
                    await asyncio.sleep(5)
                    continue

                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError:
                return []
            except Exception as e:
                logger.error("crowdstrike_config_assessment_error", error=str(e))
                break

            resources = data.get("resources") or []
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

        logger.info("crowdstrike_config_assessments_fetched", count=len(all_findings))
        return all_findings

    def _normalize_config_assessment(self, item: dict) -> NormalizedMisconfiguration | None:
        rule = item.get("rule", {}) or {}
        resource = item.get("resource", {}) or {}

        rule_id = str(rule.get("id") or item.get("rule_id") or item.get("id", ""))
        rule_name = str(rule.get("name") or rule.get("description") or item.get("title", "Unknown"))[:500]

        severity_raw = (rule.get("severity") or item.get("severity", "medium")).lower()
        severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")

        category_raw = rule.get("category") or item.get("category", "Other")
        category = CS_CSPM_CATEGORY_MAP.get(category_raw, "OTHER")

        benchmarks = rule.get("benchmarks") or item.get("benchmarks") or []
        frameworks = []
        if isinstance(benchmarks, list):
            for b in benchmarks:
                frameworks.append(b.get("name", str(b)) if isinstance(b, dict) else str(b))

        cloud = (resource.get("cloud_provider") or item.get("cloud_provider", "")).upper()
        if cloud not in ("AWS", "AZURE", "GCP"):
            cloud = None

        return NormalizedMisconfiguration(
            rule_id=rule_id,
            rule_name=rule_name,
            rule_description=str(rule.get("description") or rule.get("rationale", ""))[:2000] or None,
            category=category,
            severity=severity,
            frameworks=frameworks,
            resource_id=str(resource.get("id") or item.get("resource_id", "")),
            resource_name=str(resource.get("name") or item.get("resource_name", ""))[:300] or None,
            resource_type=str(resource.get("type") or item.get("resource_type", ""))[:100] or None,
            resource_region=str(resource.get("region") or item.get("region", ""))[:50] or None,
            cloud_provider=cloud,
            cloud_account_id=str(resource.get("account_id") or item.get("account_id", ""))[:100] or None,
            source_finding_id=str(item.get("id", "")),
            remediation_info=str(rule.get("remediation") or item.get("remediation", ""))[:2000] or None,
        )

    async def _fetch_cspm_fallback(self) -> list[NormalizedMisconfiguration]:
        """Fallback CSPM endpoints if Configuration Assessment is not available."""
        endpoints = [
            "/cloud-connect-cspm-aws/entities/iom/v2",
            "/detects/entities/iom/v2",
        ]

        for endpoint in endpoints:
            try:
                resp = await self.client.get(
                    endpoint,
                    headers=self._headers(),
                    params={"limit": 500},
                )
                if resp.status_code not in (200, 207):
                    continue

                resources = resp.json().get("resources") or []
                if not resources:
                    continue

                findings = []
                for item in resources:
                    severity_raw = (item.get("severity") or "medium").lower()
                    severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")
                    category_raw = item.get("policy_type") or "Other"
                    category = CS_CSPM_CATEGORY_MAP.get(category_raw, "OTHER")
                    cloud = (item.get("cloud_provider") or "").upper()
                    if cloud not in ("AWS", "AZURE", "GCP"):
                        cloud = None

                    findings.append(NormalizedMisconfiguration(
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
                    ))

                if findings:
                    logger.info("crowdstrike_cspm_fallback_fetched", endpoint=endpoint, count=len(findings))
                    return findings

            except Exception as e:
                logger.warning("crowdstrike_cspm_fallback_error", endpoint=endpoint, error=str(e))

        logger.info("crowdstrike_cspm_no_data",
                     detail="Add 'Configuration Assessment — Read' scope in Falcon Console")
        return []

    async def close(self):
        if self.client:
            await self.client.aclose()
FILEEOF

echo "🧹 Clearing old data and re-syncing with correct mapping..."

# Restart to pick up new code
docker compose up -d --force-recreate backend
sleep 10

# Clear old incorrectly-mapped data
curl -s -X POST http://localhost:8000/dev/clear-test-data \
  -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "Cleared"

echo ""
echo "⏳ Triggering fresh sync (this may take a few minutes for 45k+ vulns)..."

# Get connector ID
CONNECTOR_ID=$(curl -s "http://localhost:8000/api/v1/connectors" \
  -H "Authorization: Bearer dev-token" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for c in data:
    if c['connector_type'] == 'CROWDSTRIKE':
        print(c['id'])
        break
" 2>/dev/null || echo "")

if [ -n "$CONNECTOR_ID" ]; then
    echo "Connector ID: $CONNECTOR_ID"
    curl -s -X POST "http://localhost:8000/api/v1/connectors/${CONNECTOR_ID}/sync" \
      -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "Sync triggered"
    
    echo ""
    echo "⏳ Sync is running in the background. Checking progress every 30s..."
    
    for i in $(seq 1 20); do
        sleep 30
        STATUS=$(curl -s "http://localhost:8000/api/v1/connectors/${CONNECTOR_ID}/sync-status" \
          -H "Authorization: Bearer dev-token" 2>/dev/null)
        IS_RUNNING=$(echo "$STATUS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('is_running', False))" 2>/dev/null || echo "unknown")
        
        if [ "$IS_RUNNING" = "False" ] || [ "$IS_RUNNING" = "false" ]; then
            echo "✅ Sync complete!"
            echo "$STATUS" | python3 -m json.tool 2>/dev/null
            break
        else
            echo "   Still syncing... (check $i)"
        fi
    done
else
    echo "⚠️ No CrowdStrike connector found. Sync manually from the UI."
fi

echo ""
echo "🔍 Checking results..."
echo "Vuln stats:"
curl -s "http://localhost:8000/api/v1/vulnerabilities/stats" \
  -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null

echo ""
echo "CSPM stats:"
curl -s "http://localhost:8000/api/v1/cspm/stats" \
  -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null

echo ""
echo "Sample vulns (first 5):"
curl -s "http://localhost:8000/api/v1/vulnerabilities?page_size=5" \
  -H "Authorization: Bearer dev-token" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for v in data.get('items', []):
    print(f\"  {v['severity']:10s} {v.get('cve_id', 'N/A'):20s} {v.get('asset_hostname', 'unknown'):30s} {v.get('affected_product', '')}\")
" 2>/dev/null || echo "Failed"

echo ""
echo "📝 Commit when ready:"
echo "   git add -A && git commit -m 'fix: CrowdStrike severity per-filter query + hostname via Hosts API' && git push"
echo ""
echo "⚠️  CSPM: If still 0 findings, add 'Configuration Assessment — Read' scope"
echo "   in Falcon Console → API Clients and Keys → Edit your client"
