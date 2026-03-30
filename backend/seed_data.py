"""Seed data script — populates the default tenant with realistic demo data.

Usage:
    docker compose exec -T backend python3 /app/seed_data.py
"""

import asyncio
import hashlib
import json
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db.session import async_session_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)


def make_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:32]


def rand_past(days_back: int = 90) -> datetime:
    return NOW - timedelta(days=random.randint(1, days_back), hours=random.randint(0, 23))


def rand_recent(days_back: int = 7) -> datetime:
    return NOW - timedelta(days=random.randint(0, days_back), hours=random.randint(0, 23))


def jl(obj: list | dict) -> str:
    """JSON literal for SQL."""
    return json.dumps(obj)


# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------

WORKSTATIONS = [
    ("WS-MBP-JCHEN", "10.1.1.101", "macOS", "14.5", "Apple Inc.", "MacBook Pro 16-inch", "C02G1234HKJY", "jchen", "JAMF", ["CROWDSTRIKE", "JAMF"]),
    ("WS-MBP-SLEE", "10.1.1.102", "macOS", "14.4.1", "Apple Inc.", "MacBook Pro 14-inch", "C02G5678HKJY", "slee", "JAMF", ["CROWDSTRIKE", "JAMF"]),
    ("WS-MBP-AMARTIN", "10.1.1.103", "macOS", "14.3", "Apple Inc.", "MacBook Air M2", "C02G9012HKJY", "amartin", "JAMF", ["CROWDSTRIKE", "JAMF"]),
    ("WS-WIN-DKIM", "10.1.2.101", "Windows", "11 23H2", "Dell Inc.", "Latitude 5540", "JKFL234KDF", "dkim", None, ["CROWDSTRIKE", "DEFENDER"]),
    ("WS-WIN-RPATEL", "10.1.2.102", "Windows", "11 23H2", "Lenovo", "ThinkPad X1 Carbon Gen 11", "PF4A2BCD", "rpatel", None, ["CROWDSTRIKE", "DEFENDER"]),
    ("WS-WIN-MWILSON", "10.1.2.103", "Windows", "10 22H2", "HP", "EliteBook 840 G10", "5CD3456789", "mwilson", None, ["DEFENDER"]),
    ("WS-MBP-LJONES", "10.1.1.104", "macOS", "14.5", "Apple Inc.", "MacBook Pro 16-inch", "C02H3456HKJY", "ljones", "JAMF", ["CROWDSTRIKE", "JAMF"]),
    ("WS-WIN-NGARCIA", "10.1.2.104", "Windows", "11 23H2", "Dell Inc.", "XPS 15 9530", "GHTK567LMN", "ngarcia", None, ["CROWDSTRIKE", "DEFENDER"]),
    ("WS-MBP-TWANG", "10.1.1.105", "macOS", "14.2", "Apple Inc.", "MacBook Air M3", "C02J7890HKJY", "twang", "JAMF", ["CROWDSTRIKE", "JAMF"]),
    ("WS-WIN-BTHOMPSON", "10.1.2.105", "Windows", "11 23H2", "Lenovo", "ThinkPad T14s Gen 4", "PF5C3DEF", "bthompson", None, ["CROWDSTRIKE", "DEFENDER"]),
]

SERVERS = [
    ("SRV-WEB-01", "10.2.1.10", "Ubuntu", "22.04.4 LTS", "Dell Inc.", "PowerEdge R750", "SVR-DL-001", ["CROWDSTRIKE", "NESSUS"]),
    ("SRV-WEB-02", "10.2.1.11", "Ubuntu", "22.04.4 LTS", "Dell Inc.", "PowerEdge R750", "SVR-DL-002", ["CROWDSTRIKE", "NESSUS"]),
    ("SRV-DB-01", "10.2.2.10", "Red Hat Enterprise Linux", "9.3", "HP", "ProLiant DL380 Gen10", "SVR-HP-001", ["CROWDSTRIKE", "NESSUS"]),
    ("SRV-APP-01", "10.2.3.10", "Ubuntu", "24.04 LTS", "Dell Inc.", "PowerEdge R660", "SVR-DL-003", ["CROWDSTRIKE", "NESSUS"]),
    ("SRV-CI-01", "10.2.4.10", "Ubuntu", "22.04.4 LTS", "Supermicro", "SYS-1029P-WTR", "SVR-SM-001", ["NESSUS"]),
    ("SRV-WIN-DC01", "10.2.5.10", "Windows Server", "2022", "Dell Inc.", "PowerEdge R750", "SVR-DL-004", ["CROWDSTRIKE", "DEFENDER"]),
    ("SRV-WIN-FS01", "10.2.5.11", "Windows Server", "2019", "HP", "ProLiant DL360 Gen10", "SVR-HP-002", ["CROWDSTRIKE", "DEFENDER"]),
    ("SRV-K8S-NODE01", "10.2.6.10", "Ubuntu", "22.04.4 LTS", "Dell Inc.", "PowerEdge R660", "SVR-DL-005", ["CROWDSTRIKE", "NESSUS"]),
]

NETWORK_DEVICES = [
    ("FW-EDGE-01", "10.0.0.1", "Palo Alto PAN-OS", "11.1.2", "Palo Alto Networks", "PA-3260", "PA-SN-001", ["NESSUS"]),
    ("FW-CORE-01", "10.0.0.2", "FortiOS", "7.4.3", "Fortinet", "FortiGate 600E", "FG-SN-001", ["NESSUS"]),
    ("SW-CORE-01", "10.0.1.1", "Cisco IOS XE", "17.12.3", "Cisco", "Catalyst 9300", "CSC-SN-001", ["NESSUS"]),
    ("SW-ACCESS-01", "10.0.1.2", "Cisco IOS", "15.9(3)M7", "Cisco", "Catalyst 2960X", "CSC-SN-002", ["NESSUS"]),
]

