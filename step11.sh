#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "💊 Adding remediation views + exploit/KEV enrichment..."

git checkout main 2>/dev/null && git pull 2>/dev/null || true
git checkout -b feat/remediation-views 2>/dev/null || git checkout feat/remediation-views

# ══════════════════════════════════════════════
#  DB: Migration — add remediation + exploit fields
# ══════════════════════════════════════════════

cat > backend/alembic/versions/004_add_remediation_fields.py << 'FILEEOF'
"""004 - Add remediation_id, exploit_status_id, cisa_kev fields.

Revision ID: 004_add_remediation_fields
Revises: 003_widen_credentials_column
"""

from alembic import op
import sqlalchemy as sa

revision = "004_add_remediation_fields"
down_revision = "003_widen_credentials_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vulnerabilities", sa.Column("remediation_id", sa.String(200)))
    op.add_column("vulnerabilities", sa.Column("remediation_action", sa.Text))
    op.add_column("vulnerabilities", sa.Column("exploit_status_id", sa.Integer))
    op.add_column("vulnerabilities", sa.Column("exploit_status_name", sa.String(100)))
    op.create_index("idx_vuln_remediation_id", "vulnerabilities", ["remediation_id"])
    op.create_index("idx_vuln_exploit_available", "vulnerabilities", ["tenant_id", "exploit_available"])
    op.create_index("idx_vuln_cisa_kev", "vulnerabilities", ["tenant_id", "cisa_kev"])


def downgrade() -> None:
    op.drop_index("idx_vuln_cisa_kev", table_name="vulnerabilities")
    op.drop_index("idx_vuln_exploit_available", table_name="vulnerabilities")
    op.drop_index("idx_vuln_remediation_id", table_name="vulnerabilities")
    op.drop_column("vulnerabilities", "exploit_status_name")
    op.drop_column("vulnerabilities", "exploit_status_id")
    op.drop_column("vulnerabilities", "remediation_action")
    op.drop_column("vulnerabilities", "remediation_id")
FILEEOF

# ══════════════════════════════════════════════
#  Model: Add new fields to Vulnerability
# ══════════════════════════════════════════════

# Add columns to the model
python3 << 'PYEOF'
content = open("backend/app/vulnerabilities/models.py").read()

# Add new fields before remediation_info
old = '    remediation_info: Mapped[str | None] = mapped_column(Text)'
new = '''    remediation_id: Mapped[str | None] = mapped_column(String(200), index=True)
    remediation_action: Mapped[str | None] = mapped_column(Text)
    exploit_status_id: Mapped[int | None] = mapped_column(Integer)
    exploit_status_name: Mapped[str | None] = mapped_column(String(100))
    remediation_info: Mapped[str | None] = mapped_column(Text)'''

content = content.replace(old, new)

# Make sure Integer is imported
if "Integer," not in content.split("from sqlalchemy import")[1].split("\n")[0]:
    content = content.replace(
        "from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint",
        "from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint"
    )

open("backend/app/vulnerabilities/models.py", "w").write(content)
print("Updated vulnerability model")
PYEOF

# ══════════════════════════════════════════════
#  CrowdStrike connector: fetch remediation + exploit data
# ══════════════════════════════════════════════

cat > backend/app/connectors/crowdstrike.py << 'FILEEOF'
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
FILEEOF

# ══════════════════════════════════════════════
#  Sync: persist new fields
# ══════════════════════════════════════════════

