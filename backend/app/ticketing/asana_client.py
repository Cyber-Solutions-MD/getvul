"""Asana API client — creates tasks, adds comments, resolves users.

API docs: https://developers.asana.com/reference
Base URL: https://app.asana.com/api/1.0
Auth: Bearer token (Personal Access Token or Service Account)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger()

BASE_URL = "https://app.asana.com/api/1.0"


@dataclass
class AsanaTask:
    """Result of creating or fetching an Asana task."""
    gid: str
    name: str
    url: str
    assignee: str | None
    completed: bool
    due_on: str | None


class AsanaClient:
    """Client for the Asana REST API."""

    def __init__(self, access_token: str) -> None:
        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def test_connection(self) -> dict:
        """Test the token and return user info + workspaces."""
        resp = await self.client.get("/users/me")
        if resp.status_code != 200:
            return {"success": False, "message": f"Auth failed: HTTP {resp.status_code}"}

        me = resp.json().get("data", {})

        # Get workspaces
        ws_resp = await self.client.get("/workspaces", params={"limit": 50})
        workspaces = []
        if ws_resp.status_code == 200:
            workspaces = [
                {"gid": w["gid"], "name": w["name"]}
                for w in ws_resp.json().get("data", [])
            ]

        return {
            "success": True,
            "message": "Successfully authenticated with Asana",
            "user": me.get("name", ""),
            "email": me.get("email", ""),
            "workspaces": workspaces,
        }

    async def list_projects(self, workspace_gid: str) -> list[dict]:
        """List projects in a workspace."""
        projects = []
        offset = None

        while True:
            params: dict = {"workspace": workspace_gid, "limit": 100, "opt_fields": "name,archived"}
            if offset:
                params["offset"] = offset

            resp = await self.client.get("/projects", params=params)
            if resp.status_code != 200:
                break

            data = resp.json()
            for p in data.get("data", []):
                if not p.get("archived", False):
                    projects.append({"gid": p["gid"], "name": p["name"]})

            next_page = data.get("next_page")
            if not next_page:
                break
            offset = next_page.get("offset")

        return projects

    async def find_user_by_email(self, workspace_gid: str, email: str) -> str | None:
        """Find an Asana user GID by email address. Returns None if not found."""
        try:
            resp = await self.client.get(f"/users/{email}", params={"opt_fields": "gid,name,email"})
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("gid")
        except Exception:
            pass
        return None

    async def create_task(
        self,
        workspace_gid: str,
        project_gid: str,
        name: str,
        notes: str | None = None,
        html_notes: str | None = None,
        assignee: str | None = None,
        due_on: str | None = None,
        tags: list[str] | None = None,
    ) -> AsanaTask | None:
        """Create a task in Asana. Assignee can be a user GID or email."""
        task_data: dict = {
            "workspace": workspace_gid,
            "projects": [project_gid],
            "name": name,
        }
        if html_notes:
            task_data["html_notes"] = html_notes
        elif notes:
            task_data["notes"] = notes
        if assignee:
            task_data["assignee"] = assignee
        if due_on:
            task_data["due_on"] = due_on
        if tags:
            task_data["tags"] = tags

        resp = await self.client.post("/tasks", json={"data": task_data})

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning("asana_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            resp = await self.client.post("/tasks", json={"data": task_data})

        if resp.status_code not in (200, 201):
            logger.error("asana_create_task_failed", status=resp.status_code, body=resp.text[:500])
            return None

        data = resp.json().get("data", {})
        gid = data.get("gid", "")
        return AsanaTask(
            gid=gid,
            name=data.get("name", name),
            url=f"https://app.asana.com/0/{project_gid}/{gid}",
            assignee=data.get("assignee", {}).get("gid") if data.get("assignee") else None,
            completed=data.get("completed", False),
            due_on=data.get("due_on"),
        )

    async def add_comment(self, task_gid: str, text: str) -> bool:
        """Add a comment to a task."""
        resp = await self.client.post(
            f"/tasks/{task_gid}/stories",
            json={"data": {"text": text}},
        )
        return resp.status_code in (200, 201)

    async def get_task(self, task_gid: str) -> dict | None:
        """Get task details."""
        resp = await self.client.get(
            f"/tasks/{task_gid}",
            params={"opt_fields": "gid,name,completed,completed_at,assignee,due_on,permalink_url"},
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("data")

    async def update_task(self, task_gid: str, **fields) -> bool:
        """Update task fields (completed, assignee, due_on, etc.)."""
        resp = await self.client.put(f"/tasks/{task_gid}", json={"data": fields})
        return resp.status_code == 200

    async def close(self) -> None:
        await self.client.aclose()
