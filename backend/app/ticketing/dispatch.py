"""TicketingClient Protocol + per-provider adapters + factory (D-06).

Today ticket dispatch is scattered `if provider == "ASANA"` branches, each
speaking the concrete client's own method names (`create_task` vs
`create_ticket`; `get_task` vs `get_issue`). This module normalizes all
three clients onto one create/get/comment/close verb surface via thin
adapters — the concrete clients' method names are NOT renamed, only wrapped.

Credential decryption stays OUT of this module: callers (Plan 04's helpers)
must pass already-decrypted credentials into `build_ticketing_client`.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.ticketing.asana_client import AsanaClient
from app.ticketing.github_client import GitHubClient
from app.ticketing.jira_client import JiraClient
from app.ticketing.providers import TicketProvider


@runtime_checkable
class TicketingClient(Protocol):
    """Common create/get/comment/close verb surface for all ticket providers."""

    async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
        """Create a ticket. Returns the external ticket URL/id, or None on failure."""
        ...

    async def get(self, ref: str) -> dict | None:
        """Fetch a ticket's raw provider payload by its external ref."""
        ...

    async def comment(self, ref: str, body: str) -> None:
        """Post a status/progress comment on the ticket."""
        ...

    async def close(self, ref: str) -> None:
        """Mark the ticket resolved/closed on the provider."""
        ...


class AsanaAdapter:
    """Adapts AsanaClient's task-oriented verbs to the TicketingClient protocol."""

    def __init__(self, client: AsanaClient, *, workspace_gid: str, project_gid: str) -> None:
        self._client = client
        self._workspace_gid = workspace_gid
        self._project_gid = project_gid

    async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
        task = await self._client.create_task(
            workspace_gid=self._workspace_gid,
            project_gid=self._project_gid,
            name=title,
            notes=body,
            **kwargs,
        )
        return task.url if task else None

    async def get(self, ref: str) -> dict | None:
        return await self._client.get_task(ref)

    async def comment(self, ref: str, body: str) -> None:
        await self._client.add_comment(ref, body)

    async def close(self, ref: str) -> None:
        await self._client.update_task(ref, completed=True)


class JiraAdapter:
    """Adapts JiraClient's issue-oriented verbs to the TicketingClient protocol."""

    def __init__(self, client: JiraClient, *, project_key: str) -> None:
        self._client = client
        self._project_key = project_key

    async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
        issue = await self._client.create_ticket(
            project_key=self._project_key,
            summary=title,
            description=body,
            **kwargs,
        )
        return issue.url if issue else None

    async def get(self, ref: str) -> dict | None:
        return await self._client.get_issue(ref)

    async def comment(self, ref: str, body: str) -> None:
        await self._client.comment(ref, body)

    async def close(self, ref: str) -> None:
        # Named close_issue on the concrete client (not close()) — close()
        # is already the HTTP-cleanup method inherited from the pre-existing
        # canonical JiraClient; see 23-03-SUMMARY.md deviations.
        await self._client.close_issue(ref)


class GitHubAdapter:
    """Adapts GitHubClient's issue-oriented verbs to the TicketingClient protocol."""

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
        issue = await self._client.create_ticket(title=title, body=body)
        return issue.url if issue else None

    async def get(self, ref: str) -> dict | None:
        return await self._client.get_issue(int(ref))

    async def comment(self, ref: str, body: str) -> None:
        await self._client.add_comment(int(ref), body)

    async def close(self, ref: str) -> None:
        await self._client.close_issue(int(ref))


def build_ticketing_client(
    provider: TicketProvider, credentials: dict[str, Any], config: dict[str, Any]
) -> TicketingClient:
    """Construct the adapter+client pair for `provider`.

    Args:
        provider: which ticketing provider to dispatch to.
        credentials: ALREADY-DECRYPTED provider credentials (this module
            never touches Fernet or ConnectorConfig).
        config: provider-specific routing needed at create-time (Asana
            workspace_gid/project_gid, Jira project_key, GitHub owner/repo).

    Returns:
        A `TicketingClient`-shaped adapter wrapping a freshly-constructed
        concrete client.
    """
    if provider == TicketProvider.ASANA:
        asana_client = AsanaClient(credentials.get("access_token", ""))
        return AsanaAdapter(
            asana_client,
            workspace_gid=config.get("workspace_gid", ""),
            project_gid=config.get("project_gid", ""),
        )
    if provider == TicketProvider.JIRA:
        jira_client = JiraClient(
            email=credentials.get("email", ""),
            api_token=credentials.get("api_token", ""),
            base_url=credentials.get("url", ""),
        )
        return JiraAdapter(jira_client, project_key=config.get("project_key", ""))
    if provider == TicketProvider.GITHUB:
        github_client = GitHubClient(
            token=credentials.get("token", ""),
            owner=config.get("owner", ""),
            repo=config.get("repo", ""),
        )
        return GitHubAdapter(github_client)

    raise ValueError(f"Unsupported ticket provider: {provider!r}")
