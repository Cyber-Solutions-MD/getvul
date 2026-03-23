"""
Jira sync — not applicable.

Jira is a ticketing connector, not a data-source connector. It does not
pull vulnerability data into the platform. Ticket creation and lifecycle
management are handled by the ticketing service (see sync.py) which
delegates to ``jira_client.JiraClient``.
"""
