---
phase: 26-prioritization-narrative
plan: 04
subsystem: ui
tags: [react, nextjs, typescript, ai, drill-panel, no-rank, vitest]

# Dependency graph
requires:
  - phase: 26-03
    provides: "GET/POST /api/v1/ai/explain-prioritization/{finding_id} -- the on-demand route this plan's AiExplanationSection mount consumes verbatim (via the existing useExplainCache/useExplainStream hooks, zero hook changes needed); GET's cache-miss shape is currently the bare {cached:false} (no queued key yet, by 26-03's own explicit design)"
  - phase: 24-ai-foundation-explain-this-vuln
    provides: "AiExplanationSection + AiExplanationCitations + useExplainCache + useExplainStream + the drill-content.tsx section-mount pattern -- reused completely unchanged (D-09), only additively extended"
  - phase: 25-asset-aware-remediation-guidance
    provides: "the isRemediationGuidance discriminator + resourceType-scoped copy-object pattern (ai-explanation-section.tsx lines 164-184) and the groundable===false structural-guarantee branch placement (lines 278-287) -- both mirrored verbatim for this plan's 5th resourceType and new queued branch"
provides:
  - "resourceType='prioritization' -- the 5th value on the shared AiExplanationSection, with its own LOCKED heading/trigger/viewer-empty/insufficient-evidence copy (26-UI-SPEC.md Copywriting Contract)"
  - "the NEW queued/being-prepared card: DegradedCardProps gains an additive icon?:'sparkles'|'clock' prop (defaults to 'sparkles', every existing call site unaffected); a queued===true branch renders it with a subordinate 'Generate it now' action for Analyst+, no action for Viewer (D-17)"
  - "queued?: boolean on ExplainCacheResult's cached:false arm (use-explain-cache.ts) -- structurally ready for 26-06's AiBatchJob-backed GET response, hook body unchanged"
  - "the <section aria-labelledby='drill-prioritization-h'> mount in drill-content.tsx, placed between AI Explanation and the raw Remediation section (desktop + mobile in one edit)"
  - "frontend/tests/no-ai-rank.test.ts -- the literal, grep-provable SC2/Pitfall #7 'no AI rank anywhere in the UI' CI check, self-verified against an injected fake violation before landing"