cat > backend/app/connectors/sync.py << 'FILEEOF'
"""Sync orchestrator — runs connectors and persists normalized data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability
from app.connectors.crowdstrike import CrowdStrikeConnector
from app.connectors.service import get_decrypted_credentials
from app.cspm.models import Misconfiguration
from app.ticketing.models import ConnectorConfig, SyncLog
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

CONNECTOR_CLASSES: dict[str, type[BaseConnector]] = {
    "CROWDSTRIKE": CrowdStrikeConnector,
}


async def run_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    now = datetime.now(timezone.utc)
    log = SyncLog(connector_id=connector_config.id, tenant_id=connector_config.tenant_id, status="RUNNING", started_at=now)
    db.add(log)
    await db.flush()

    connector_cls = CONNECTOR_CLASSES.get(connector_config.connector_type)
    if not connector_cls:
        log.status = "FAILED"
        log.error_message = f"Unknown connector: {connector_config.connector_type}"
        log.finished_at = datetime.now(timezone.utc)
        return log

    connector = connector_cls()
    credentials = get_decrypted_credentials(connector_config)

    try:
        authed = await connector.authenticate(credentials, connector_config.config or {})
        if not authed:
            log.status = "FAILED"
            log.error_message = "Authentication failed"
            log.finished_at = datetime.now(timezone.utc)
            return log

        vulns = await connector.fetch_vulnerabilities()
        vc, vu = 0, 0
        for v in vulns:
            asset = await _upsert_asset(db, connector_config.tenant_id, v, connector_config.connector_type)
            created = await _upsert_vulnerability(db, connector_config.tenant_id, v, asset.id, connector_config.connector_type)
            if created: vc += 1
            else: vu += 1

        misconfigs = await connector.fetch_misconfigurations()
        mc = 0
        for m in misconfigs:
            if await _upsert_misconfiguration(db, connector_config.tenant_id, m, connector_config.connector_type):
                mc += 1

        log.status = "SUCCESS"
        log.records_fetched = len(vulns) + len(misconfigs)
        log.records_created = vc + mc
        log.records_updated = vu
        log.details = {"vulns_fetched": len(vulns), "vulns_created": vc, "vulns_updated": vu,
                       "misconfigs_fetched": len(misconfigs), "misconfigs_created": mc}
        connector_config.last_sync_at = datetime.now(timezone.utc)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = log.records_fetched

    except Exception as e:
        logger.error("sync_error", error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(timezone.utc)
        if hasattr(connector, "close"):
            await connector.close()

    return log


async def _upsert_asset(db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability, source: str) -> Asset:
    hostname = (v.hostname or "unknown").lower().strip()
    result = await db.execute(select(Asset).where(Asset.tenant_id == tenant_id, Asset.hostname == hostname))
    asset = result.scalar_one_or_none()
    if asset is None:
        asset = Asset(tenant_id=tenant_id, hostname=hostname, ip_addresses=v.ip_addresses,
                      os_name=v.os_name, os_version=v.os_version, asset_type=v.asset_type,
                      seen_by_sources=[source])
        db.add(asset)
        await db.flush()
    else:
        sources = asset.seen_by_sources or []
        if source not in sources:
            asset.seen_by_sources = sources + [source]
    return asset


async def _upsert_vulnerability(db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability,
                                 asset_id: uuid.UUID, source: str) -> bool:
    now = datetime.now(timezone.utc)
    result = await db.execute(select(Vulnerability).where(
        Vulnerability.tenant_id == tenant_id, Vulnerability.cve_id == v.cve_id,
        Vulnerability.asset_id == asset_id, Vulnerability.source == source,
    ))
    existing = result.scalar_one_or_none()

    if existing:
        existing.last_seen_at = now
        existing.severity = v.severity
        existing.exploit_available = v.exploit_available
        existing.cisa_kev = v.cisa_kev
        existing.remediation_id = getattr(v, "remediation_id", None)
        existing.remediation_action = getattr(v, "remediation_action", None) or v.remediation_info
        existing.exploit_status_id = getattr(v, "exploit_status_id", None)
        existing.exploit_status_name = getattr(v, "exploit_status_name", None)
        return False
    else:
        vuln = Vulnerability(
            tenant_id=tenant_id, cve_id=v.cve_id, vulnerability_name=v.vulnerability_name,
            cvss_v3_score=v.cvss_v3_score, severity=v.severity,
            exploit_available=v.exploit_available, cisa_kev=v.cisa_kev,
            asset_id=asset_id, source=source, source_vuln_id=v.source_vuln_id,
            affected_product=v.affected_product, affected_version=v.affected_version,
            fixed_version=v.fixed_version,
            remediation_id=getattr(v, "remediation_id", None),
            remediation_action=getattr(v, "remediation_action", None) or v.remediation_info,
            remediation_info=v.remediation_info,
            exploit_status_id=getattr(v, "exploit_status_id", None),
            exploit_status_name=getattr(v, "exploit_status_name", None),
            status="OPEN", first_detected_at=now, last_seen_at=now,
        )
        db.add(vuln)
        await db.flush()
        return True


async def _upsert_misconfiguration(db: AsyncSession, tenant_id: uuid.UUID, m: NormalizedMisconfiguration, source: str) -> bool:
    now = datetime.now(timezone.utc)
    result = await db.execute(select(Misconfiguration).where(
        Misconfiguration.tenant_id == tenant_id, Misconfiguration.rule_id == m.rule_id,
        Misconfiguration.resource_id == m.resource_id, Misconfiguration.source == source,
    ))
    existing = result.scalar_one_or_none()
    if existing:
        existing.last_seen_at = now
        existing.severity = m.severity
        return False
    else:
        mc = Misconfiguration(
            tenant_id=tenant_id, rule_id=m.rule_id, rule_name=m.rule_name,
            rule_description=m.rule_description, category=m.category, severity=m.severity,
            frameworks=m.frameworks, resource_id=m.resource_id, resource_name=m.resource_name,
            resource_type=m.resource_type, resource_region=m.resource_region,
            cloud_provider=m.cloud_provider, cloud_account_id=m.cloud_account_id,
            cloud_account_name=m.cloud_account_name, source=source,
            source_finding_id=m.source_finding_id, remediation_info=m.remediation_info,
            remediation_url=m.remediation_url, status="OPEN",
            first_detected_at=now, last_seen_at=now, details=m.details,
        )
        db.add(mc)
        await db.flush()
        return True
FILEEOF

# ══════════════════════════════════════════════
#  Backend: Remediation + host grouping endpoints
# ══════════════════════════════════════════════

cat > backend/app/vulnerabilities/remediation_service.py << 'FILEEOF'
"""Remediation-centric queries: group by remediation, group by host."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


