/**
 * Microcopy for the /dashboard/analytics surface (Phase 42 Plan 01 —
 * TREND-01/03 tracer slice: the tenant risk-exposure trend line only).
 * Co-located so copy reviews live next to the components they ship with;
 * mirrors `frontend/src/components/coverage/microcopy.ts`'s structure.
 * Tone follows `copy-voice.md` — "peer, not butler."
 *
 * Strings transcribe 42-UI-SPEC.md's Copywriting Contract verbatim (page
 * title, window control labels, trend section heading, version-boundary
 * label/tooltip, insufficient-history empty state). Plans 02/03 extend this
 * module additively (aging/burndown/scope sections) rather than inventing a
 * second copy module for the same page.
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
} as const;
