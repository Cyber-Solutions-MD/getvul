"""GitHub Issues REST API client — creates issues, reads state.

API docs: https://docs.github.com/en/rest/issues
Base URL: https://api.github.com
Auth: Bearer token (PAT or GitHub App installation token)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger()

_GITHUB_API_BASE = "https://api.github.com"


@dataclass
class GitHubIssue:
    """Normalized result of creating or fetching a GitHub issue."""

    id: int
    number: int
    url: str
    title: str
    state: str
    assignee: str | None


class GitHubClient:
    """Client for the GitHub Issues REST API.

    Auth uses a Bearer token (Personal Access Token or GitHub App installation
    token). The token is NEVER logged.
    """

    def __init__(self, token: str, owner: str, repo: str) -> None:
        """Construct the client.

        Args:
            token: A GitHub PAT or App installation token (never logged).
            owner: The repository owner login (user or organization).
            repo: The repository name (without owner prefix).
        """
        self._owner = owner
        self._repo = repo
        self._client = httpx.AsyncClient(
            base_url=_GITHUB_API_BASE,
            timeout=30,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def test_connection(self) -> dict:
        """Probe the GitHub API by fetching the configured repository.

        Returns:
            ``{"success": True, "message": "..."}`` on success, or
            ``{"success": False, "message": "..."}`` on failure.
        """
        try:
            resp = await self._client.get(f"/repos/{self._owner}/{self._repo}")
        except Exception as exc:
            logger.error("github_test_connection_error", error=str(exc))
            return {"success": False, "message": f"Connection error: {exc}"}

        if resp.status_code != 200:
            return {
                "success": False,
                "message": f"Auth failed or repo not found: HTTP {resp.status_code}",
            }

        data = resp.json()
        return {
            "success": True,
            "message": f"Successfully connected to {data.get('full_name', '')}",
        }

    async def create_ticket(self, title: str, body: str) -> GitHubIssue | None:
        """Create a GitHub issue via POST /repos/{owner}/{repo}/issues.

        Returns a :class:`GitHubIssue` on 201, ``None`` on failure.
        """
        payload = {"title": title, "body": body}
        resp = await self._client.post(
            f"/repos/{self._owner}/{self._repo}/issues",
            json=payload,
        )

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning("github_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            resp = await self._client.post(
                f"/repos/{self._owner}/{self._repo}/issues",
                json=payload,
            )

        if resp.status_code != 201:
            logger.error(
                "github_create_ticket_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            return None

        data = resp.json()
        assignee_login: str | None = None
        if data.get("assignee"):
            assignee_login = data["assignee"].get("login")

        return GitHubIssue(
            id=data["id"],
            number=data["number"],
            url=data["html_url"],
            title=data.get("title", title),
            state=data.get("state", "open"),
            assignee=assignee_login,
        )

    async def get_issue(self, number: int) -> dict | None:
        """Fetch a GitHub issue by its number.

        Returns the raw response dict so the caller can read ``state``
        (``"open"``/``"closed"``) for ``external_status``. Returns ``None``
        on failure.
        """
        try:
            resp = await self._client.get(
                f"/repos/{self._owner}/{self._repo}/issues/{number}"
            )
        except Exception as exc:
            logger.error("github_get_issue_error", error=str(exc))
            return None

        if resp.status_code != 200:
            logger.warning(
                "github_get_issue_failed",
                status=resp.status_code,
                number=number,
            )
            return None

        return resp.json()

    async def get_watchers(self) -> list:
        """Return provider-level watchers for an issue.

        GitHub has no per-issue watcher primitive — the platform uses
        notification subscriptions which are not exposed as a per-issue list.
        This stub always returns an empty list so the watcher-union code in
        Plan 03 has a uniform call surface across all providers. Local
        GetVul subscriptions (``ticket_watchers`` table) provide the actual
        watcher data for GitHub-backed tickets.

        See D-W-01 in CONTEXT.md and §Connector Stubs in 13-RESEARCH.md.
        """
        return []

    async def close(self) -> None:
        """Close the underlying httpx client and release connections."""
        await self._client.aclose()