async def get_remediations_grouped(
    db: AsyncSession, tenant_id: uuid.UUID,
    severity: list[str] | None = None,
    exploit_only: bool = False,
    kev_only: bool = False,
    search: str | None = None,
    page: int = 1, page_size: int = 25,
) -> dict:
    """Group open vulns by remediation_id — shows each unique remediation and how many hosts are affected."""

    base = select(
        Vulnerability.remediation_id,
        Vulnerability.remediation_action,
        Vulnerability.affected_product,
        func.count(func.distinct(Vulnerability.asset_id)).label("affected_hosts"),
        func.count(Vulnerability.id).label("vuln_count"),
        func.max(case(
            (Vulnerability.severity == "CRITICAL", 4),
            (Vulnerability.severity == "HIGH", 3),
            (Vulnerability.severity == "MEDIUM", 2),
            (Vulnerability.severity == "LOW", 1),
            else_=0,
        )).label("max_severity_rank"),
    ).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status == "OPEN",
        Vulnerability.remediation_id.isnot(None),
        Vulnerability.remediation_id != "",
    ).group_by(
        Vulnerability.remediation_id,
        Vulnerability.remediation_action,
        Vulnerability.affected_product,
    )

    if severity:
        base = base.where(Vulnerability.severity.in_(severity))
    if exploit_only:
        base = base.where(Vulnerability.exploit_available.is_(True))
    if kev_only:
        base = base.where(Vulnerability.cisa_kev.is_(True))
    if search:
        base = base.having(
            func.coalesce(Vulnerability.remediation_action, "").ilike(f"%{search}%") |
            func.coalesce(Vulnerability.affected_product, "").ilike(f"%{search}%")
        )

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Data
    data_q = base.order_by(
        func.max(case(
            (Vulnerability.severity == "CRITICAL", 4),
            (Vulnerability.severity == "HIGH", 3),
            (Vulnerability.severity == "MEDIUM", 2),
            else_=1,
        )).desc(),
        func.count(func.distinct(Vulnerability.asset_id)).desc(),
    ).offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(data_q)).all()

    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "INFO"}

    items = []
    for row in rows:
        items.append({
            "remediation_id": row.remediation_id,
            "remediation_action": row.remediation_action,
            "affected_product": row.affected_product,
            "affected_hosts": row.affected_hosts,
            "vuln_count": row.vuln_count,
            "max_severity": sev_map.get(row.max_severity_rank, "MEDIUM"),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


async def get_hosts_for_remediation(
    db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str,
) -> list[dict]:
    """Get all hosts affected by a specific remediation."""
    q = (
        select(
            Asset.id, Asset.hostname, Asset.os_name, Asset.os_version,
            Vulnerability.cve_id, Vulnerability.severity,
            Vulnerability.exploit_available, Vulnerability.cisa_kev,
            Vulnerability.exploit_status_name,
        )
        .join(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.remediation_id == remediation_id,
            Vulnerability.status == "OPEN",
        )
        .order_by(Asset.hostname)
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "asset_id": str(r.id), "hostname": r.hostname,
            "os_name": r.os_name, "os_version": r.os_version,
            "cve_id": r.cve_id, "severity": r.severity,
            "exploit_available": r.exploit_available, "cisa_kev": r.cisa_kev,
            "exploit_status": r.exploit_status_name,
        }
        for r in rows
    ]


async def get_remediations_for_host(
    db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID,
) -> list[dict]:
    """Get all remediations needed for a specific host."""
    q = (
        select(
            Vulnerability.remediation_id,
            Vulnerability.remediation_action,
            Vulnerability.cve_id,
            Vulnerability.severity,
            Vulnerability.affected_product,
            Vulnerability.exploit_available,
            Vulnerability.cisa_kev,
            Vulnerability.exploit_status_name,
            Vulnerability.exploit_status_id,
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.asset_id == asset_id,
            Vulnerability.status == "OPEN",
            Vulnerability.remediation_id.isnot(None),
        )
        .order_by(
            case(
                (Vulnerability.severity == "CRITICAL", 1),
                (Vulnerability.severity == "HIGH", 2),
                (Vulnerability.severity == "MEDIUM", 3),
                else_=4,
            ),
            Vulnerability.cve_id,
        )
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "remediation_id": r.remediation_id,
            "remediation_action": r.remediation_action,
            "cve_id": r.cve_id, "severity": r.severity,
            "affected_product": r.affected_product,
            "exploit_available": r.exploit_available, "cisa_kev": r.cisa_kev,
            "exploit_status": r.exploit_status_name,
            "exploit_status_id": r.exploit_status_id,
        }
        for r in rows
    ]
