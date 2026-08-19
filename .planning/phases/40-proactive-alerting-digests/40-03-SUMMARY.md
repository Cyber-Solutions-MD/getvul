---
phase: 40-proactive-alerting-digests
plan: 03
subsystem: alerting
tags: [sqlalchemy, fastapi, pytest, digests, sla, email, zoneinfo]

# Dependency graph
requires:
  - phase: 40-proactive-alerting-digests
    plan: "01"
    provides: "Tenant.alerting_config/alerting_last_digest_sent_at (migration 051), alerting_config.py::DEFAULT_ALERTING_CONFIG/merged_alerting_config, 7 RED test scaffolds in test_digests.py"
  - phase: 40-proactive-alerting-digests
    plan: "02"
    provides: "get_directory_user (app/assets/directory.py) owner-resolution helper, proven dispatch_channel/_build_channel_config usage pattern"
  - phase: 36-remediation-sla-engine-escalation
    provides: "resolve_state_for_vuln + get_tier_policy (sla_tier_service.py) -- due/breaching state classification, reused verbatim"
  - phase: 39-exception-risk-acceptance-workflow
    provides: "active_exception_subquery + lapsed_exception_seconds (D-20/D-16) + ExceptionRecord.expires_at, reused verbatim"
provides:
  - "email.py::send_email(..., html_body=...) -- multipart/alternative support, byte-for-byte unchanged when html_body is omitted"
  - "notifications/digests.py -- run_digests(db), _send_hour_due(tenant, now) wall-clock gate, _assemble_sections(db, tenant, asset_ids, now), _render_digest_html(sections, ...), per-owner email + per-team channel dispatch loops"
  - "scheduler.py digest-dispatch tick block -- fail-isolated, runs every 60s, gate lives inside run_digests"
