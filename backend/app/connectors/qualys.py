"""Qualys VMDR vulnerability scanner connector."""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedVulnerability

logger = structlog.get_logger(__name__)

SEVERITY_MAP = {
    1: "INFO",
    2: "LOW",
    3: "MEDIUM",
    4: "HIGH",
    5: "CRITICAL",
}

# Maximum QIDs to look up in a single knowledge-base request.
_KB_BATCH_SIZE = 50


class QualysConnector(BaseConnector):
    """Connector for Qualys VMDR vulnerability management platform."""

    source_name = "QUALYS"

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._base_url: str = ""
        # In-memory cache of knowledge-base entries keyed by QID.
        self._kb_cache: dict[int, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(
        self,
        credentials: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> bool:
        """Authenticate to the Qualys platform using Basic auth.

        ``credentials`` must contain:
        - ``url``      – base URL, e.g. ``https://qualysapi.qualys.com``
        - ``username`` – Qualys API username
        - ``password`` – Qualys API password
        """
        config = config or {}

        username = credentials.get("username", "")
        password = credentials.get("password", "")
        self._base_url = credentials.get("url", "").rstrip("/")

        if not all([username, password, self._base_url]):
            logger.error("qualys.authenticate.missing_credentials")
            return False

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            auth=(username, password),
            headers={
                "X-Requested-With": "Python",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(120.0),
        )

        try:
            # Simple connectivity check – list hosts with limit=1
            resp = await self._client.get(
                "/api/2.0/fo/asset/host/",
                params={"action": "list", "truncation_limit": 1},
            )
            resp.raise_for_status()
            logger.info(
                "qualys.authenticate.success",
                base_url=self._base_url,
            )
            return True
        except Exception as exc:
            logger.error("qualys.authenticate.failed", error=str(exc))
            await self.close()
            return False

    # ------------------------------------------------------------------
    # Fetch vulnerabilities
    # ------------------------------------------------------------------

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Retrieve vulnerabilities from Qualys VMDR."""
        if self._client is None:
            raise RuntimeError("Not authenticated – call authenticate() first")

        # Step 1 – fetch all hosts
        hosts_by_id = await self._fetch_all_hosts()
        logger.info("qualys.hosts.fetched", total=len(hosts_by_id))

        # Step 2 – fetch all vulnerability detections
        detections = await self._fetch_all_detections()
        logger.info("qualys.detections.fetched", total=len(detections))

        # Step 3 – collect unique QIDs and fetch KB entries
        unique_qids: set[int] = set()
        for det in detections:
            qid = det.get("qid")
            if qid is not None:
                unique_qids.add(int(qid))

        await self._fetch_kb_entries(unique_qids)
        logger.info("qualys.kb.fetched", cached=len(self._kb_cache))

        # Step 4 – normalise
        results: list[NormalizedVulnerability] = []
        for det in detections:
            host_id = det.get("host_id")
            host = hosts_by_id.get(host_id, {})
            normalized = _normalize_detection(det, host, self._kb_cache)
            results.extend(normalized)

        logger.info("qualys.fetch_vulnerabilities.done", total=len(results))
        return results

    # ------------------------------------------------------------------
    # Internal API helpers – hosts
    # ------------------------------------------------------------------

    async def _fetch_all_hosts(self) -> dict[int, dict[str, Any]]:
        """Paginate through /api/2.0/fo/asset/host/ and return hosts keyed by ID."""
        assert self._client is not None

        hosts: dict[int, dict[str, Any]] = {}
        id_min: int = 0

        while True:
            params: dict[str, Any] = {
                "action": "list",
                "truncation_limit": 1000,
            }
            if id_min > 0:
                params["id_min"] = id_min

            resp = await self._request_with_rate_limit(
                "GET", "/api/2.0/fo/asset/host/", params=params,
            )
            data = _parse_response(resp)

            host_list = _extract_list(data, "host")
            if not host_list:
                break

            max_id = 0
            for h in host_list:
                hid = _int(h.get("id"))
                if hid is None:
                    continue
                hosts[hid] = h
                if hid > max_id:
                    max_id = hid

            logger.info(
                "qualys.hosts.page",
                fetched=len(host_list),
                cumulative=len(hosts),
            )

            # If we received fewer than the limit we are done.
            if len(host_list) < 1000:
                break

            id_min = max_id + 1
            await asyncio.sleep(0.5)

        return hosts

    # ------------------------------------------------------------------
    # Internal API helpers – detections
    # ------------------------------------------------------------------

    async def _fetch_all_detections(self) -> list[dict[str, Any]]:
        """Paginate through host VM detections."""
        assert self._client is not None

        all_detections: list[dict[str, Any]] = []
        id_min: int = 0

        while True:
            params: dict[str, Any] = {
                "action": "list",
                "truncation_limit": 1000,
                "status": "New,Active,Re-Opened",
                "show_igs": 0,
            }
            if id_min > 0:
                params["id_min"] = id_min

            resp = await self._request_with_rate_limit(
                "GET",
                "/api/2.0/fo/asset/host/vm/detection/",
                params=params,
            )
            data = _parse_response(resp)

            # Detections are nested under host records.
            host_records = _extract_list(data, "host")
            page_detections: list[dict[str, Any]] = []
            max_id = 0

            for host_rec in host_records:
                host_id = _int(host_rec.get("id"))
                dets = _extract_list(host_rec, "detection")
                for d in dets:
                    d["host_id"] = host_id
                    page_detections.append(d)
                if host_id is not None and host_id > max_id:
                    max_id = host_id

            if not page_detections:
                break

            all_detections.extend(page_detections)
            logger.info(
                "qualys.detections.page",
                fetched=len(page_detections),
                cumulative=len(all_detections),
            )

            if len(host_records) < 1000:
                break

            id_min = max_id + 1
            await asyncio.sleep(0.5)

        return all_detections

    # ------------------------------------------------------------------
    # Internal API helpers – knowledge base
    # ------------------------------------------------------------------

    async def _fetch_kb_entries(self, qids: set[int]) -> None:
        """Fetch KB entries for the given QIDs in batches of 50."""
        assert self._client is not None

        # Remove already-cached QIDs.
        to_fetch = sorted(qids - set(self._kb_cache.keys()))
        if not to_fetch:
            return

        for i in range(0, len(to_fetch), _KB_BATCH_SIZE):
            batch = to_fetch[i : i + _KB_BATCH_SIZE]
            ids_str = ",".join(str(q) for q in batch)

            resp = await self._request_with_rate_limit(
                "GET",
                "/api/2.0/fo/knowledge_base/vuln/",
                params={"action": "list", "ids": ids_str},
            )
            data = _parse_response(resp)

            vuln_list = _extract_list(data, "vuln")
            for v in vuln_list:
                qid = _int(v.get("qid"))
                if qid is not None:
                    self._kb_cache[qid] = v

            logger.info(
                "qualys.kb.batch",
                requested=len(batch),
                received=len(vuln_list),
            )
            await asyncio.sleep(0.25)

    # ------------------------------------------------------------------
    # Rate-limit aware request helper
    # ------------------------------------------------------------------

    async def _request_with_rate_limit(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        _retries: int = 3,
    ) -> httpx.Response:
        """Execute a request, honouring Qualys rate-limit headers."""
        assert self._client is not None

        for attempt in range(1, _retries + 1):
            try:
                resp = await self._client.request(method, url, params=params)
            except httpx.TimeoutException:
                if attempt == _retries:
                    raise
                logger.warning(
                    "qualys.request.timeout",
                    url=url,
                    attempt=attempt,
                )
                await asyncio.sleep(5 * attempt)
                continue

            # Qualys returns 409 when rate-limited.
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                try:
                    remaining_int = int(remaining)
                except ValueError:
                    remaining_int = 100
                if remaining_int <= 2:
                    wait = int(resp.headers.get("X-RateLimit-ToWait-Sec", "30"))
                    logger.warning(
                        "qualys.rate_limit.near",
                        remaining=remaining_int,
                        waiting=wait,
                    )
                    await asyncio.sleep(wait)

            if resp.status_code == 409:
                wait = int(resp.headers.get("X-RateLimit-ToWait-Sec", "60"))
                logger.warning(
                    "qualys.rate_limit.hit",
                    waiting=wait,
                    attempt=attempt,
                )
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            return resp

        # Should not be reached, but satisfy the type checker.
        raise RuntimeError("qualys: request retries exhausted")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("qualys.client.closed")


# ======================================================================
# Response parsing helpers
# ======================================================================


def _parse_response(resp: httpx.Response) -> Any:
    """Parse a Qualys API response.

    Tries JSON first; falls back to simple XML parsing if the
    ``Content-Type`` indicates XML.
    """
    content_type = resp.headers.get("Content-Type", "")

    # Attempt JSON first (our Accept header requests it).
    if "json" in content_type:
        try:
            return resp.json()
        except Exception:
            pass

    # Attempt XML parsing.
    if "xml" in content_type or resp.text.lstrip().startswith("<?xml"):
        try:
            return _xml_to_dict(ET.fromstring(resp.text))
        except ET.ParseError:
            pass

    # Last resort: try JSON anyway (some Qualys endpoints ignore Accept).
    try:
        return resp.json()
    except Exception:
        pass

    # Return raw text wrapped in a dict so callers always get a dict.
    return {"_raw": resp.text}


def _xml_to_dict(element: ET.Element) -> dict[str, Any]:
    """Recursively convert an XML Element to a nested dict/list structure.

    Repeated child tag names are collected into lists automatically.
    """
    result: dict[str, Any] = {}

    for child in element:
        tag = child.tag
        child_data: Any
        if len(child):
            child_data = _xml_to_dict(child)
        else:
            child_data = (child.text or "").strip()

        if tag in result:
            existing = result[tag]
            if isinstance(existing, list):
                existing.append(child_data)
            else:
                result[tag] = [existing, child_data]
        else:
            result[tag] = child_data

    return result


def _extract_list(data: Any, key: str) -> list[dict[str, Any]]:
    """Robustly extract a list of dicts from parsed response data.

    Qualys nesting can look like:
    - ``{"HOST_LIST_OUTPUT": {"RESPONSE": {"HOST_LIST": {"HOST": [...]}}}}``
    - or a flat ``{"host": [...]}``

    This helper searches recursively for the target *key* (case-insensitive)
    and returns it as a list.
    """
    if not isinstance(data, dict):
        return []

    key_lower = key.lower()

    for k, v in data.items():
        if k.lower() == key_lower:
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                return [v]
            return []

    # Recurse one level deeper.
    for v in data.values():
        if isinstance(v, dict):
            found = _extract_list(v, key)
            if found:
                return found

    return []


def _int(value: Any) -> int | None:
    """Safely cast a value to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    """Safely cast a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ======================================================================
# Normalisation helpers
# ======================================================================


def _parse_os(raw: str) -> tuple[str, str]:
    """Best-effort parse of an OS string into (name, version)."""
    if not raw:
        return ("", "")

    match = re.search(r"(\d+(?:\.\d+)+)\s*$", raw)
    if match:
        version = match.group(1)
        name = raw[: match.start()].strip()
        return (name or raw, version)

    return (raw, "")


def _kb_cves(kb: dict[str, Any]) -> list[str]:
    """Extract CVE identifiers from a KB entry."""
    cves: list[str] = []

    # JSON variant: {"CVE_LIST": {"CVE": [{"ID": "CVE-..."}]}}
    cve_data = kb.get("CVE_LIST") or kb.get("cve_list") or {}
    if isinstance(cve_data, dict):
        items = cve_data.get("CVE") or cve_data.get("cve") or []
        if isinstance(items, dict):
            items = [items]
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    cve_id = item.get("ID") or item.get("id") or ""
                    if cve_id:
                        cves.append(str(cve_id))
                elif isinstance(item, str) and item.startswith("CVE-"):
                    cves.append(item)

    return cves


def _kb_cvss3(kb: dict[str, Any]) -> float | None:
    """Extract CVSS v3 base score from a KB entry."""
    # Try nested path: CVSS_V3 -> BASE or cvss_v3 -> base
    for outer_key in ("CVSS_V3", "cvss_v3", "CVSS3", "cvss3"):
        block = kb.get(outer_key)
        if isinstance(block, dict):
            for inner_key in ("BASE", "base", "BASE_SCORE", "base_score"):
                val = _float(block.get(inner_key))
                if val is not None:
                    return val

    # Flat key
    return _float(kb.get("CVSS3_BASE") or kb.get("cvss3_base"))


def _kb_exploit_available(kb: dict[str, Any]) -> bool:
    """Check if the KB entry indicates exploit availability."""
    # Presence of an exploit list
    for key in ("EXPLOIT_LIST", "exploit_list"):
        val = kb.get(key)
        if val:
            return True

    # is_patchable can sometimes hint at active exploitation context
    for key in ("IS_PATCHABLE", "is_patchable"):
        val = kb.get(key)
        if val and str(val).lower() in ("1", "true", "yes"):
            return True

    return False


def _kb_solution(kb: dict[str, Any]) -> str | None:
    """Extract solution / remediation text from a KB entry."""
    for key in ("SOLUTION", "solution"):
        val = kb.get(key)
        if val and isinstance(val, str):
            return val
        if isinstance(val, dict):
            # Sometimes nested as {"TEXT": "..."}
            return val.get("TEXT") or val.get("text") or str(val)
    return None


def _normalize_detection(
    detection: dict[str, Any],
    host: dict[str, Any],
    kb_cache: dict[int, dict[str, Any]],
) -> list[NormalizedVulnerability]:
    """Convert a single Qualys detection into one or more NormalizedVulnerability."""
    qid = _int(detection.get("qid") or detection.get("QID"))
    if qid is None:
        return []

    severity_int = _int(detection.get("severity") or detection.get("SEVERITY")) or 1
    severity = SEVERITY_MAP.get(severity_int, "INFO")

    # Host metadata
    host_ip = str(host.get("ip") or host.get("IP") or "")
    host_dns = str(host.get("dns") or host.get("DNS") or host.get("dns_name") or "")
    os_raw = str(host.get("os") or host.get("OS") or "")
    os_name, os_version = _parse_os(os_raw)
    hostname = host_dns or host_ip

    # KB enrichment
    kb = kb_cache.get(qid, {})
    vuln_name = str(
        kb.get("TITLE") or kb.get("title") or f"QID {qid}"
    )
    cvss3 = _kb_cvss3(kb)
    cves = _kb_cves(kb)
    exploit_available = _kb_exploit_available(kb)
    solution = _kb_solution(kb)

    base = dict(
        vulnerability_name=vuln_name,
        cvss_v3_score=cvss3,
        severity=severity,
        source_vuln_id=str(qid),
        remediation_info=solution,
        hostname=hostname or None,
        ip_addresses=[host_ip] if host_ip else [],
        os_name=os_name or None,
        os_version=os_version or None,
        exploit_available=exploit_available,
    )

    results: list[NormalizedVulnerability] = []

    if cves:
        for cve in cves:
            results.append(NormalizedVulnerability(cve_id=cve, **base))
    else:
        results.append(
            NormalizedVulnerability(cve_id=f"QID-{qid}", **base)
        )

    return results
