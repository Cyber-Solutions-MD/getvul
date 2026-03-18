"""Seed database with sample data for development."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.tenants.models import Tenant, User, UserRole, IdPProvider
from app.vulnerabilities.models import Vulnerability


SAMPLE_CVES = [
    ("CVE-2024-3094", "xz-utils", "5.6.0", "5.6.2", 10.0, "CRITICAL"),
    ("CVE-2024-21887", "Ivanti Connect Secure", "9.x", "9.1R18.3", 9.1, "CRITICAL"),
    ("CVE-2024-1709", "ConnectWise ScreenConnect", "23.9.7", "23.9.8", 10.0, "CRITICAL"),
    ("CVE-2023-44487", "HTTP/2 Rapid Reset", None, None, 7.5, "HIGH"),
    ("CVE-2024-0204", "GoAnywhere MFT", "7.4.0", "7.4.1", 9.8, "CRITICAL"),
    ("CVE-2023-46805", "Ivanti Policy Secure", "9.x", "22.6R1.2", 8.2, "HIGH"),
    ("CVE-2024-23917", "TeamCity", "2023.11.2", "2023.11.3", 9.8, "CRITICAL"),
    ("CVE-2024-27198", "TeamCity", "2023.11.3", "2023.11.4", 9.8, "CRITICAL"),
    ("CVE-2023-22527", "Confluence Server", "8.5.3", "8.5.4", 9.8, "CRITICAL"),
    ("CVE-2024-21762", "FortiOS", "7.4.2", "7.4.3", 9.6, "CRITICAL"),
    ("CVE-2023-4966", "Citrix NetScaler", "14.1-8.50", "14.1-12.35", 9.4, "CRITICAL"),
    ("CVE-2024-6387", "OpenSSH", "8.5p1", "9.8p1", 8.1, "HIGH"),
    ("CVE-2023-38545", "curl", "7.69.0", "8.4.0", 7.5, "HIGH"),
    ("CVE-2023-36884", "Microsoft Office", "2019", "patched", 7.5, "HIGH"),
    ("CVE-2024-28255", "OpenMetadata", "1.2.4", "1.3.1", 9.8, "CRITICAL"),
    ("CVE-2023-20198", "Cisco IOS XE", "16.x", "17.9.4a", 10.0, "CRITICAL"),
    ("CVE-2024-4577", "PHP CGI", "8.1.28", "8.1.29", 9.8, "CRITICAL"),
    ("CVE-2023-48788", "FortiClient EMS", "7.2.2", "7.2.3", 9.3, "CRITICAL"),
    ("CVE-2024-5806", "MOVEit Transfer", "2024.0.0", "2024.0.2", 9.1, "CRITICAL"),
    ("CVE-2023-34362", "MOVEit Transfer", "2023.0.1", "2023.0.2", 9.8, "CRITICAL"),
    ("CVE-2024-1234", "nginx", "1.25.0", "1.25.4", 6.5, "MEDIUM"),
    ("CVE-2024-2345", "PostgreSQL", "15.2", "15.6", 5.3, "MEDIUM"),
    ("CVE-2024-3456", "Redis", "7.0.0", "7.2.4", 4.3, "MEDIUM"),
    ("CVE-2024-4567", "Node.js", "20.0.0", "20.11.1", 3.1, "LOW"),
    ("CVE-2024-5678", "Python", "3.11.0", "3.11.8", 3.7, "LOW"),
    ("CVE-2024-6789", "OpenSSL", "3.0.0", "3.0.13", 5.9, "MEDIUM"),
    ("CVE-2024-7890", "Apache httpd", "2.4.58", "2.4.59", 4.0, "MEDIUM"),
    ("CVE-2024-8901", "Docker Engine", "24.0.0", "24.0.9", 6.1, "MEDIUM"),
    ("CVE-2024-9012", "Kubernetes", "1.28.0", "1.28.6", 2.5, "LOW"),
    ("CVE-2024-0123", "Git", "2.43.0", "2.43.2", 3.3, "LOW"),
]

HOSTNAMES = [
    "web-prod-01", "web-prod-02", "web-prod-03",
    "api-prod-01", "api-prod-02",
    "db-prod-01", "db-prod-02",
    "cache-prod-01",
    "worker-prod-01", "worker-prod-02",
    "ci-runner-01", "ci-runner-02",
    "monitoring-01",
    "bastion-01",
    "vpn-gateway-01",
    "mail-01",
    "dev-server-01", "dev-server-02",
    "staging-web-01", "staging-api-01",
]

SOURCES = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"]
STATUSES = ["OPEN", "OPEN", "OPEN", "OPEN", "IN_PROGRESS", "REMEDIATED", "SUPPRESSED"]
OS_OPTIONS = [
    ("Ubuntu", "22.04"), ("Ubuntu", "20.04"),
    ("Windows Server", "2022"), ("Windows Server", "2019"),
    ("Amazon Linux", "2023"), ("RHEL", "9.3"),
    ("Debian", "12"), ("CentOS", "8"),
]


async def seed_database(db: AsyncSession) -> dict:
    """Seed the database with sample vulnerability data."""

    # Check if already seeded
    result = await db.execute(select(Tenant).limit(1))
    if result.scalar_one_or_none() is not None:
        return {"message": "Database already seeded", "seeded": False}

    # Create tenant
    tenant = Tenant(
        name="Demo Organization",
        slug="demo",
        domain="demo.getvul.app",
        idp_provider="GOOGLE",
        idp_tenant_id="demo",
    )
    db.add(tenant)
    await db.flush()

    # Create demo user
    user = User(
        tenant_id=tenant.id,
        email="admin@demo.getvul.app",
        display_name="Demo Admin",
        role="OWNER",
        idp_subject="demo-subject-001",
    )
    db.add(user)
    await db.flush()

    # Create assets
    assets = []
    for hostname in HOSTNAMES:
        os_name, os_version = random.choice(OS_OPTIONS)
        asset = Asset(
            tenant_id=tenant.id,
            hostname=hostname,
            ip_addresses=[f"10.0.{random.randint(1,20)}.{random.randint(1,254)}"],
            os_name=os_name,
            os_version=os_version,
            asset_type=random.choice(["SERVER", "ENDPOINT", "VM"]),
            cloud_provider=random.choice(["AWS", "AZURE", None]),
            seen_by_sources=random.sample(SOURCES, k=random.randint(1, 3)),
            risk_score=random.randint(0, 100),
        )
        db.add(asset)
        assets.append(asset)
    await db.flush()

    # Create vulnerabilities
    vuln_count = 0
    now = datetime.now(timezone.utc)

    for _ in range(300):
        cve_data = random.choice(SAMPLE_CVES)
        cve_id, product, affected_ver, fixed_ver, cvss, severity = cve_data
        asset = random.choice(assets)
        source = random.choice(SOURCES)
        status = random.choice(STATUSES)
        days_ago = random.randint(1, 180)

        first_detected = now - timedelta(days=days_ago)
        last_seen = now - timedelta(days=random.randint(0, min(3, days_ago)))
        remediated = (now - timedelta(days=random.randint(0, days_ago // 2))) if status == "REMEDIATED" else None

        vuln = Vulnerability(
            tenant_id=tenant.id,
            cve_id=cve_id,
            vulnerability_name=f"{product} vulnerability",
            cvss_v3_score=cvss,
            severity=severity,
            exploit_available=random.random() < 0.3,
            cisa_kev=random.random() < 0.15,
            asset_id=asset.id,
            source=source,
            source_vuln_id=f"{source}-{uuid.uuid4().hex[:8]}",
            affected_product=product,
            affected_version=affected_ver,
            fixed_version=fixed_ver,
            status=status,
            first_detected_at=first_detected,
            last_seen_at=last_seen,
            remediated_at=remediated,
        )
        try:
            db.add(vuln)
            await db.flush()
            vuln_count += 1
        except Exception:
            await db.rollback()
            continue

    return {
        "message": "Database seeded",
        "seeded": True,
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "user_email": user.email,
        "assets_created": len(assets),
        "vulnerabilities_created": vuln_count,
    }
