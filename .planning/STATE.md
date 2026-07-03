---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Production Readiness
status: Ready to plan
last_updated: "2026-07-03T08:57:44.572Z"
progress:
  total_phases: 8
  completed_phases: 4
  total_plans: 11
  completed_plans: 11
  percent: 100
---

# STATE — GetVul GSD Session Memory

## Project Reference

See: [.planning/PROJECT.md](PROJECT.md) (updated 2026-05-12)

**Core value:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console.

**Current focus:** Phase 04 — doc-code-parity

## Current Position

Phase: 5
Plan: Not started
| Field | Value |
|-------|-------|
| Active milestone | v1.0 Production Readiness — **RESUMED 2026-06-30** (Phases 1–2 done; Phases 3–8 remaining) |
| Last completed phase | 3 — Update Path Reconciliation ✓ (2026-07-02) — auto-update cron hard-removed (install.sh + 3× startup.sh + `git rm` auto-update.sh); CD pinned to `refs/tags/$DEPLOY_TAG` with allowlist-validated `release_tag` dispatch input; rollback runbook in docs/13 with DB-migration warning. Verifier 9/10 (1 human dry-run pending, tracked in 03-HUMAN-UAT.md). Code review caught + fixed a critical cd.yml command-injection RCE (CR-01) and a branch-checkout bypass (WR-01). |
| Last action | 2026-07-02 — Phase 3 executed (1 wave, 2 plans). Recovered from a stale-base worktree incident (03-02 worktree tried to mass-delete phases 11–15/backend/frontend; salvaged scoped files only, no data lost). Fixed CR-01/WR-01/WR-05 post-review (commit 37c3a37). |
| Next action | Phase 4 (Doc/Code Parity) needs planning: `/gsd-discuss-phase 4` then `/gsd-plan-phase 4`. |
| Open items | 03 human dry-run rollback on a test VM (SC#4) still pending; cd.yml WR-02/03/04 (host-key verification, remote set -e, health-loop) logged in 03-REVIEW.md, not yet fixed. |
| Deploy note | Local `main` is ~286 commits ahead of `origin/main`; armed `ci.yml` not yet on remote `main` — pushing this work to remote is a separate step. |
| Phase numbering | v1.0 = Phases 1–8. v2.0 occupied Phases 9–15 (shipped). |
| Follow-up queued | mypy 619-error burn-down = a new deferred phase (baseline ratchets down); sequence before/with Phase 8. |

## v1.0 Phase 2 Decisions (CONTEXT, 2026-06-30)

- **Triggers:** re-enable `push`→main + `pull_request`→main; keep `workflow_dispatch` (ci.yml:4–8).
- **Masks:** remove `|| true` from mypy (ci.yml:59), npm lint (95), tsc (97); drive surfaced errors to zero, no blanket suppressions.
- **ZAP DAST:** advisory — keep `continue-on-error`; run only on push-to-main + a nightly `schedule:` cron, NOT on PRs; not a required check.
- **Branch protection:** configured via `gh api` (operator has admin); require PR + checks `backend`, `frontend`, `semgrep`, `terraform`; documented in docs/13-deployment.md.
- **Boundaries:** cd.yml / update-path = Phase 3; new test authoring = Phase 8.

## v2.0 Closeout Notes (2026-06-30)

- **Quality gate green on production build:** Playwright suite 28 passed / 2 skipped (Firefox theme-bootstrap — unreliable colorScheme emulation; covered on Chromium+WebKit) / 0 failed. Bundle budget 15/15 routes ≤250 KB. Lighthouse mobile ≥90 perf+a11y on /login + /dashboard.
- **Open follow-ups for the design system (flagged, not silent):** three dark-theme contrast overrides were applied at the app layer (vendored `sunset.css` untouched) and must be reconciled into the `sketch-findings-getvul` skill — `--color-text-faint` #6B6488→#8B84A8 (globals.css), OWNER/ADMIN role badges + Open status pill lifted to brighter same-hue shades. Each carries a `DESIGN-SYSTEM GAP` comment.
- **Pending human:** Safari.app severity-glyph 14px legibility (D-02) — does not block the gate.
- **Light-theme WCAG** remains the explicitly-deferred UX-D-03 polish pass (the gate audits the shipping dark theme).

## v2.0 Phase Map

| Phase | Name | Requirements |
|-------|------|--------------|
| 9 | `/login` + Foundation | UX-01-01..05, UX-F-01..04 |
| 10 | `/dashboard` | UX-02-01..06 |
| 11 | `/vulnerabilities` + State Patterns | UX-03-01..06, UX-S-01..05 |
| 12 | `/assets` List + Detail | UX-04-01..05 |
| 13 | `/tickets` List + Detail | UX-05-01..06 |
| 14 | Remaining Screens | UX-06-01..04 |
| 15 | Mobile + a11y + Perf Quality Gate | UX-07-01..07 |

Coverage: 50/50 v2.0 requirements mapped. Foundation (UX-F-*) embedded in Phase 9 — no foundation-only phase. UX-D-* (future) and Out of Scope items intentionally unmapped.

## Deferred — v1.0 Production Readiness

v1.0 Phase 1 (Multi-Replica State) shipped 2026-05-09. Phases 2–8 deferred while v2.0 redesign takes precedence. Backend hardening work doesn't share files with frontend rebuild — can resume as a future v1.1 milestone in parallel or sequentially.

Phases preserved in [.planning/ROADMAP.md](ROADMAP.md) under the collapsed v1.0 section for reference. Recovery branch from the rolled-back v2-01 attempt: `v2-01-rollback-recovery` (at commit `c09194c`).

## Audit Reference

The v1.0 roadmap is sourced from a codebase audit performed 2026-05-08 against commit `8cede77`. The v2.0 redesign is sourced from a 6-sketch design exploration on 2026-05-12 — see [.planning/sketches/WRAP-UP-SUMMARY.md](sketches/WRAP-UP-SUMMARY.md) and `.claude/skills/sketch-findings-getvul/SKILL.md`.

## Workflow Notes

- GSD installed locally to `.claude/` via `npx get-shit-done-cc@latest --claude --local` on 2026-05-08.
- Sketch findings skill auto-loads on UI work per [CLAUDE.md](../CLAUDE.md) routing — every frontend implementation phase consumes the 7 reference files.
- v0.1 features in [PROJECT.md](PROJECT.md) "Validated Requirements" remain intact; v2.0 rebuilds the UI surface, not the backend.
- **Anti-pattern guarded:** No foundation-only phase. UX-F-01..F-04 (token system, theme architecture, persistent shell, first primitive set) ride inside Phase 9. The rolled-back v2-01 attempt failed because it shipped foundation without a visible screen ("looks worse than before"). v2.0 ships visible screens from day one.

## Decisions

- DrillPanel chrome generalized additively (D-D-02): idKey/id/renderContent/ariaLabel props with vuln-preserving defaults; cveId kept as back-compat alias
- close() deletes 'open' + active idKey; ticket callers pass idKey='ticket'; vuln callers get default idKey='cve'
- TicketDrillData type exported from ticket-drill-content.tsx for Plan 07 contract
- renderBlockedToggle slot renders disabled placeholder when absent (Plan 06/08 wires real BlockedToggle)
- WatcherStack role-priority Map dedupes by userId (assignee=0, reporter=1, watcher=2); strongest wins per unique userId
- ActivityTimeline groups by local calendar day key (YYYY-MM-DD) to avoid locale issues; ascending sort D-C-04
- BlockedToggle whitespace-only reason coerces to null per D-P-02; backend validator mirrors this
- CommentInput Ctrl/Cmd+Enter shortcut; char-count warning at 9500 chars before 10000 hard limit
- TicketAssetCard null assetId renders "Multiple hosts" with no link (multi-host ticket safety)
- asana_not_configured error renders connector deep-link EmptyState (D-S-02), not PartialFailureBanner — expected "unconfigured" signal vs transient failure
- useMarkBlocked patches both byId cache AND list cache in onMutate for immediate table row update
- Predicate-based invalidation targets ['assets', *, 'remediations'] on blocked toggle success (RESEARCH Pattern 4)
- Board placeholder copy verbatim: "Board view coming in a future update — for now, use the List view with the Status chip filter to organize work by status."
- CURRENT_USER_ID = '' stub in /tickets/[id] page: no established global user hook; watch toggle functional (server truth authoritative on invalidation); optimistic 'You' watcher patch is degraded until a session context is introduced
- buildWatcherList constructs D-W-04-compliant role-tagged watcher list on the page (not inside WatcherStack): merge assignee+reporter+watchers, dedupe by userId (strongest role: assignee=0 > reporter=1 > watcher=2), sort chronologically
- Phase 15-01: used --legacy-peer-deps for npm install (lucide-react 0.383.0 peer react@^18 vs project's React 19); consistent with existing overrides in package.json
- Phase 15-01: Playwright 1.61.1 resolved (plan specified ~1.60); API-compatible, no breaking changes
- Phase 15-02: nav-items.ts single source-of-truth for all 9 nav destinations consumed by sidebar/bottom-nav/drawer/more-sheet
- Phase 15-02: NavDrawer kept mounted with translate (not null-guarded) for motion-safe:transition; NavMoreSheet uses null-guard (vaul portal lifecycle)
- Phase 15-02: topbar.tsx promoted to 'use client' — onMenuClick/hamburgerRef props added; hamburger conditional on prop presence (backward-compatible)
- Phase 15-02: Bottom-nav gradient-strip on TOP edge (inverted from sidebar's left edge) per bar orientation
- Phase 15-02: MORE_ITEMS computed via Set subtraction from ALL_ITEMS — future BOTTOM_NAV_PRIMARY changes auto-update MORE_ITEMS
- Phase 15-03: ResponsiveDialog if(!open) return null guard (matches drill-panel-mobile precedent; preserves queryByRole('dialog')===null jsdom contract)
- Phase 15-03: isMobile guard skips programmatic focus + Tab trap in ConfirmModal — vaul manages focus natively on mobile
- Phase 15-03: Skeleton loading animate-pulse in hero.tsx NOT converted — transient state, acceptable via globals.css blanket per research audit
- Phase 15-03: motion-safe: Tailwind prefix used for gradient-drift + urgency dot (belt-and-suspenders alongside globals.css blanket; UX-07-04)
- Phase 15-04: watcher-stack.tsx Escape key moved to outer wrapper div (no role) — jsx-a11y/no-noninteractive-element-interactions satisfied without changing dialog semantics
- Phase 15-04: backdrop split pattern (role=presentation outer + role=dialog inner) — AT announces only the inner dialog; Escape/click-outside on outer div
- Phase 15-04: Wrapper.displayName='Wrapper' pattern for factory-returned test components (react/display-name); vitest-axe.d.ts eslint-disable comments removed (nonexistent rule)

---
*Last updated: 2026-06-30 — Phase 15 COMPLETE & verified (7/7 SC). Full quality gate green on the production build (Playwright 28 passed, bundle 15/15, Lighthouse ≥90). v2.0 UI/UX Redesign milestone COMPLETE (Phases 9–15). 676 unit tests + lint green.*
