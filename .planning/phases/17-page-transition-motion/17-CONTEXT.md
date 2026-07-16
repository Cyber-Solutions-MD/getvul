# Phase 17: Page-transition motion - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Route changes **within the `(authed)` app shell** get a smooth, reduced-motion-safe
cross-fade at zero bundle cost, driven by the native **View Transitions API** via a
single `(authed)/template.tsx`. A CSS-keyframe fallback covers browsers without View
Transitions (Firefox). The transition must not race with DrillPanel close, cause no
layout shift, and keep every route ≤250 KB First-Load JS.

This phase clarifies **how the transition feels** and **when it fires** — the technical
approach (View Transitions API, `template.tsx`, reduced-motion handling, CSS fallback,
budget) is locked by the milestone (`v2.2-ROADMAP.md` / `v2.2-REQUIREMENTS.md`).

Covers requirements **UX-D-06-01..05**.

</domain>

<decisions>
## Implementation Decisions

### Trigger — when the cross-fade fires
- **D-01:** The cross-fade fires **only on pathname changes** (e.g. Dashboard →
  Vulnerabilities → Assets). It must key off `usePathname()`, **not** raw navigation.
- **D-02:** `searchParams`-only changes do **NOT** fade. This explicitly excludes:
  opening/closing a DrillPanel (`?drill=...`), tab switches (`?tab=...`), and the
  list↔board toggle (`?view=...`). This is the primary safeguard for UX-D-06-04
  (no race with DrillPanel Esc/clickaway close — those close paths mutate searchParams,
  which by decision never trigger a fade).

### Feel — style & duration
- **D-03:** **Pure opacity cross-fade — no transforms.** No vertical drift, no slide.
  Matches the design contract's Motion section ("cross-fade only, no transforms" for
  page transitions) and eliminates layout-shift risk (supports UX-D-06-04).
- **D-04:** Duration is **snappy: 220–320ms**, not the reserved 520ms `--motion-xslow`.
  A 520ms fade on every navigation feels sluggish for a triage tool where analysts move
  fast. **Claude's discretion within 220–320ms**, leaning `--motion-slow` (320ms) since a
  full-content cross-fade of two snapshots reads better slightly longer than a hover.

### Scope — what actually fades
- **D-05:** **Content region only.** The sidebar + topbar (persistent chrome, owned by
  `(authed)/layout.tsx`) stay perfectly still; only the main content cross-fades. This
  requires assigning a `view-transition-name` to the content wrapper so it is isolated
  from the default root snapshot (which would otherwise fade the whole viewport, chrome
  included).

### Fallback — no View Transitions support (Firefox)
- **D-06:** Firefox (and any browser lacking View Transitions) gets a **CSS-keyframe
  opacity cross-fade** on `template` mount for feature parity — not a bare instant swap.
  Because it is a CSS animation, the existing `globals.css` D-12 reduced-motion blanket
  (`animation-duration: 0.01ms !important`) already suppresses it — one mechanism covers
  both the native and fallback paths under `prefers-reduced-motion`. Adds 0 KB JS.

### First paint & entry
- **D-07:** **No fade on first load / hard refresh.** The first painted route and hard
  reloads appear instantly; fades kick in only on subsequent in-app route-to-route
  navigations. Avoids delaying first meaningful paint.
- **D-08:** **No fade on app entry (login → dashboard).** The first mount of the
  `(authed)` template (arriving from login) appears instantly — consistent with D-07.
  Login already has its own gradient-mesh moment; a fade here would only delay the
  dashboard.