CLOUD_RESOURCES = [
    ("aws-ec2-prod-api", "172.31.10.50", "Amazon Linux", "2023.4", "AWS", "t3.xlarge", "i-0a1b2c3d4e5f67890", ["CROWDSTRIKE", "WIZ"]),
    ("azure-vm-staging", "10.10.0.4", "Windows Server", "2022", "Microsoft", "Standard_D4s_v3", "az-vm-001", ["DEFENDER", "WIZ"]),
    ("gcp-instance-data", "10.128.0.5", "Debian", "12", "Google", "e2-standard-4", "gcp-inst-001", ["WIZ"]),
]

# Real CVEs with details: (cve_id, name, severity, cvss, affected_product, remediation, exploit_available, cisa_kev)
HIGH_PROFILE_CVES = [
    ("CVE-2024-3094", "XZ Utils Backdoor", "CRITICAL", 10.0, "xz-utils", "Downgrade xz-utils to version 5.4.x or upgrade to 5.6.2+", True, True),
    ("CVE-2024-21762", "FortiOS Out-of-Bound Write", "CRITICAL", 9.8, "FortiOS", "Upgrade FortiOS to 7.4.3, 7.2.7, or 7.0.14", True, True),
    ("CVE-2023-44487", "HTTP/2 Rapid Reset DDoS", "HIGH", 7.5, "nginx", "Update nginx to 1.25.3+ or apply HTTP/2 rate limiting", True, True),
    ("CVE-2024-1709", "ScreenConnect Authentication Bypass", "CRITICAL", 10.0, "ConnectWise ScreenConnect", "Upgrade ScreenConnect to 23.9.8+", True, True),
    ("CVE-2023-4966", "Citrix Bleed - NetScaler Information Disclosure", "CRITICAL", 9.4, "Citrix NetScaler ADC", "Apply Citrix firmware update CTX579459", True, True),
    ("CVE-2024-23897", "Jenkins CLI Arbitrary File Read", "HIGH", 8.8, "Jenkins", "Upgrade Jenkins to 2.442+ or LTS 2.426.3+", True, False),
    ("CVE-2023-22518", "Confluence Data Center Authentication Bypass", "CRITICAL", 9.8, "Atlassian Confluence", "Upgrade Confluence to 8.3.4, 8.4.4, 8.5.3, or 8.6.1", True, True),
    ("CVE-2024-0012", "PAN-OS Management Interface Authentication Bypass", "CRITICAL", 9.8, "PAN-OS", "Apply PAN-OS hotfix or restrict management interface access", True, True),
    ("CVE-2023-46747", "F5 BIG-IP Configuration Utility Authentication Bypass", "CRITICAL", 9.8, "F5 BIG-IP", "Apply F5 hotfix or restrict access to Configuration utility", True, True),
    ("CVE-2024-27198", "TeamCity Authentication Bypass", "CRITICAL", 9.8, "JetBrains TeamCity", "Upgrade TeamCity to 2023.11.4+", True, False),
    ("CVE-2023-34362", "MOVEit Transfer SQL Injection", "CRITICAL", 9.8, "Progress MOVEit Transfer", "Apply MOVEit Transfer patches and rotate credentials", True, True),
    ("CVE-2024-6387", "OpenSSH regreSSHion Race Condition", "HIGH", 8.1, "OpenSSH", "Upgrade OpenSSH to 9.8p1+ or set LoginGraceTime to 0", True, False),
    ("CVE-2024-4577", "PHP CGI Argument Injection", "CRITICAL", 9.8, "PHP", "Upgrade PHP to 8.3.8+, 8.2.20+, or 8.1.29+", True, True),
    ("CVE-2023-20198", "Cisco IOS XE Web UI Privilege Escalation", "CRITICAL", 10.0, "Cisco IOS XE", "Disable HTTP server feature or restrict access; apply Cisco patch", True, True),
    ("CVE-2024-21887", "Ivanti Connect Secure Command Injection", "CRITICAL", 9.1, "Ivanti Connect Secure", "Apply Ivanti patches or use XML mitigation", True, True),
]

