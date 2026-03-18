"""Seed database with sample data for development."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.tenants.models import Tenant, User
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

    # Commit tenant + user + assets first so they survive vuln insert failures
    await db.commit()

    # Create vulnerabilities using savepoints for each insert
    vuln_count = 0
    skipped = 0
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
            async with db.begin_nested():
                db.add(vuln)
                await db.flush()
            vuln_count += 1
        except Exception:
            skipped += 1
            continue

    await db.commit()

    # Seed CSPM data
    cspm_count = await seed_cspm_data(db, tenant.id)

    return {
        "message": "Database seeded",
        "seeded": True,
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "user_email": user.email,
        "assets_created": len(assets),
        "vulnerabilities_created": vuln_count,
        "vulnerabilities_skipped": skipped,
        "misconfigurations_created": cspm_count,
    }


# ── CSPM Sample Data ──

SAMPLE_MISCONFIGS = [
    ("CIS-1.2.1", "S3 bucket without encryption", "ENCRYPTION", "HIGH", "aws_s3_bucket", "AWS"),
    ("CIS-1.3.5", "Public S3 bucket ACL", "STORAGE", "CRITICAL", "aws_s3_bucket", "AWS"),
    ("CIS-2.1.1", "CloudTrail not enabled", "LOGGING", "HIGH", "aws_cloudtrail", "AWS"),
    ("CIS-3.4.2", "Security group allows 0.0.0.0/0 ingress on port 22", "NETWORK", "CRITICAL", "aws_security_group", "AWS"),
    ("CIS-1.4.1", "Root account has active access keys", "IAM", "CRITICAL", "aws_iam_user", "AWS"),
    ("CIS-1.5.3", "MFA not enabled for IAM users", "IAM", "HIGH", "aws_iam_user", "AWS"),
    ("CIS-4.1.1", "EBS volumes not encrypted", "ENCRYPTION", "MEDIUM", "aws_ebs_volume", "AWS"),
    ("CIS-2.2.1", "RDS instance publicly accessible", "DATABASE", "CRITICAL", "aws_rds_instance", "AWS"),
    ("AZ-1.1.1", "Storage account allows public blob access", "STORAGE", "HIGH", "azure_storage_account", "AZURE"),
    ("AZ-2.1.3", "NSG allows inbound from any source", "NETWORK", "CRITICAL", "azure_nsg", "AZURE"),
    ("AZ-3.1.1", "Key Vault soft delete not enabled", "ENCRYPTION", "MEDIUM", "azure_key_vault", "AZURE"),
    ("AZ-4.1.2", "SQL Server auditing disabled", "DATABASE", "HIGH", "azure_sql_server", "AZURE"),
    ("GCP-1.1.1", "Default service account used", "IAM", "HIGH", "gcp_compute_instance", "GCP"),
    ("GCP-2.1.1", "Firewall rule allows 0.0.0.0/0", "NETWORK", "CRITICAL", "gcp_firewall_rule", "GCP"),
    ("WIZ-SEC-01", "Container running as root", "CONTAINER", "HIGH", "k8s_pod", "AWS"),
    ("WIZ-SEC-02", "Secret exposed in environment variable", "SECRETS", "CRITICAL", "k8s_deployment", "AWS"),
    ("CS-CSPM-101", "Unrotated access keys older than 90 days", "IAM", "MEDIUM", "aws_iam_access_key", "AWS"),
    ("CS-CSPM-202", "VPC flow logs disabled", "LOGGING", "MEDIUM", "aws_vpc", "AWS"),
    ("DEF-CLOUD-01", "VM disk encryption disabled", "ENCRYPTION", "HIGH", "azure_vm", "AZURE"),
    ("DEF-CLOUD-02", "Web app does not use HTTPS only", "NETWORK", "MEDIUM", "azure_web_app", "AZURE"),
]

CSPM_SOURCES = ["CROWDSTRIKE", "WIZ", "DEFENDER"]
CSPM_FRAMEWORKS = [
    ["CIS AWS 1.5"], ["CIS AWS 1.5", "SOC2"], ["PCI-DSS 3.2.1"],
    ["CIS Azure 2.0"], ["HIPAA"], ["SOC2", "ISO 27001"], ["NIST 800-53"],
]
CSPM_REGIONS = [
    "us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
    "eastus", "westeurope", "us-central1", "asia-east1",
]
CSPM_ACCOUNTS = [
    ("123456789012", "prod-account"), ("987654321098", "dev-account"),
    ("sub-abc-123", "Azure Prod"), ("sub-def-456", "Azure Dev"),
    ("proj-main-001", "GCP Main"),
]


async def seed_cspm_data(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Seed CSPM misconfiguration data."""
    from app.cspm.models import Misconfiguration

    count = 0
    now = datetime.now(timezone.utc)

    for _ in range(200):
        rule_id, rule_name, category, severity, res_type, cloud = random.choice(SAMPLE_MISCONFIGS)
        source = random.choice(CSPM_SOURCES)
        account = random.choice(CSPM_ACCOUNTS)
        region = random.choice(CSPM_REGIONS)
        frameworks = random.choice(CSPM_FRAMEWORKS)
        days_ago = random.randint(1, 120)
        status = random.choice(["OPEN", "OPEN", "OPEN", "REMEDIATED", "SUPPRESSED"])

        resource_id = f"arn:{cloud.lower()}:{res_type}:{region}:{account[0]}:{uuid.uuid4().hex[:8]}"

        m = Misconfiguration(
            tenant_id=tenant_id,
            rule_id=rule_id,
            rule_name=rule_name,
            category=category,
            severity=severity,
            frameworks=frameworks,
            resource_id=resource_id,
            resource_name=f"{res_type}-{uuid.uuid4().hex[:6]}",
            resource_type=res_type,
            resource_region=region,
            cloud_provider=cloud,
            cloud_account_id=account[0],
            cloud_account_name=account[1],
            source=source,
            source_finding_id=f"{source}-{uuid.uuid4().hex[:8]}",
            status=status,
            first_detected_at=now - timedelta(days=days_ago),
            last_seen_at=now - timedelta(days=random.randint(0, min(3, days_ago))),
            remediated_at=(now - timedelta(days=random.randint(0, days_ago // 2))) if status == "REMEDIATED" else None,
        )

        try:
            async with db.begin_nested():
                db.add(m)
                await db.flush()
            count += 1
        except Exception:
            continue

    await db.commit()
    return count
