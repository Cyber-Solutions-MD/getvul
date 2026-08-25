---
phase: 36-remediation-sla-engine-escalation
plan: 02
subsystem: notifications
tags: [fastapi, sqlalchemy, alembic, httpx, ssrf, webhooks, pagerduty, slack, teams, smtp]

# Dependency graph
requires:
  - phase: 36 (Plan 01)
    provides: "the risk-tier SLA engine (sla_tier_service.py) that establishes on_track/approaching/breached state -- this plan builds the delivery mechanism those transitions will fire through in Plan 03; no direct code import between the two"
provides:
  - "SlaEscalationEvent model + sla_escalation_events table (migration 046) -- the once-only escalation-fire gate + audit-visible history Plan 03's firing loop will INSERT into (UniqueConstraint(tenant_id, vulnerability_id, to_state, channel) = uq_escalation_once)"
  - "escalation_channels.py: _validate_webhook_url, send_slack, send_teams, send_pagerduty, send_email_channel, dispatch_channel(channel, config, context) -> {ok, error}"
  - "Email-channel config contract: dispatch_channel(\"email\", {\"to\": [...], \"smtp_config\": {...}}, context) -- caller must merge Tenant.smtp_config into the per-call config since it lives on a different Tenant column than sla_config.channels.email"
affects: [36-03, 36-04, 36-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SSRF guard: https-only + ipaddress-literal private/loopback/link-local/reserved/multicast/unspecified rejection + a small metadata-hostname denylist, applied before every outbound webhook POST -- including PagerDuty's own fixed, non-tenant-controlled URL, for defense in depth"
    - "Every channel sender AND the dispatch_channel router itself is wrapped in its own try/except returning {ok:False, error:...} -- a channel/tenant failure can never propagate and stall a scheduler tick (Pattern 1 isolation)"
    - "dispatch_channel routes via a plain if/elif chain on bare module-global function names (not a dict-of-callables captured once at import time), so monkeypatching an individual sender is honored on the very next call -- mirrors this codebase's existing dispatcher-monkeypatch convention (test_scheduler_enrichment_refresh.py)"

key-files:
  created:
    - backend/app/notifications/escalation_channels.py
    - backend/alembic/versions/046_add_sla_escalation_events.py
    - backend/tests/test_escalation_channels.py
  modified:
    - backend/app/vulnerabilities/models.py

key-decisions:
  - "Task 1 checkpoint (reversibility gate) resolved to option-a per pre-resolved orchestrator instruction, not re-prompted: 046 is a STANDALONE escalation-event migration; the sibling remediation_events table (D-09/SLA-04) is 047 in Plan 04, not combined here"
  - "dispatch_channel's email config shape is {\"to\": [...], \"smtp_config\": {...}} -- Tenant.smtp_config and sla_config.channels.email live on different Tenant columns, and dispatch_channel's signature is fixed at (channel, config, context) per the plan's own artifact contract, so Plan 03's firing loop must merge the two before calling dispatch_channel(\"email\", ...)"
  - "PagerDuty tier-to-severity mapping (critical->critical, high->error, moderate->warning, unscored/unknown->warning) is a new Claude's-Discretion choice -- RESEARCH only locked 'severity in {critical,error,warning,info}', not an exact mapping"
  - "Chose the simple Teams {\"text\": ...} payload form over the richer adaptive-card envelope -- satisfies D-15's 'never the classic MessageCard connector' requirement with the smallest payload; a richer card is a natural future enhancement, not required this phase"
  - "SLA-03 intentionally left [ ] Pending in REQUIREMENTS.md -- it is also declared by not-yet-executed Plans 03 and 06 (shared-ID gate); flipping now would be a false-positive Complete before the firing logic or admin pane exist"

patterns-established:
  - "Pattern: an outbound-webhook SSRF guard (https-only + ipaddress-literal classification + metadata-hostname denylist) applied before every httpx.AsyncClient(follow_redirects=False) POST anywhere a tenant-admin-controlled URL is involved"
  - "Pattern: dispatch_channel(name, config, context) -> {ok, error} as the uniform multi-channel delivery contract -- adding a channel means adding one sender function + one branch, never touching call sites"

requirements-completed: []

# Metrics
duration: ~30min
completed: 2026-08-13
---

# Phase 36 Plan 02: Escalation Delivery Infrastructure Summary

**SSRF-guarded Slack/Teams/PagerDuty/email escalation senders (raw httpx, no vendor SDKs) plus the durable once-only `sla_escalation_events` table (migration 046) that Plan 03's firing logic will gate on and INSERT into.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-08-13T13:28:00Z (context + research load)
- **Completed:** 2026-08-13T13:58:11Z
- **Tasks:** 1 checkpoint (resolved, no code) + 2 code tasks (RED, GREEN)
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- `SlaEscalationEvent` model + migration `046_add_sla_escalation_events` land the once-only escalation-fire gate: `UniqueConstraint(tenant_id, vulnerability_id, to_state, channel)` as `uq_escalation_once`, mirroring `RiskExposureBackfillJob`'s shape exactly (CASCADE FKs + indexes on both `tenant_id`/`vulnerability_id`, `delivery_status` default `"sent"`, `error_message` for the failed-POST audit trail). Verified upgrade→downgrade→upgrade round-trip against the real dev Postgres, plus a direct `\d sla_escalation_events` confirming every column/constraint/index.
- `escalation_channels.py` builds all four D-04 channel payloads (Slack `{text, blocks}`, Teams simple `{text}` form targeting Workflows webhooks — never the retired classic connector, PagerDuty Events v2 `trigger` with a stable `dedup_key`, email delegating verbatim to `app.email.send_email`) via raw `httpx.AsyncClient(follow_redirects=False)` — zero vendor SDKs, zero new dependencies.
- `_validate_webhook_url` closes Pitfall 10 (SSRF): https-only, rejects loopback/private/link-local/reserved/multicast IP literals and well-known cloud-metadata hostnames, proven to run *before* any network call (a dedicated test asserts the fake POST is never even invoked for an unsafe URL).
- Every sender and `dispatch_channel` itself catch their own failures (raise, non-2xx, unknown channel, even a monkeypatched sender that raises) and return `{"ok": False, "error": ...}` — never propagate an exception (Pattern 1), proven directly against `httpx.AsyncClient.post` monkeypatches (no respx/pytest-httpx added).
- PagerDuty sends `event_action="trigger"` only this phase; the D-13 manual-resolution limitation is documented in the module docstring and proven via both a dedicated test and the plan's own literal `grep -c 'event_action.*resolve' == 0` acceptance gate.

## Task Commits

1. **Task 1: Reversibility gate — confirm the escalation-event table (D-07)** — *decision recorded, no commit.* Pre-resolved by the orchestrator per the user's prior selection: **option-a** (two separate migrations — 046 escalation this plan, 047 remediation in Plan 04). Not re-prompted.
2. **Task 2 (Wave 0): Failing tests for channel payloads + SSRF guard + failure handling** - `14a0483` (test) — RED via genuine `ImportError` (module doesn't exist yet)
3. **Task 3: Migration + model + channel senders (GREEN)** - `d106789` (feat) — GREEN, 33/33, migration round-trip verified, 0 new mypy-baseline errors

**Plan metadata:** _pending — this commit._

## Files Created/Modified

- `backend/app/notifications/escalation_channels.py` — `_validate_webhook_url`, `_build_summary_text`/`_build_slack_payload`/`_build_teams_payload`/`_build_pagerduty_payload`/`_pagerduty_severity` (private payload builders), `_post_json_with_retry`/`_post_json` (shared outbound POST + 429 retry), `send_slack`/`send_teams`/`send_pagerduty`/`send_email_channel`, `dispatch_channel`
- `backend/alembic/versions/046_add_sla_escalation_events.py` — `sla_escalation_events` table: `tenant_id`/`vulnerability_id` FKs CASCADE+index, `from_state`/`to_state`/`channel` String(20), `fired_at`, `delivery_status` default `"sent"`, `error_message`, `uq_escalation_once` UniqueConstraint
- `backend/app/vulnerabilities/models.py` — added `SlaEscalationEvent` (appended after `RiskExposureBackfillJob`, same mixins/shape convention)
- `backend/tests/test_escalation_channels.py` — 33 tests: 7 payload-shape, 11 SSRF-guard parametrized cases, 11 failure-handling (raise/404/missing-config/unknown-channel/429-retry/sender-exception, all via `httpx.AsyncClient.post` monkeypatch), 4 email-channel-delegation

## Decisions Made

See `key-decisions` in frontmatter. Most consequential for downstream plans: (1) the Task 1 checkpoint's option-a resolution keeps 046 and Plan 04's `remediation_events` migration fully independent; (2) the email channel's `{"to", "smtp_config"}` merged-config shape is the exact contract Plan 03 must build before calling `dispatch_channel("email", ...)`; (3) `dispatch_channel`'s if/elif (not dict-of-callables) dispatch shape is deliberate so a future test can monkeypatch an individual sender.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy: `Any | None` from `dict.get()` not narrowed before a `str`-typed parameter**
- **Found during:** Task 3, post-implementation mypy sweep before commit
- **Issue:** `send_slack`/`send_teams` extracted `url = (config or {}).get("url")` (typed `Any | None`) and guarded only via `if not _validate_webhook_url(url):` — mypy cannot narrow `url` itself from a boolean-returning function call, producing 2 new `arg-type` errors when `url` was passed into `_post_json(url: str, ...)`.
- **Fix:** Changed the guard to `if not url or not _validate_webhook_url(url):` (mirroring `send_pagerduty`'s pre-existing `if not routing_key:` shape), which lets mypy narrow `url` from `Any | None` to `Any` post-guard, matching this codebase's 0-new-mypy-errors gate.
- **Files modified:** backend/app/notifications/escalation_channels.py
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` → `new: 0, fixed: 0` (confirmed before and after, isolating exactly these 2 as newly introduced)
- **Committed in:** `d106789` (Task 3 commit)

**2. [Rule 1 - Bug] Module docstring's D-13 prose initially tripped the plan's own literal acceptance-criteria grep**
- **Found during:** Task 3, acceptance-criteria self-verification before commit
- **Issue:** The first draft of the D-13 manual-resolution-limitation paragraph phrased it as `` `event_action="resolve"` `` on a single line — which is exactly the substring the plan's own acceptance criterion (`grep -c 'event_action.*resolve' ... == 0`) is designed to catch, even though the sentence's actual meaning was "this is never sent," not an instruction to send it.
- **Fix:** Reworded the paragraph so "event_action" and "resolve" never co-occur on one physical line, while still documenting the limitation in prose elsewhere in the same docstring (`grep -ci resolve` → 3 matches, unaffected).
- **Files modified:** backend/app/notifications/escalation_channels.py
- **Verification:** `grep -c 'event_action.*resolve' backend/app/notifications/escalation_channels.py` → 0; full suite still 33/33 pass
- **Committed in:** `d106789` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs, both caught and fixed pre-commit during this plan's own verification steps)
**Impact on plan:** Both are minimal, in-file-scope corrections with zero scope creep — no new features, no architectural changes, no new dependencies. Neither was ever committed in a broken state.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required. (Live Slack/Teams/PagerDuty/SMTP credentials are per-tenant, remote, and out of scope for this dev environment per 36-RESEARCH.md's Environment Availability table — every test monkeypatches `httpx.AsyncClient.post` instead of hitting a real endpoint.)

## Next Phase Readiness

- Plan 03 (transition-detection + firing logic) has a stable, tested contract to build against: `dispatch_channel(channel, config, context) -> {"ok": bool, "error": str | None}` for all four channels, plus `SlaEscalationEvent`/`sla_escalation_events` as the once-only gate + audit-history table to query-before-insert against (mirroring `alerts.py::_notification_exists`, per 36-RESEARCH Pattern 2). Plan 03 must also call `audit()` on every fire (D-07) — that call is explicitly NOT in this plan's scope.
- Plan 03 must assemble the `context` dict this plan's builders expect: `{"vuln_id", "cve_id", "hostname", "tier", "tier_days", "to_state"}` — all optional/falsy-safe, but richer context produces a better message.
- Plan 03 must assemble the email channel's merged config (`{"to": [...], "smtp_config": tenant.smtp_config}`) before calling `dispatch_channel("email", ...)` — see key-decisions.
- Plan 04 (remediation_events / SLA-04) can now safely create its own `047_*` migration chained off `046_add_sla_escalation_events` — the two tables are confirmed independent per the Task 1 resolution.
- SLA-03 remains `[ ]` Pending in REQUIREMENTS.md by design — Plans 03 and 06 also declare it; do not flip it from a future plan's summary step without re-running the requirements-readiness check.
- No blockers.

---
*Phase: 36-remediation-sla-engine-escalation*
*Completed: 2026-08-13*

## Self-Check: PASSED

- FOUND: backend/app/notifications/escalation_channels.py
- FOUND: backend/alembic/versions/046_add_sla_escalation_events.py
- FOUND: backend/tests/test_escalation_channels.py
- FOUND: backend/app/vulnerabilities/models.py
- FOUND: commit 14a0483 (test(36-02): add failing tests for escalation channel payloads + SSRF guard (RED))
- FOUND: commit d106789 (feat(36-02): add sla_escalation_events table + SSRF-guarded channel senders (GREEN))
- FOUND: class SlaEscalationEvent in backend/app/vulnerabilities/models.py
- FOUND: def dispatch_channel in backend/app/notifications/escalation_channels.py
