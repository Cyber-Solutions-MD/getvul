# Phase 31 — API Coverage Declaration

**Purpose:** Satisfy the seal-time api-coverage gate.

## External data feeds (not a capability-surface API)

This phase downloads two read-only public reference feeds. Neither is an interactive,
multi-verb capability-surface SDK, so there is no verb matrix to cover.

| Feed | Verb | Disposition | Notes |
|------|------|-------------|-------|
| EPSS (FIRST.org daily CSV) — `https://epss.empiricalsecurity.com/epss_scores-current.csv.gz` | GET (download) | INTEGRATE | Single-purpose bulk download; 302-redirect → dated snapshot; gzip payload (no `Content-Encoding` header — manual `gzip.decompress`); ~355k rows; header comment line skipped before `csv.DictReader`. |
| CISA KEV (JSON catalog) — `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | GET (download) | INTEGRATE | Single-purpose download; `{catalogVersion,count,vulnerabilities[]}` envelope; ~1,660 entries; plain `resp.json()`. |

**Reasoned declaration:** No external capability-surface API. This phase downloads two
read-only public reference feeds (EPSS CSV, CISA KEV JSON), not an interactive API. Both
URLs are hardcoded constants, never user/tenant-derived (SSRF N/A — see each PLAN's
`<threat_model>`).