COMMON_CVES = [
    ("CVE-2024-7971", "Chrome V8 Type Confusion", "HIGH", 8.8, "Google Chrome", "Update Chrome to 128.0.6613.84+", False, False),
    ("CVE-2024-9680", "Firefox Use-After-Free in Animation", "HIGH", 8.8, "Mozilla Firefox", "Update Firefox to 131.0.2+", True, False),
    ("CVE-2024-28882", "OpenVPN keepalive DoS", "MEDIUM", 5.3, "OpenVPN", "Update OpenVPN to 2.6.10+", False, False),
    ("CVE-2024-2511", "OpenSSL Unbounded Memory Growth", "MEDIUM", 5.9, "OpenSSL", "Update OpenSSL to 3.2.2, 3.1.6, 3.0.14", False, False),
    ("CVE-2024-0727", "OpenSSL PKCS12 NULL Dereference", "MEDIUM", 5.5, "OpenSSL", "Update OpenSSL to 3.2.1, 3.1.5, 3.0.13, 1.1.1x", False, False),
    ("CVE-2024-3596", "RADIUS Protocol Forgery (Blast-RADIUS)", "HIGH", 7.5, "FreeRADIUS", "Enforce Message-Authenticator attribute on all RADIUS packets", False, False),
    ("CVE-2024-5535", "OpenSSL SSL_select_next_proto Buffer Overread", "MEDIUM", 5.9, "OpenSSL", "Update OpenSSL to 3.3.2, 3.2.3, 3.1.7, 3.0.15", False, False),
    ("CVE-2024-38063", "Windows TCP/IP IPv6 Remote Code Execution", "CRITICAL", 9.8, "Windows", "Apply KB5041585 cumulative update", True, False),
    ("CVE-2023-48795", "SSH Terrapin Prefix Truncation Attack", "MEDIUM", 5.9, "OpenSSH", "Update SSH client/server and disable affected ciphers", False, False),
    ("CVE-2024-30088", "Windows Kernel Elevation of Privilege", "HIGH", 7.8, "Windows", "Apply June 2024 Patch Tuesday updates", True, False),
    ("CVE-2024-38077", "Windows RRAS Remote Code Execution", "CRITICAL", 9.8, "Windows", "Apply August 2024 security update", False, False),
    ("CVE-2024-28995", "SolarWinds Serv-U Path Traversal", "HIGH", 7.5, "SolarWinds Serv-U", "Upgrade Serv-U to 15.4.2 HF 2+", True, True),
    ("CVE-2024-0204", "GoAnywhere MFT Authentication Bypass", "CRITICAL", 9.8, "Fortra GoAnywhere MFT", "Upgrade GoAnywhere MFT to 7.4.1+", True, False),
    ("CVE-2023-36884", "Office and Windows HTML Remote Code Execution", "HIGH", 7.5, "Microsoft Office", "Apply Microsoft security updates and enable Attack Surface Reduction rules", True, True),
    ("CVE-2024-21413", "Microsoft Outlook Remote Code Execution", "CRITICAL", 9.8, "Microsoft Outlook", "Apply February 2024 Patch Tuesday updates", True, False),
    ("CVE-2024-24576", "Rust std::process::Command Argument Injection on Windows", "CRITICAL", 10.0, "Rust", "Update Rust toolchain to 1.77.2+", False, False),
    ("CVE-2023-50164", "Apache Struts Path Traversal", "CRITICAL", 9.8, "Apache Struts", "Upgrade Apache Struts to 6.3.0.2+ or 2.5.33+", True, False),
    ("CVE-2024-22024", "Ivanti Connect Secure XXE", "HIGH", 8.3, "Ivanti Connect Secure", "Apply Ivanti XML mitigation or upgrade to patched version", True, False),
    ("CVE-2024-20353", "Cisco ASA and FTD Denial of Service", "HIGH", 8.6, "Cisco ASA", "Apply Cisco security advisory cisco-sa-asaftd-websrvs-dos", True, True),
    ("CVE-2024-3400", "PAN-OS GlobalProtect Command Injection", "CRITICAL", 10.0, "PAN-OS", "Apply PAN-OS hotfix; disable GlobalProtect if not needed", True, True),
    ("CVE-2023-42793", "JetBrains TeamCity RCE", "CRITICAL", 9.8, "JetBrains TeamCity", "Upgrade TeamCity to 2023.05.4+", True, True),
    ("CVE-2024-47575", "FortiManager Missing Authentication", "CRITICAL", 9.8, "FortiManager", "Upgrade FortiManager to 7.6.1, 7.4.5, 7.2.8, or 7.0.13", True, True),
    ("CVE-2024-5274", "Chrome V8 Type Confusion", "HIGH", 8.8, "Google Chrome", "Update Chrome to 125.0.6422.112+", True, True),
    ("CVE-2024-4671", "Chrome Visuals Use-After-Free", "HIGH", 8.8, "Google Chrome", "Update Chrome to 124.0.6367.201+", True, True),
    ("CVE-2024-4947", "Chrome V8 Type Confusion", "HIGH", 8.8, "Google Chrome", "Update Chrome to 125.0.6422.60+", True, True),
    ("CVE-2023-7024", "Chrome WebRTC Heap Buffer Overflow", "HIGH", 8.8, "Google Chrome", "Update Chrome to 120.0.6099.129+", True, True),
    ("CVE-2024-21338", "Windows Kernel Pool Corruption", "HIGH", 7.8, "Windows", "Apply February 2024 Patch Tuesday updates", True, True),
    ("CVE-2023-36025", "Windows SmartScreen Bypass", "HIGH", 8.8, "Windows", "Apply November 2023 Patch Tuesday updates", True, True),
    ("CVE-2024-29988", "Windows SmartScreen Prompt Bypass", "HIGH", 8.8, "Windows", "Apply April 2024 Patch Tuesday updates", True, False),
    ("CVE-2024-26169", "Windows Error Reporting Privilege Escalation", "HIGH", 7.8, "Windows", "Apply March 2024 Patch Tuesday updates", True, True),
]

ALL_CVES = HIGH_PROFILE_CVES + COMMON_CVES

