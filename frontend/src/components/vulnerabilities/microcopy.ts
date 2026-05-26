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
      hosts: 'Affected hosts',
      description: 'Description',
      remediation: 'Remediation',
      activity: 'Activity',
      actions: 'Actions',
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