FILEEOF

# Add remediation routes to vuln router
cat >> backend/app/vulnerabilities/router.py << 'FILEEOF'


# ── Remediation views ──

@router.get("/remediations/grouped")
async def remediations_grouped(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    severity: list[str] | None = Query(None),
    exploit_only: bool = Query(False),
    kev_only: bool = Query(False),
    search: str | None = Query(None),
):
    """List remediations grouped — each row is a unique remediation with affected host count."""
    from app.vulnerabilities.remediation_service import get_remediations_grouped
    return await get_remediations_grouped(
        db, user.tenant_id, severity=severity, exploit_only=exploit_only,
        kev_only=kev_only, search=search, page=page, page_size=page_size,
    )


@router.get("/remediations/{remediation_id}/hosts")
async def hosts_for_remediation(
    remediation_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get all hosts affected by a specific remediation."""
    from app.vulnerabilities.remediation_service import get_hosts_for_remediation
    return await get_hosts_for_remediation(db, user.tenant_id, remediation_id)


@router.get("/hosts/{asset_id}/remediations")
async def remediations_for_host(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get all remediations needed for a specific host."""
    from app.vulnerabilities.remediation_service import get_remediations_for_host
    return await get_remediations_for_host(db, user.tenant_id, asset_id)
FILEEOF

# ══════════════════════════════════════════════
#  Update vuln schemas to include new fields
# ══════════════════════════════════════════════

python3 << 'PYEOF'
content = open("backend/app/vulnerabilities/schemas.py").read()

# Add fields to VulnerabilitySummary
old = '''    first_detected_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class VulnerabilityFilter'''

new = '''    exploit_status_name: str | None = None
    remediation_id: str | None = None
    remediation_action: str | None = None
    first_detected_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class VulnerabilityFilter'''

content = content.replace(old, new)

# Add to VulnerabilityResponse too
old2 = '''    remediation_info: str | None
    status: str'''
new2 = '''    remediation_id: str | None = None
    remediation_action: str | None = None
    exploit_status_id: int | None = None
    exploit_status_name: str | None = None
    remediation_info: str | None
    status: str'''
content = content.replace(old2, new2)

open("backend/app/vulnerabilities/schemas.py", "w").write(content)
print("Updated vuln schemas")
PYEOF

# ══════════════════════════════════════════════
#  FRONTEND: Remediation tab in vulnerability page
# ══════════════════════════════════════════════

mkdir -p frontend/src/app/dashboard/vulnerabilities

cat > frontend/src/app/dashboard/vulnerabilities/page.tsx << 'FILEEOF'
"use client";

import { useCallback, useEffect, useState } from "react";
import { Bug, RefreshCw, Loader2, Pill, Monitor } from "lucide-react";
import { api } from "@/lib/api";
import VulnFilters, { type VulnFilterState } from "@/components/vulnerabilities/VulnFilters";
import VulnTable from "@/components/vulnerabilities/VulnTable";
import BulkActions from "@/components/vulnerabilities/BulkActions";
import Pagination from "@/components/ui/Pagination";
import { SeverityBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface PaginatedVulns {
  items: VulnerabilitySummary[];
  total: number; page: number; page_size: number; total_pages: number;
}

interface RemediationGrouped {
  remediation_id: string; remediation_action: string | null;
  affected_product: string | null; affected_hosts: number;
  vuln_count: number; max_severity: string;
}

interface PaginatedRemediations {
  items: RemediationGrouped[];
  total: number; page: number; page_size: number; total_pages: number;
}

interface HostForRemediation {
  asset_id: string; hostname: string; os_name: string | null;
  os_version: string | null; cve_id: string | null; severity: string;
  exploit_available: boolean; cisa_kev: boolean; exploit_status: string | null;
}

interface RemediationForHost {
  remediation_id: string; remediation_action: string | null;
  cve_id: string | null; severity: string; affected_product: string | null;
  exploit_available: boolean; cisa_kev: boolean;
  exploit_status: string | null; exploit_status_id: number | null;
}

const DEFAULT_FILTERS: VulnFilterState = {
  search: "", severity: [], source: [], status: [],
  exploit_available: null, cisa_kev: null,
};

type Tab = "vulnerabilities" | "remediations";

export default function VulnerabilitiesPage() {
  const [tab, setTab] = useState<Tab>("vulnerabilities");
  const [vulnData, setVulnData] = useState<PaginatedVulns | null>(null);
  const [remData, setRemData] = useState<PaginatedRemediations | null>(null);
  const [filters, setFilters] = useState<VulnFilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Drill-down states
  const [selectedRemediation, setSelectedRemediation] = useState<RemediationGrouped | null>(null);
  const [remHosts, setRemHosts] = useState<HostForRemediation[] | null>(null);
  const [selectedHostId, setSelectedHostId] = useState<string | null>(null);
  const [selectedHostName, setSelectedHostName] = useState<string>("");
  const [hostRemediations, setHostRemediations] = useState<RemediationForHost[] | null>(null);

  const fetchVulns = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      p.set("page", String(page)); p.set("page_size", "25");
      if (filters.search) p.set("search", filters.search);
      filters.severity.forEach((s) => p.append("severity", s));
      filters.source.forEach((s) => p.append("source", s));
      filters.status.forEach((s) => p.append("status", s));
      if (filters.exploit_available !== null) p.set("exploit_available", String(filters.exploit_available));
      if (filters.cisa_kev !== null) p.set("cisa_kev", String(filters.cisa_kev));
      setVulnData(await api<PaginatedVulns>(`/api/v1/vulnerabilities?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, filters]);

  const fetchRemediations = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      p.set("page", String(page)); p.set("page_size", "25");
      if (filters.search) p.set("search", filters.search);
      filters.severity.forEach((s) => p.append("severity", s));
      if (filters.exploit_available === true) p.set("exploit_only", "true");
      if (filters.cisa_kev === true) p.set("kev_only", "true");
      setRemData(await api<PaginatedRemediations>(`/api/v1/vulnerabilities/remediations/grouped?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, filters]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (tab === "vulnerabilities") fetchVulns();
      else fetchRemediations();
    }, 300);
    return () => clearTimeout(t);
  }, [tab, fetchVulns, fetchRemediations]);

  useEffect(() => { setPage(1); setSelectedIds(new Set()); }, [filters, tab]);

  async function drillRemediation(rem: RemediationGrouped) {
    setSelectedRemediation(rem);
    try {
      const hosts = await api<HostForRemediation[]>(`/api/v1/vulnerabilities/remediations/${encodeURIComponent(rem.remediation_id)}/hosts`);
      setRemHosts(hosts);
    } catch (e) { console.error(e); }
  }

  async function drillHost(assetId: string, hostname: string) {
    setSelectedHostId(assetId); setSelectedHostName(hostname);
    try {
      const rems = await api<RemediationForHost[]>(`/api/v1/vulnerabilities/hosts/${assetId}/remediations`);
      setHostRemediations(rems);
    } catch (e) { console.error(e); }
  }

  const data = tab === "vulnerabilities" ? vulnData : remData;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bug className="h-6 w-6 text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Vulnerabilities</h1>
            {data && <p className="text-sm text-gray-400">{data.total.toLocaleString()} {tab === "vulnerabilities" ? "vulnerabilities" : "remediations"}</p>}
          </div>
        </div>
        <button onClick={() => tab === "vulnerabilities" ? fetchVulns() : fetchRemediations()} disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-900 p-1 w-fit">
        <button onClick={() => { setTab("vulnerabilities"); setSelectedRemediation(null); setSelectedHostId(null); }}
          className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
            tab === "vulnerabilities" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white")}>
          <Bug className="h-4 w-4" />Vulnerabilities
        </button>
        <button onClick={() => { setTab("remediations"); setSelectedRemediation(null); setSelectedHostId(null); }}
          className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
            tab === "remediations" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white")}>
          <Pill className="h-4 w-4" />Remediations
        </button>
      </div>

      <VulnFilters filters={filters} onChange={setFilters} />

      {selectedIds.size > 0 && (
        <BulkActions selectedCount={selectedIds.size} selectedIds={Array.from(selectedIds)}
          onComplete={() => { setSelectedIds(new Set()); fetchVulns(); }} />
      )}

      {loading && !data ? (
        <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : tab === "vulnerabilities" ? (
        <>
          <VulnTable vulnerabilities={vulnData?.items || []} selectedIds={selectedIds}
            onSelectToggle={(id) => setSelectedIds(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; })}
            onSelectAll={(ids) => setSelectedIds(ids.length ? new Set(ids) : new Set())}
            onHostClick={(assetId, hostname) => { setTab("remediations"); drillHost(assetId, hostname); }} />
          {vulnData && vulnData.total_pages > 1 && (
            <Pagination page={vulnData.page} totalPages={vulnData.total_pages} total={vulnData.total} pageSize={vulnData.page_size} onPageChange={setPage} />
          )}
        </>
      ) : selectedRemediation && remHosts ? (
        /* Drill-down: hosts affected by a remediation */
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <button onClick={() => { setSelectedRemediation(null); setRemHosts(null); }} className="text-xs text-indigo-400 hover:text-indigo-300">← Back to remediations</button>
              <h2 className="mt-1 text-lg font-medium text-white">{selectedRemediation.remediation_action || "Unknown remediation"}</h2>
              <p className="text-sm text-gray-400">{selectedRemediation.affected_product} · {remHosts.length} affected hosts</p>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Hostname</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">CVE</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Exploit Status</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">CISA KEV</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">OS</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {remHosts.map((h, i) => (
                  <tr key={i} className="hover:bg-gray-800/30 cursor-pointer" onClick={() => drillHost(h.asset_id, h.hostname)}>
                    <td className="px-3 py-2.5 text-white">{h.hostname}</td>
                    <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{h.cve_id}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={h.severity} /></td>
                    <td className="px-3 py-2.5"><ExploitBadge status={h.exploit_status} available={h.exploit_available} /></td>
                    <td className="px-3 py-2.5">{h.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600">—</span>}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400">{h.os_name} {h.os_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : selectedHostId && hostRemediations ? (
        /* Drill-down: remediations needed for a host */
        <div className="space-y-4">
          <div>
            <button onClick={() => { setSelectedHostId(null); setHostRemediations(null); }} className="text-xs text-indigo-400 hover:text-indigo-300">← Back</button>
            <h2 className="mt-1 text-lg font-medium text-white flex items-center gap-2"><Monitor className="h-5 w-5 text-gray-400" />{selectedHostName}</h2>
            <p className="text-sm text-gray-400">{hostRemediations.length} remediations needed</p>
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">CVE</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Exploit</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">KEV</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {hostRemediations.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-800/30">
                    <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{r.cve_id}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={r.severity} /></td>
                    <td className="px-3 py-2.5 text-xs text-gray-400 max-w-[150px] truncate">{r.affected_product}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-300 max-w-[300px] truncate">{r.remediation_action || "—"}</td>
                    <td className="px-3 py-2.5"><ExploitBadge status={r.exploit_status} available={r.exploit_available} /></td>
                    <td className="px-3 py-2.5">{r.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Remediations grouped table */
        <>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Max Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Affected Hosts</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Vuln Count</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {(remData?.items || []).map((rem) => (
                  <tr key={rem.remediation_id} className="hover:bg-gray-800/30 cursor-pointer" onClick={() => drillRemediation(rem)}>
                    <td className="px-3 py-2.5 text-white max-w-[400px] truncate">{rem.remediation_action || rem.remediation_id}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400 max-w-[200px] truncate">{rem.affected_product}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={rem.max_severity} /></td>
                    <td className="px-3 py-2.5 text-white font-medium">{rem.affected_hosts}</td>
                    <td className="px-3 py-2.5 text-gray-400">{rem.vuln_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {remData?.items.length === 0 && <div className="py-12 text-center text-gray-500">No remediations found</div>}
          </div>
          {remData && remData.total_pages > 1 && (
            <Pagination page={remData.page} totalPages={remData.total_pages} total={remData.total} pageSize={remData.page_size} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}

function ExploitBadge({ status, available }: { status: string | null; available: boolean }) {
  if (!available && !status) return <span className="text-gray-600 text-xs">—</span>;
  const color = status === "Used in the Wild" ? "text-red-400" :
                status === "Used in Malware" ? "text-red-400" :
                status === "Functional" ? "text-orange-400" :
                status === "Proof of Concept" ? "text-yellow-400" : "text-gray-400";
  return <span className={cn("text-xs font-medium", color)}>🔥 {status || (available ? "Yes" : "No")}</span>;
}
FILEEOF

# Update VulnTable to add exploit/KEV columns and host click
cat > frontend/src/components/vulnerabilities/VulnTable.tsx << 'FILEEOF'
"use client";

import { Flame, ShieldAlert } from "lucide-react";
import { SeverityBadge, StatusBadge, SourceBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface Props {
  vulnerabilities: VulnerabilitySummary[];
  selectedIds: Set<string>;
  onSelectToggle: (id: string) => void;
  onSelectAll: (ids: string[]) => void;
  onHostClick?: (assetId: string, hostname: string) => void;
}

export default function VulnTable({ vulnerabilities, selectedIds, onSelectToggle, onSelectAll, onHostClick }: Props) {
  const allSelected = vulnerabilities.length > 0 && vulnerabilities.every((v) => selectedIds.has(v.id));

  return (
    <div className="overflow-hidden rounded-xl border border-gray-800">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-gray-800 bg-gray-900/70">
          <th className="w-10 px-3 py-3">
            <input type="checkbox" checked={allSelected}
              onChange={() => allSelected ? onSelectAll([]) : onSelectAll(vulnerabilities.map((v) => v.id))}
              className="rounded border-gray-600 bg-gray-800 text-indigo-600" />
          </th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">CVE</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Source</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Status</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Host</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Exploit</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">KEV</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
        </tr></thead>
        <tbody className="divide-y divide-gray-800/50">
          {vulnerabilities.map((v) => (
            <tr key={v.id} className={cn("transition-colors hover:bg-gray-800/30", selectedIds.has(v.id) && "bg-indigo-500/5")}>
              <td className="px-3 py-2.5">
                <input type="checkbox" checked={selectedIds.has(v.id)} onChange={() => onSelectToggle(v.id)}
                  className="rounded border-gray-600 bg-gray-800 text-indigo-600" />
              </td>
              <td className="px-3 py-2.5 font-mono text-sm text-white">{v.cve_id || "N/A"}</td>
              <td className="px-3 py-2.5"><SeverityBadge severity={v.severity} /></td>
              <td className="px-3 py-2.5"><SourceBadge source={v.source} /></td>
              <td className="px-3 py-2.5"><StatusBadge status={v.status} /></td>
              <td className="px-3 py-2.5">
                {v.asset_hostname && v.asset_id && onHostClick ? (
                  <button onClick={() => onHostClick(v.asset_id!, v.asset_hostname!)}
                    className="text-indigo-400 hover:text-indigo-300 text-sm hover:underline">
                    {v.asset_hostname}
                  </button>
                ) : <span className="text-gray-400">{v.asset_hostname || "—"}</span>}
              </td>
              <td className="max-w-[150px] truncate px-3 py-2.5 text-gray-400 text-xs">{v.affected_product || "—"}</td>
              <td className="px-3 py-2.5">
                {v.exploit_available ? (
                  <span className="flex items-center gap-1 text-xs font-medium text-orange-400">
                    <Flame className="h-3.5 w-3.5" />{v.exploit_status_name || "Yes"}
                  </span>
                ) : <span className="text-gray-600 text-xs">—</span>}
              </td>
              <td className="px-3 py-2.5">
                {v.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600 text-xs">—</span>}
              </td>
              <td className="max-w-[200px] truncate px-3 py-2.5 text-xs text-gray-400">{v.remediation_action || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {vulnerabilities.length === 0 && <div className="py-12 text-center text-gray-500">No vulnerabilities found</div>}
    </div>
  );
}
FILEEOF

# Update frontend types
cat > frontend/src/types/vulnerability.ts << 'FILEEOF'
export interface VulnerabilitySummary {
  id: string;
  cve_id: string | null;
  severity: string;
  source: string;
  status: string;
  exploit_available: boolean;
  cisa_kev: boolean;
  exploit_status_name: string | null;
  remediation_id: string | null;
  remediation_action: string | null;
  affected_product: string | null;
  asset_id: string | null;
  asset_hostname: string | null;
  first_detected_at: string;
  last_seen_at: string;
}

export interface DashboardStats {
  total_vulnerabilities: number;
  open_vulnerabilities: number;
  by_severity: { severity: string; count: number }[];
  by_source: { source: string; count: number }[];
  exploitable_count: number;
  cisa_kev_count: number;
  correlated_cves: number;
  mttr_days: number | null;
}
FILEEOF

# ══════════════════════════════════════════════
#  RUN MIGRATION + RESTART
# ══════════════════════════════════════════════

echo "🔄 Running migration + restarting..."
docker compose exec -T backend alembic upgrade head 2>/dev/null || {
    echo "Migration may need rebuild..."
    docker compose up -d --force-recreate backend
    sleep 15
    docker compose exec -T backend alembic upgrade head
}

docker compose up -d --force-recreate backend frontend
sleep 15

echo "🧹 Clearing old data for clean re-sync..."
curl -s -X POST http://localhost:8000/dev/clear-test-data -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "Cleared"

echo ""
echo "⏳ Triggering fresh sync with remediation + exploit enrichment..."
CONNECTOR_ID=$(curl -s "http://localhost:8000/api/v1/connectors" -H "Authorization: Bearer dev-token" | python3 -c "
import json, sys
for c in json.load(sys.stdin):
    if c['connector_type'] == 'CROWDSTRIKE':
        print(c['id']); break
" 2>/dev/null || echo "")

if [ -n "$CONNECTOR_ID" ]; then
    curl -s -X POST "http://localhost:8000/api/v1/connectors/${CONNECTOR_ID}/sync" -H "Authorization: Bearer dev-token"
    echo ""
    echo "   Sync started in background. This will take a few minutes for 45k+ vulns."
    echo "   The connector now fetches:"
    echo "     - Remediations via /spotlight/entities/remediations/v2"
    echo "     - Exploit status via /spotlight/entities/vulnerabilities/v2"
    echo "     - CISA KEV from exploit_status >= 50"
fi

# ══════════════════════════════════════════════
#  COMMIT
# ══════════════════════════════════════════════

echo ""
echo "📝 Committing..."
git add -A
git commit -m "feat: remediation views + exploit/KEV enrichment from CrowdStrike

Backend:
- New fields: remediation_id, remediation_action, exploit_status_id/name
- CrowdStrike: fetch remediations via /spotlight/entities/remediations/v2
- CrowdStrike: fetch exploit status via /spotlight/entities/vulnerabilities/v2
- CISA KEV: derived from exploit_status >= 50 (Used in the Wild)
- Exploit levels: Unknown → Unproven → PoC → Functional → Malware → Wild
- API: GET /remediations/grouped — group by remediation, show affected host count
- API: GET /remediations/{id}/hosts — hosts affected by a remediation
- API: GET /hosts/{id}/remediations — all remediations needed for a host

Frontend:
- Vulnerabilities page: Vulnerabilities + Remediations tabs
- Vuln table: exploit status, CISA KEV, remediation columns
- Remediations tab: grouped by remediation action, click to see affected hosts
- Host drill-down: click hostname to see all remediations needed
- Exploit badge: color-coded by severity (PoC → Functional → Wild)
- Bidirectional navigation: remediation → hosts → host remediations"

git push -u origin feat/remediation-views

gh pr create \
  --title "feat: remediation views + exploit/KEV enrichment" \
  --body "## New Features

### Remediation-Centric View
- **Remediations tab**: Group vulns by remediation action, showing affected host count
- **Drill into remediation**: Click to see all hosts that need it
- **Drill into host**: Click hostname to see all remediations needed for that host
- Bidirectional: remediation → hosts ↔ host → remediations

### Exploit & CISA KEV Enrichment
- Exploit status from CrowdStrike: Unknown → Unproven → PoC → Functional → Malware → Wild
- CISA KEV flag from exploit_status >= 50
- Color-coded exploit badges in the table
- Filter by exploitable and CISA KEV

### CrowdStrike API Endpoints Used
- \`/spotlight/entities/remediations/v2\` — remediation actions
- \`/spotlight/entities/vulnerabilities/v2\` — exploit status metadata
- Batch resolves (100 per call) for performance" \
  --base main

echo ""
echo "✅ Done! PR created."
echo "   Dashboard: http://localhost:3000/dashboard/vulnerabilities"
echo "   Switch to 'Remediations' tab to see grouped view"
echo ""
echo "   Sync is running in background — check back in a few minutes."
echo "   To merge: gh pr merge --squash && git checkout main && git pull"
