// All vulnerabilities-page strings centralized — copy-voice.md compliance
// verified by grep at acceptance. Mirrors dashboard/microcopy.ts shape.
//
// Hard rules: sentence case; no exclamation; no begging/greeting prefixes; no
// generic CTA phrasing. CVE / SLA / HTTP code / request ID rendered in mono.

export const microcopy = {
  page: {
    h1: 'Vulnerabilities',
    searchPlaceholder: 'Search CVE, product…',
    clearAll: 'Clear all',
    savedFilterPrefix: '★',
    savedFilterDefault: "Today's triage",
  },
  chips: {
    critical: 'Critical',
    high: 'High',
    medium: 'Medium',
    low: 'Low',
    info: 'Info',
    kev: 'CISA KEV',
    exploit: 'Exploit available',
    // Phase 35 SRC-02/03/04 — OR/AND source-mode toggle. Avoids AND/OR
    // jargon per copy-voice.md; the button label reflects the current mode.
    sourceModeLabel: 'Match',
    sourceModeAny: 'Any selected',
    sourceModeAll: 'All selected',
    sourceModeDisabledHint: 'Select 2 or more sources to match all of them',
  },
  viewToggle: {
    byCve: 'By CVE',
    byHost: 'By Host',
  },
  empty: {
    title: 'Nothing matches your filters',
    body: "That's a tight net — relax one or two and try again.",
    clearAll: 'Clear all filters',
    broadenSeverity: 'Include Medium severity',
    searchAll: 'Search all sources',
    suggestion: 'Try broadening severity or removing the date range.',
  },
  totalFailure: {
    title: 'Couldn’t load vulnerabilities',
    body: 'The vulnerabilities service is unreachable.',
    retry: 'Retry now',
  },
  drill: {
    sections: {
      cvss: 'CVSS',
      riskExposure: 'Risk exposure',
      hosts: 'Affected hosts',
      description: 'Description',
      remediation: 'Remediation',
      activity: 'Activity',
      actions: 'Actions',
    },
    // Phase 33 Plan 04 (RISK-05): the shadow/preview Risk Exposure section
    // sitting between CVSS and Affected hosts. RISK-06 lock — this caption
    // must make it unmistakable that the score is not yet a triage driver.
    riskExposure: {
      previewCaption: 'Shadow score — not yet used for sorting or alerts.',
      kevFloorChip: '★ KEV floor applied',
      scoreAriaLabel: (score: number) => `Risk exposure score ${score}`,
    },
    createTicket: 'Create ticket',
    snooze24h: 'Snooze 24h',
    copyNvd: 'Copy NVD link',
    closeAria: 'Close drill panel',
  },
  ticket: {
    confirmTitle: (cve: string) => `Create ticket for ${cve}?`,
    confirmBody: 'This opens a Jira/Asana ticket. Irreversible from our side.',
    toastSuccess: (id: string) => `Ticket ${id} created`,
    toastViewAction: 'View',
  },
  table: {
    columns: {
      severity: 'Severity',
      cve: 'CVE',
      title: 'Title',
      asset: 'Asset',
      cvss: 'CVSS',
      status: 'Status',
      sla: 'SLA',
    },
    empty: 'No vulnerabilities found.',
  },
  tabTitle: {
    base: 'Vulnerabilities · GetVul',
    withCount: (n: number) => `(${n}) Vulnerabilities · GetVul`,
  },
} as const;