affects: [26-05-tracer-gate, 26-06-batch-job-registry, 26-07-batch-submitter, 26-08-scheduler-integration, 28-eval-cost-observability-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "5th resourceType value added to the shared AiExplanationSection purely additively (mirrors Phase 25's 4th) -- no per-view component fork, no change to AiExplanationCitations/use-explain-stream.ts/keys.ts"
    - "the queued branch ships now, structurally guaranteed and fixture-tested, even though the backend queued signal only starts flowing once 26-06 builds the AiBatchJob registry -- the branch is real, tested, dark-safe code (not a stub): it activates automatically the instant the GET route starts returning queued:true, with zero further frontend changes"
    - "no-ai-rank.test.ts: a Vitest fs-based repo-wide static check (no file-shaped analog existed, per 26-PATTERNS.md) -- strips comment-only lines and quoted-string CONTENTS before scanning for bare priority/rank code-level identifiers (so this very plan's own LOCKED prose, e.g. 'Explain the priority', never trips it), while ai_score/aiPriority/aiRank stay forbidden in ANY context including inside strings"

key-files:
  created:
    - frontend/tests/no-ai-rank.test.ts
  modified:
    - frontend/src/components/ai/ai-explanation-section.tsx
    - frontend/src/lib/queries/use-explain-cache.ts
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/ai/ai-explanation-section.test.tsx
    - frontend/src/components/vulnerabilities/drill-panel.test.tsx

key-decisions:
  - "The 'Generate it now' queued-card action reuses DegradedCard's existing action prop (bordered SECONDARY_BTN_CLASS button/link, the same mechanism as 'Try again'/'Raise the cap'/'Configure AI'), per the plan's own literal action={{label,onClick}} instruction -- not a new small-text-link variant matching CopyToDescriptionButton's lighter chrome, which 26-UI-SPEC.md's prose alone had suggested. Chosen because inventing a second action-rendering path inside DegradedCard would itself be new visual chrome, which the task explicitly forbids; the plan's code-level instruction is the more authoritative, execution-time-reconciled source"
  - "no-ai-rank.test.ts distinguishes code-level identifiers from human-readable copy by stripping quoted-string CONTENTS before the generic priority/rank scan -- this is what lets the check coexist with this SAME plan's own new copy ('Explain the priority', 'Not enough signal to explain priority reliably') without needing to allowlist it, while still catching a hypothetical <option value=\"ai_priority\">Sort by AI priority</option> (ai_priority is checked against the RAW, unstripped line, since that identifier is unconditionally forbidden in any context)"
  - "watcher-stack.tsx's pre-existing ROLE_PRIORITY role-strength dedupe map is the check's one allowlist entry, scoped by {file, /ROLE_PRIORITY/} rather than a blanket per-file exemption, so a genuinely new violation added anywhere else in that file would still be caught"

patterns-established:
  - "DegradedCardProps.icon?:'sparkles'|'clock' -- an additive, defaulted prop is the established shape for adding a new icon to an existing degraded-state card family without touching any existing call site"
  - "A resourceType-agnostic branch (queued) can sit alongside resourceType-scoped copy variables (insufficientEvidenceCopy) in the same component -- the branch's OWN copy is hardcoded (not resourceType-branched) because only the prioritization GET route will ever populate `queued`, exactly mirroring how `groundable` is scoped by which route returns it, not by an explicit resourceType guard in the branch"

requirements-completed: []  # AIP-01 intentionally NOT marked complete -- satisfied only at the 26-05 TRACER GATE (per 26-01/26-02/26-03-SUMMARY.md's explicit rationale, reiterated by this plan's own tracking_tool_caution)

# Metrics
duration: 25min
completed: 2026-07-31
---

# Phase 26 Plan 04: Prioritization Drill Section + No-Rank UI Contract Summary

**A 5th `resourceType='prioritization'` value on the shared `AiExplanationSection` (LOCKED copy, Clock-icon queued card, signal-driven never-timing-based) mounted into `drill-content.tsx` between AI Explanation and Remediation, plus `frontend/tests/no-ai-rank.test.ts` — a self-verified, grep-provable CI check enforcing that no AI-derived rank/priority ever reaches a table, sort control, or numeric badge.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-31T13:32:09Z
- **Completed:** 2026-07-31T13:56:38Z
- **Tasks:** 2/2 completed
- **Files modified:** 6 (1 new test file, 5 modified)

## Accomplishments

- `ai-explanation-section.tsx`: `isPrioritization` discriminator extends `heading`/`triggerLabel`/`viewerEmptyText`/`insufficientEvidenceCopy` with a 3rd branch using 26-UI-SPEC.md's LOCKED strings verbatim ("Prioritization", "Explain the priority", "No prioritization narrative generated yet.", "Not enough signal to explain priority reliably" + its exploit/KEV/SLA/severity body). `DegradedCardProps` gains an additive `icon?: 'sparkles' | 'clock'` (default `'sparkles'`, every existing call site byte-identical). A new `cacheQuery.data?.cached === false && cacheQuery.data?.queued === true` branch — checked `=== true` explicitly, inserted BEFORE the `isAnalystOrAbove` trigger branch (same structural-guarantee placement as `groundable === false`) — renders the Clock-icon neutral/violet card with the LOCKED "Prioritization narrative is being prepared" heading + body; Analyst+ gets a subordinate "Generate it now" action (`onClick: () => void start()`), Viewer gets the identical card with no action (D-17).
- `use-explain-cache.ts`: `ExplainCacheResult`'s `cached: false` arm gains `queued?: boolean`, mirroring the existing `groundable?` precedent exactly — hook body unchanged, the field rides along in the generic JSON the moment 26-06 starts populating it.
- `drill-content.tsx`: new `<section aria-labelledby="drill-prioritization-h">` mounts `<AiExplanationSection resourceType="prioritization" resourceId={v.id ?? idOrCve} headingId="drill-prioritization-h" />` (exactly 3 props, `onCopyToDescription` deliberately omitted) immediately after `drill-ai-h` and before `drill-remed-h` — one insertion covers desktop + mobile.
- `frontend/tests/no-ai-rank.test.ts` (new): recursively scans `components/**/*.tsx` + `lib/queries/**/*.ts`; always forbids `ai_score`/`aiPriority`/`aiRank` (and snake/camel siblings) in ANY context; forbids bare `priority`/`rank` as CODE-level constructs only (quoted-string contents stripped first, so this plan's own prose never trips it). Self-verified live: a temporarily-injected fixture (`{ value: 'ai_priority', label: 'Sort by AI priority' }` + a bare `<th>{aiRank}</th>`) was caught and the test failed as expected, then the fixture was removed and the suite re-confirmed green — proving the check has real teeth, not a vacuous pass.
- 8 new tests in `ai-explanation-section.test.tsx` (locked copy ×4, queued-card backstop ×4) + a rewritten 10-section order test and a new dedicated placement test in `drill-panel.test.tsx`.
- Full wave-merge regression: 853/853 frontend tests green (131 test files), `tsc --noEmit` clean, `eslint` clean on every touched file.

## Task Commits

Each task was committed atomically:

1. **Task 1: resourceType='prioritization' + queued branch in AiExplanationSection (+ cache-check type)** - `53b29c8` (feat)
2. **Task 2: mount the Prioritization drill section + the No-Rank UI CI check** - `8619b6e` (feat)

**Plan metadata:** (this commit) - `docs(26-04): complete plan`

## Files Created/Modified

- `frontend/src/components/ai/ai-explanation-section.tsx` - `isPrioritization` discriminator + LOCKED copy branch; `DegradedCardProps.icon` + Clock render branch; the new `queued === true` card branch
- `frontend/src/lib/queries/use-explain-cache.ts` - `queued?: boolean` added to `ExplainCacheResult`'s `cached: false` arm
- `frontend/src/components/vulnerabilities/drill-content.tsx` - new `<section aria-labelledby="drill-prioritization-h">` mount between AI Explanation and raw Remediation
- `frontend/src/components/ai/ai-explanation-section.test.tsx` - 8 new tests (locked copy + queued-card signal-driven backstop)
- `frontend/src/components/vulnerabilities/drill-panel.test.tsx` - 10-section order test (was 9) + dedicated Prioritization placement test
- `frontend/tests/no-ai-rank.test.ts` (new) - the SC2/Pitfall #7 No-Rank UI Contract CI check

## Decisions Made

- **"Generate it now" reuses the standard `DegradedCard` action button, not a new small-text-link variant:** 26-UI-SPEC.md's prose described "same visual weight as Copy into ticket description" (a lighter text-link), but the plan's own `<action>` block gives the literal code shape `action={{ label: 'Generate it now', onClick: () => void start() }}` — the existing bordered-button mechanism every other `DegradedCard` action already uses. Implementing a second action-rendering path inside `DegradedCard` would itself be new visual chrome, which the task explicitly forbids ("Do NOT restyle or introduce any new visual chrome"). The plan's literal instruction, being the execution-time-reconciled artifact, took precedence over the more abstract UI-SPEC description.
- **no-ai-rank.test.ts's two-tier forbidden-identifier design:** `ai_score`/`aiPriority`/`aiRank` (and snake/camel siblings) are checked against the RAW line (any context, including inside a string) since there is no legitimate reason a UI file should ever name one of these identifiers at all. The bare words `priority`/`rank` are checked only against the STRING-STRIPPED "bare code" — this is what lets the check catch `watcher-stack.tsx`'s pre-existing `ROLE_PRIORITY` (a real identifier) while never flagging this very plan's own LOCKED prose strings ("Explain the priority," "Not enough signal to explain priority reliably"), which live entirely inside quoted string literals.
- **The queued branch is real, tested, and intentionally dark in production today** — not a stub in the sense the self-check guidance warns about. 26-03's GET route currently returns the bare `{cached: false}` (no `queued` key, by 26-03's own explicit design); this plan's branch only activates once 26-06 adds the `AiBatchJob`-backed signal. The distinction from an accidental stub: the code path is fully implemented and fixture-tested (`{cached:false, queued:true}` renders the pending card correctly, `queued:undefined`/`false` correctly fall through), and needs zero further frontend changes once the backend starts returning `queued:true` — exactly the plan's own stated intent ("the branch stays dark in production until then, which is correct").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Semgrep pre-commit hook flagged a path-traversal false positive in the new test file**
- **Found during:** Task 2, first commit attempt
- **Issue:** `semgrep scan --config p/default --config p/owasp-top-ten` (run by the repo's `.git/hooks/pre-commit`) flagged `javascript.lang.security.audit.path-traversal.path-join-resolve-traversal` on `no-ai-rank.test.ts`'s `join(dir, entry)` call inside its directory-walking helper. `entry` is a filesystem directory-entry name returned by `readdirSync()` over this repo's own fixed, local `src/` tree at test time — never external/user-controlled input (Node's `readdirSync` never returns `.`/`..`) — a genuine false positive of the same class as the two pre-existing `nosemgrep`-suppressed findings already in this codebase (`backend/app/assets/router.py`, `backend/tests/test_auth.py`).
- **Fix:** Added a `// nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal` comment on the line immediately before the flagged `join()` call (confirmed via a direct `semgrep scan --json` invocation that this is the full, correctly-qualified rule ID — the pre-commit hook's own summary only prints the last dot-segment), with a one-line explanation of why the finding doesn't apply.
- **Files modified:** `frontend/tests/no-ai-rank.test.ts`
- **Verification:** `semgrep scan --config p/default --config p/owasp-top-ten --config p/secrets --config p/dockerfile --json frontend/tests/no-ai-rank.test.ts` now returns 0 results; the commit then succeeded with the hook's own "0 findings" pass.
- **Committed in:** `8619b6e` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking-issue fix, zero functional/behavioral impact — a suppression comment only).
**Impact on plan:** None on behavior. No scope creep.

## Issues Encountered

- None beyond the semgrep false positive documented above.

## User Setup Required

None - no external service configuration required.

## Requirements Tracking

`REQUIREMENTS.md`'s AIP-01 checkbox remains deliberately **not** marked complete, per this plan's own `tracking_tool_caution` and 26-01/26-02/26-03-SUMMARY.md's consistent rationale: AIP-01 is satisfied only once the 26-05 TRACER GATE checkpoint confirms an analyst can see a cited prioritization narrative end-to-end in a live browser. `ROADMAP.md`'s per-plan tracking (updated via direct edit, verified by `git diff` below) now reads "4/8 plans, In Progress" for Phase 26.

## Next Phase Readiness

- The frontend half of the on-demand tracer is code-complete and test-proven: `resourceType='prioritization'` renders cited narratives via the unmodified `AiExplanationCitations` two-tier renderer, the trigger/viewer-empty/insufficient-evidence copy is locked verbatim, and the queued/being-prepared card is real and fixture-tested even though it stays dark in production until 26-06 ships the backend signal.
- The No-Rank UI Contract (SC2/Pitfall #7) now has a literal, automated CI artifact (`frontend/tests/no-ai-rank.test.ts`) that Phase 28's audit can re-run directly rather than re-deriving a manual check.
- Ready for **26-05 (TRACER GATE)**: the checkpoint that verifies the end-to-end on-demand slice (admin key → analyst click → validated cited streamed narrative → cited render → no rank) in a live browser, before batch expansion (26-06..08) begins.
- No blockers.

## Self-Check: PASSED

- FOUND: `frontend/src/components/ai/ai-explanation-section.tsx` (isPrioritization, queued branch present)
- FOUND: `frontend/src/lib/queries/use-explain-cache.ts` (queued field present)
- FOUND: `frontend/src/components/vulnerabilities/drill-content.tsx` (drill-prioritization-h mount present)
- FOUND: `frontend/tests/no-ai-rank.test.ts`
- FOUND commit `53b29c8` (Task 1) in `git log --oneline --all`
- FOUND commit `8619b6e` (Task 2) in `git log --oneline --all`

---
*Phase: 26-prioritization-narrative*
*Completed: 2026-07-31*
