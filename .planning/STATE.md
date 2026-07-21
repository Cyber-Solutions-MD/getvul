---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Deferred UI Features
status: Ready to execute
last_updated: "2026-07-21T12:46:29.563Z"
progress:
  total_phases: 15
  completed_phases: 12
  total_plans: 41
  completed_plans: 41
  percent: 100
---

# STATE — GetVul GSD Session Memory

## Project Reference

See: [.planning/PROJECT.md](PROJECT.md) (updated 2026-05-12)

**Core value:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console.

**Current focus:** Phase 21 — page-transition-verification

## Current Position

Phase: 21 (page-transition-verification) — EXECUTING
Next: `/gsd-plan-phase 18`
Prior: Phase 17 (page-transition-motion) COMPLETE — human-UAT checkpoint OUTSTANDING (17-02 Task 4: perceptual cross-fade, chrome stillness, DrillPanel-during-transition, Firefox feel).
Plan: 2 of 2
| Field | Value |
|-------|-------|
| Active milestone | v2.2 Deferred UI Features — **OPENED 2026-07-15** (Phases 16–19). v1.0 (1–8), v2.0 (9–15), v2.1 (BL-01..05 backlog) all shipped. Next: `/gsd-plan-phase 16`. Locked: View Transitions API (motion) + @dnd-kit (kanban). |
| History (v1.0, retained) | Rows below describe the v1.0 Phase 6/7 era and are kept as accumulated context. |
| Active milestone (v1.0, archived) | v1.0 Production Readiness — **RESUMED 2026-06-30** (Phases 1–6 done; Phases 7–8 remaining) |
| Last completed phase | 6 — Default Admin Hardening ✓ (2026-07-09) — forced first-login password rotation for the install.sh admin. Migration 029 adds `users.must_change_password` (NOT NULL, server_default false); `create_admin.py` seeds it true on the OWNER admin; JWT carries the claim through to `CurrentUser`; `get_current_user` 403-gates all non-allowlist routes (`password_change_required`) while flagged; `/auth/change-password` clears the flag, emits `auth.first_login_rotation`, returns fresh flag-free tokens, and rejects reusing `Admin123!`; frontend `/change-password` page (Phase 9 primitives + sunset tokens) + `auth.tsx` redirect gate. Verifier 5/5 must-haves. PROD-06-01..04 Complete. |
| Last action | 2026-07-09 — Phase 6 executed via `/gsd-execute-phase 6` (4 plans, 3 waves, worktree parallel; Wave 1 06-00/06-01 in parallel). Both Wave-1 agents hit the known stale-base hazard and self-recovered via the branch-check reset; 06-00/06-01 both authored `test_admin_hardening.py` (add/add merge conflict resolved in favor of owner 06-00). Verifier first pass found SC#4 blocker (WR-01: `/auth/login` UserInfo omitted `must_change_password`, so the SPA redirect gate never fired on the primary login path — only after a hard reload via `/auth/me`). Fixed inline (commit db20589): added the field to `UserInfo` schema + populated in `issue_tokens()`, plus backend + frontend regression tests. Re-verify 5/5 passed. |
| Next action | Phase 7 (Health and Observability). `/gsd-discuss-phase 7` → `/gsd-plan-phase 7` → `/gsd-execute-phase 7`. |
| Open items | Phase 6: 3 non-blocking code-review findings in 06-REVIEW.md unfixed — WR-03 (React crash if `/auth/change-password` error `detail` is a non-string object), WR-04 (over-broad `create_admin` skip guard counts password users across all tenants), WR-05 (brittle literal `"Admin123!"` reject permits near-default rotations like `Admin1234!`). Run `/gsd-code-review-fix 06` to address. Also 2 pre-existing environmental test failures on local runs (test_rate_limit.py needs real Redis + doc/security.md; test_snooze.py async-teardown) — Docker-only, not phase-6 regressions. Phase 5: 1 human-UAT item outstanding (05-HUMAN-UAT.md). Phase 4: 03 human dry-run rollback on a test VM (SC#4) pending; cd.yml WR-02/03/04 in 03-REVIEW.md unfixed. |
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

- [Phase 18]: 18-00: --legacy-peer-deps required for @dnd-kit/core install (pre-existing lucide-react/React19 peer conflict blocks any plain npm install)
- [Phase 18]: 18-00: useMarkBlocked onMutate/onError switched from exact setQueryData(['tickets']) to fuzzy setQueriesData/getQueriesData({queryKey:['tickets','list']}) — fixes Pitfall 1 latent list-cache no-op and unblocks board optimistic reprojection
- [Phase 18]: 18-01: Board DOM contract pinned (data-column + data-ticket-id) via RED e2e spec; KanbanReasonPromptProps (ticketLabel/onSave/onCancel) pinned via RED unit spec mirroring blocked-toggle.tsx
- [Phase 18]: 18-02: severity-glyph.ts extracted as single-source SEVERITY_GLYPH/SEVERITY_CLASS consumed by tickets-table.tsx and kanban-card.tsx
- [Phase 18]: 18-02: kanban-card.tsx calls useDraggable unconditionally even for overlay clone (react-hooks/rules-of-hooks) — overlay branch skips attaching ref/listeners, not the hook call
- [Phase 18]: 18-02: kanban-column.tsx drops aria-disabled on role=region (unsupported ARIA prop for that role); opacity-40 dim cue alone satisfies D-DRAG-03
- [Phase 18]: 18-03: board is pure projection of bucketTickets(rows), no local ticket-row state; onDragEnd gates only read-only->Blocked (via reason prompt) and Blocked->read-only (immediate unblock)
- [Phase 18]: 18-03: KanbanReasonPrompt renders in a fixed top-centered overlay (not anchored to drop position); board lazily imported via next/dynamic({ssr:false}) keeping @dnd-kit off First-Load JS (/dashboard/tickets confirmed 167 kB)
- [Phase 18]: Keyboard coordinateGetter tracks column index via useRef, not context.over (avoids collision-detection lag under rapid keypresses)
- [Phase 18]: 18-04 gate evidence fixed 3 live e2e-spec race conditions (networkidle wait, Save-click settle wait, post-mutation reflow settle wait) rather than only documenting them, since they blocked producing genuine gate evidence
- [Phase 21]: 21-01: ChipBar severity chip is present/visible in e2e data state -> used as the real no-fade router.replace trigger (Pattern 3), not a skip
- [Phase 21]: 21-01: Playwright-managed Firefox (151.0) now natively supports document.startViewTransition -> CSS-keyframe fallback path is unreachable on this engine; Firefox test rewritten as a feature-detecting dual-branch assertion, verified green via the native-VT branch (5 named animations observed live)
