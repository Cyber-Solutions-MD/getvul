/**
 * microcopy.ts — CSPM screen copy strings.
 *
 * Copy voice: peer-not-butler (copy-voice.md). Sentence case. No "welcome", no "please".
 * Plan 14-03.
 */

export const CSPM_MICROCOPY = {
  page: {
    h1: 'Cloud security posture',
    subtitle: 'Misconfigurations across cloud environments',
  },
  emptyState: {
    heading: 'Nothing matches these filters',
    body: "No CSPM findings match the current combination. Relax one or two filters and try again.",
    clearAll: 'Clear all filters',
    broadenSeverity: 'Include all severities',
    broadenSource: 'Search all sources',
    lightbulb: 'Save this as a watch — you\'ll be notified when anything matches.',
  },
  bulkActions: {
    resolve: 'Resolve',
    ignore: 'Ignore',
    reopen: 'Reopen',
    selected: (n: number) => `${n} selected`,
    clear: 'Clear',
  },
  toasts: {
    resolved: (n: number) => `Resolved ${n} finding${n === 1 ? '' : 's'}.`,
    suppressed: (n: number) => `Ignored ${n} finding${n === 1 ? '' : 's'}.`,
    reopened: (n: number) => `Reopened ${n} finding${n === 1 ? '' : 's'}.`,
    error: 'Bulk action failed. Please try again.',
  },
  // Phase 35 SRC-02/05 — OR/AND source-mode toggle. Copy reused verbatim
  // from vulnerabilities/microcopy.ts (Plan 02) so the label is identical
  // across every surface. Avoids AND/OR jargon (copy-voice.md).
  chips: {
    sourceModeLabel: 'Match',
    sourceModeAny: 'Any selected',
    sourceModeAll: 'All selected',
    sourceModeDisabledHint: 'Select 2 or more sources to match all of them',
  },
} as const;

/** Severity glyphs per visual-language.md (CRITICAL ■ / HIGH ▲ / MEDIUM ◆ / LOW ○). */
export const SEVERITY_GLYPH: Record<string, string> = {
  CRITICAL: '■',
  HIGH: '▲',
  MEDIUM: '◆',
  LOW: '○',
  INFO: '□',
};

/** Severity text color classes per severity level. */
export const SEVERITY_CLASS: Record<string, string> = {
  CRITICAL: 'text-[var(--color-severity-critical-on-soft)]',
  HIGH: 'text-[var(--color-severity-high-on-soft)]',
  MEDIUM: 'text-severity-medium',
  LOW: 'text-severity-low',
  INFO: 'text-severity-info',
};
