---
status: partial
phase: 44-natural-language-query-assistant
source: [44-VERIFICATION.md, 44-04-SUMMARY.md]
started: 2026-08-25
updated: 2026-08-25
note: "The 1 live item (full Ask flow with a BYOK key + interactive browser) was accepted as tracked debt by the user at phase close (2026-08-25), consistent with the 24/26/27/40 proceed-on-trust precedent. Plan 44-04 carried an explicit checkpoint:human-verify (autonomous:false); all 8 code-level must-haves and 222 automated tests pass (zero gaps, zero regressions). This item requires a live Docker stack + a configured tenant Anthropic key + browser observation, none available in the headless run. Re-run /gsd-verify-work 44 once available."
---

## Current Test

[testing paused — the 1 live item is blocked on prerequisites (configured tenant Anthropic key, live browser). Re-run /gsd-verify-work 44 once available.]

<details><summary>Deferred test detail</summary>

number: 1
name: Full live Ask flow (BYOK key + interactive browser)
expected: |
  With a real tenant Anthropic key configured, at /dashboard/ask:
  1. Before the key is configured, the page shows the D-12 "Configure AI" inert card (never a query box that errors).
  2. After configuring the key, submitting the north-star question ("critical KEV vulns older than 30 days" and the multi-predicate variant) renders results-first: the interpreted-filter card + result table appear BEFORE the streamed narrative.
  3. The narrative streams in token-by-token below the results and is grounded in the shown result set (no hallucinated counts/CVEs).
  4. The four starter-question chips click-to-fill the query box.
  5. "Open in {Vulnerabilities|Assets|Tickets}" deep-links carry the SAME interpreted filter into the real list page and the list returns the matching rows.
  6. Refuse (out-of-scope question), zero-results (with interpretation retained), budget-exceeded, and safety-flagged states each render their dedicated card — exercised against real model responses, not just mocked.
awaiting: user response

</details>

## Notes

- Deferred on-trust during the headless Phase 44 execution (no live Anthropic key / browser available), following this repo's Phase 24–27 / 40 precedent.
- All code paths for every state were verified at the source level and all 222 automated tests pass (see 44-VERIFICATION.md). This UAT covers ONLY the live runtime behavior that automated tests cannot exercise.
- Exact reproduction steps also documented in 44-04-SUMMARY.md.
- Close via `/gsd-verify-work 44`.
