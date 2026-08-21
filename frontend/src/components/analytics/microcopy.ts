/**
 * Microcopy for the /dashboard/analytics surface (Phase 42 Plan 01 —
 * TREND-01/03 tracer slice: the tenant risk-exposure trend line; Plan 02
 * adds TREND-02's aging + burndown sections below).
 * Co-located so copy reviews live next to the components they ship with;
 * mirrors `frontend/src/components/coverage/microcopy.ts`'s structure.
 * Tone follows `copy-voice.md` — "peer, not butler."
 *
 * Strings transcribe 42-UI-SPEC.md's Copywriting Contract verbatim (page
 * title, window control labels, trend section heading, version-boundary
 * label/tooltip, insufficient-history empty state, aging bucket labels +
 * overdue tile, burndown net-velocity + projected-clear copy). Plan 03
 * extends this module additively (scope dropdown/custom range) rather than
 * inventing a second copy module for the same page.
 */
export const microcopy = {
  page: {
    h1: 'Analytics',
  },
  // Plan 01 has no real scope dropdown yet (D-02's group scope ships in
  // Plan 03) — `allTenantLabel` is the exact locked "Scope dropdown trigger
  // (default)" copy, reused now as the empty-state scope substitution so
  // Plan 03's real dropdown selection needs no copy change at the call site.
  scope: {
    allTenantLabel: 'All (tenant)',
  },
  window: {
    d7: '7d',
    d7A11y: 'Last 7 days',
    d30: '30d',
    d30A11y: 'Last 30 days',
    d90: '90d',
    d90A11y: 'Last 90 days',
    y1: '1y',
    y1A11y: 'Last year',
    groupLabel: 'Trend window',
  },
  trend: {
    h2: 'Risk-exposure trend',
    // e.g. "v1 → v2" — literal RISK_MODEL_VERSION strings, mono.
    versionBoundaryLabel: (oldVersion: string, newVersion: string) => `${oldVersion} → ${newVersion}`,
    versionBoundaryTooltip:
      "Model version changed here — scores before and after aren't directly comparable.",
  },
  empty: {
    // D-04 — below the minimum-history threshold (zero snapshot points in
    // the window). Gated on the snapshot ROW COUNT, never on a falsy score
    // value (a healthy tenant scoring 0 is not empty).
    insufficientHistory: {
      title: 'Trends appear after a few days of history',
      body: (scope: string) =>
        `${scope} doesn't have enough snapshot history yet — check back in a few days.`,
    },
  },
  // Plan 02 (TREND-02/D-08) — backlog aging distribution. Bucket label
  // strings are LOCKED by 42-UI-SPEC.md's Copywriting Contract (exact day
  // thresholds are planner discretion; these 3 label strings are not).
  aging: {
    h2: 'Backlog aging',
    buckets: {
      within_sla: 'Within SLA',
      recently_breached: 'Recently breached',
      long_overdue: 'Long overdue',
    } as const,
    // UI-SPEC E3 zero-one-many: renders explicitly at zero — never blank
    // or omitted ("0% of open backlog is overdue").
    overdueTile: (n: number) => `${n}% of open backlog is overdue`,
  },
  // Plan 02 (TREND-02/D-09) — burndown rate. `netVelocity` is the
  // directional headline row (3 branches: shrinking/growing/no_change,
  // the last a distinct UI-SPEC E4 branch — never framed as "shrinking"
  // at 0). `projectedClear` has only 2 defined branches (shrinking/
  // growing) — no_change has no clear-date framing (there's nothing to
  // project when the rate is exactly flat), so the component omits that
  // line for the no_change status rather than inventing a 3rd variant.
  burndown: {
    h2: 'Burndown',
    netVelocity: {
      shrinking: (n: number) => `Backlog shrinking — ${n} findings/week net`,
      growing: (n: number) => `Backlog growing — ${n} findings/week net`,
      noChange: 'No change this period',
    },
    projectedClear: {
      shrinking: (n: number) => `${n}d to clear at this rate`,
      growing: 'Backlog growing — no clear date at this rate',
      // UI-SPEC E4 overflow: capped projection — never an absurd exact
      // multi-thousand-day number.
      capped: '500+ d to clear',
    },
  },
} as const;
