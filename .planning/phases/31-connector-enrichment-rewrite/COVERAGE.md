# Phase 31 — API Coverage Declaration

**Purpose:** Satisfy the seal-time api-coverage gate.

## External data feeds (not a capability-surface API)

This phase downloads two read-only public reference feeds. Neither is an interactive,
multi-verb capability-surface SDK — each exposes a single GET (bulk download), and both
are INTEGRATE (the whole point of the phase). Canonical capability/decision/reason matrix:

| capability | decision | reason |
|---|---|---|
| EPSS daily CSV feed (FIRST.org bulk download, epss_scores-current.csv.gz) | INTEGRATE | Single-purpose read-only GET download; 302→dated snapshot; manual gzip.decompress; ~355k rows into global epss_scores ref table. |
| CISA KEV JSON catalog download (known_exploited_vulnerabilities.json) | INTEGRATE | Single-purpose read-only GET download; {catalogVersion,count,vulnerabilities[]} envelope; ~1,660 entries into global cisa_kev ref table. |

**Reasoned declaration:** No external capability-surface API. This phase downloads two
read-only public reference feeds (EPSS CSV, CISA KEV JSON), not an interactive API. Both
URLs are hardcoded constants, never user/tenant-derived (SSRF N/A — see each PLAN's
`<threat_model>`).
