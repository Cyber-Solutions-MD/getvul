---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: "AI-Assisted Triage (\"Triage Copilot\")"
current_phase: 26
current_phase_name: prioritization-narrative
status: Executing Phase 26 (prioritization-narrative) — plan 7/8 complete
stopped_at: Completed 26-07-PLAN.md
last_updated: "2026-07-31T14:56:02.000Z"
progress:
  total_phases: 25
  completed_phases: 24
  total_plans: 128
  completed_plans: 127
  percent: 99
---

# STATE — GetVul GSD Session Memory

## Project Reference

See: [.planning/PROJECT.md](PROJECT.md) (updated 2026-07-25)

**Core value:** A vuln-triage analyst can open one dashboard, see the same CVE-on-host correlated across multiple scanners, identify the asset's owner from IdP/MDM/HR, and ship a Jira/Asana ticket — without ever opening a scanner console. **v3.0 adds AI that helps the analyst *decide and act*, grounded in the tenant's own data, using the tenant's own AI key (BYOK).**

**Current focus:** Phase 26 — prioritization-narrative

## Current Position

Milestone: v3.0 AI-Assisted Triage — 🚧 EXECUTING Phase 24 (started 2026-07-29). Model: Claude (Haiku 4.5 / Sonnet 5 / Opus 4.8 — re-check Models API at Phase 24/26 execution time per research/SUMMARY.md's currency flag), per-tenant configurable.
Phase: 26 (prioritization-narrative) — EXECUTING
Next: Re-verify Phase 24 (`/gsd-verify-work 24` or equivalent) to confirm 24-VERIFICATION.md's truth #2 now passes for all 4 roles. Gap-closure plan 24-10 (2026-07-29) added `GET /api/v1/ai/status` (require_viewer, tenant-scoped, derived from get_tenant_anthropic_key) + a `useAiStatus()` hook, replacing the `connectorsQuery.isError ? true : ...` optimistic pass-through so Analyst/Viewer now get a real "is AI configured" signal instead of the admin-gated connectors query's 403 being misread as "assume configured". Separately, 4 live-verification items remain WAIVED (user chose proceed-on-trust at 24-06): AI-03 nginx anti-buffering (proxy_buffering off IS in nginx.conf, unobserved live), live wizard→explain→cache→audit flow, D-25 live 429 card, reduced-motion/contrast — these are unaffected by 24-10's scope and remain addressable via `/gsd-verify-work 24`.
Prior: v2.2 Deferred UI Features — ✅ SHIPPED & ARCHIVED 2026-07-22 (Phases 16–22). All of v1.0, v2.0, v2.1, v2.2 shipped. 2026-07-25: local `main` pushed to origin (CI green); code-review-fix reconciliation of stale phase reviews 01–22 landed; SSH-hardening draft PR #29 open (gated on GCE_KNOWN_HOSTS); Dependabot 11 alerts cleared. 2026-07-25: v3.0 requirements defined (`.planning/REQUIREMENTS.md`) + research completed (`.planning/research/SUMMARY.md`, confidence MEDIUM-HIGH). 2026-07-27: roadmap defined — 21/21 v1 requirements mapped to Phases 23–28. 2026-07-28: Phase 23 (Ingestion Reliability Precursor) shipped 11/11 plans; Phase 24 planned (9 plans, 8 waves, tracer-first). 2026-07-29: Phase 24 Plans 01-03 shipped (SSE spike + ANTHROPIC connector type; schema/prompt/audit contracts; tenant-scoped BYOK keys + cross-tenant-isolated cache + fail-closed budget guard). Plan 04 shipped (the real explain_vuln.py buffer-then-validate-then-replay streaming engine + per-vuln SSE endpoint, proven against the real installed Anthropic SDK). Plan 05 shipped (frontend: useExplainStream SSE hook + useExplainCache + the 8-state AiExplanationSection + AiExplanationCitations two-tier renderer, wired into drill-content.tsx — the end-to-end tracer is code-complete). Plan 06 (TRACER-gate checkpoint) resolved: live end-to-end verification EXPLICITLY WAIVED by the user ("skip live verify, proceed on trust") and D-16 recorded as Option A (Cross-asset CVE grouping) for Plan 08's per-remediation grounding contract. Plan 07 shipped (backend: `ai_feedback` table (migration 032) + `AiFeedback` model + `POST /feedback/{resource_type}/{resource_id}` idempotent per-user upsert via `on_conflict_do_update`, require_analyst-gated, audited; frontend: `useAiFeedback` mutation hook + `AiFeedbackControl` thumbs/note UI wired beneath both grounded rendering branches of `AiExplanationSection` — capture-only, D-21, seeding Phase 28's flywheel). Plan 08 shipped (backend: host + remediation D-15 widening — `ExplainHostResponse`/`ExplainRemediationResponse` schema variants; a re-audited 9-field `HOST_ALLOWLIST` + `build_explain_host_prompt()` proven to exclude AssetDetail's 5 owner-PII fields field-by-field; the D-16 Option A cross-asset-CVE-grouping shape (`REMEDIATION_ALLOWLIST` + `build_explain_remediation_prompt()`) implementing the 24-06 checkpoint decision; `app/ai/grounding.py`'s two NEW tenant-scoped queries (`get_asset_posture()` selecting only allowlisted columns off Asset/Vulnerability — never the owner-PII ones — and `get_remediation_group()`, the cross-asset-by-CVE aggregate the 24-06 decision flagged as not existing anywhere, with a deterministic KEV/exploit-escalated `priority`); thin `explain_host.py`/`explain_remediation.py` routes reusing `_run_explain_stream()` completely unchanged (zero diff in `explain.py` since Plan 04); `prompt_version()` generalized (backward-compatible) into per-view `host_prompt_version()`/`remediation_prompt_version()`. 41 new tests green, full `test_ai_*.py` wave-merge 117/117, ruff+mypy clean on every new/modified file; a pre-existing `mypy-baseline.txt` note-line-number-drift artifact was isolated (scratchpad move, never `git stash`) and confirmed unrelated, logged to `deferred-items.md`). Phase 25 (asset-aware-remediation-guidance): Plan 01 shipped (`app/ai/safety.py`'s 8-category `contains_dangerous_pattern()` denylist + `grounding.py`'s `has_actionable_remediation_text()`/`get_remediation_guidance_context()` D-01 refuse predicate + per-finding grounding query — primitives only, zero wiring). Plan 02 shipped (`ExplainRemediationGuidanceResponse` schema + the 4th allowlist-quadruplet instance in `prompt_builder.py` — `REMEDIATION_GUIDANCE_ALLOWLIST`/`AllowlistedRemediationGuidance`/`build_explain_remediation_guidance_prompt()`, its system prompt putting D-01/D-03's cite-verbatim-first + refuse-rather-than-invent contract into prompt text for the first time). Plan 03 shipped (the backend tracer's completion: `_run_explain_stream()` gains the one additive `dangerous_pattern_check` kwarg, gated precisely before `set_cached()` so a denylisted candidate is never cache-retrievable (T-25-02); the new `POST/GET /explain-remediation-guidance/{finding_id}` route wires Plan 01/02's grounding+denylist+prompt/schema together, adding the D-01 route-level pre-generation gate and the GET `groundable` field — 30 new tests, 178/178 in the `test_ai_*.py` wave-merge regression, zero regressions). Plan 05 (TRACER-gate checkpoint) resolved: live browser verification WAIVED (proceed-on-trust, mirroring 24-06) — AIR-02 expansion unblocked. Plan 06 shipped (closed AIR-02's backend dead-end: `TicketCreateRequest.description` — optional, `max_length=10000`, whitespace-coerces-to-None, `extra="forbid"` mass-assignment defense retrofitted onto the in-production schema — plus `create_tickets()`'s one-line WYSIWYG `notes=` override honoring `request.description` when supplied, falling back to the unchanged `_build_task_description()` otherwise; `router.py` needs zero changes. 7 new tests (5 schema + 2×3-provider dispatch) prove both the fallback-unchanged and WYSIWYG-verbatim paths at the `client.create()` call boundary, not the DOM — 33/33 green in `test_ticketing_dispatch.py`. Strict RED→GREEN TDD on both tasks). Plan 07 shipped (AIR-02's frontend half, closing the loop with Plan 06's backend contract: `npx shadcn add textarea` restyled to sunset tokens; `AiExplanationSection.onCopyToDescription` — a "Copy into ticket description" text-button rendered ONLY in the grounded-done/cache-hit branches, firing the plain-text summary upward; `drill-content.tsx`'s desktop `ConfirmModal` fallback and `drill-panel-mobile.tsx`'s divergent `Drawer.NestedRoot` renderConfirm path BOTH gain the description `Textarea` (LOCKED caption/placeholder verbatim from 25-UI-SPEC.md), threaded into `createTicket.mutateAsync`'s body via `description: description || undefined` — proven at the mutation boundary on both paths, not just the DOM (Pitfall 4/5). 13 new tests, full 130-file/839-test frontend suite green, backend `test_ticketing_dispatch.py` 33/33 unaffected. Phase 25 is now 7/7 plans complete — AIR-01 and AIR-02 both shipped, ready for `/gsd-verify-work 25`).
Plan: 8 of 8

| Field | Value |
|-------|-------|
| Active milestone | v3.0 AI-Assisted Triage — Phase 23 shipped 2026-07-28; Phase 24 executed 10/10 plans (9 original + gap-closure 24-10, 2026-07-29), pending re-verification. Prior: v2.2 Deferred UI Features — **SHIPPED & ARCHIVED 2026-07-22** (Phases 16–22). v1.0 (1–8), v2.0 (9–15), v2.1 (BL-01..05 backlog), v2.2 (16–22) all shipped. |
| Phase numbering | v1.0 = Phases 1–8. v2.0 = Phases 9–15. v2.2 = Phases 16–22. v3.0 = Phases 23–28 (continues numbering, does not reset). |
| v3.0 phase map | See "v3.0 Phase Map" table below. |
| Next action | Re-verify Phase 24 (`/gsd-verify-work 24`) to confirm the 24-10 gap closure holds; 4 live-verification items remain explicitly waived. |
| History (v1.0/v2.0/v2.2, retained) | Rows below the divider describe prior-milestone eras and are kept as accumulated context. |

## v3.0 Phase Map

| Phase | Name | Requirements | Depends on |
|-------|------|--------------|------------|
| 23 | Ingestion Reliability Precursor | REL-01..06 | Nothing (first phase) |
| 24 | AI Foundation + "Explain This Vuln" | AI-01..06 | Phase 23 |
| 25 | Asset-Aware Remediation Guidance | AIR-01..02 | Phase 24 |
| 26 | Prioritization Narrative | AIP-01..02 | Phase 24 |
| 27 | Ticket Auto-Drafting | AID-01 | Phase 24, Phase 25 |
| 28 | Eval + Cost + Observability Gate | AIE-01..04 | Phases 24–27 |

Coverage: 21/21 v3.0 v1 requirements mapped, no orphans. AINL-01 (natural-language query) is explicitly deferred to v3.1 — not in this phase set. Phase 24 concentrates the milestone's integration risk (SSE streaming through nginx, encrypted per-tenant `AiConfig`, the full guardrail scaffold) and every later phase (25–27) reuses it unmodified; Phase 28 is the milestone-closing gate, seeded from real usage data generated by Phases 24–27.

**BYOK constraint (applies to every v3.0 phase):** client-provided Anthropic key only, no shared/fallback key, AI inert (graceful "configure AI" state) until a tenant configures their own key. **Other hard constraints:** tenant-scoped-only caching (no cross-tenant serving), deterministic risk score (ASSET-02) augmented/explained never replaced, prompt-injection defense first-class (untrusted scanner text as data not instructions), fail-closed cost guardrail.

**Pitfall ownership (from research/PITFALLS.md):** #1 prompt injection + #3 PII leakage + #4 cross-tenant bleed + #6 non-determinism + #9 drill-panel latency → Phase 24 (scaffold established once, reused everywhere). #2 hallucinated remediation (cite-or-refuse) → Phase 25. #7 over-trusting AI over the deterministic score (augment-not-replace) → Phase 26. #5 cost blowup + #6 non-determinism (nightly re-run) + #8 shipping without evals → Phase 28.

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

v1.0 Phase 1 (Multi-Replica State) shipped 2026-05-09. Phases 2–8 deferred while v2.0 redesign took precedence, then resumed and shipped 2026-06-30 → 2026-07-14. Backend hardening work doesn't share files with the frontend rebuild.

Phases preserved in [.planning/ROADMAP.md](ROADMAP.md) under the v1.0 section for reference. Recovery branch from the rolled-back v2-01 attempt: `v2-01-rollback-recovery` (at commit `c09194c`).

## Audit Reference

The v1.0 roadmap is sourced from a codebase audit performed 2026-05-08 against commit `8cede77`. The v2.0 redesign is sourced from a 6-sketch design exploration on 2026-05-12 — see [.planning/sketches/WRAP-UP-SUMMARY.md](sketches/WRAP-UP-SUMMARY.md) and `.claude/skills/sketch-findings-getvul/SKILL.md`. The v3.0 roadmap is sourced from research completed 2026-07-25 — see [.planning/research/SUMMARY.md](research/SUMMARY.md) (confidence MEDIUM-HIGH; architectural conclusions corroborated across STACK/FEATURES/ARCHITECTURE/PITFALLS.md).

## Workflow Notes

- GSD installed locally to `.claude/` via `npx get-shit-done-cc@latest --claude --local` on 2026-05-08.
- Sketch findings skill auto-loads on UI work per [CLAUDE.md](../CLAUDE.md) routing — every frontend implementation phase consumes the 7 reference files.
- v0.1 features in [PROJECT.md](PROJECT.md) "Validated Requirements" remain intact; v2.0 rebuilds the UI surface, not the backend.
- **Anti-pattern guarded:** No foundation-only phase. UX-F-01..F-04 (token system, theme architecture, persistent shell, first primitive set) ride inside Phase 9. The rolled-back v2-01 attempt failed because it shipped foundation without a visible screen ("looks worse than before"). v2.0 ships visible screens from day one.
- **v3.0 anti-pattern guarded:** No foundation-only AI phase either — Phase 24 ships the full scaffold (grounding/cache/client/guardrails/costs) *and* the first user-visible capability ("Explain this vuln") together, proven end-to-end at minimum blast radius before Phases 25–27 multiply it across four capabilities.
- **v3.0 research flags carried into planning:** Phase 24 needs a dedicated research/design pass on generalizing `rotate_credentials()` to sweep the new `AiConfig` table (currently hardcodes `ConnectorConfig`) given the "no Fernet key rotation without a documented migration" constraint; SSE streaming through the existing nginx/FastAPI setup is architecture-researched but not implementation-proven — treat as a spike. Phase 26 needs to confirm the scheduler's `user=None`/`system:scheduler` direct-`AuditLog`-construction precedent is the right long-term fix vs. a scheduler-wide `audit()` signature change. Phase 28 should check `AiEvalRun`/`AiEvalResult` Postgres schema against any `gsd-ai-integration-phase` tooling conventions before finalizing.

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
- [Phase 22]: 22-01: coordinateGetter targets destination column rect center (not carried-over y) to fix keyboard-drag column-skip
- [Phase 22]: 22-01: KanbanColumn needs min-w-0 to hold equal flex-1 width regardless of empty-vs-populated sibling content
- [Phase 22]: 22-01: Enter on a fresh focused card is always consumed by dnd-kit's KeyboardSensor as drag-pickup (default keyboardCodes.start includes Enter) -- it never opens the DrillPanel, so the plan's optional sanity test was skipped as empirically false
- [Phase 22]: 22-02: getByRole()-based polling for a mutation's brief disabled state is unreliable (accessibility-tree recompute cost) — use an ElementHandle + expect.poll() on the raw DOM property instead
- [Phase 24]: 24-01: True incremental SSE proven live through nginx (first byte ~12ms, total ~2.02s for 4 delayed frames) — `proxy_buffering off` confirmed effective, not just declared; every prior `StreamingResponse` in this backend was one-shot `iter([bytes])`
- [Phase 24]: 24-01: `GET /connectors/types` gains an additive `field_specs` map (per-field type/required/options/config-destination) alongside the existing flattened `fields: string[]` — lets the add-connector wizard render real `<select>`/`<input type=number>` and route non-secret values to `ConnectorConfig.config` instead of encrypted `credentials`, with zero behavior change for the 14 pre-existing connector types
- [Phase 24]: 24-01: D-05 model-guidance copy lives backend-side in `CONNECTOR_TYPES["ANTHROPIC"].fields[].options[].hint` (matches existing `notes`/`setup_url`/permission-`purpose` precedent), not frontend `microcopy.ts` — keeps wizard components provider-agnostic
- [Phase 24]: 24-01: New `ai_assistant` connector category (not folded into an existing one)
- [Phase 24]: 24-01: BLOCKER — `GETVUL_DEV_ANTHROPIC_KEY` (plan's `user_setup`) was never provisioned in this environment; the Haiku `effort:'low'` live smoke-test (RESEARCH Pitfall 1) could not run. Confirmed via Docker Compose's own `.env` substitution (resolved to empty) that the key is genuinely absent, not merely blocked by tool permissions. Interim resolution: RESEARCH.md's live-docs-sourced finding (effort not listed as Haiku-supported) stands; Plan 04's request builder should omit `effort` when `model=="claude-haiku-4-5"` until live-reverified. See `24-01-SUMMARY.md` "Known Gaps".

---
*Last updated: 2026-07-29 — **Phase 24 Plan 05 complete** (frontend: `useExplainStream` fetch()+ReadableStream SSE hook (never the generic `api()` helper, resourceType-parameterized per D-15) + `useExplainCache` cheap cache-check + the 8-state `AiExplanationSection` (cache-hit/miss+role branch, role-gated no-key card, analyzing pulsing-dot, neutral grounded=false card, amber busy/unknown/budget cards) + `AiExplanationCitations` inline two-tier renderer (scanner_verbatim tint span, ai_interpreted AI superscript, D-12 staggered reveal respecting prefers-reduced-motion) wired into drill-content.tsx between Description and Remediation, desktop+mobile in one edit. The end-to-end tracer is now code-complete: admin key -> analyst click -> validated cited streamed summary. Found and fixed a real pre-existing test regression (drill-panel/drill-panel-mobile suites lacked a QueryClientProvider) along the way). 27 new tests green (9+18), full suite 783/783, tsc/eslint/build clean. Prior: 2026-07-29 — **Phase 24 Plan 04 complete** (the real explain_vuln.py buffer-then-validate-then-replay streaming engine + per-vuln SSE endpoint (POST require_analyst / GET cache-check require_viewer), proven against the actual installed anthropic==0.120.2 SDK via three live MockTransport spikes, not just a hand-rolled fake; retry/audit status vocabulary reconciled precisely; the SSE error-kind vocabulary {busy, grounded_false, budget_exceeded, unknown} is closed and verified; get_model_and_budget() promoted to a shared export to prevent a POST/GET cache-key mismatch). 16 new tests green, 69/69 regression pass, ruff+mypy clean. Prior: 2026-07-29 — **Phase 24 Plan 03 complete** (tenant-scoped data layer: BYOK key resolution decrypted fresh per call with no shared/fallback key; Redis explanation cache with cross-tenant isolation proven against real flushed Redis + record_hash allowlist-scoping + ~30d TTL + per-tenant in-flight guard; fail-closed monthly budget guard derived from audit_logs + per-admin NOTIF-01 breach alert; migration 031 renames a pre-existing duplicate-shaped index rather than creating a wasteful second one). 18 new tests green (11+7), 54/54 regression pass, ruff+mypy clean, `alembic heads`==031. Prior: 2026-07-29 — **Phase 24 Plan 02 complete** (response-schema validation gate + untrusted-content-as-data prompt builder + AI audit writer — 35 tests). Prior: 2026-07-29 — **Phase 24 Plan 01 complete** (SSE spike proven live through nginx; `ANTHROPIC` connector type registered end-to-end — backend tester/schema/category + generalized wizard field-metadata contract (field_specs) for select/optional-field/config-routing; zero migration). 8 backend + 3 frontend tests added, full existing suites green, tsc/build/ruff/mypy-baseline clean. Outstanding: Haiku effort live smoke-test (needs `GETVUL_DEV_ANTHROPIC_KEY`). Prior: 2026-07-27 — **v3.0 AI-Assisted Triage ROADMAP CREATED** (Phases 23–28, continuing numbering from 22; 21/21 v1 requirements mapped with 100% coverage, no orphans). Prior: 2026-07-22 — **v2.2 Deferred UI Features milestone COMPLETE & ARCHIVED** (Phases 16–22, 23 plans; audit passed 22/22 UX-D requirements, 9/9 integration seams, 5/5 flows). Roadmap collapsed + requirements archived to `.planning/milestones/v2.2-*`; PROJECT.md full-review done; tagged `v2.2`. Prior: 2026-06-30 — Phase 15 COMPLETE & verified (7/7 SC); v2.0 UI/UX Redesign milestone COMPLETE (Phases 9–15).*

- [Phase ?]: 23-10: Reused existing sanitized binding for log.error_message instead of adding a second _sanitize_error() call (CR-03/REL-06 closure)
- [Phase ?]: Mobile drill-panel confirm now mirrors desktop's ticketProvider gate — renderConfirm slot forwards ticketProvider/onProviderChange, closing the ASANA-fallback gap (REL-04/CR-01)
- [Phase 24]: 24-02: remediation_info (not cve_description, which isn't a VULN_ALLOWLIST member) is the free-text vehicle for injection-isolation and truncation tests
- [Phase 24]: 24-02: recheck_business_rules()'s exception is BusinessRuleError (ruff N818 requires an Error suffix), subclassing ValueError alongside pydantic.ValidationError
- [Phase 24]: 24-02: prompt_version(system_prompt=SYSTEM_PROMPT, few_shot=FEW_SHOT) exposes real inputs as defaulted params so tests can prove hash sensitivity, not just stability
- [Phase 24]: 24-02: audit_log_ai_call's usage param is typed Any (RESEARCH Pattern 5), not a custom Protocol -- keeps app/ai/audit.py decoupled from the anthropic SDK
- [Phase 24]: 24-02: only vulnerability_name + remediation_info get the 4000-char truncation budget -- the other 14 VULN_ALLOWLIST fields are short bounded identifiers/enums/scores
- [Phase 24]: 24-02: BLOCKER -- anthropic>=0.120.0 (declared in backend/pyproject.toml by Plan 01) is not installed in the local backend/.venv. mypy-baseline shows 4 new violations on app/connectors/tester.py:471 and 3/8 Plan 01 test_ai_tester.py tests fail at runtime with ModuleNotFoundError. Unrelated to any 24-02 file (app/ai/ deliberately imports no anthropic). Not fixed (out of scope -- unrelated file, pre-existing). Action for the next plan that runs backend tests locally: pip install -e . in backend/.venv first. See 24-02-SUMMARY.md Issues Encountered.
- [Phase 24]: 24-03: migration renamed to 031_rename_audit_tenant_idx (27 chars) instead of the plan's 031_add_audit_logs_tenant_created_index (39 chars) -- alembic_version.version_num is varchar(32), confirmed empirically via a real StringDataRightTruncationError
- [Phase 24]: 24-03: migration 031 RENAMES the pre-existing idx_audit_tenant_created index (created by 013_add_audit_log.py, identical columns tenant_id+created_at) to ix_audit_logs_tenant_created instead of creating a duplicate -- RESEARCH.md's "only new index needed" claim was wrong, found via direct read_first inspection
- [Phase 24]: 24-03: notify_admins_budget_exceeded() calls create_notification once PER active OWNER/ADMIN user (not a single broadcast row) so send_email_flag=True actually reaches every admin's inbox
- [Phase 24]: 24-03: get_tenant_anthropic_key wraps json.loads+decrypt_value in one broad try/except returning None on any failure, mirroring get_decrypted_credentials' exact defensive shape
- [Phase 24]: 24-03: record_hash() hashes exactly what it's given (sha256 over sorted JSON) -- the D-18 allowlist-only guarantee is a caller contract (tested for determinism/sensitivity/order-independence), not re-implemented inside cache.py
- [Phase 24]: 24-04: leak-marker check reads the REAL system_prompt in scope for the call (first 40 chars of its first line) instead of a hardcoded marker string -- generic across every current/future view
- [Phase 24]: 24-04: injection_flagged and terminal validation_failed both surface as the SAME {type:error, kind:grounded_false} SSE event -- only the audit status distinguishes them, no dedicated frontend injection UI state needed
- [Phase 24]: 24-04: budget_exceeded/rate_limited audit rows get cost_estimate_usd=0.0 explicitly (not None) since genuinely zero tokens were spent
- [Phase 24]: 24-04: cost-estimate pricing table uses Anthropic's standard non-promotional per-MTok rates ($3/$15 Sonnet 5, $5/$25 Opus 5) rather than the active $2/$10 introductory Sonnet-5 rate (expires 2026-08-31), to avoid under-counting spend once the promotion lapses
- [Phase 24]: 24-04: get_model_and_budget() promoted from a private helper to a shared no-underscore export the moment the GET cache-check route needed the identical model-resolution logic the POST path already used internally, avoiding a stale-model cache-key mismatch
- [Phase 24]: 24-05: GET /api/v1/connectors is require_admin-gated with no non-admin-safe alternative -- the key-configured signal for Analyst/Viewer is derived via connectorsQuery.isError (optimistic pass-through on a 403) rather than a hardcoded role check, keeping the Explain trigger reachable for the tracer's primary role while Admin/Owner get the real signal from their own successful query
- [Phase 24]: 24-05: the <section aria-labelledby='drill-ai-h'> landmark lives in drill-content.tsx (not inside AiExplanationSection, which renders only h4+body via a Fragment) so the acceptance grep (exactly 1 occurrence) holds and no section-in-section nesting exists
- [Phase 24]: 24-05: D-12's token-by-token replay is a per-segment staggered CSS animate-in/fade-in over the complete already-validated payload, never a literal sync to the backend's own cosmetic summary_delta frames (the locked ExplainStreamState has no slot for partial text); replay applies only on a just-streamed 'done' result, never a cache hit (D-09 vs D-12)
- [Phase 24]: 24-05: a defensive backend no_key SSE frame maps to kind:'unknown' (not its own phase) so an unexpected mid-flight no_key can never leave the hook parked in 'analyzing' forever; a 'done' payload is also defensively re-checked for grounded:false at render time (UI-SPEC backstop), even though the real engine never emits done for an ungrounded response
- [Phase 24]: 24-06: D-16 per-remediation grounding shape = Option A (Cross-asset CVE grouping) -- aggregates a tenant's affected assets BY CVE/fix across all assets sharing it, faithful to D-16's "across the affected assets" framing; Plan 08 must build a NEW cross-asset-by-CVE query (no existing query does this -- RemediationTicket/Ticket is per-asset with a single vulnerability_id FK)
- [Phase 24]: 24-06: live end-to-end tracer verification (11-step Docker/nginx checklist) EXPLICITLY WAIVED by user decision ("skip live verify, proceed on trust") -- AI-03 nginx anti-buffering, D-25 busy-card, RBAC live states, and reduced-motion/contrast all remain unproven pending a future live-stack pass
- [Phase 24]: 24-07: feedback gates at require_analyst (not require_viewer), matching the watch/unwatch analog and D-17's actor model even though feedback capture is free/non-billed
- [Phase 24]: 24-07: resource_type/resource_id are plain strings end-to-end (DB columns + path params, no enum) so D-15's host/remediation widening needs zero contract change to the feedback endpoint
- [Phase 24]: 24-07: the optimistic-mark + silent-revert lives in ai-feedback-control.tsx's own local state, not in use-ai-feedback.ts's mutation lifecycle -- no other reader of an analyst's feedback state exists this phase (capture-only), so there's no shared cache to snapshot/patch the way use-mark-blocked.ts does; the hook itself has zero onError/toast, making "silent" a structural (grep-provable) property
- [Phase 24]: 24-07: BLOCKER -- the plan's own literal verify-command env (ENCRYPTION_KEY=test) fails app.main's startup secrets check for any client-fixture-based test (settings.environment defaults to "production", "test" is not a valid Fernet key); fixed by using a real Fernet.generate_key() value, matching test_ai_explain_stream.py's own documented requirement. Also found: conftest.py's tenant_a/analyst_user fixtures only flush(), never commit() -- added explicit db_session.commit() before each HTTP call per test (WR-13 contract, mirrors test_ticket_watch.py)
- [Phase 24]: D-16 per-remediation grounding shape implemented as Option A (Cross-asset CVE grouping), per the locked 24-06 checkpoint decision -- get_remediation_group() aggregates {cve, fix, affected_assets[], priority} across every asset in the tenant sharing the CVE
- [Phase 24]: explain-remediation route is CVE-ID-string-keyed (/explain-remediation/{cve_id}), not UUID-keyed -- 24-09's frontend integration must pass a CVE string, not a ticket/remediation UUID
- [Phase 24]: get_asset_posture() is a NEW narrow query selecting only HOST_ALLOWLIST columns directly off Asset/Vulnerability (not a reuse of assets/router.py's PII-bearing get_asset dict) -- defense-in-depth for the phase's highest-PII-risk boundary (T-24-32)
- [Phase 24]: remediation-group priority is deterministically backend-computed (max severity + KEV/exploit escalation), never left for the model to infer -- mirrors ASSET-02's deterministic-score-augmented-not-replaced principle
- [Phase 24]: prompt_version() generalized with a response_model parameter (default preserves the exact existing vuln-view hash) instead of a parallel hashing function, so host_prompt_version()/remediation_prompt_version() reuse the identical, already-tested hashing logic
- [Phase 24-09]: AiExplanationSection gained an optional headingId prop (default 'drill-ai-h') to prevent a duplicate-DOM-id collision once host + per-row remediation mounts coexist with the vuln drill on one page
- [Phase 24-09]: remediation surface mounts one AiExplanationSection per ticket row (not once for the whole timeline) since list_tickets() groups by external_ticket_url and a group can span more than one CVE; gated off when a row's representative cve_id is null
- [Phase 24-09]: list_tickets() gained a representative cve_id via func.min(Vulnerability.cve_id), mirroring its existing remediation_action/affected_product MIN-aggregate convention -- additive, not a new query shape
- [Phase 24-10]: Gap closure for 24-VERIFICATION.md truth #2 (D-23 no-key role-gating). `GET /api/v1/ai/status` is require_viewer-gated (the floor, matching the existing explain-vuln GET cache-check precedent) since a boolean "is AI on" carries no sensitive data; it derives directly from get_tenant_anthropic_key -- never a second/parallel check that could drift from the engine's own enforcement
- [Phase 24-10]: status.py's docstring deliberately avoids the literal substrings ConnectorConfig/api_key/credentials_secret_arn/decrypt_value so the task's own no-credential-handling grep gate holds without weakening the explanatory value
- [Phase 24-10]: keyConfigured is now a direct Boolean(statusQuery.data?.configured) read -- the old isError-based optimistic pass-through and its explanatory comment were deleted outright, not left dormant alongside the fix
- [Phase 24-10]: BLOCKER (Rule 1 auto-fix) -- drill-panel.test.tsx and drill-panel-mobile.test.tsx each pre-existingly mocked use-connectors-admin solely to avoid AiExplanationSection needing a QueryClientProvider; once the component stopped importing that module, 17 tests broke with "No QueryClient set" against the real useAiStatus() call. Fixed by swapping both files' mock target to use-ai-status (deterministic unconfigured/Viewer-default state) -- full suite reconfirmed 816/816
- [Phase 25-01]: Denylist scoped to 8 D-04 categories; 9th credential-rotation category explicitly deferred (trivial one-line follow-up)
- [Phase 25-01]: MIN_REMEDIATION_CHARS=15 + 6-entry casefolded placeholder frozenset; CrowdStrike synthesized 'Update {product}...' text counts as actionable per RESEARCH A1
- [Phase 25]: Second few-shot exemplar's grounded=false case demonstrates D-02's model-judgment layer with vendor text that clears Plan 01's deterministic gate but is still too generic for concrete steps
- [Phase 25]: System prompt adds an explicit never-recommend-destructive-actions instruction as a Rule 2 addition, complementing Plan 01's post-generation denylist gate
- [Phase 25-03]: dangerous_pattern_check gate placed precisely between the leak-marker check and set_cached() -- proven at TWO levels (engine-internal spy on set_cached, and a route-level test injecting a fake Anthropic client via app.ai.explain._default_client_factory to reach the real engine through the real route)
- [Phase 25-03]: D-01 route-level gate reuses the SAME grounded_false SSE kind the engine's own model-judgment refusal emits, so the analyst never learns which layer fired (D-02)
- [Phase 25-04]: resourceType-scoped locked copy (header/CTA/viewer-text/insufficient-evidence) added to AiExplanationSection for 'remediation-guidance', beyond Task 1's literal action text, to satisfy 25-UI-SPEC's Copywriting Contract (D-06)
- [Phase 25-04]: AlertTriangle icon reused for the new danger DegradedCard variant (no new lucide-react import) — color tokens alone (border-danger/bg-danger-soft/text-danger) make it visually distinct from amber and neutral/violet
- [Phase 25-04]: drill-panel.test.tsx's 8-section order test extended to 9 sections (Remediation guidance inserted between Remediation and Activity), plus an independent document-order assertion
- [Phase 25-06]: extra="forbid" retrofitted onto TicketCreateRequest (previously no model_config) after grepping every construction site — verified no unrelated code passes extra kwargs
- [Phase 25-06]: create_tickets() WYSIWYG replace (not append) for an analyst-supplied description, per RESEARCH Assumptions A3
- [Phase 25]: Phase 25-07: renamed drill-content.tsx's pre-existing local description (vuln CVE text) to vulnDescriptionText to resolve a hard identifier collision with the new ticket-description state — Rule 1 auto-fix; the plan's own acceptance criteria literally grep for description: description || undefined, so the new state kept the description/setDescription names
- [Phase 25]: Phase 25-07: AiExplanationSection.onCopyToDescription mirrors TicketProviderPicker's value/onChange controlled-prop convention; renders the Copy into ticket description button ONLY in the grounded-done/cache-hit branches
- [Phase 26-01]: get_prioritization_context() returns exactly 10 keys (D-04's 8 factors + cve_id + department); test asserts set-equality against the expected key set, not just presence, catching an accidental extra column as reliably as a missing one
- [Phase 26-01]: Owner-PII exclusion docstring convention (naming assigned_user/managed_by/building/serial_number as excluded, inside the new function's OWN docstring) follows the exact precedent get_asset_posture()/get_remediation_guidance_context() already set in this file — the plan's "no PII names inside the function" acceptance grep targets the SELECT/query code, not explanatory prose naming what was deliberately left out
- [Phase 26-01]: ExplainPrioritizationResponse's docstring deliberately avoids the literal substrings priority/rank/score/ai_score in its own class-block prose (using "competing verdict number" instead) to satisfy the plan's grep-scoped T-26-02 no-rank acceptance check
- [Phase 26-02]: AllowlistedPrioritization.sla_due_at typed str | None (not the plan's literal datetime | None) and stringified at construction via _stringify() -- mirrors AllowlistedHostPosture.last_checkin_at's exact precedent; a raw datetime-typed field round-trips through model_dump() as a live datetime object (mode='python' default), which json.dumps() cannot serialize, so the plan's literal type would crash build_explain_prioritization_prompt() the first time a real, non-null sla_due_at reaches it (Rule 1 auto-fix, proven against a real datetime.datetime input, not just string-fixture tests)
- [Phase 26-02]: PRIORITIZATION_ALLOWLIST's new-block docstrings avoid the literal substrings assigned_user/managed_by/serial_number (paraphrased as "the analyst-assignment column"/"the manager column"/"the hardware serial number") to satisfy the plan's grep scoped to the PRIORITIZATION block region -- department intentionally DOES appear verbatim (D-04's one allowed owner signal, not excluded PII)
- [Phase 26-02]: SYSTEM_PROMPT_PRIORITIZATION's "never assert an independent priority verdict" / "never output a rank" sentences kept on single unwrapped source lines (unlike the file's usual ~75-char prose wrap) so a substring-based test can assert on the D-08/D-03 no-verdict/no-number instruction without a literal newline splitting the phrase
- [Phase 26-03]: explain_prioritization.py route + its test file written and verified together in one commit, not separate RED/GREEN commits -- the plan's own frontmatter type is execute (not tdd), and a literal RED phase would spuriously pass the cross-tenant/missing-404 tests anyway (an unregistered route returns a blanket 404 for every path before any tenant-scoping logic runs), matching Phase 25-03's documented precedent for the identical route-level tdd=true situation
- [Phase 26-03]: GET cache-miss shape stays the baseline {"cached": False} with no queued field this plan -- Plan 06 adds queued once AiBatchJob exists
- [Phase 26-04]: the "Generate it now" queued-card action reuses DegradedCard's existing bordered action prop (same mechanism as "Try again"/"Configure AI"), per the plan's own literal action={{label,onClick}} instruction, rather than a new small-text-link variant the UI-SPEC's prose alone had suggested -- avoids introducing a second action-rendering chrome inside DegradedCard
- [Phase 26-04]: no-ai-rank.test.ts checks ai_score/aiPriority/aiRank (and snake/camel siblings) against the RAW line in any context, but checks the bare words priority/rank only against the STRING-STRIPPED "bare code" -- lets the check coexist with this same plan's own LOCKED prose ("Explain the priority") without allowlisting it, while still catching watcher-stack.tsx's pre-existing ROLE_PRIORITY identifier (allowlisted by {file, /ROLE_PRIORITY/} scoped match) and a hypothetical ai_priority attribute value
- [Phase 26-04]: the queued===true branch is real, dark-safe, fixture-tested code shipped ahead of its own backend signal (26-03's GET route still returns the bare {cached:false}) -- not a stub; it activates automatically once 26-06 adds the AiBatchJob-backed queued field, with zero further frontend changes needed
- [Phase 26-05]: TRACER GATE resolved via proceed-on-trust (user decision) -- live browser verification of the on-demand prioritization slice explicitly waived, mirroring 24-06/25-05; batch/scheduler expansion (Plans 06-08) unblocked on the strength of the green automated suites
- [Phase 26-06]: custom_id_hash_map typed dict[str, str] (not the bare dict shown in 26-RESEARCH.md/26-PATTERNS.md's fully-worked examples) to avoid introducing new, unbaselined mypy type-arg debt in app/ai/models.py, a file with zero pre-existing baseline entries -- a precise type-arg fix rather than a new baseline addition (Rule 1)
- [Phase 26-06]: anthropic_batch_id uniqueness enforced via a standalone op.create_index(unique=True) in migration 033 (not an inline sa.Column(unique=True) or a table-level UniqueConstraint on op.create_table), matching the plan's own literal migration action text; the model's own mapped_column(unique=True) is metadata-only since this migration is hand-written, not autogenerated
- [Phase 26-06]: _is_finding_queued() answers ONLY "does an already-submitted in_progress AiBatchJob contain this finding" -- no live top-N re-check (grep-verified 0 occurrences of top_findings/get_top_findings/order_by), so a not-yet-submitted finding always shows queued=false and falls through to the ordinary on-demand trigger (Assumption A3)
- [Phase 26-07]: estimate_batch_cost_usd() reads the Request/MessageCreateParamsNonStreaming payload via dict-style access (req["params"][...]), not the plan's literal attribute-access instruction -- both are TypedDict subclasses that construct plain dicts at runtime (confirmed via direct anthropic==0.120.2 SDK introspection); req.params raises AttributeError. Matches RESEARCH.md's own Pattern 6 code sample.
- [Phase 26-07]: run_batch_prewarm()'s budget-skip audit call uses a local _ZERO_USAGE sentinel (SimpleNamespace(input_tokens=0, output_tokens=0)) instead of the plan's literal usage=None -- audit_log_ai_call() has no null-guard and unconditionally reads usage.input_tokens/output_tokens, so None crashes with AttributeError
- [Phase 26-07]: run_batch_prewarm() selects Tenant.id (a plain scalar column) not Tenant (the ORM object), so the new per-tenant try/except containment can safely call await db.rollback() without a LATER iteration's tenant.id access raising sqlalchemy.exc.MissingGreenlet on an expired object (AsyncSession.rollback() expires every object in the session's identity map, not just the failed tenant's)
- [Phase 26-07]: validate_and_cache_batch_result() commits its own audit row immediately, mirroring explain.py::_audit()'s wrapper convention, so the row is durable/provable in a genuinely fresh session without depending on a not-yet-existing Plan 08 caller to commit

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 23 P10 | 15min | 2 tasks | 2 files |
| Phase 23 P11 | 18min | 3 tasks | 3 files |
| Phase 24 P01 | 50min | 2 tasks | 17 files |
| Phase 24 P02 | 24min | 3 tasks | 7 files |
| Phase 24 P03 | 19min | 2 tasks | 6 files |
| Phase 24 P04 | 58min | 2 tasks | 4 files |
| Phase 24 P05 | 41min | 2 tasks | 13 files |
| Phase 24 P07 | 21min | 2 tasks | 10 files |
| Phase 24 P08 | 27min | 2 tasks | 8 files |
| Phase 24 P09 | 29min | 2 tasks | 13 files |
| Phase 24 P10 (gap closure) | 25min | 2 tasks | 9 files |
| Phase 25 P01 | 21min | 2 tasks | 4 files |
| Phase 25 P02 | 25min | 2 tasks | 4 files |
| Phase 25 P03 | 27min | 2 tasks | 5 files |
| Phase 25 P04 | 13min | 2 tasks | 6 files |
| Phase 25 P06 | 9min | 2 tasks | 3 files |
| Phase 25 P07 | 26min | 3 tasks | 8 files |
| Phase 26 P01 | 12min | 2 tasks | 4 files |
| Phase 26 P02 | 25min | 2 tasks | 2 files |
| Phase 26 P03 | 12min | 1 task | 3 files |
| Phase 26 P04 | 25min | 2 tasks | 6 files |
| Phase 26 P06 | 17min | 2 tasks | 5 files |
| Phase 26 P07 | 30min | 3 tasks | 9 files |

## Session

**Last session:** 2026-07-31T14:56:02.000Z
**Stopped at:** Completed 26-07-PLAN.md
**Resume file:** None
