# Phase 23: Ingestion Reliability Precursor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-27
**Phase:** 23-ingestion-reliability-precursor
**Areas discussed:** GitHub finish/retire, Jira create-path shape, Connector health surface, Integration-test convention, Rapid7 TLS, Sync error-capture, REL-01/02 done-bar, Retry policy, Dispatch scope, GitHub sync-back, Configured-providers source, Provider modeling

---

## Area selection (round 1)

| Option | Selected |
|--------|----------|
| GitHub: finish vs retire | ✓ |
| Jira create-path shape | ✓ |
| Connector health surface | ✓ |
| Integration-test convention | ✓ |

**User's choice:** All four.

---

## GitHub: finish vs retire (REL-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Retire it | Delete client + tests + provider option + docstring mention | |
| Finish it | Wire into create + sync + rule_engine + UI + tests | ✓ |
| Finish create-only | Create + tests, skip sync-back | |

**User's choice:** Finish it. **Notes:** GitHub Issues is a wanted ticketing destination; treated as first-class.

---

## Jira create-path shape (REL-04)

**Q1 — dispatch approach**

| Option | Description | Selected |
|--------|-------------|----------|
| Provider-dispatch protocol | One client interface, dispatch by provider | ✓ |
| Per-provider branches | if provider== branches in each create fn | |

**Q2 — duplicate JiraClient**

| Option | Description | Selected |
|--------|-------------|----------|
| Consolidate to one | Single canonical client under app/ticketing/ | ✓ |
| Keep both, document | Leave split, add comments | |
| Investigate in research | Defer | |

**Q3 — create UX**

| Option | Description | Selected |
|--------|-------------|----------|
| Drill panel, provider picker | Choose provider at create time, filtered to configured | ✓ |
| Drill panel, per-provider buttons | One button per configured provider | |
| Backend-only this phase | API + tests, defer UI selection | |

**User's choice:** Dispatch protocol + consolidate to one + drill-panel provider picker.

---

## Connector health surface (REL-06)

**Q1 — error display**

| Option | Description | Selected |
|--------|-------------|----------|
| Inline on failure, expand for full | Error line only when failed, expand/hover for full | ✓ |
| Always-visible error row | Reserved line on every card | |
| Only in edit/detail view | Card unchanged, error in detail | |

**Q2 — extra fields (multiSelect)**

| Option | Description | Selected |
|--------|-------------|----------|
| Nothing more | last_error only | ✓ (contradictory — resolved below) |
| Next scheduled sync | frontend-derived next-sync line | ✓ |
| Consecutive-failure count | new backend counter | ✓ |

**Clarification (contradiction resolved):** User picked "Nothing more" alongside two additions. Re-asked with scope note (consecutive-failure needs a new backend column + migration).

| Option | Selected |
|--------|----------|
| Both additions | ✓ |
| Next-sync only | |
| Last-error only | |

**User's choice:** last-error inline-on-failure + next-scheduled-sync + consecutive-failure-count (accepting the new backend column + migration + harness logic).

---

## Integration-test convention (REL-03)

Codebase-decided: harness = `httpx.MockTransport` (6 existing test files use it; `test_connectors/` empty). Only rigor was open.

| Option | Description | Selected |
|--------|-------------|----------|
| Auth + pagination + mapping | Auth success/fail, multi-page pagination, field-for-field mapping | ✓ |
| Add error/rate-limit paths | + 429/5xx retry + error propagation | |
| Happy-path smoke only | One happy path per connector | |

**User's choice:** Auth + pagination + mapping.

---

## Follow-up areas (round 2 — user chose "explore more")

Selected: Rapid7 TLS, Sync error-capture, REL-01/02 done-bar, Retry policy (all four).

### Rapid7 verify=False

| Option | Description | Selected |
|--------|-------------|----------|
| Per-connector opt-out, default ON | verify_tls field, default True | ✓ |
| Force TLS ON | Remove verify=False entirely | |
| Leave as-is, flag only | Keep off, comment as tech debt | |

### Sync error-capture

| Option | Description | Selected |
|--------|-------------|----------|
| Sanitized+truncated, redaction-reused | exc type+message, truncated, Phase-7 redaction, reset-on-success | ✓ |
| Full exception + traceback | Full traceback | |
| Decide in planning | Defer | |

### REL-01/02 done-bar

| Option | Description | Selected |
|--------|-------------|----------|
| MockTransport integration test | CI-runnable, no live creds | ✓ |
| Mock test + manual live smoke | + one-time live-credential smoke | |

### Retry policy

| Option | Description | Selected |
|--------|-------------|----------|
| Leave per-connector, tests pin it | No standardization | ✓ |
| Standardize retry helper | Shared backoff helper across six connectors | |

---

## Finer points (round 3 — user chose "explore more")

Selected: Dispatch scope, GitHub sync-back, Configured-providers source, Provider modeling (all four).

### Dispatch scope

| Option | Description | Selected |
|--------|-------------|----------|
| All three create paths | create_tickets + host + remediation all multi-provider | ✓ |
| Per-vuln path only | Only create_tickets this phase | |

### GitHub sync-back

| Option | Description | Selected |
|--------|-------------|----------|
| State map + auto-close parity | Inbound closed→completed + GetVul PATCHes issue closed | ✓ |
| Inbound state map only | Sync in, no auto-close | |

### Configured-providers source

| Option | Description | Selected |
|--------|-------------|----------|
| Backend endpoint | Authoritative endpoint, reused by Phase 27 | ✓ |
| Derive client-side | From existing connector-configs query | |

### Provider modeling

| Option | Description | Selected |
|--------|-------------|----------|
| Formalize enum + shared union | Python Enum + TS union | ✓ |
| Keep string-literal convention | Add GITHUB to existing literals | |

---

## Resolved under Claude's discretion (round 4 — user said "go")

Natural consequences of the dispatch decision, captured as D-13 / D-20 / D-09 / D-10:
- Connector-config model for GitHub (`GITHUB` type: token/owner/repo) + Jira; generalize `_get_asana_client` → `_get_ticketing_client(provider)`.
- Migration/backfill: `last_error` nullable NULL; `consecutive_failure_count` INT NOT NULL default 0.
- Rule engine honors per-rule `provider` via dispatch (default ASANA).

## Deferred Ideas

- Shared connector retry/backoff helper (out of scope this phase).
- Forcing Rapid7 TLS fully ON (rejected for the opt-out).
- Reconcile Phase-8 "6 connector tests" memory vs empty test_connectors/ (planner verify).
