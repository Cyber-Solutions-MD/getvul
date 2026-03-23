"""Asset device type classification.

Priority:
  1. CrowdStrike product_type_desc (most authoritative)
  2. Hostname patterns
  3. OS patterns
  4. Platform hints
  5. Default = OTHER
"""

from __future__ import annotations

import re

# ── CrowdStrike product_type_desc mapping ──
CS_TYPE_MAP = {
    "workstation": "WORKSTATION",
    "server": "SERVER",
    "domain controller": "SERVER",
    "kubernetes cluster": "SERVER",
}

# ── Hostname patterns ──
CONTAINER_PATTERNS = [
    r"(?i)^gke-",
    r"(?i)^eks-",
    r"(?i)^aks-",
    r"(?i)^k8s-",
    r"(?i)^node-",
    r"(?i)^ip-10-",
]
SERVER_HOSTNAME = [
    r"(?i)^srv-",
    r"(?i)^db-",
    r"(?i)^web-",
    r"(?i)^api-",
    r"(?i)^app-",
    r"(?i)^mgmt-",
    r"(?i)^infra-",
    r"(?i)-srv\d*$",
    r"(?i)-db\d*$",
    r"(?i)-web\d*$",
    r"(?i)^prod-",
    r"(?i)^stg-",
    r"(?i)^dev-",
    r"(?i)server",
    r"(?i)^dc\d",
    r"(?i)^esxi",
    r"(?i)^master-",
    r"(?i)^worker-",
]
WORKSTATION_HOSTNAME = [
    r"(?i)macbook",
    r"(?i)imac",
    r"(?i)mbp-",
    r"(?i)desktop-",
    r"(?i)laptop-",
    r"(?i)^ws-",
    r"(?i)\.local$",
    r"(?i)^[A-Z]{2,4}-LT",
    r"(?i)^[A-Z]{2,4}-DT",
    r"(?i)^DEP---",  # Apple DEP enrolled devices
    r"(?i)^par\d",  # PAR device naming convention
]
NETWORK_HOSTNAME = [
    r"(?i)^sw-",
    r"(?i)^switch",
    r"(?i)^rtr-",
    r"(?i)^router",
    r"(?i)^fw-",
    r"(?i)^firewall",
    r"(?i)^ap-",
    r"(?i)^wap-",
    r"(?i)meraki",
    r"(?i)cisco",
    r"(?i)fortigate",
    r"(?i)paloalto",
]
MOBILE_HOSTNAME = [
    r"(?i)iphone",
    r"(?i)ipad",
    r"(?i)android",
]

# ── OS patterns ──
SERVER_OS = [
    r"(?i)windows server",
    r"(?i)rhel",
    r"(?i)red hat",
    r"(?i)centos",
    r"(?i)amazon linux",
    r"(?i)ubuntu server",
    r"(?i)debian",
    r"(?i)suse",
    r"(?i)oracle linux",
    r"(?i)vmware",
    r"(?i)esxi",
    r"(?i)cos\b",
    r"(?i)container.optimized",
    r"(?i)flatcar",
    r"(?i)bottlerocket",
    r"(?i)talos",
]
WORKSTATION_OS = [
    r"(?i)windows 1[01]",
    r"(?i)windows 11",
    r"(?i)^mac",
    r"(?i)macos",
    r"(?i)mac os",
    r"(?i)os x",
    r"(?i)chrome\s?os",
    r"(?i)ubuntu desktop",
    r"(?i)tahoe",
    r"(?i)sequoia",
    r"(?i)sonoma",
    r"(?i)ventura",
]
MOBILE_OS = [
    r"(?i)^ios",
    r"(?i)ipados",
    r"(?i)android",
]


def _match(value: str | None, patterns: list[str]) -> bool:
    if not value:
        return False
    return any(re.search(p, value) for p in patterns)


def classify_asset_from_data(
    hostname: str = "",
    os_name: str = "",
    platform_name: str = "",
    product_type_desc: str = "",
) -> str:
    """Classify a device into a category.

    Args:
        hostname: Device hostname
        os_name: Operating system name
        platform_name: CrowdStrike platform (Mac/Windows/Linux)
        product_type_desc: CrowdStrike product type (Workstation/Server/Domain Controller)
    """
    # 1. CrowdStrike product_type_desc is the most authoritative source
    if product_type_desc:
        mapped = CS_TYPE_MAP.get(product_type_desc.lower().strip())
        if mapped:
            return mapped

    # 2. Hostname patterns
    if _match(hostname, NETWORK_HOSTNAME):
        return "NETWORK"
    if _match(hostname, MOBILE_HOSTNAME):
        return "MOBILE"
    if _match(hostname, CONTAINER_PATTERNS):
        return "SERVER"  # K8s/GKE/EKS nodes are servers
    if _match(hostname, SERVER_HOSTNAME):
        return "SERVER"
    if _match(hostname, WORKSTATION_HOSTNAME):
        return "WORKSTATION"

    # 3. OS patterns
    if _match(os_name, MOBILE_OS):
        return "MOBILE"
    if _match(os_name, SERVER_OS):
        return "SERVER"
    if _match(os_name, WORKSTATION_OS):
        return "WORKSTATION"

    # 4. Platform hints
    pl = platform_name.lower() if platform_name else ""
    if pl == "mac":
        return "WORKSTATION"
    if pl == "windows":
        if os_name and "server" in os_name.lower():
            return "SERVER"
        return "WORKSTATION"
    if pl == "linux":
        if _match(os_name, WORKSTATION_OS):
            return "WORKSTATION"
        return "SERVER"  # Linux without desktop OS → server

    return "OTHER"


def classify_asset(asset) -> str:
    """Classify from an Asset ORM object.

    Uses asset_type as the source-reported type (e.g., CrowdStrike product_type_desc
    like "Workstation" or "Server") and os_name as the platform hint.
    """
    return classify_asset_from_data(
        hostname=asset.hostname or "",
        os_name=asset.os_name or "",
        platform_name=asset.os_name or "",  # os_name holds platform ("Mac", "Linux", "Windows")
        product_type_desc=asset.asset_type or "",  # asset_type holds CrowdStrike product_type_desc
    )