### Loading & scroll behavior
- **D-09:** **Fade into the skeleton.** On navigating to a `force-dynamic` route that
  shows a loading skeleton, the cross-fade runs on the pathname change (old content →
  new route's skeleton); the subsequent skeleton→data resolution is a normal render with
  **no second fade**. Motion is never coupled to network/data-fetch timing.
- **D-10:** **Keep Next.js default scroll behavior** — scroll to top on forward
  navigation, restore on back/forward. No custom scroll management (avoids racing the
  fade and DrillPanel; supports the no-layout-shift requirement).

### DrillPanel interaction
- **D-11:** When a DrillPanel is open and the user navigates to a **different route**
  (pathname change), the panel **fades out with the content** — it lives inside the
  content region, so it is captured in the outgoing snapshot and cross-fades away with
  everything else. The new route simply lacks the drill searchParam. No special-case
  close choreography (which would risk racing the Esc/clickaway path — UX-D-06-04).

### Claude's Discretion
- Exact duration within the 220–320ms band (D-04), leaning 320ms.
- The exact `view-transition-name` value and where the content wrapper lives
  (`template.tsx` vs a thin client component inside it).
- Where the transition CSS lives — recommend following the single-source convention in
  `globals.css` (alongside the existing keyframes and the D-12 blanket) rather than a new
  stylesheet.
- **Validation depth (raised, not explicitly answered):** recommend a lightweight e2e
  assertion that the cross-fade fires on a real pathname change (in addition to keeping
  `e2e/reduced-motion.spec.ts` green for UX-D-06-02), given the milestone's history of
  a11y/motion claims going unverified. Planner to size this.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope & requirements
- `.planning/milestones/v2.2-ROADMAP.md` — Phase 17 goal + success criteria; locked
  decisions (View Transitions API = 0 KB native; `template.tsx`; phase-15 quality gate).
- `.planning/milestones/v2.2-REQUIREMENTS.md` §"Phase 17" — UX-D-06-01..05 testable units.

### Design contract (authoritative for feel)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` §Motion (lines ~141-169)
  — the four eases, the four durations incl. `--motion-xslow: 520ms /* page transitions
  if added */`, and "What does NOT animate: page transitions (cross-fade only …)".
- `.claude/skills/sketch-findings-getvul/references/foundation.md` §"Reduced motion" —
  "cross-fade only (no transforms)" substitution rule.
- `.claude/skills/sketch-findings-getvul/references/app-shell.md` — persistent sidebar +
  topbar chrome (the parts that must NOT fade, per D-05).

### Existing enforcement to preserve
- `frontend/src/app/globals.css` lines 116-124 — the D-12 `prefers-reduced-motion`
  blanket that must also suppress the new transition (D-06). Lines 155-173 — existing
  `@keyframes` block (add the fallback fade keyframe here per single-source convention).
- `frontend/e2e/reduced-motion.spec.ts` — must stay green (UX-D-06-02).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`frontend/src/app/(authed)/layout.tsx`** — the single chrome owner (`AppShell` +
  `ToastProvider`), already `export const dynamic = 'force-dynamic'`. The new
  `template.tsx` sits as a **sibling** in the same `(authed)/` directory; Next.js nests
  `template` inside `layout`, so chrome stays mounted while `template` remounts per
  navigation — exactly the D-05 content-only model.
- **`frontend/src/app/globals.css`** — motion tokens/eases available as CSS vars; D-12
  reduced-motion blanket (lines 116-124); `@keyframes` registry (lines 155-173) is the
  single home for the fallback fade keyframe.
- **`frontend/src/components/shell/app-shell.tsx`** — the persistent chrome that must
  remain visually static during a transition.

### Established Patterns
- **Reduced motion is handled globally, not per-component** (D-12 blanket). The new
  transition must be expressed as a **CSS animation** (native VT default + the Firefox
  fallback) so the blanket catches it automatically — do not gate motion in JS.
- **URL state drives panels/tabs/toggles via `searchParams`** (DrillPanel, tab bars,
  list/board). `template.tsx` remounting on those changes is the failure mode D-01/D-02
  guard against — the trigger must be pathname-scoped.
- **Single-source-of-hex/keyframes convention** — animation primitives live once in
  `globals.css` (see the Phase 9-14 keyframes and provider-gradient comments).

### Integration Points
- New file: `frontend/src/app/(authed)/template.tsx` (drives the transition).
- CSS: `frontend/src/app/globals.css` (`::view-transition-*` rules + fallback keyframe +
  the `view-transition-name` on the content wrapper).
- DrillPanel components (`frontend/src/components/vulnerabilities/drill-panel.tsx` and
  `drill-panel-mobile.tsx`) — verify Esc/clickaway close still works during/after a
  transition (UX-D-06-04); no code change expected given D-02, but must be tested.

</code_context>

<specifics>
## Specific Ideas

- The transition is deliberately **restrained**: pure opacity, snappy, content-only,
  chrome-static. The mental model is "the shell is a stable frame; only the picture inside
  it cross-fades." Anything more (drift, entry fades, choreographed panel closes) was
  explicitly rejected in discussion.
- `--motion-xslow: 520ms` exists in the design contract as the reserved page-transition
  token, but the team chose to **undershoot it** (220-320ms) for this triage tool.

</specifics>

<deferred>
## Deferred Ideas

- **Navigation pending indicator** (top loading bar / pending cue during navigation to
  `force-dynamic` routes) — raised as a possible addition; the cross-fade is currently the
  sole navigation-feedback signal. This is a new capability, not part of UX-D-06 — note
  for a future backlog item if analysts report the fade alone is insufficient feedback.

</deferred>

---

*Phase: 17-page-transition-motion*
*Context gathered: 2026-07-16*
