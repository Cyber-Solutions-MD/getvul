# Phase 23 — Deferred Items (out of scope, logged not fixed)

## From Plan 23-01

- **mypy-baseline drift in `app/connectors/google_workspace.py`** (unrelated file,
  not touched by this plan): `mypy app/ | mypy-baseline filter --allow-unsynced`
  reports "new: 3" — all 3 are `note:` lines under the pre-existing
  `Library stubs not installed for "jose"` `import-untyped` error at
  `google_workspace.py:23`. Reproduced identically with 23-01's diff fully
  reverted (stash test), confirming this is pre-existing baseline/mypy-version
  drift, not a regression introduced by 23-01. Verified 23-01's own touched
  files (wiz.py, rapid7.py, nessus.py, tester.py, schemas.py) introduce zero
  new mypy errors — mypy's `override`/`call-arg` baseline entries for
  wiz.py/rapid7.py were *removed* (genuine fixes), not added to.

## From Plan 23-02

- **`app/connectors/qualys.py` — lowercase-only key reads at three sites, no
  uppercase fallback** (discovered while authoring `test_qualys_connector.py`;
  out of scope for this test-authoring plan per D-22/threat model — no
  production code changes made):
  - `_fetch_all_hosts`: `h.get("id")` (id_min pagination cursor)
  - `_fetch_all_detections`: `host_rec.get("id")` (host_id association with detections)
  - `fetch_vulnerabilities`'s KB-prefetch step: `det.get("qid")` (which QIDs get
    knowledge-base-enriched)
  - `_fetch_kb_entries`: `v.get("qid")` (which KB response rows get cached)

  Unlike these four sites, `_normalize_detection` itself checks BOTH cases
  (`detection.get("qid") or detection.get("QID")`, similarly for severity/ip/dns/os).
  Real Qualys XML conventionally uses uppercase `<ID>`/`<QID>` tags — against a
  live API this would silently: (1) break `id_min` cursoring so `_fetch_all_hosts`/
  `_fetch_all_detections` would treat every page as page 1 forever (or never
  paginate past the first page depending on `len(...) < 1000` framing), (2) fail
  to associate any detection with its host (`hosts_by_id.get(host_id)` always
  misses), and (3) leave the knowledge-base cache permanently empty, so every
  vulnerability would ship with the `QID {qid}` fallback title, no CVE, no CVSS,
  no solution — i.e. Qualys VMDR ingestion is very plausibly non-functional for
  most metadata fields against a real tenant, not just untested. The test file
  pins the connector's CURRENT *working* code path (fixture uses lowercase
  `id`/`qid` tags at exactly these four read sites) to genuinely exercise
  pagination/mapping rather than assert a broken path — see the test file's
  module docstring for the full trace. Recommended follow-up: a small,
  low-risk backend fix (dual-case fallback matching `_normalize_detection`'s
  existing pattern) in a future connector-hardening phase, plus a live-tenant
  smoke check if any real Qualys VMDR customer is currently in production.
