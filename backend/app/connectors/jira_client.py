"""
Jira Cloud/Server REST API client for vulnerability ticket management.

Uses Jira REST API v2 with Basic authentication (email + API token).
This is a standalone API client, NOT a BaseConnector subclass.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class JiraClient:
    """Jira REST API client for vulnerability ticket management."""

    def __init__(self, url: str, email: str, api_token: str):
        self.base_url = url.rstrip("/")
        self.email = email
        self._api_url = f"{self.base_url}/rest/api/2"

        credentials = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def test_connection(self) -> dict:
        """Test the Jira connection by fetching the authenticated user.

        GET /rest/api/2/myself

        Returns:
            dict with ``success`` bool and user information on success,
            or ``error`` string on failure.
        """
        try:
            resp = await self._client.get(f"{self._api_url}/myself")
            resp.raise_for_status()
            data = resp.json()
            logger.info("jira.test_connection.success", user=data.get("emailAddress"))
            return {
                "success": True,
                "display_name": data.get("displayName"),
                "email": data.get("emailAddress"),
                "account_id": data.get("accountId"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("jira.test_connection.http_error", status=exc.response.status_code)
            return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
        except Exception as exc:
            logger.error("jira.test_connection.error", error=str(exc))
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def list_projects(self) -> list[dict]:
        """List all accessible Jira projects.

        GET /rest/api/2/project

        Returns:
            List of dicts with ``key``, ``name``, and ``id`` for each project.
        """
        try:
            resp = await self._client.get(f"{self._api_url}/project")
            resp.raise_for_status()
            projects = resp.json()
            logger.info("jira.list_projects.success", count=len(projects))
            return [
                {"key": p["key"], "name": p["name"], "id": p["id"]}
                for p in projects
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("jira.list_projects.http_error", status=exc.response.status_code)
            raise
        except Exception as exc:
            logger.error("jira.list_projects.error", error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: str = "Medium",
        assignee_email: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """Create a new Jira issue.

        POST /rest/api/2/issue

        Returns:
            dict with ``key``, ``id``, and ``url`` of the created issue.
        """
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
        if labels:
            fields["labels"] = labels
        if assignee_email:
            fields["assignee"] = {"emailAddress": assignee_email}

        try:
            resp = await self._client.post(
                f"{self._api_url}/issue",
                json={"fields": fields},
            )
            resp.raise_for_status()
            data = resp.json()
            issue_key = data["key"]
            issue_id = data["id"]
            issue_url = f"{self.base_url}/browse/{issue_key}"
            logger.info("jira.create_issue.success", key=issue_key)
            return {"key": issue_key, "id": issue_id, "url": issue_url}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "jira.create_issue.http_error",
                status=exc.response.status_code,
                body=exc.response.text,
            )
            raise
        except Exception as exc:
            logger.error("jira.create_issue.error", error=str(exc))
            raise

    async def update_issue(
        self,
        issue_key: str,
        comment: str | None = None,
        status: str | None = None,
    ) -> dict:
        """Update an existing Jira issue by adding a comment and/or transitioning its status.

        - Comment: POST /rest/api/2/issue/{issue_key}/comment
        - Status transition: GET transitions, then POST the matching transition.

        Returns:
            dict summarising what was updated.
        """
        result: dict[str, Any] = {"issue_key": issue_key, "updated": []}

        # --- Add comment ------------------------------------------------
        if comment:
            try:
                resp = await self._client.post(
                    f"{self._api_url}/issue/{issue_key}/comment",
                    json={"body": comment},
                )
                resp.raise_for_status()
                result["updated"].append("comment")
                logger.info("jira.update_issue.comment_added", key=issue_key)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "jira.update_issue.comment_error",
                    key=issue_key,
                    status=exc.response.status_code,
                )
                raise

        # --- Transition status ------------------------------------------
        if status:
            try:
                # Fetch available transitions
                resp = await self._client.get(
                    f"{self._api_url}/issue/{issue_key}/transitions"
                )
                resp.raise_for_status()
                transitions = resp.json().get("transitions", [])

                transition_id: str | None = None
                for t in transitions:
                    if t["name"].lower() == status.lower():
                        transition_id = t["id"]
                        break

                if transition_id is None:
                    available = [t["name"] for t in transitions]
                    logger.warning(
                        "jira.update_issue.transition_not_found",
                        key=issue_key,
                        requested=status,
                        available=available,
                    )
                    result["transition_error"] = (
                        f"Transition '{status}' not found. "
                        f"Available: {available}"
                    )
                else:
                    resp = await self._client.post(
                        f"{self._api_url}/issue/{issue_key}/transitions",
                        json={"transition": {"id": transition_id}},
                    )
                    resp.raise_for_status()
                    result["updated"].append("status")
                    logger.info(
                        "jira.update_issue.transitioned",
                        key=issue_key,
                        status=status,
                    )
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "jira.update_issue.transition_error",
                    key=issue_key,
                    status_code=exc.response.status_code,
                )
                raise

        return result

    async def get_issue(self, issue_key: str) -> dict:
        """Fetch a single Jira issue by key.

        GET /rest/api/2/issue/{issue_key}

        Returns:
            Full issue payload as returned by the Jira API.
        """
        try:
            resp = await self._client.get(f"{self._api_url}/issue/{issue_key}")
            resp.raise_for_status()
            logger.info("jira.get_issue.success", key=issue_key)
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "jira.get_issue.http_error",
                key=issue_key,
                status=exc.response.status_code,
            )
            raise
        except Exception as exc:
            logger.error("jira.get_issue.error", key=issue_key, error=str(exc))
            raise

    async def delete_issue(self, issue_key: str) -> bool:
        """Delete a Jira issue.

        DELETE /rest/api/2/issue/{issue_key}

        Returns:
            True if the issue was deleted successfully, False otherwise.
        """
        try:
            resp = await self._client.delete(f"{self._api_url}/issue/{issue_key}")
            resp.raise_for_status()
            logger.info("jira.delete_issue.success", key=issue_key)
            return True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "jira.delete_issue.http_error",
                key=issue_key,
                status=exc.response.status_code,
            )
            return False
        except Exception as exc:
            logger.error("jira.delete_issue.error", key=issue_key, error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_issues(self, jql: str, max_results: int = 50) -> list[dict]:
        """Search for Jira issues using JQL.

        POST /rest/api/2/search

        Returns:
            List of issue dicts from the search results.
        """
        try:
            resp = await self._client.post(
                f"{self._api_url}/search",
                json={"jql": jql, "maxResults": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
            issues = data.get("issues", [])
            logger.info("jira.search_issues.success", jql=jql, count=len(issues))
            return issues
        except httpx.HTTPStatusError as exc:
            logger.error(
                "jira.search_issues.http_error",
                status=exc.response.status_code,
                body=exc.response.text,
            )
            raise
        except Exception as exc:
            logger.error("jira.search_issues.error", error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
        logger.info("jira.client.closed")
