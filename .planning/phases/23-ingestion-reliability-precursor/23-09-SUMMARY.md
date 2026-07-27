---
phase: 23-ingestion-reliability-precursor
plan: 09
subsystem: frontend-connectors
tags: [connectors, health, ui, reliability]
dependency_graph:
  requires: [23-06]
  provides: [connector-card-health-signals]
  affects: [frontend/src/components/connectors/connector-card.tsx]
tech_stack:
  added: []
  patterns:
    - "native <details>/<summary> for expand-on-click (no JS state, no custom animation)"
    - "pure client-side derived label (nextSyncLabel) with no backend call"
key_files:
  created: []
  modified:
    - frontend/src/components/connectors/connector-card.tsx
    - frontend/src/components/connectors/connector-card.test.tsx
decisions:
  - "Last-error summary and expanded body intentionally repeat the same text (summary = one-liner, body = full message + timestamp); tests scope queries to the <summary> element to avoid ambiguous duplicate-text matches rather than de-duplicating the rendered content"
  - "consecutive_failure_count > 1 threshold (not >= 1): a single failure is a blip, not a persistent-outage signal — comment left inline per plan D-18"
  - "next-sync line always renders (even for healthy connectors) directly beneath last-sync-time; error summary/failure-count render only inside the failed-state <details> block"
metrics:
  duration_minutes: 45
  completed: "2026-07-27"
---

# Phase 23 Plan 09: Connector Card Health-at-a-Glance Summary

Surfaced per-connector health signals (last-error inline summary, frontend-derived next-sync countdown, consecutive-failure count) on the `/dashboard/connectors` card grid, consuming the health fields Plan 06 added to `ConnectorConfig`/`ConnectorConfigResponse` and the now-crash-safe `SyncStatusPill`.

## What Was Built

**Task 1 — Inline last-error summary + failure count (D-16, D-18):**
- A `<details>`/`<summary>` block renders **only** when `connector.last_sync_status === 'failed'`; healthy (`ok`/`syncing`/`null`) connectors render nothing extra — the card stays clean.
- The `<summary>` shows a one-line, truncated, `text-[var(--color-severity-critical-on-soft)]`-styled summary of `connector.last_error`, falling back to "Last sync failed" when `last_error` is null.
- Clicking/tapping the summary expands the native `<details>` to reveal the full message (mono font, since `last_error` often carries terminal-pasteable HTTP codes/request IDs) plus the `last_sync_at` relative timestamp (reusing the existing `formatSyncTime` helper).
- When `consecutive_failure_count > 1`, an additional line "failed {n} times in a row" renders inside the expanded block, with an inline code comment documenting the `>1` threshold (a single failure is a blip, not a persistent-outage signal — count of exactly 1 shows nothing extra).
- Error text is rendered as plain JSX children (no `dangerouslySetInnerHTML`) — no injection surface, no re-exposure of anything beyond what Plan 07's redaction already sanitized server-side.

**Task 2 — Frontend-derived next-sync line (D-17):**
- New pure helper `nextSyncLabel(lastSyncAt, syncIntervalMinutes)` computes `next = last_sync_at + sync_interval_minutes*60_000` against `Date.now()` — zero network calls.
- Branches: `last_sync_at` null → `"not synced yet"`; computed next-sync already elapsed → `"sync due"`; otherwise `< 60m` → `"next sync in ~Xm"`, `>= 60m` → `"next sync in ~Xh"`.
- Rendered on every card (healthy or failed) directly beneath the last-sync-time + record-count row, in muted `text-text-faint` Inter text.

## Verification

- `npm run test -- connector-card`: **14/14 passed** (5 pre-existing tests + 5 new for Task 1 + 4 new for Task 2).
  - Test 6: failed+last_error → one-line summary in `<summary>`, expands `<details>` to reveal full message.
  - Test 7: failed+`last_error=null` → `<summary>` falls back to "Last sync failed".
  - Test 8: healthy connector → no `<details>` element, no "times in a row" text.
  - Test 9: `consecutive_failure_count=5` → "failed 5 times in a row".
  - Test 10: `consecutive_failure_count=1` → no "times in a row" text.
  - Test 11: future <60m → "next sync in ~10m" (frozen clock via `vi.useFakeTimers`/`setSystemTime`).
  - Test 12: future >=60m → "next sync in ~2h".
  - Test 13: `last_sync_at=null` → "not synced yet".
  - Test 14: computed next-sync already elapsed → "sync due".
- `grep -nE "#[0-9A-Fa-f]{6}"` on `connector-card.tsx`: **zero hits** — no freehand hex, all color via CSS variable tokens.
- `npx tsc --noEmit`: clean.
- Full frontend suite (`npm run test -- run`): **125 test files / 746 tests, all passing** — no regressions.
- Native `<details>` expand has no CSS transition/animation, so `prefers-reduced-motion` is trivially respected (nothing to suppress).

## Deviations from Plan

None — plan executed exactly as written. One test-design refinement during implementation: the initial RED tests for Task 1 used a global `screen.getByText(...)` for the error message, which became ambiguous once the summary and the expanded body both render the same `last_error` text (by design — one is the collapsed one-liner, the other is the "full message" the plan explicitly calls for). Scoped those two assertions to `document.querySelector('summary')` instead of de-duplicating the rendered content, since the plan's behavior spec requires both a summary line AND a full-message reveal.

## Environment Note (not a deviation)

This worktree's `frontend/node_modules` was absent at execution start (worktrees don't share `node_modules` — documented hazard). Ran `npm install --legacy-peer-deps` (consistent with prior phases' documented override for the lucide-react/React 19 peer conflict) before any test could run.

## Self-Check

- `frontend/src/components/connectors/connector-card.tsx` — FOUND, contains `last_error`, `consecutive_failure_count`, `nextSyncLabel`, `next sync in`, `not synced yet`, `sync due`, `times in a row`.
- `frontend/src/components/connectors/connector-card.test.tsx` — FOUND, 14 tests, all passing.
- Commits `3a6c1d6`, `d45c40f`, `91dee15`, `9e733c3`, `4ff1677` — all present in `git log`.

## Threat Flags

None — the plan's own `<threat_model>` (T-23-25 last_error DOM rendering, T-23-26 error-text contrast) fully covers the surface touched by this plan; no new network endpoints, auth paths, or schema changes were introduced.

## Self-Check: PASSED

All claimed files and commits verified present.
