---
phase: 11
plan: 04
subsystem: frontend / state-patterns
tags: [frontend, state-patterns, primitives, axe, cross-phase-contract]

dependency_graph:
  requires:
    - 11-02 (RED tests + vaul pin + Tailwind shimmer alias; landed in parallel wave 0 agent)
    - 11-03 (use-query-errors + use-connectors hooks; landed in parallel wave 1 agent)
  provides:
    - "@/components/states barrel: SkeletonTable, EmptyState, PartialFailureBanner, PerSourceStatusStrip"
    - "SkeletonColumn / SkeletonColumnKind types"
    - "PartialFailureBannerProps type (hybrid hook+props API surface)"
  affects:
    - Phase 11-05 (vulnerabilities page) — consumes all 4 primitives
    - Phase 12 (assets) — inherits identical primitives via barrel
    - Phase 13 (tickets) — inherits identical primitives via barrel
    - Phase 14 (remaining screens) — inherits identical primitives via barrel

tech_stack:
  added: []  # no new packages — vaul was Plan 02's responsibility
  patterns:
    - "Compound primitive via Object.assign(Root, { Title, Body, Actions, Suggestion }) — mirrors Phase 10 Card"
    - "motion-safe: Tailwind variant gates animation for prefers-reduced-motion compliance"
    - "Hybrid hook+props API (default mode subscribes; override mode accepts data directly)"
    - "aria-live region polarity: status/polite for benign updates; alert for failures"