MISCONFIGURATIONS = [
    ("CIS-AWS-1.14", "S3 Bucket Public Access Enabled", "Public read access is enabled on S3 bucket", "STORAGE", "CRITICAL", "AWS", "arn:aws:s3:::prod-data-exports", "prod-data-exports", "aws_s3_bucket", "us-east-1", ["CIS", "SOC2", "PCI-DSS"], "Enable S3 Block Public Access at the bucket level"),
    ("CIS-AWS-4.1", "Security Group Allows SSH from 0.0.0.0/0", "Inbound SSH (port 22) is open to the internet", "NETWORK", "HIGH", "AWS", "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0abc123", "sg-web-prod", "aws_security_group", "us-east-1", ["CIS", "SOC2"], "Restrict SSH access to specific CIDR ranges"),
    ("CIS-AWS-1.4", "IAM Root Account Without MFA", "Root account does not have MFA enabled", "IAM", "CRITICAL", "AWS", "arn:aws:iam::123456789012:root", "root-account", "aws_iam_user", "global", ["CIS", "SOC2", "HIPAA"], "Enable MFA on the root account immediately"),
    ("CIS-AWS-2.1.1", "RDS Instance Publicly Accessible", "RDS instance has public accessibility enabled", "DATABASE", "HIGH", "AWS", "arn:aws:rds:us-east-1:123456789012:db:prod-postgres", "prod-postgres", "aws_rds_instance", "us-east-1", ["CIS", "PCI-DSS"], "Disable public accessibility on RDS instance"),
    ("CIS-AWS-3.8", "KMS Key Rotation Disabled", "Automatic key rotation is not enabled for KMS key", "ENCRYPTION", "MEDIUM", "AWS", "arn:aws:kms:us-east-1:123456789012:key/abc-123", "app-encryption-key", "aws_kms_key", "us-east-1", ["CIS", "HIPAA"], "Enable automatic key rotation for KMS keys"),
    ("CIS-AWS-3.1", "CloudTrail Not Enabled in All Regions", "CloudTrail logging is not enabled globally", "LOGGING", "HIGH", "AWS", "arn:aws:cloudtrail:us-east-1:123456789012:trail/main", "main-trail", "aws_cloudtrail", "us-east-1", ["CIS", "SOC2", "HIPAA"], "Enable CloudTrail multi-region logging"),
    ("CIS-AWS-4.3", "Security Group Allows RDP from 0.0.0.0/0", "Inbound RDP (port 3389) open to the internet", "NETWORK", "HIGH", "AWS", "arn:aws:ec2:us-east-1:123456789012:security-group/sg-0def456", "sg-windows-mgmt", "aws_security_group", "us-east-1", ["CIS", "PCI-DSS"], "Restrict RDP access to VPN CIDR only"),
    ("CIS-AZURE-3.1", "Storage Account Allows HTTP", "Azure Storage account allows unencrypted HTTP access", "ENCRYPTION", "MEDIUM", "AZURE", "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/prodstore01", "prodstore01", "azure_storage_account", "eastus", ["CIS", "SOC2"], "Enable 'Secure transfer required' on storage account"),
    ("CIS-AZURE-4.1.1", "Network Security Group Allows All Inbound", "NSG rule allows all inbound traffic", "NETWORK", "CRITICAL", "AZURE", "/subscriptions/sub-001/resourceGroups/rg-staging/providers/Microsoft.Network/networkSecurityGroups/nsg-staging", "nsg-staging", "azure_network_security_group", "eastus", ["CIS", "PCI-DSS"], "Remove overly permissive inbound rules from NSG"),
    ("CIS-AZURE-1.2", "Azure AD User Without MFA", "Multiple users in Azure AD do not have MFA enabled", "IAM", "HIGH", "AZURE", "/subscriptions/sub-001/providers/Microsoft.AAD/users", "azure-ad-users", "azure_ad_user", "global", ["CIS", "SOC2", "HIPAA"], "Enforce MFA via Conditional Access policy"),
    ("CIS-AZURE-5.1", "Key Vault Soft Delete Disabled", "Azure Key Vault does not have soft delete enabled", "SECRETS", "MEDIUM", "AZURE", "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.KeyVault/vaults/kv-prod", "kv-prod", "azure_key_vault", "eastus", ["CIS"], "Enable soft delete and purge protection on Key Vault"),
    ("CIS-AZURE-9.1", "App Service Does Not Use Latest TLS", "App Service is not configured to use TLS 1.2+", "ENCRYPTION", "MEDIUM", "AZURE", "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Web/sites/api-prod", "api-prod", "azure_app_service", "eastus", ["CIS", "PCI-DSS"], "Set minimum TLS version to 1.2 on App Service"),
    ("CIS-GCP-3.1", "Default Network Exists", "Default VPC network still exists in project", "NETWORK", "MEDIUM", "GCP", "projects/getvul-prod/global/networks/default", "default-network", "gcp_compute_network", "global", ["CIS"], "Delete the default network and create custom VPC"),
    ("CIS-GCP-1.1", "Service Account Key Older Than 90 Days", "Service account key has not been rotated", "IAM", "HIGH", "GCP", "projects/getvul-prod/serviceAccounts/sa-deploy@getvul-prod.iam.gserviceaccount.com/keys/key-001", "sa-deploy-key", "gcp_service_account_key", "global", ["CIS", "SOC2"], "Rotate service account keys every 90 days"),
    ("CIS-GCP-6.1.1", "Compute Instance With Public IP", "GCP VM instance has an external IP address attached", "COMPUTE", "MEDIUM", "GCP", "projects/getvul-prod/zones/us-central1-a/instances/data-processor", "data-processor", "gcp_compute_instance", "us-central1", ["CIS"], "Remove external IP and use Cloud NAT for egress"),
    ("CIS-GCP-6.2", "Compute Instance Without Shielded VM", "GCP VM instance does not have Shielded VM enabled", "COMPUTE", "LOW", "GCP", "projects/getvul-prod/zones/us-central1-a/instances/test-runner", "test-runner", "gcp_compute_instance", "us-central1", ["CIS"], "Enable Shielded VM features (Secure Boot, vTPM)"),
    ("CIS-AWS-2.1", "EBS Volume Not Encrypted", "EBS volume attached to production instance is not encrypted", "ENCRYPTION", "HIGH", "AWS", "arn:aws:ec2:us-east-1:123456789012:volume/vol-0abc123", "vol-prod-data", "aws_ebs_volume", "us-east-1", ["CIS", "HIPAA", "PCI-DSS"], "Enable default EBS encryption and re-create unencrypted volumes"),
    ("CIS-AWS-1.16", "IAM Policy Allows Full Admin Access", "IAM policy attached to role grants *:* permissions", "IAM", "CRITICAL", "AWS", "arn:aws:iam::123456789012:policy/LegacyAdminPolicy", "LegacyAdminPolicy", "aws_iam_policy", "global", ["CIS", "SOC2"], "Replace with least-privilege policies"),
    ("CIS-GCP-2.2", "Cloud SQL Instance Publicly Accessible", "Cloud SQL instance allows connections from 0.0.0.0/0", "DATABASE", "CRITICAL", "GCP", "projects/getvul-prod/instances/analytics-db", "analytics-db", "gcp_sql_instance", "us-central1", ["CIS", "PCI-DSS"], "Remove 0.0.0.0/0 from authorized networks"),
    ("CIS-AZURE-6.1", "SQL Server Auditing Disabled", "Azure SQL Server does not have auditing enabled", "LOGGING", "HIGH", "AZURE", "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Sql/servers/sql-prod", "sql-prod", "azure_sql_server", "eastus", ["CIS", "SOC2", "HIPAA"], "Enable auditing on Azure SQL Server"),
]

