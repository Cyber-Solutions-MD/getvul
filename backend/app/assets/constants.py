"""Phase 35 Plan 03 (SRC-06) — scanner vs enrichment source-class partition.

Assets' `seen_by_sources` column carries values from two different
provenance classes that must never be conflated in a filter:

  - SCANNER_SOURCES: real vulnerability scanners (the `VulnSource` enum) —
    the class eligible for OR/AND multi-scanner *corroboration* semantics
    (`?scanner=`/`?source_mode=`).
  - ENRICHMENT_SOURCES: MDM/HR enrichment feeds (JAMF, HUMAANS, Intune) —
    presence facts, not corroboration signals. Exposed only via the
    separate `?enrichment_source=` OR-only facet (Pattern 3, CONTEXT.md).

Mirrors the frozenset allow-list convention already established by
`vulnerabilities/service.py:31` (`_ALLOWED_FACET_GROUPS`). Imported by BOTH
`assets/router.py::list_assets` and `ticketing/rule_engine.py::
find_matching_assets` so the two call sites (same 2-line AND-bug, per
CONTEXT.md "Real bug to fix") clamp against the identical partition.
"""

from __future__ import annotations

from app.vulnerabilities.models import VulnSource

SCANNER_SOURCES: frozenset[str] = frozenset(s.value for s in VulnSource)
ENRICHMENT_SOURCES: frozenset[str] = frozenset({"JAMF", "HUMAANS", "INTUNE"})
