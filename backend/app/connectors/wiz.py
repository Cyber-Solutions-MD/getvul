"""Wiz cloud security connector — vulnerabilities + CSPM misconfigurations."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from app.connectors.base import (
    BaseConnector,
    NormalizedMisconfiguration,
    NormalizedVulnerability,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

VULNERABILITY_QUERY = """
query VulnerabilityFindings($after: String) {
  vulnerabilityFindings(
    first: 500
    after: $after
    filterBy: { status: [OPEN, IN_PROGRESS] }
  ) {
    nodes {
      id
      name
      CVEDescription
      severity
      score
      exploitAvailable
      hasExploit
      hasCisaKevExploit
      status
      remediation
      detailedName
      version
      fixedVersion
      firstDetectedAt
      lastDetectedAt
      vulnerableAsset {
        id
        name
        type
        cloudPlatform
        subscriptionId
        subscriptionName
        region
        providerUniqueId
        operatingSystem
        ipAddresses
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

CONFIGURATION_QUERY = """
query ConfigurationFindings($after: String) {
  configurationFindings(
    first: 500
    after: $after
    filterBy: { status: [OPEN, IN_PROGRESS] }
  ) {
    nodes {
      id
      rule {
        id
        name
        description
        severity
        remediationInstructions
        frameworkReferences { name version }
      }
      resource {
        id
        name
        type
        region
        cloudPlatform
        subscriptionId
        subscriptionName
        providerUniqueId
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

_VULN_SEVERITY_MAP: dict[str, str] = {
    "CRITICAL": "CRITICAL",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
    "INFORMATIONAL": "INFO",
}

_MISCONFIG_SEVERITY_MAP: dict[str, str] = {
    "CRITICAL": "CRITICAL",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
    "INFORMATIONAL": "LOW",
}


def _map_vuln_severity(raw: str | None) -> str:
    if not raw:
        return "MEDIUM"
    return _VULN_SEVERITY_MAP.get(raw.upper(), "MEDIUM")


def _map_misconfig_severity(raw: str | None) -> str:
    if not raw:
        return "LOW"
    return _MISCONFIG_SEVERITY_MAP.get(raw.upper(), "LOW")


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class WizConnector(BaseConnector):
    """Connector for the Wiz cloud security platform."""

    source_name: str = "WIZ"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._api_url: str = ""
        self._token: str = ""

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def authenticate(
        self,
        credentials: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> None:
        """Authenticate via OAuth2 client_credentials grant."""

        client_id: str = credentials["client_id"]
        client_secret: str = credentials["client_secret"]
        api_url: str = credentials["api_url"]
        auth_url: str = credentials["auth_url"]

        self._api_url = api_url.rstrip("/")

        self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))

        token_endpoint = f"{auth_url.rstrip('/')}/oauth/token"
        logger.info("wiz.authenticate", token_endpoint=token_endpoint)

        resp = await self._client.post(
            token_endpoint,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": "wiz-api",
            },
        )
        resp.raise_for_status()

        self._token = resp.json()["access_token"]
        self._client.headers["Authorization"] = f"Bearer {self._token}"

        logger.info("wiz.authenticated")

    # ------------------------------------------------------------------
    # Internal GraphQL helper
    # ------------------------------------------------------------------

    async def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a single GraphQL request with basic rate-limit handling."""

        assert self._client is not None, "Call authenticate() first"

        url = f"{self._api_url}/graphql"
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        for attempt in range(1, 6):
            resp = await self._client.post(url, json=payload)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                logger.warning(
                    "wiz.rate_limited",
                    attempt=attempt,
                    retry_after=retry_after,
                )
                await asyncio.sleep(retry_after)
                continue

            resp.raise_for_status()
            body = resp.json()

            if "errors" in body:
                logger.error("wiz.graphql_errors", errors=body["errors"])
                raise RuntimeError(f"Wiz GraphQL errors: {body['errors']}")

            return body["data"]

        raise RuntimeError("Wiz rate-limit retries exhausted")

    async def _paginate(self, query: str, root_key: str) -> list[dict[str, Any]]:
        """Paginate through a Wiz GraphQL connection and return all nodes."""

        all_nodes: list[dict[str, Any]] = []
        cursor: str | None = None
        page = 0

        while True:
            page += 1
            variables: dict[str, Any] = {}
            if cursor:
                variables["after"] = cursor

            data = await self._graphql(query, variables)
            connection = data[root_key]
            nodes = connection.get("nodes", [])
            all_nodes.extend(nodes)

            page_info = connection.get("pageInfo", {})
            logger.info(
                "wiz.page_fetched",
                root_key=root_key,
                page=page,
                nodes_in_page=len(nodes),
                total_so_far=len(all_nodes),
            )

            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        return all_nodes

    # ------------------------------------------------------------------
    # Vulnerabilities
    # ------------------------------------------------------------------

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Fetch all open/in-progress vulnerability findings from Wiz."""

        logger.info("wiz.fetch_vulnerabilities.start")
        nodes = await self._paginate(VULNERABILITY_QUERY, "vulnerabilityFindings")
        logger.info("wiz.fetch_vulnerabilities.done", total=len(nodes))

        results: list[NormalizedVulnerability] = []
        for node in nodes:
            asset = node.get("vulnerableAsset") or {}
            results.append(
                NormalizedVulnerability(
                    cve_id=node.get("name"),
                    vulnerability_name=node.get("detailedName") or node.get("name"),
                    cvss_v3_score=node.get("score"),
                    severity=_map_vuln_severity(node.get("severity")),
                    exploit_available=bool(node.get("exploitAvailable") or node.get("hasExploit")),
                    cisa_kev=bool(node.get("hasCisaKevExploit")),
                    source_vuln_id=node.get("id"),
                    hostname=asset.get("name"),
                    ip_addresses=asset.get("ipAddresses") or [],
                    os_name=asset.get("operatingSystem"),
                    affected_version=node.get("version"),
                    fixed_version=node.get("fixedVersion"),
                    remediation_info=node.get("remediation"),
                )
            )

        return results

    # ------------------------------------------------------------------
    # Misconfigurations (CSPM)
    # ------------------------------------------------------------------

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        """Fetch all open/in-progress CSPM configuration findings from Wiz."""

        logger.info("wiz.fetch_misconfigurations.start")
        nodes = await self._paginate(CONFIGURATION_QUERY, "configurationFindings")
        logger.info("wiz.fetch_misconfigurations.done", total=len(nodes))

        results: list[NormalizedMisconfiguration] = []
        for node in nodes:
            rule = node.get("rule") or {}
            resource = node.get("resource") or {}
            framework_refs = rule.get("frameworkReferences") or []

            results.append(
                NormalizedMisconfiguration(
                    rule_id=rule.get("id"),
                    rule_name=rule.get("name"),
                    rule_description=rule.get("description"),
                    severity=_map_misconfig_severity(rule.get("severity")),
                    frameworks=[ref.get("name") for ref in framework_refs if ref.get("name")],
                    resource_id=resource.get("providerUniqueId") or resource.get("id"),
                    resource_name=resource.get("name"),
                    resource_type=resource.get("type"),
                    resource_region=resource.get("region"),
                    cloud_provider=resource.get("cloudPlatform"),
                    cloud_account_id=resource.get("subscriptionId"),
                    cloud_account_name=resource.get("subscriptionName"),
                    source_finding_id=node.get("id"),
                    remediation_info=rule.get("remediationInstructions"),
                )
            )

        return results

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("wiz.client_closed")