DIRECTORY_USERS = [
    ("Jordan Chen", "jchen@demo.getvul.local", "Engineering", "Senior Software Engineer", True),
    ("Sarah Lee", "slee@demo.getvul.local", "Engineering", "Backend Engineer", True),
    ("Alex Martin", "amartin@demo.getvul.local", "Security", "Security Engineer", True),
    ("David Kim", "dkim@demo.getvul.local", "Engineering", "Frontend Engineer", True),
    ("Rina Patel", "rpatel@demo.getvul.local", "DevOps", "Site Reliability Engineer", True),
    ("Marcus Wilson", "mwilson@demo.getvul.local", "IT", "IT Support Specialist", True),
    ("Lena Jones", "ljones@demo.getvul.local", "Security", "Security Analyst", True),
    ("Nicole Garcia", "ngarcia@demo.getvul.local", "Engineering", "Full Stack Developer", True),
    ("Tyler Wang", "twang@demo.getvul.local", "DevOps", "DevOps Engineer", True),
    ("Brian Thompson", "bthompson@demo.getvul.local", "Finance", "Financial Analyst", True),
    ("Priya Sharma", "psharma@demo.getvul.local", "Engineering", "Staff Engineer", True),
    ("Carlos Mendez", "cmendez@demo.getvul.local", "IT", "IT Manager", True),
    ("Emily Zhang", "ezhang@demo.getvul.local", "Security", "CISO", True),
    ("Jake Foster", "jfoster@demo.getvul.local", "Engineering", "Junior Developer", False),  # suspended
    ("Maria Santos", "msantos@demo.getvul.local", "Finance", "Controller", False),  # suspended
]

NOTIFICATIONS = [
    ("Critical Vulnerability: CVE-2024-3094 (XZ Backdoor)", "A critical backdoor vulnerability was detected in xz-utils on 3 assets. Immediate patching required.", "critical", "new_critical_vuln", False),
    ("SLA Breach: 5 HIGH vulns overdue on SRV-WEB-01", "5 HIGH severity vulnerabilities have exceeded their 30-day SLA on server SRV-WEB-01.", "high", "sla_breach", False),
    ("Sync Complete: CrowdStrike", "CrowdStrike Spotlight sync completed successfully. 87 vulnerabilities ingested across 18 assets.", "medium", "sync_complete", True),
    ("Risk Score Spike: SRV-DB-01 (45 -> 92)", "Server SRV-DB-01 risk score increased from 45 to 92 after new critical vulnerabilities were detected.", "high", "risk_spike", False),
    ("SLA Breach: 2 CRITICAL vulns overdue on FW-EDGE-01", "2 CRITICAL severity vulnerabilities have exceeded their 7-day SLA on firewall FW-EDGE-01.", "critical", "sla_breach", True),
]


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------