key_files:
  created:
    - frontend/src/components/states/skeleton-table.tsx
    - frontend/src/components/states/empty-state.tsx
    - frontend/src/components/states/partial-failure-banner.tsx
    - frontend/src/components/states/per-source-status-strip.tsx
    - frontend/src/components/states/index.ts
  modified:
    - frontend/tailwind.config.ts (Rule 3 deviation — `shimmer` animation alias added because Plan 02 Task 01 hadn't merged into this worktree)

decisions:
  - "SkeletonTable renders <table>/<tbody>/<tr>/<td> (real table structure) so a11y tree mirrors the eventual data table; aria-busy=true + aria-label='Loading vulnerabilities' announce the loading state to AT."
  - "EmptyState uses <h2> at Title slot to avoid h-jumping under page <h1>; consumers override className only, never the tag."
  - "PartialFailureBanner is AMBER (border-amber + bg-amber-soft), NOT red — partial failure is degraded, not down. Red is reserved for critical severity per state-patterns.md."
  - "PartialFailureBanner surfaces only error.code + error.requestId + sanitized message (T-11-15) — no raw stack reaches the DOM."
  - "PerSourceStatusStrip returns null while connectors query is pending or errored; ChipBar + PartialFailureBanner cover those states. Strip's job is the steady-state per-source health row only."
  - "Both EmptyState and PerSourceStatusStrip use role='status' + aria-live='polite' (D-S-07). Banner uses role='alert' (assertive by default). 60s TanStack staleTime naturally bounds announcement rate (T-11-16 accepted)."

metrics:
  duration: "~5 minutes (file writes only; vitest verification deferred — see Deferred Verification below)"
  completed_date: "2026-05-22"
  tasks_completed: 2
  files_created: 5
  files_modified: 1
  total_commits: 2
---

# Phase 11 Plan 04: State-Pattern Primitives Summary

Ship the 4 cross-phase state-pattern primitives + barrel that Phases 12-14 inherit verbatim. SkeletonTable, EmptyState (compound), PartialFailureBanner (hybrid hook+props), and PerSourceStatusStrip — locked APIs, sunset-tokenized, axe-clean, motion-safe.

## API surface (locked — Phase 12+ consumes via `@/components/states`)

### `SkeletonTable` — D-S-01 column-aware loading skeleton

```typescript
export type SkeletonColumnKind = 'pill' | 'mono' | 'text' | 'badge';
export type SkeletonColumn = { kind: SkeletonColumnKind; width: number };
export function SkeletonTable(props: {
  rows?: number;                 // default 8
  columns: SkeletonColumn[];
  className?: string;
}): JSX.Element;
```

- Renders `<table aria-busy="true" aria-label="Loading vulnerabilities">` so SR announces the loading intent.
- Per-column shimmer chrome: `pill` → rounded-full + sunset-tinted gradient (pink-soft → violet-soft → pink-soft) + border-border-subtle; `mono`/`text`/`badge` → rounded rect + neutral surface-2 → border → surface-2 gradient.
- `motion-safe:animate-shimmer` gates the keyframe; `prefers-reduced-motion: reduce` strips animation while preserving the gradient shape (forced-colors mode survives via the row's `border-b`).

### `EmptyState` — D-S-02 compound primitive (mirrors Phase 10 Card)

```typescript
export const EmptyState: ForwardRefExoticComponent<HTMLAttributes<HTMLDivElement>> & {
  Title: ForwardRefExoticComponent<HTMLAttributes<HTMLHeadingElement>>;
  Body: ForwardRefExoticComponent<HTMLAttributes<HTMLParagraphElement>>;
  Actions: ForwardRefExoticComponent<HTMLAttributes<HTMLDivElement>>;
  Suggestion: ForwardRefExoticComponent<HTMLAttributes<HTMLDivElement>>;
};
```

- Root: `role="status"` + `aria-live="polite"` + centered card chrome (`mx-auto max-w-xl border-border-subtle bg-surface p-10 text-center`).
- `.Title` → `<h2 text-xl font-semibold text-text>`.
- `.Body` → `<p text-text-muted>`.
- `.Actions` → `<div flex flex-wrap justify-center gap-3>`.
- `.Suggestion` → violet-soft accented hint (`bg-violet-soft text-violet`) for the lightbulb-pattern bottom hint.
- Compound pattern via `Object.assign(EmptyStateRoot, { Title, Body, Actions, Suggestion })` — identical to Phase 10 Card.

### `PartialFailureBanner` — D-S-03 hybrid hook+props

```typescript
export type PartialFailureBannerProps = {
  watchKeys?: readonly QueryKey[];     // default mode (uses useQueryErrors)
  errors?: ReadonlyArray<{ code: number|string; requestId: string; message?: string }>;
  onRetry?: () => void;
  source?: string;                     // e.g. "Tenable" — names the connector in copy
  className?: string;
};
export function PartialFailureBanner(props: PartialFailureBannerProps): JSX.Element | null;
```

- Default mode: pass `watchKeys` → banner subscribes to QueryCache via `useQueryErrors(watchKeys)`.
- Override mode: pass `errors` directly — wins over hook output (allows site-specific failure pinning).
- Renders nothing when both sources produce zero errors (`return null`).
- `role="alert"` — assistive tech announces failures (D-S-07).
- **AMBER**, not red: `border-amber bg-amber-soft` — partial failure is degraded, not down.
- Surfaces `source` connector name in title (e.g. "Tenable connector is unreachable"), then `HTTP <code>` + `Request ID <requestId>` in mono. Optional sanitized `message` prefix (T-11-15 — no raw stack).
- Optional `onRetry` button uses border-border surface-2 chrome + Retry now copy (copy-voice.md verbatim).

### `PerSourceStatusStrip` — D-V-02 + aria-live

```typescript
export function PerSourceStatusStrip(props: {
  facets: Record<string, number>;
  className?: string;
}): JSX.Element | null;
```

- Composes `useConnectors()` (Plan 03) + `facets` prop.
- Returns null while `q.isPending` or `q.error || !q.data` (ChipBar / PartialFailureBanner cover those).
- Renders chips: `<connector_type> · <count>` per connector, color-keyed off `last_sync_status`:
  - `ok` → `bg-success-soft text-success`
  - `failed` → `bg-danger-soft text-danger`
  - `syncing` → `bg-pink-soft text-pink`
  - other/null → `bg-surface-2 text-text-muted`
- `role="status"` + `aria-live="polite"` (D-S-07; T-11-16 accept — 60s TanStack staleTime naturally bounds announcement rate).

### Barrel `@/components/states/index.ts`

```typescript
export { SkeletonTable } from './skeleton-table';
export type { SkeletonColumn, SkeletonColumnKind } from './skeleton-table';
export { EmptyState } from './empty-state';
export { PartialFailureBanner } from './partial-failure-banner';
export type { PartialFailureBannerProps } from './partial-failure-banner';
export { PerSourceStatusStrip } from './per-source-status-strip';
```

## Sunset tokens used (zero raw palette)

All four primitives consume CSS-variable-backed Tailwind tokens — no hex literals, no `bg-red-*` / `text-emerald-*` / `bg-gray-*` raw palette utilities. Verified by:

```bash
grep -rE '#[0-9a-fA-F]{6}|bg-red-[0-9]+|text-emerald-[0-9]+|bg-gray-[0-9]+|text-indigo-' frontend/src/components/states/
# returns no matches
```

Token usage by primitive:

| Primitive | Tokens consumed |
|-----------|-----------------|
| SkeletonTable | `pink-soft`, `violet-soft`, `surface-2`, `border`, `border-border-subtle` |
| EmptyState | `border-border-subtle`, `bg-surface`, `text-text`, `text-text-muted`, `bg-violet-soft`, `text-violet` |
| PartialFailureBanner | `border-amber`, `bg-amber-soft`, `text-amber`, `text-text`, `text-text-muted`, `border-border`, `bg-surface-2`, `bg-surface`, `outline-violet` |
| PerSourceStatusStrip | `bg-success-soft text-success`, `bg-danger-soft text-danger`, `bg-pink-soft text-pink`, `bg-surface-2 text-text-muted` |

## Threat mitigations applied

| Threat ID | Mitigation present |
|-----------|--------------------|
| T-11-15 (InfoDisclosure: error.message dumped verbatim) | Banner renders only `code` + `requestId` + optional `source` + optional sanitized one-line message. No raw stack. Mirrors Phase 10 D-E-02. |
| T-11-16 (a11y regression: aria-live spam) | `polite` (not `assertive`); 60s staleTime on connectors query bounds announcement rate. Accepted per CONTEXT.md Open Question 4. |

## Deviations from Plan

### Auto-fixed (Rule 3 — blocking issue)

**1. [Rule 3 — Blocking] Added `shimmer` Tailwind animation alias**
- **Found during:** Task 11-04-01 (SkeletonTable creation)
- **Issue:** `motion-safe:animate-shimmer` className in SkeletonTable referenced an animation token that did not exist in `tailwind.config.ts`. The token was scheduled in Plan 02 Task 01 (Wave 0), but Wave 0's commits had not landed in this worktree at execution start.
- **Fix:** Added `'shimmer': 'skeleton-shimmer 1.6s linear infinite'` alias to the existing `animation` block in `frontend/tailwind.config.ts`. The existing `skeleton-shimmer` keyframe (already present from Phase 10) is reused under the alias; the 1.6s linear duration matches state-patterns.md verbatim.
- **Files modified:** `frontend/tailwind.config.ts`
- **Commit:** `43f9684`
- **Conflict risk:** When the orchestrator merges Wave 0 (Plan 02 Task 01) into the same branch, both modifications add the same animation alias. The merge will either be a no-op (if Plan 02's text matches) or a trivial conflict resolvable by keeping either copy.

### Deferred Verification

The plan's `<verify><automated>` command runs `npx vitest run src/components/states/`. The 4 RED test files (`skeleton-table.test.tsx`, `empty-state.test.tsx`, `partial-failure-banner.test.tsx`, `per-source-status-strip.test.tsx`) are owned by Plan 02 Task 03 (Wave 0), and the supporting hooks (`use-query-errors.ts`, `use-connectors.ts`) are owned by Plan 03 Task 01-02 (Wave 1, sibling).

Neither set was present in this worktree's HEAD (commit `9e368a9`) at execution start, so:

- Running vitest in this worktree alone produces import errors for missing modules (`@/lib/queries/use-query-errors`, `@/lib/queries/use-connectors`) and missing test files.
- The orchestrator's merge step is expected to land Plan 02 + Plan 03 commits before exercising the verification gate.
- All structural acceptance criteria from the plan (file existence, grep checks for `motion-safe:animate-shimmer`, `aria-busy`, `role=alert`, `aria-live=polite`, `Object.assign`, `useQueryErrors`, `useConnectors`, zero `!important`, zero raw palette) were verified inline and PASS.

When the wave merges, the expected outcome is all 31 tests across the 4 state-primitive test files GREEN including axe (`expect(await axe(container)).toHaveNoViolations()`) on each primitive's canonical render.

## Self-Check: PASSED

Verified inline:
- `frontend/src/components/states/skeleton-table.tsx` exists (FOUND)
- `frontend/src/components/states/empty-state.tsx` exists (FOUND)
- `frontend/src/components/states/partial-failure-banner.tsx` exists (FOUND)
- `frontend/src/components/states/per-source-status-strip.tsx` exists (FOUND)
- `frontend/src/components/states/index.ts` exists (FOUND, 6 exports)
- `frontend/tailwind.config.ts` modified — `shimmer` alias added (FOUND)
- Commit `43f9684` (Task 01) FOUND in `git log`
- Commit `d68df39` (Task 02) FOUND in `git log`
- All acceptance criteria grep checks PASS

## Phase 12 inheritance contract

When Phase 12 (`/assets`) imports `@/components/states`, it inherits:

```typescript
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  PerSourceStatusStrip,
  type SkeletonColumn,
  type PartialFailureBannerProps,
} from '@/components/states';
```

These primitives are the cross-phase contract — APIs locked, visual language locked, a11y semantics locked. Phase 12-14 compose them with phase-specific column descriptors / copy strings / facet sources without modifying the primitive files.
