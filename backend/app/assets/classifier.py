"""Classify assets into device categories based on OS, hostname, and platform."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset

# Hostname patterns suggesting servers
SERVER_PATTERNS = [
    r"(?i)(srv|server|db-|rds|redis|cache|web-prod|api-prod|worker|queue|proxy|lb|load.?bal|nginx|apache|haproxy)",
    r"(?i)(elasticsearch|kafka|rabbit|mongo|postgres|mysql|oracle|mssql)",
    r"(?i)(k8s|kube|node-|etcd|master-|control-plane|bastion|jump|vpn-gw|gateway)",
    r"(?i)(nas|san|storage|backup|vault|ci-|jenkins|gitlab|build)",
    r"(?i)(dc\d|ad\d|dns\d|dhcp|mail|smtp|exchange|imap)",
    r"(?i)^(par\d{3,}|ip-\d|ec2|vm-|instance)",  # Cloud instances
]

# Hostname patterns suggesting workstations
WORKSTATION_PATTERNS = [
    r"(?i)(macbook|imac|mac-|mbp|mba)",
    r"(?i)(desktop|laptop|workstation|ws-)",
    r"(?i)(-pc$|-lt$|-dt$|-nb$)",
    r"(?i)(\.local$|\.home$|\.internal$)",
    r"(?i)^[a-z]+-[a-z]+-pro\.local",  # firstname-macbook-pro.local
]

# Network device patterns
NETWORK_PATTERNS = [
    r"(?i)(switch|router|firewall|fw-|ap-|access.?point|wap|meraki|fortinet|palo)",
]

# Mobile patterns
MOBILE_PATTERNS = [
    r"(?i)(iphone|ipad|android|pixel|galaxy|mobile)",
]

# OS-based classification
SERVER_OS = [
    "windows server", "ubuntu server", "rhel", "centos", "debian",
    "amazon linux", "suse", "oracle linux", "rocky", "alma",
]

WORKSTATION_OS = [
    "macos", "mac os", "sequoia", "ventura", "sonoma", "monterey", "big sur", "catalina",
    "windows 10", "windows 11", "windows 7", "windows 8",
    "ubuntu desktop", "fedora", "mint", "pop!_os", "elementary",
]

MOBILE_OS = [
    "ios", "ipados", "android",
]


def classify_device(hostname: str | None, os_name: str | None, os_version: str | None, platform: str | None = None) -> str:
    """Classify a device into WORKSTATION, SERVER, NETWORK, MOBILE, or OTHER."""
    h = (hostname or "").lower()
    os_full = f"{os_name or ''} {os_version or ''}".lower().strip()
    plat = (platform or "").lower()

    # 1. Check hostname patterns first (most specific)
    for pattern in NETWORK_PATTERNS:
        if re.search(pattern, h):
            return "NETWORK"

    for pattern in MOBILE_PATTERNS:
        if re.search(pattern, h):
            return "MOBILE"

    for pattern in SERVER_PATTERNS:
        if re.search(pattern, h):
            return "SERVER"

    for pattern in WORKSTATION_PATTERNS:
        if re.search(pattern, h):
            return "WORKSTATION"

    # 2. Check OS
    for os_pat in MOBILE_OS:
        if os_pat in os_full:
            return "MOBILE"

    for os_pat in SERVER_OS:
        if os_pat in os_full:
            return "SERVER"

    for os_pat in WORKSTATION_OS:
        if os_pat in os_full:
            return "WORKSTATION"

    # 3. Platform-based (from CrowdStrike)
    if plat in ("mac", "macos"):
        return "WORKSTATION"
    if plat == "windows":
        # Windows without "server" in OS = workstation
        if "server" not in os_full:
            return "WORKSTATION"
        return "SERVER"
    if plat == "linux":
        # Linux without workstation indicators = assume server
        return "SERVER"

    return "OTHER"


async def classify_all_assets(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Reclassify all assets in a tenant. Returns counts by category."""
    result = await db.execute(
        select(Asset).where(Asset.tenant_id == tenant_id)
    )
    assets = result.scalars().all()

    counts: dict[str, int] = {}
    for asset in assets:
        category = classify_device(asset.hostname, asset.os_name, asset.os_version)
        if asset.device_category != category:
            asset.device_category = category
        counts[category] = counts.get(category, 0) + 1

    return counts
