"""Compliance package (Phase 43 Plan 01 -- RPT-03 tracer slice).

Bundles the built-in framework-control catalog (`catalog.py`), the
compute-once-per-read posture metric service (`service.py`), and the
tenant-scoped `require_viewer` read endpoint (`router.py`) that together
evidence SOC 2 / ISO 27001 / PCI DSS / NIST CSF control status from
existing posture metrics (D-08/D-09/D-13) -- never per-CVE tagging, never
a new table or cache.
"""

from __future__ import annotations
