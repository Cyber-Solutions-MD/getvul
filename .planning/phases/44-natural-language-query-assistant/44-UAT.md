---
status: testing
phase: 44-natural-language-query-assistant
source: [44-VERIFICATION.md, 44-04-SUMMARY.md]
started: 2026-08-25
updated: 2026-08-25
---

## Current Test

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

## Notes

- Deferred on-trust during the headless Phase 44 execution (no live Anthropic key / browser available), following this repo's Phase 24–27 / 40 precedent.
- All code paths for every state were verified at the source level and all 222 automated tests pass (see 44-VERIFICATION.md). This UAT covers ONLY the live runtime behavior that automated tests cannot exercise.
- Exact reproduction steps also documented in 44-04-SUMMARY.md.
- Close via `/gsd-verify-work 44`.
