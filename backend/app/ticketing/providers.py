"""TicketProvider — the single source of truth for the ASANA/JIRA/GITHUB
provider identifier used across the ticketing subsystem (D-23).

Wire convention (CR-06): stored/compared UPPERCASE on the backend; only
lowercased at the serialization boundary (existing emit sites are
unchanged by this module).
"""

from __future__ import annotations

from enum import Enum


class TicketProvider(str, Enum):
    """Supported ticket-creation providers."""

    ASANA = "ASANA"
    JIRA = "JIRA"
    GITHUB = "GITHUB"