affects: [40-04, 40-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Durable wall-clock send-gate: _send_hour_due converts `now` into Tenant.timezone via zoneinfo.ZoneInfo, compares local hour against the tenant's configured send_hour, then compares (year, day-of-year) or ISO (year, week) period keys against Tenant.alerting_last_digest_sent_at (also tz-converted) -- survives restarts because the marker is a persisted column, not an in-memory dict (Pitfall 4)"
    - "Assembly/render split: _assemble_sections returns FULL, risk-sorted, uncapped section lists; the top-N cap + 'and N more' overflow line is applied only at _render_digest_html render time -- keeps the assembled data reusable for a future 'send test digest' preview without re-querying"
    - "Digest content reuses Phase 36/39 primitives verbatim (resolve_state_for_vuln + lapsed_exception_seconds batched D-16 subtraction for due/breaching; active_exception_subquery + status.notin_ for every section's D-20 exclusion) rather than re-deriving SLA/exception logic in the alerting layer"
    - "Team-channel push reuses the existing single-finding-shaped dispatch_channel/_build_channel_config seam as a 'most urgent item' heads-up notification (not a full digest replica) -- documented discretion resolving 40-RESEARCH.md Assumptions Log A3, since escalation_channels.py is out of this plan's files_modified"

key-files:
  created:
    - backend/app/notifications/digests.py
  modified:
    - backend/app/email.py
    - backend/app/connectors/scheduler.py

key-decisions:
  - "ALERT-02 left UNCHECKED in REQUIREMENTS.md per this plan's own tracking_note/40-01's established convention -- Plan 05 is the designated closer for ALL of ALERT-01/02/03 at phase end, even though Plan 05's own frontmatter only declares ALERT-03. This intentionally deviates from a strict per-requirement 'last declaring plan' rule (which would flip ALERT-02 here, since no later plan re-declares it) in favor of the phase-wide convention 40-01/40-02 already locked in."
  - "_send_hour_due gate implemented with zoneinfo.ZoneInfo (stdlib, no new dependency) rather than a naive UTC-only comparison -- Tenant.timezone (default 'UTC') is honored exactly as D-12 specifies; an invalid/unknown tz string logs a warning and falls back to UTC rather than crashing the scheduler tick."
  - "Team-digest channel push builds a 'most urgent item' context (top item from breaching > due > newly_critical > expiring_exceptions, by risk) reusing escalation_channels.py's existing single-finding-shaped payload builders verbatim, rather than extending escalation_channels.py with a digest-specific builder -- that file is not in this plan's files_modified, and 40-RESEARCH.md flags this exact gap as Assumptions Log A3 (planner's discretion). The full itemized multi-section content is what the per-owner HTML email carries; the channel push is a pointer/heads-up, not a duplicate of the email."
  - "Per-owner email digest skips sending (returns 0, no error) when tenant.smtp_config is missing/disabled -- mirrors the existing reports.py:219 'silently skip if SMTP isn't configured' convention rather than surfacing a send failure for an intentionally-unconfigured channel."
  - "newly-critical section's lookback window is derived from the tenant's own digest cadence (24h for daily, 168h/7d for weekly) rather than reusing alerts.py::_check_new_critical_vulns's unrelated 2h fire-once dedup window -- these are two independent, differently-scoped concepts (a digest summary window vs. a real-time dedup window) per the plan's own action text."
  - "Expiring-exceptions horizon fixed at 7 days (EXPIRING_EXCEPTION_HORIZON_DAYS) -- not pinned by any D-ID in CONTEXT/RESEARCH; chosen as a reasonable 'act before it lapses' window, documented as a constant so a future plan can tune it without touching query logic."

requirements-completed: []  # Deliberately empty -- see key-decisions; Plan 05 is the designated closer for ALERT-01/02/03.

coverage:
  - id: D1
    description: "send_email gains optional html_body support (multipart/alternative, plain-then-html part order) with zero behavior change when html_body is omitted"
    requirement: "ALERT-02"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_digests.py -k html -x -- test_html_body_renders_sections passes"
        status: pass
      - kind: static
        ref: "grep -c html_body app/email.py >= 2; grep MIMEMultipart(\"alternative\") app/email.py present"
        status: pass
    human_judgment: false
  - id: D2
    description: "digests.py: wall-clock send-hour gate (fires past target hour, not before, not twice per period across a simulated restart), four D-13-ordered D-20-excluded sections (due/breaching via resolve_state_for_vuln, newly-critical via CRITICAL+first_detected_at-in-window, expiring-exceptions via ExceptionRecord.expires_at), D-14 empty-suppression, escaped HTML rendering with top-10 cap + overflow line, per-owner-email vs per-team-channel routing"
    requirement: "ALERT-02"
    verification:
      - kind: unit
        ref: "cd backend && pytest tests/test_digests.py -x -- 7/7 pass (test_send_hour_gate_fires_past_target_not_before, test_not_sent_twice_per_period, test_empty_digest_suppressed, test_sections_read_sla_and_exception_state, test_newly_critical_section_content, test_html_body_renders_sections, test_per_owner_email_vs_per_team_channel)"
        status: pass
      - kind: static
        ref: "grep -c '_is_due' digests.py == 0; grep resolve_state_for_vuln/active_exception_subquery/html.escape all present; alerting_last_digest_sent_at written"
        status: pass
    human_judgment: false
  - id: D3
    description: "scheduler.py gains a new isolated try/except digest-dispatch block calling run_digests(db) every tick, fail-isolated, no elapsed-hours guard at the scheduler level (the gate lives inside run_digests)"
    requirement: "ALERT-02"
    verification:
      - kind: static
        ref: "grep -c run_digests app/connectors/scheduler.py == 3 (import + call + log key); python3 -c \"import ast; ast.parse(open('app/connectors/scheduler.py').read())\" exits 0"
        status: pass
      - kind: unit
        ref: "cd backend && pytest tests/test_digests.py tests/test_scheduler_ai_batch.py tests/test_scheduler_enrichment_refresh.py -q -- all pass, no regression from the new block"
        status: pass
    human_judgment: false
  - id: D4
    description: "E4 backstop: digest email finding rows truncate a hostname longer than ~40 chars with an ellipsis, verified visually in Gmail web + Apple Mail"
    verification: []
    human_judgment: true
    rationale: "The truncation LOGIC itself is unit-proven (_truncate_hostname + a rendered-HTML assertion confirming the untruncated string never appears in output), but this environment has no browser or live email client to actually open Gmail web / Apple Mail and visually confirm cross-client table-layout rendering, per the UI-SPEC's explicit backstop requirement. Documented as an unresolved backstop, matching this project's established pattern (STATE.md 'uat'/'nyquist-doc' deferred items) rather than falsely claiming live cross-client verification."

duration: ~20min
completed: 2026-08-19
status: complete
---

# Phase 40 Plan 03: ALERT-02 — Scheduled Owner/Team Digests Summary

**`run_digests` assembles due/breaching/newly-critical/expiring-exception sections (Phase 36 SLA state + Phase 39 exception expiry, D-20-excluded), gates on a NEW persisted wall-clock send-hour check, renders escaped top-10-capped HTML, and dispatches per-owner email + per-team Slack/Teams digests on the existing scheduler tick — all 7 Wave-0 RED tests now green.**

## Performance

- **Duration:** ~20 min (autonomous, no checkpoints)
- **Started:** 2026-08-19T13:35Z (immediately after 40-02's metadata commit)
- **Completed:** 2026-08-19T13:51Z
- **Tasks:** 3/3 (Task 1 auto/tdd, Task 2 auto/tdd, Task 3 auto)
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- Extended `send_email` with optional `html_body` (multipart/alternative, plain-then-html part order per RFC 2046) with byte-for-byte unchanged behavior when omitted — closes the "HTML digest email" gap 40-RESEARCH.md flagged as genuinely new work (`email.py` previously only attached a single plain-text part)
- Built `_send_hour_due` — the NEW wall-clock gate D-12 requires: converts `now` into `Tenant.timezone` via `zoneinfo`, checks `local_now.hour >= send_hour`, and compares calendar-period keys (day for daily, ISO week for weekly) against the DURABLE `Tenant.alerting_last_digest_sent_at` marker (migration 051) — proven to fire past the target hour, not before, and not twice within the same period even across a simulated restart (the marker is a real column, never reset by an in-memory dict)
- Built `_assemble_sections`: due/breaching classified via `resolve_state_for_vuln` (with the SAME batched `lapsed_exception_seconds` D-16 subtraction `sla_tier_service.py`'s own passes apply — not re-derived), newly-critical from CRITICAL findings whose `first_detected_at` falls within a cadence-derived digest window (24h daily / 168h weekly — distinct from `_check_new_critical_vulns`'s unrelated 2h fire-once dedup), expiring-exceptions from `ExceptionRecord.expires_at` within a 7-day horizon — every section independently `tenant_id`-scoped, `status NOT IN (SUPPRESSED, FALSE_POSITIVE)`-filtered, and `~active_exception_subquery`-excluded (D-20)
- Built `_render_digest_html`: light-background inline-CSS HTML (per the UI-SPEC's deliberate dark-theme exception for email clients), every finding-derived string (CVE id, hostname) passed through `html.escape` (T-40-09 XSS mitigation), top-10-per-section cap with an "and N more →" dashboard deep-link overflow line, hostname truncation at 40 chars with an ellipsis
- Wired `run_digests`: groups tenant assets by resolved owner (`get_directory_user`, same precedence ALERT-01 uses) for per-owner email digests (D-14 empty-suppressed per owner); iterates only `AssetGroup`s with members for per-team channel digests via the shared Phase-36 `_build_channel_config`/`dispatch_channel` seam (fail-isolated, D-14 empty-suppressed per group); stamps `alerting_last_digest_sent_at` once a due tenant has been processed, regardless of whether any individual recipient's digest ended up empty
- Added a new isolated try/except digest-dispatch block to `scheduler.py::_scheduler_loop` (runs every 60s tick, own session, logs sent count, logs+continues on error) — the elapsed-hours-style guard other blocks use is deliberately absent here since the real gate lives inside `run_digests`

## Task Commits

1. **Task 1: send_email html_body multipart/alternative** — `73a5477` (feat)
2. **Task 2: digests.py — send-hour gate, section assembly, escaped HTML, per-owner/per-team routing, empty suppression** — `9a0d2e3` (feat)
3. **Task 3: Scheduler digest-dispatch block** — `52de9ec` (feat)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `backend/app/email.py` (modified) — adds `html_body: str | None = None` to `send_email`; builds `MIMEMultipart("alternative")` with plain-then-html parts when provided, unchanged single-plain-part path otherwise
- `backend/app/notifications/digests.py` (created) — `run_digests(db, *, tenant_id=None, now=None)`, `_send_hour_due(tenant, *, now)`, `_assemble_sections(db, tenant, asset_ids=None, now=None)`, `_render_digest_html(sections, *, recipient_label=None, dashboard_url=...)`, `_dispatch_owner_digests`, `_dispatch_team_digests`, `_team_digest_channel_context`, plus rendering/text helpers
- `backend/app/connectors/scheduler.py` (modified) — one new isolated try/except block in `_scheduler_loop` calling `run_digests(db)` every tick

## Decisions Made

See `key-decisions` in frontmatter for the full list (ALERT-02 requirement-marking deferral, zoneinfo-based send-hour gate, team-channel "most urgent item" context reuse, SMTP-disabled silent skip, cadence-derived newly-critical window, 7-day expiring-exceptions horizon).

## Deviations from Plan

None — plan executed exactly as written. All three tasks' acceptance criteria were met on the first implementation pass (all 7 named tests passed without needing a fix-and-retry cycle); the only follow-up work was two self-caught mypy type-narrowing fixes in the new file itself (not deviations from the plan's behavior, just type-correctness on code this plan introduced):

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy: expiring-exceptions sort-key type mismatch**
- **Found during:** Task 2, mypy pass before commit
- **Issue:** `expiring_items.sort(key=lambda item: item["expires_at"])` inferred the dict's value type too broadly (`datetime | UUID | str | None`), which doesn't satisfy `sort`'s ordering-comparable bound.
- **Fix:** Added an explicit `list[dict[str, Any]]` annotation on `expiring_items` and a `or now` fallback in the sort key (defensive against a theoretical `None`, though the query itself guarantees `expires_at` is set).
- **Files modified:** `backend/app/notifications/digests.py`
- **Verification:** `mypy app/notifications/digests.py` — zero errors after the fix.
- **Committed in:** `9a0d2e3` (Task 2 commit)

**2. [Rule 1 - Bug] mypy: `tenants` variable type narrowed by first branch**
- **Found during:** Task 2, mypy pass before commit
- **Issue:** `tenants = [tenant]` (a `list[Tenant]`) in the `tenant_id is not None` branch, then reassigned to `.scalars().all()`'s `Sequence[Tenant]` in the `else` branch, produced an incompatible-assignment error.
- **Fix:** Added an explicit `tenants: Sequence[Tenant]` annotation before the branch (imported `collections.abc.Sequence`).
- **Files modified:** `backend/app/notifications/digests.py`
- **Verification:** `mypy app/notifications/digests.py` — zero errors after the fix.
- **Committed in:** `9a0d2e3` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — mypy type-correctness in new code this plan itself introduced, not pre-existing rot).
**Impact on plan:** No scope creep — no architectural changes, no new dependencies, both fixes are type-annotation-only and were folded into Task 2's own commit before it landed.

## Issues Encountered

- No dedicated `test_email.py`/`test_reports.py` files exist in this codebase to regression-check Task 1 against beyond `test_digests.py` itself and a manual grep/acceptance-criteria pass — confirmed via `find`/`ls tests` before relying solely on the plan's own `-k html` verification command.
- Ran full regression passes beyond the plan's minimum verification commands as a precaution: `test_alerts_kev_epss.py`, `test_sla_policy.py`, `test_alerting_settings.py` (17 passed/3 xfailed/5 xpassed), all five `test_exceptions*.py` files (44 passed), and both existing scheduler test files (15 passed) — zero regressions from this plan's three file changes.
- `ENCRYPTION_KEY`/`JWT_SECRET_KEY` generated fresh per test invocation (real Fernet key + random secret) since persisted `.env` files aren't readable via the sandboxed shell — matches 40-01/40-02's documented precedent and this project's own pytest-env memory entry.
- E4 backstop (hostname truncation visually confirmed in Gmail web + Apple Mail) could not be live-verified in this sandboxed, browser-less environment — see coverage `D4`/`human_judgment: true` above. The underlying truncation logic itself IS unit-proven (a rendered-HTML assertion confirms the untruncated 78-char test hostname never appears in output, only its 40-char-plus-ellipsis form).

## User Setup Required

None — no external service configuration required. (A tenant must have `smtp_config.enabled`/`host` set and/or a Slack/Teams webhook configured under `sla_config.channels` for digests to actually deliver anywhere — this is existing Phase 36 tenant-admin configuration, not new setup introduced by this plan.)

## Next Phase Readiness

- Plan 04 (ALERT-03 config save: PATCH `/settings` alerting_config validation/persistence/audit) is unaffected by this plan's files and can proceed independently.
- Plan 05 (ALERT-03 settings pane) can now wire a real "Send test digest" action against `run_digests(db, tenant_id=..., now=...)` — both keyword args exist specifically to support a single-tenant, deterministic-`now` test-send call without needing a second code path. Per this plan's key-decisions, Plan 05 is also the designated plan to flip ALERT-01/02/03 in REQUIREMENTS.md.
- No blockers. `test_digests.py` is fully green (7/7); the existing SLA-tier, exceptions, alerts-kev-epss, alerting-settings, and scheduler regression suites (81 tests total across those files) all still pass unmodified, confirming no regression from the three file changes.
- Known gap carried forward (not a blocker): the E4 cross-client visual truncation backstop (D4 above) needs a human with access to a real Gmail web session + Apple Mail to close out fully — logged for `/gsd-verify-work 40` rather than silently claimed.

## Self-Check: PASSED

`backend/app/notifications/digests.py` confirmed present via `[ -f ... ]`. All three commit hashes (`73a5477`, `9a0d2e3`, `52de9ec`) confirmed present via `git log --oneline --all`. No missing items.

---
*Phase: 40-proactive-alerting-digests*
*Completed: 2026-08-19*
