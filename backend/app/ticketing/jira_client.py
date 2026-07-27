"""Jira Cloud REST API v3 client — creates issues, reads state.

API docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
Base URL: https://<domain>.atlassian.net
Auth: Basic auth — email:api_token (base64-encoded per RFC 7617)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class JiraIssue:
    """Normalized result of creating or fetching a Jira issue."""

    id: str
    key: str
    url: str
    summary: str
    status: str
    assignee: str | None


def _adf_paragraph(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format (ADF) paragraph node.

    Jira Cloud REST v3 requires ADF for the `description` field.
    https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


class JiraClient:
    """Client for the Jira Cloud REST API v3.

    Auth uses HTTP Basic authentication: `email:api_token` (base64).
    Jira Cloud does NOT accept password-based Basic auth — an API token
    is required. The token is NEVER logged.
    """

    def __init__(self, email: str, api_token: str, base_url: str) -> None:
        """Construct the client.

        Args:
            email: The Atlassian account email address.
            api_token: A Jira API token (never logged, never persisted here).
            base_url: The Jira Cloud base URL, e.g.
                      ``https://acme.atlassian.net``.
        """
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=30,
            auth=httpx.BasicAuth(email, api_token),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def test_connection(self) -> dict:
        """Probe the Jira Cloud API and return the authenticated user info.

        Returns:
            ``{"success": True, "message": "...", "account_id": "..."}`` on
            success, or ``{"success": False, "message": "..."}`` on failure.
        """
        try:
            resp = await self._client.get("/rest/api/3/myself")
        except Exception as exc:
            logger.error("jira_test_connection_error", error=str(exc))
            return {"success": False, "message": f"Connection error: {exc}"}

        if resp.status_code != 200:
            return {
                "success": False,
                "message": f"Auth failed: HTTP {resp.status_code}",
            }

        data = resp.json()
        return {
            "success": True,
            "message": "Successfully authenticated with Jira",
            "account_id": data.get("accountId", ""),
            "display_name": data.get("displayName", ""),
        }

    async def create_ticket(
        self,
        project_key: str,
        summary: str,
        description: str,
        assignee_account_id: str | None = None,
    ) -> JiraIssue | None:
        """Create a Jira issue via POST /rest/api/3/issue.

        The ``description`` is wrapped in ADF automatically — pass plain text.
        Returns a :class:`JiraIssue` on 201, ``None`` on failure.
        """
        fields: dict = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": "Task"},
            "description": _adf_paragraph(description),
        }
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}

        payload = {"fields": fields}
        resp = await self._client.post("/rest/api/3/issue", json=payload)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning("jira_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            resp = await self._client.post("/rest/api/3/issue", json=payload)

        if resp.status_code != 201:
            logger.error(
                "jira_create_ticket_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            return None

        data = resp.json()
        issue_id = data.get("id", "")
        issue_key = data.get("key", "")
        url = f"{self._base_url}/browse/{issue_key}"

        return JiraIssue(
            id=issue_id,
            key=issue_key,
            url=url,
            summary=summary,
            status="",  # not returned by create endpoint; caller can call get_issue
            assignee=assignee_account_id,
        )

    async def get_issue(self, issue_id_or_key: str) -> dict | None:
        """Fetch a Jira issue by ID or key.

        Returns the raw response dict so the caller can read
        ``fields.status.name`` for ``external_status``. Returns ``None`` on
        failure.
        """
        try:
            resp = await self._client.get(f"/rest/api/3/issue/{issue_id_or_key}")
        except Exception as exc:
            logger.error("jira_get_issue_error", error=str(exc))
            return None

        if resp.status_code != 200:
            logger.warning(
                "jira_get_issue_failed",
                status=resp.status_code,
                issue=issue_id_or_key,
            )
            return None

        return resp.json()

    async def comment(self, issue_key: str, body: str) -> None:
        """Post a comment to a Jira issue via POST /rest/api/3/issue/{key}/comment.

        Ported from the deleted legacy connectors Jira client's
        ``update_issue(comment=...)`` (D-08 consolidation) — same call site
        and body text, now ADF-shaped for the v3 API this client already
        uses for ``description``. Logs and returns on failure rather than
        raising, matching this client's existing get/create conventions.
        """
        payload = {"body": _adf_paragraph(body)}
        try:
            resp = await self._client.post(f"/rest/api/3/issue/{issue_key}/comment", json=payload)
        except Exception as exc:
            logger.error("jira_comment_error", issue=issue_key, error=str(exc))
            return

        if resp.status_code not in (200, 201):
            logger.error(
                "jira_comment_failed",
                issue=issue_key,
                status=resp.status_code,
                body=resp.text[:500],
            )

    async def transition(self, issue_key: str, target_status: str) -> None:
        """Transition a Jira issue to ``target_status`` by name.

        Ported from ``update_issue(status=...)`` (D-08 consolidation): GET
        the issue's available transitions, match one by its ``name`` or
        destination ``to.name`` (case-insensitive), then POST that
        transition id. No-ops (logs a warning) if no transition matches,
        mirroring the deleted client's non-raising "not found" behavior.
        """
        try:
            resp = await self._client.get(f"/rest/api/3/issue/{issue_key}/transitions")
        except Exception as exc:
            logger.error("jira_transition_lookup_error", issue=issue_key, error=str(exc))
            return

        if resp.status_code != 200:
            logger.warning(
                "jira_transition_lookup_failed",
                issue=issue_key,
                status=resp.status_code,
            )
            return

        transitions = resp.json().get("transitions", [])
        transition_id: str | None = None
        for t in transitions:
            name = t.get("name", "")
            to_name = t.get("to", {}).get("name", "")
            if target_status.lower() in (name.lower(), to_name.lower()):
                transition_id = t.get("id")
                break

        if transition_id is None:
            available = [t.get("name", "") for t in transitions]
            logger.warning(
                "jira_transition_not_found",
                issue=issue_key,
                requested=target_status,
                available=available,
            )
            return

        try:
            resp = await self._client.post(
                f"/rest/api/3/issue/{issue_key}/transitions",
                json={"transition": {"id": transition_id}},
            )
        except Exception as exc:
            logger.error("jira_transition_post_error", issue=issue_key, error=str(exc))
            return

        if resp.status_code not in (200, 204):
            logger.error(
                "jira_transition_failed",
                issue=issue_key,
                status=resp.status_code,
                body=resp.text[:500],
            )

    async def close_issue(self, issue_key: str) -> None:
        """Transition an issue to the tenant's done status ('Done').

        Thin wrapper matching the GitHubClient's create/get/comment/close
        surface (D-12) so ``JiraAdapter.close`` in dispatch.py can dispatch
        uniformly. Named ``close_issue`` — not ``close`` — because this
        class's existing ``close()`` is unrelated HTTP-client cleanup (see
        below); reusing that name would silently shadow it.
        """
        await self.transition(issue_key, "Done")

    async def close(self) -> None:
        """Close the underlying httpx client and release connections."""
        await self._client.aclose()