async def seed() -> None:
    async with async_session_factory() as session:
        # ------------------------------------------------------------------
        # 0. Pre-check
        # ------------------------------------------------------------------
        row = (await session.execute(text("SELECT count(*) FROM assets"))).scalar()
        if row and row > 5:
            print("Seed data already exists — skipping.")
            return

        # ------------------------------------------------------------------
        # 1. Get tenant
        # ------------------------------------------------------------------
        tenant_id = (await session.execute(text("SELECT id FROM tenants ORDER BY created_at LIMIT 1"))).scalar()
        if not tenant_id:
            print("ERROR: No tenant found. Please create a tenant first.")
            return
        print(f"Using tenant: {tenant_id}")

        # ------------------------------------------------------------------
        # 2. Connector configs
        # ------------------------------------------------------------------
        print("Creating connector configs...")
        connectors = [
            ("CROWDSTRIKE", '{"base_url": "https://api.crowdstrike.com"}', "demo-crowdstrike-creds"),
            ("NESSUS", '{"url": "https://nessus.demo.local:8834"}', "demo-nessus-creds"),
            ("DEFENDER", '{}', "demo-defender-creds"),
            ("WIZ", '{"api_url": "https://api.us1.app.wiz.io/graphql"}', "demo-wiz-creds"),
            ("JIRA", '{"project_key": "VULN", "workspace": "Demo"}', "demo-jira-creds"),
            ("GOOGLE_WORKSPACE", '{"domain": "demo.getvul.local"}', "demo-gws-creds"),
            ("JAMF", '{"base_url": "https://jamf.demo.getvul.local"}', "demo-jamf-creds"),
        ]
        connector_ids = {}
        for ctype, config, creds_arn in connectors:
            cid = str(uuid.uuid4())
            connector_ids[ctype] = cid
            await session.execute(text("""
                INSERT INTO connector_configs (id, tenant_id, connector_type, is_enabled, config, credentials_secret_arn,
                    last_sync_at, last_sync_status, last_sync_record_count, sync_interval_minutes, created_at, updated_at)
                VALUES (:id, :tid, :ctype, true, :config::jsonb, :creds,
                    :last_sync, 'SUCCESS', :count, 60, now(), now())
                ON CONFLICT (tenant_id, connector_type) DO NOTHING
            """), {
                "id": cid, "tid": str(tenant_id), "ctype": ctype, "config": config, "creds": creds_arn,
                "last_sync": rand_recent(2).isoformat(), "count": random.randint(15, 120),
            })
        print(f"  -> {len(connectors)} connector configs")

        # ------------------------------------------------------------------
        # 3. Assets
        # ------------------------------------------------------------------
        print("Creating assets...")
        asset_ids: list[str] = []
        asset_categories: list[str] = []
        asset_sources: list[list[str]] = []

        # Workstations
        for hostname, ip, osn, osv, mfr, model, serial, user, mgr, sources in WORKSTATIONS:
            aid = str(uuid.uuid4())
            asset_ids.append(aid)
            asset_categories.append("WORKSTATION")
            asset_sources.append(sources)
            ext_ip = f"203.0.113.{random.randint(10, 250)}"
            risk = random.randint(20, 90)
            await session.execute(text("""
                INSERT INTO assets (id, tenant_id, hostname, ip_addresses, os_name, os_version,
                    device_category, risk_score, host_status, seen_by_sources, serial_number, model,
                    system_manufacturer, last_seen_at, external_ip, assigned_user, last_login_user,
                    managed_by, asset_type, created_at, updated_at)
                VALUES (:id, :tid, :hostname, :ips::jsonb, :osn, :osv,
                    'WORKSTATION', :risk, 'normal', :sources::jsonb, :serial, :model,
                    :mfr, :seen, :ext_ip, :user, :user,
                    :mgr, 'WORKSTATION', now(), now())
                ON CONFLICT (tenant_id, hostname) DO NOTHING
            """), {
                "id": aid, "tid": str(tenant_id), "hostname": hostname,
                "ips": jl([ip]), "osn": osn, "osv": osv,
                "risk": risk, "sources": jl(sources), "serial": serial, "model": model,
                "mfr": mfr, "seen": rand_recent(1).isoformat(), "ext_ip": ext_ip,
                "user": user, "mgr": mgr,
            })

        # Servers
        for hostname, ip, osn, osv, mfr, model, serial, sources in SERVERS:
            aid = str(uuid.uuid4())
            asset_ids.append(aid)
            asset_categories.append("SERVER")
            asset_sources.append(sources)
            ext_ip = f"198.51.100.{random.randint(10, 250)}"
            risk = random.randint(40, 95)
            await session.execute(text("""
                INSERT INTO assets (id, tenant_id, hostname, ip_addresses, os_name, os_version,
                    device_category, risk_score, host_status, seen_by_sources, serial_number, model,
                    system_manufacturer, last_seen_at, external_ip, asset_type, created_at, updated_at)
                VALUES (:id, :tid, :hostname, :ips::jsonb, :osn, :osv,
                    'SERVER', :risk, 'normal', :sources::jsonb, :serial, :model,
                    :mfr, :seen, :ext_ip, 'SERVER', now(), now())
                ON CONFLICT (tenant_id, hostname) DO NOTHING
            """), {
                "id": aid, "tid": str(tenant_id), "hostname": hostname,
                "ips": jl([ip]), "osn": osn, "osv": osv,
                "risk": risk, "sources": jl(sources), "serial": serial, "model": model,
                "mfr": mfr, "seen": rand_recent(2).isoformat(), "ext_ip": ext_ip,
            })

        # Network devices
        for hostname, ip, osn, osv, mfr, model, serial, sources in NETWORK_DEVICES:
            aid = str(uuid.uuid4())
            asset_ids.append(aid)
            asset_categories.append("NETWORK")
            asset_sources.append(sources)
            risk = random.randint(15, 60)
            await session.execute(text("""
                INSERT INTO assets (id, tenant_id, hostname, ip_addresses, os_name, os_version,
                    device_category, risk_score, host_status, seen_by_sources, serial_number, model,
                    system_manufacturer, last_seen_at, asset_type, created_at, updated_at)
                VALUES (:id, :tid, :hostname, :ips::jsonb, :osn, :osv,
                    'NETWORK', :risk, 'normal', :sources::jsonb, :serial, :model,
                    :mfr, :seen, 'NETWORK', now(), now())
                ON CONFLICT (tenant_id, hostname) DO NOTHING
            """), {
                "id": aid, "tid": str(tenant_id), "hostname": hostname,
                "ips": jl([ip]), "osn": osn, "osv": osv,
                "risk": risk, "sources": jl(sources), "serial": serial, "model": model,
                "mfr": mfr, "seen": rand_recent(3).isoformat(),
            })

        # Cloud resources
        for hostname, ip, osn, osv, cloud, model, crid, sources in CLOUD_RESOURCES:
            aid = str(uuid.uuid4())
            asset_ids.append(aid)
            asset_categories.append("OTHER")
            asset_sources.append(sources)
            risk = random.randint(30, 80)
            cloud_map = {"AWS": "AWS", "Microsoft": "AZURE", "Google": "GCP"}
            await session.execute(text("""
                INSERT INTO assets (id, tenant_id, hostname, ip_addresses, os_name, os_version,
                    device_category, risk_score, host_status, seen_by_sources, model,
                    system_manufacturer, last_seen_at, cloud_provider, cloud_resource_id,
                    asset_type, created_at, updated_at)
                VALUES (:id, :tid, :hostname, :ips::jsonb, :osn, :osv,
                    'OTHER', :risk, 'normal', :sources::jsonb, :model,
                    :mfr, :seen, :cloud, :crid,
                    'OTHER', now(), now())
                ON CONFLICT (tenant_id, hostname) DO NOTHING
            """), {
                "id": aid, "tid": str(tenant_id), "hostname": hostname,
                "ips": jl([ip]), "osn": osn, "osv": osv,
                "risk": risk, "sources": jl(sources), "model": model,
                "mfr": cloud, "seen": rand_recent(1).isoformat(),
                "cloud": cloud_map.get(cloud, "AWS"), "crid": crid,
            })

        print(f"  -> {len(asset_ids)} assets")

        # ------------------------------------------------------------------
        # 4. Vulnerabilities
        # ------------------------------------------------------------------
        print("Creating vulnerabilities...")
        vuln_count = 0
        vuln_ids: list[str] = []  # track for ticket linking

        # Distribute CVEs across assets to reach 150+
        # Each high-profile CVE on 2-5 random assets; common CVEs on 1-4 assets
        assignments: list[tuple] = []  # (cve_tuple, asset_index)
        for cve_tuple in HIGH_PROFILE_CVES:
            n = random.randint(2, 5)
            chosen = random.sample(range(len(asset_ids)), min(n, len(asset_ids)))
            for idx in chosen:
                assignments.append((cve_tuple, idx))
        for cve_tuple in COMMON_CVES:
            n = random.randint(1, 4)
            chosen = random.sample(range(len(asset_ids)), min(n, len(asset_ids)))
            for idx in chosen:
                assignments.append((cve_tuple, idx))

        # Shuffle to mix order
        random.shuffle(assignments)

        sla_days = {"CRITICAL": 7, "HIGH": 30, "MEDIUM": 90, "LOW": 180}
        status_weights = ["OPEN"] * 70 + ["IN_PROGRESS"] * 15 + ["REMEDIATED"] * 10 + ["SUPPRESSED"] * 5

        for cve_tuple, asset_idx in assignments:
            cve_id, vuln_name, severity, cvss, product, remediation, exploit, kev = cve_tuple
            aid = asset_ids[asset_idx]
            sources_for_asset = asset_sources[asset_idx]
            # Pick a source from what the asset is seen by (only vuln scanner sources)
            vuln_sources = [s for s in sources_for_asset if s in ("CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ")]
            if not vuln_sources:
                vuln_sources = ["NESSUS"]
            source = random.choice(vuln_sources)

            status = random.choice(status_weights)
            first_detected = rand_past(120)
            last_seen = rand_recent(3) if status != "REMEDIATED" else rand_past(30)
            remediated_at = rand_past(15).isoformat() if status == "REMEDIATED" else None

            # SLA: some breached
            sla_offset = sla_days.get(severity, 90)
            if random.random() < 0.15:  # 15% SLA breached
                sla_due = (first_detected + timedelta(days=sla_offset)).isoformat()
                sla_breached = True
            else:
                sla_due = (NOW + timedelta(days=random.randint(1, sla_offset))).isoformat()
                sla_breached = False

            vid = str(uuid.uuid4())
            vuln_ids.append(vid)
            rem_id = make_hash(remediation)

            try:
                await session.execute(text("""
                    INSERT INTO vulnerabilities (id, tenant_id, cve_id, vulnerability_name, cvss_v3_score,
                        severity, exploit_available, cisa_kev, asset_id, source, affected_product,
                        remediation_action, remediation_id, status, first_detected_at, last_seen_at,
                        remediated_at, sla_due_at, sla_breached, created_at, updated_at)
                    VALUES (:id, :tid, :cve, :name, :cvss,
                        :sev, :exploit, :kev, :aid, :source, :product,
                        :remediation, :rem_id, :status, :first, :last,
                        :rem_at::timestamptz, :sla::timestamptz, :sla_b, now(), now())
                    ON CONFLICT (tenant_id, cve_id, asset_id, source) DO NOTHING
                """), {
                    "id": vid, "tid": str(tenant_id), "cve": cve_id, "name": vuln_name,
                    "cvss": float(cvss), "sev": severity, "exploit": exploit, "kev": kev,
                    "aid": aid, "source": source, "product": product,
                    "remediation": remediation, "rem_id": rem_id, "status": status,
                    "first": first_detected.isoformat(), "last": last_seen.isoformat(),
                    "rem_at": remediated_at, "sla": sla_due, "sla_b": sla_breached,
                })
                vuln_count += 1
            except Exception:
                pass  # dedup conflict — skip silently

        print(f"  -> {vuln_count} vulnerabilities")

        # ------------------------------------------------------------------
        # 5. CSPM Misconfigurations
        # ------------------------------------------------------------------
        print("Creating CSPM misconfigurations...")
        misconfig_count = 0
        status_mix = ["OPEN"] * 12 + ["IN_PROGRESS"] * 4 + ["REMEDIATED"] * 3 + ["SUPPRESSED"] * 1
        random.shuffle(status_mix)

        for i, mc in enumerate(MISCONFIGURATIONS):
            rule_id, rule_name, desc, category, severity, cloud, resource_id, resource_name, resource_type, region, frameworks, remediation = mc
            st = status_mix[i % len(status_mix)]
            mid = str(uuid.uuid4())
            first = rand_past(90)
            await session.execute(text("""
                INSERT INTO misconfigurations (id, tenant_id, rule_id, rule_name, rule_description,
                    category, severity, frameworks, resource_id, resource_name, resource_type,
                    resource_region, cloud_provider, cloud_account_id, cloud_account_name,
                    source, remediation_info, status, first_detected_at, last_seen_at, created_at, updated_at)
                VALUES (:id, :tid, :rule_id, :rule_name, :desc,
                    :cat, :sev, :fw::jsonb, :rid, :rname, :rtype,
                    :region, :cloud, :acct_id, :acct_name,
                    'WIZ', :rem, :status, :first, :last, now(), now())
                ON CONFLICT (tenant_id, rule_id, resource_id, source) DO NOTHING
            """), {
                "id": mid, "tid": str(tenant_id), "rule_id": rule_id, "rule_name": rule_name,
                "desc": desc, "cat": category, "sev": severity, "fw": jl(frameworks),
                "rid": resource_id, "rname": resource_name, "rtype": resource_type,
                "region": region, "cloud": cloud,
                "acct_id": "123456789012" if cloud == "AWS" else ("sub-001" if cloud == "AZURE" else "getvul-prod"),
                "acct_name": "getvul-production",
                "rem": remediation, "status": st,
                "first": first.isoformat(), "last": rand_recent(2).isoformat(),
            })
            misconfig_count += 1
        print(f"  -> {misconfig_count} misconfigurations")

        # ------------------------------------------------------------------
        # 6. Tickets
        # ------------------------------------------------------------------
        print("Creating tickets...")
        # Pick 10 OPEN/IN_PROGRESS vulnerability IDs to link to tickets
        ticket_vulns = (await session.execute(text("""
            SELECT id FROM vulnerabilities
            WHERE tenant_id = :tid AND status IN ('OPEN', 'IN_PROGRESS')
            ORDER BY severity, created_at
            LIMIT 10
        """), {"tid": str(tenant_id)})).fetchall()

        ticket_statuses = ["To Do", "To Do", "To Do", "In Progress", "In Progress", "In Progress",
                           "In Progress", "Done", "Done", "Done"]
        assignees = ["jchen@demo.getvul.local", "slee@demo.getvul.local", "amartin@demo.getvul.local",
                     "rpatel@demo.getvul.local", "ljones@demo.getvul.local"]
        ticket_count = 0
        for i, vrow in enumerate(ticket_vulns):
            vid = str(vrow[0])
            ticket_num = 101 + i
            ext_id = f"VULN-{ticket_num}"
            ext_url = f"https://demo.atlassian.net/browse/VULN-{ticket_num}"
            ext_status = ticket_statuses[i % len(ticket_statuses)]
            assignee = assignees[i % len(assignees)]
            tid_ticket = str(uuid.uuid4())
            created_d = rand_past(30)
            resolved = rand_past(7).isoformat() if ext_status == "Done" else None
            await session.execute(text("""
                INSERT INTO tickets (id, tenant_id, vulnerability_id, provider, external_ticket_id,
                    external_ticket_url, external_status, project_key, assignee,
                    ticket_created_at, resolved_at, created_at, updated_at)
                VALUES (:id, :tid, :vid, 'JIRA', :ext_id,
                    :ext_url, :ext_status, 'VULN', :assignee,
                    :created, :resolved::timestamptz, now(), now())
                ON CONFLICT (tenant_id, external_ticket_id, provider) DO NOTHING
            """), {
                "id": tid_ticket, "tid": str(tenant_id), "vid": vid, "ext_id": ext_id,
                "ext_url": ext_url, "ext_status": ext_status, "assignee": assignee,
                "created": created_d.isoformat(), "resolved": resolved,
            })
            ticket_count += 1
        print(f"  -> {ticket_count} tickets")

        # ------------------------------------------------------------------
        # 7. Notifications
        # ------------------------------------------------------------------
        print("Creating notifications...")
        for title, message, severity, category, is_read in NOTIFICATIONS:
            nid = str(uuid.uuid4())
            await session.execute(text("""
                INSERT INTO notifications (id, tenant_id, title, message, severity, category,
                    is_read, read_at, email_sent, created_at, updated_at)
                VALUES (:id, :tid, :title, :msg, :sev, :cat,
                    :read, :read_at::timestamptz, false, :created, now())
            """), {
                "id": nid, "tid": str(tenant_id), "title": title, "msg": message,
                "sev": severity, "cat": category, "read": is_read,
                "read_at": rand_recent(1).isoformat() if is_read else None,
                "created": rand_recent(5).isoformat(),
            })
        print(f"  -> {len(NOTIFICATIONS)} notifications")

        # ------------------------------------------------------------------
        # 8. Directory users
        # ------------------------------------------------------------------
        print("Creating directory users...")
        user_count = 0
        for name, email, dept, title, active in DIRECTORY_USERS:
            uid = str(uuid.uuid4())
            await session.execute(text("""
                INSERT INTO users (id, tenant_id, email, display_name, role, is_active,
                    department, job_title, idp_source, idp_subject, groups, created_at, updated_at)
                VALUES (:id, :tid, :email, :name, 'VIEWER', :active,
                    :dept, :title, 'google', :idp_sub, '[]'::jsonb, now(), now())
                ON CONFLICT (tenant_id, email) DO NOTHING
            """), {
                "id": uid, "tid": str(tenant_id), "email": email, "name": name,
                "active": active, "dept": dept, "title": title, "idp_sub": f"google-{uid[:8]}",
            })
            user_count += 1
        print(f"  -> {user_count} directory users")

        # ------------------------------------------------------------------
        # Commit
        # ------------------------------------------------------------------
        await session.commit()
        print("\nSeed data created successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
