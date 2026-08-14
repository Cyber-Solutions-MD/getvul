---
phase: 36-remediation-sla-engine-escalation
plan: 06
type: summary
status: awaiting-human-verify
tasks_total: 3
tasks_complete: 2
human_verify_pending: true
---

# 36-06 SUMMARY — SLA & Escalation Admin Pane + Drill Panel

## Status: Tasks 1–2 complete and committed; Task 3 (human-verify) AWAITING sign-off

> **Close-out note:** The executor agent was interrupted by an API error (computer
> sleep) after both code tasks were committed cleanly but before it wrote this
> SUMMARY. This SUMMARY was reconstructed by the orchestrator from the committed
> diffs (`3e05075`, `b7729b2`) and the passing component test run. No code was
> changed during reconstruction; the working tree was clean at recovery.

## What was built

### Task 1 — SLA & Escalation admin settings pane (commit `3e05075`)
- `frontend/src/components/settings/sla-escalation-pane.tsx` (new, 718 lines) — three
  token-styled section cards (SLA policy, Escalation channels, Escalation floor). Uses
  `surface`/`border`/`text` tokens only; the SaveBar "Save changes" CTA is the sole
  gradient element. Wires `useTenantSettings` + `useUpdateTenantSettings` + `useDirtyState`
  with a single SaveBar and `onDirtyChange` up-reporting (Phase 14 pattern).
- Channel secret fields (Slack/Teams webhook URL, PagerDuty routing key) seed EMPTY with a
  `••••••••` placeholder and are included in the PATCH body only when touched (mask-on-read
  twin, notifications-pane `passwordTouched` pattern, D-14).
- Tier-floor control renders as "Escalate at" → Critical only / High and critical / All
  tracked tiers (D-06). Per-transition routing renders per channel as Approaching / Breach
  checkboxes (D-05).
- **D-13 mandatory copy** (line 69): "PagerDuty incidents from this integration require
  manual resolution — GetVul doesn't send an auto-resolve event when a finding is fixed."
- **D-15 mandatory copy** (line 71): Teams Workflows setup instructions ("…Workflows → Post
  to a channel when a webhook request is received"); notes classic Incoming Webhook
  connectors are retired.
- `microcopy.ts` — added "SLA & Escalation" to the Category union + CATEGORY_LABELS.
- `settings-sidebar-shell.tsx` — added `sla` to ALL_CATEGORIES + ADMIN_ONLY (admin/owner
  gated, D-10). Sidebar test updated.
- `settings/page.tsx` — pane routed into the settings shell.
- `lib/queries/use-tenant-settings.ts` — extended for the sla_config read/write shape.
- E1 state coverage: SkeletonTable (loading), PartialFailureBanner (error), EmptyState
  ("No escalation channels configured"), populated three-card layout, per-field partial,
  truncate+title overflow.

### Task 2 — drill-panel SLA pill + escalation-history list (commit `b7729b2`)
- `frontend/src/components/vulnerabilities/drill-content.tsx` (+150) — the extended `SlaPill`
  renders the server `sla_state` on the finding drill panel (matches the row, D-11); an
  ActivityTimeline-style escalation-history list from `GET /vulnerabilities/{id}/escalations`.
  A failed delivery renders an **amber-tinted, audit-only row with NO retry button** (D-08),
  showing "{Channel} delivery failed — HTTP {code} {error_message} · fired {fired_at}"; the
  transition record stays visible (D-07). Empty → "No escalations yet" compact inline empty.
- `lib/queries/use-vuln-escalations.ts` (new) + `keys.ts` + `use-vulnerability-detail.ts` —
  the escalations query hook + key + detail wiring.
- Drill-panel + mobile drill-panel tests extended.

## Verification (automated)
- `vitest run src/components/settings/sla-escalation-pane.test.tsx` → **12/12 passed**.
- Both code commits landed with pre-commit hooks passing (lint/typecheck/semgrep).
- Working tree clean at recovery (only untracked `scratchpad/`).

## Task 3 — Human-verify gate (BLOCKING, AWAITING sign-off)

Third-party channel delivery cannot be asserted in CI (per VALIDATION.md) — this requires a
running app + real webhooks. Steps to verify (from the plan `<how-to-verify>`):

1. Log in as admin/owner. Visit `/settings` → "SLA & Escalation". Confirm the three cards
   render on the sunset theme (no zinc-gray, no raw hex), Inter + JetBrains Mono only, and
   the SaveBar "Save changes" is the only gradient element.
2. Confirm loading (reload), empty (no channels), and error (offline) states each render per
   state-patterns.md.
3. Enter a real Slack / Teams Workflow / PagerDuty webhook in a scratch tenant, map it to the
   approaching transition, save, and force an approaching transition. Confirm the message
   arrives with correct formatting.
4. Open a finding's drill panel: confirm the SlaPill matches the row and the escalation-history
   list shows the fired event (and a failed delivery renders amber with no retry button).
5. Confirm the PagerDuty manual-resolution copy (D-13) and Teams Workflows setup copy (D-15)
   are present.

**Resume signal:** type "approved", or describe issues (contrast, token, copy, or delivery).

## Requirements
- SLA-01 / SLA-02 / SLA-03 (UI halves) — declared here but left **Pending** in REQUIREMENTS.md
  until human-verify sign-off. This is the last declaring plan for these IDs.

## Self-Check: PASSED (automated scope) — human-verify PENDING
