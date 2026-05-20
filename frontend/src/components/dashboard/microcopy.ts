// All user-facing dashboard strings extracted per copy-voice.md.
// Verbatim exemplars locked from 10-CONTEXT.md <specifics>.
// Sentence case. Forbidden tokens per copy-voice.md: begging-prefix, generic
// greeting, generic CTA, exclamation marks — none appear in any string literal.
//
// Plans 03–06 import this module — DO NOT inline strings in components. New
// copy lands here so a single grep against copy-voice rules covers the surface.

export const microcopy = {
  hero: {
    // D-H-02 — singular/plural grammar selected client-side from the count.
    headlineSingular: '1 critical CVE needs your eyes',
    headlinePlural: (n: number) => `${n} critical CVEs need your eyes`,
    // D-H-03 — sub-line interpolates real host/path/cvss; this is the shape.
    // BL-01: cvss may be null (backend schema). Render '—' for null CVSS rather
    // than 0.0 (which Number(null) produces) — same fallback the StatStrip uses
    // for missing values. Hero gates the whole subLine on host && path so those
    // params are non-null at call time, but cvss may still be null.
    subLineTemplate: (
      host: string,
      path: string,
      cvss: number | null,
      exploited: boolean
    ) =>
      `Top one is on ${host} — ${path}, CVSS ${cvss !== null ? cvss.toFixed(1) : '—'}${
        exploited ? ', exploited in the wild' : ''
      }.`,
    quietWin: 'Nothing critical right now',
    ctaPrimary: 'Start triage',
    ctaSecondary: 'Snooze 1h',
  },
  stats: {
    // D-Ax-01 section h2 — sr-only on rendered page; LOCKED VERBATIM.
    h2: 'Today at a glance',
    // D-S-04 — value rendered server-side; suffix-only:
    deltaSuffix: 'from yesterday',
    // Pitfall 8 — delta unknown sentinel:
    deltaUnknown: 'Δ —',
    labels: {
      critical_open: 'Critical · open',
      sla_at_risk: 'SLA · at risk',
      kev: 'CISA KEV',
      mttr_30d: 'MTTR · 30d',
    },
  },
  trend: {
    h2: '30-day vulnerability trend', // D-Ax-01 — LOCKED VERBATIM
    todaySoFar: 'Today (so far)', // D-C-07
    // Compact range labels (Warning 16, sketch 002 variant B):
    range7d: '7d',
    range30d: '30d',
    range90d: '90d',
    // Verbose a11y aliases — screen reader friendly:
    range7dA11y: '7 days',
    range30dA11y: '30 days',
    range90dA11y: '90 days',
  },
  top5: {
    h2: 'Top 5 to triage', // D-Ax-01 — LOCKED VERBATIM
  },
  activity: {
    h2: 'Recent activity', // D-Ax-01 — LOCKED VERBATIM
    // D-A-03 — verbatim copy-voice empty-state string:
    empty: "No recent activity. We'll show events here as they happen.",
  },
  snooze: {
    // D-H-08 — message + action are SEPARATE. The `· Undo` lives in the
    // Toast `action` slot, NOT inside the message string. 8s undo window
    // is the toast `duration`; consumer wires the onClick.
    // BL-01: cve_id may be null on TopVuln — surface a generic fallback rather
    // than printing literal "null" in the toast.
    toastTitle: (cveId: string | null) => `Snoozed ${cveId ?? 'vulnerability'} for 1h`,
    toastMessage: (cveId: string | null) => `Snoozed ${cveId ?? 'vulnerability'} for 1h`,
    toastActionLabel: 'Undo',
    toastError: (errCode: string | number) =>
      `Couldn't snooze. HTTP ${errCode} · Retry`,
    undoToastMessage: 'Snooze undone',
  },
  error: {
    // copy-voice.md exemplar pattern — fills in section, code, request ID:
    inline: (section: string, code: number | string, reqId: string) =>
      `${section} unavailable. HTTP ${code} · Request ID ${reqId} · Retry now`,
  },
  onboarding: {
    noScannersTitle: 'No scanners connected yet',
    noScannersBody: 'Connect a scanner so we can start aggregating findings.',
    noScannersCta: 'Connect a scanner',
    noDataYetTitle: 'Your first sync is in progress',
    noDataYetBody: 'Findings will appear as soon as the sync completes.',
    noDataYetCta: 'Refresh',
  },
  tabTitle: {
    // D-Tab-01:
    base: 'Dashboard · GetVul',
    withCount: (n: number) => `(${n}) Dashboard · GetVul`,
  },
} as const;
