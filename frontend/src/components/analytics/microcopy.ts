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
  // Plan 03 (D-02) — the real scope dropdown: 'All (tenant)' + each
  // AssetGroup, an accessible label for the trigger, a search-filter
  // placeholder for the overflow case (UI-SPEC E1), and the mandatory
  // group-scope caption (D-06), transcribed verbatim from the UI-SPEC.
  scope: {
    allTenantLabel: 'All (tenant)',
    accessibleLabel: 'Scope',
    searchPlaceholder: 'Search groups',
    groupCaption: (groupName: string) =>
      `Shows ${groupName}'s current members, applied retroactively across this window.`,
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
    // Plan 03 (D-03) — the 5th preset, revealing the From/To fields below.
    custom: 'Custom range',
    customA11y: 'Custom date range',
    groupLabel: 'Trend window',
  },
  // Plan 03 (D-03) — custom date-range fields + client-side validation
  // text (RESEARCH Pitfall 3: from/to are NOT run through useUrlState's
  // enum allow-list; this is their own, separate validation surface).
  customRange: {
    from: 'From',
    to: 'To',
    orderError: 'End date must be after start date.',
    // UI-audit fix (Phase 42 polish, finding #1) — rendered instead of the
    // loading skeleton while the custom range is incomplete/invalid, so a
    // deliberately-disabled query (use-analytics.ts's `enabled` gate) never
    // reads as a stuck fetch. Neutral, not an error — the order-error text
    // above already covers the invalid-order case inline in the controls.
    awaitingRangeTitle: 'Waiting on a valid range',
    awaitingRangeBody: 'Set a From date and a To date on or after it to see the trend for that window.',
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
