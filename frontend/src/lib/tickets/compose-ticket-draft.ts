// Phase 27 (AID-01, Plan 02): pure, unit-testable composition functions for
// the ticket auto-draft. Zero React/network imports -- callable identically
// from the desktop ConfirmModal (drill-content.tsx) and, in Plan 03, the
// mobile Drawer.NestedRoot renderConfirm branch (drill-panel-mobile.tsx) --
// closing the "Phase 25 divergence lesson" at its source (27-RESEARCH.md
// Pattern 1).
//
// D-01: composeTicketTitle is fully DETERMINISTIC -- it mirrors the
// backend's own existing per-vuln task-name convention
// (backend/app/ticketing/service.py:202's
// `f"[{sev}] {cve} on {hostname or 'unknown host'}"`) so an unedited draft
// matches what the server would otherwise auto-build. It is NOT an AI call.
//
// Pitfall 5 / D-06: composeTicketDescription's "Asset context:" section
// reads ONLY host/product/severity/cisa_kev/exploit_available -- there is
// NO owner/department/assignee field on VulnerabilityDetail/FlexibleDetail.
// Do not invent one here.

/**
 * A cache-check result mapped from `useExplainCache().data` --
 * `null` means no usable cache hit (miss, ungrounded, or errored).
 */
export type CacheSection = { grounded: boolean; summary: string } | null;

export function composeTicketTitle(params: {
  sevLabel: string;
  cveLabel: string;
  hostsLine: string;
}): string {
  // Mirrors backend/app/ticketing/service.py:202's server convention
  // exactly (27-UI-SPEC.md section 2), so an unedited draft matches what
  // the server would otherwise auto-build.
  return `[${params.sevLabel}] ${params.cveLabel} on ${params.hostsLine}`;
}

export function composeTicketDescription(params: {
  explain: CacheSection;
  remediationGuidance: CacheSection;
  prioritization: CacheSection;
  hostsLine: string;
  affectedProduct: string | null;
  sevLabel: string;
  cisaKev: boolean;
  exploitAvailable: boolean;
}): string {
  const sections: string[] = [];

  // "Description:" (the vuln explain summary) -- present ONLY on a grounded
  // cache hit. A miss / ungrounded / errored cache is OMITTED ENTIRELY --
  // never a labeled-but-empty stub (27-UI-SPEC.md section 3).
  if (params.explain?.grounded) {
    sections.push(`Description:\n${params.explain.summary}`);
  }

  // "Remediation:" (remediation-guidance summary) -- same omission rule.
  if (params.remediationGuidance?.grounded) {
    sections.push(`Remediation:\n${params.remediationGuidance.summary}`);
  }

  // "Asset context:" is ALWAYS present -- it needs no AI call and no cache,
  // so it renders even with no AI key configured at all (D-04). Only
  // host/product/severity/cisa_kev/exploit_available feed this section --
  // never an owner/department field (Pitfall 5, D-06).
  const assetLines = [
    `Host: ${params.hostsLine}`,
    `Product: ${params.affectedProduct ?? '—'}`,
    `Severity: ${params.sevLabel}`,
  ];
  if (params.cisaKev) assetLines.push('CISA KEV: yes');
  if (params.exploitAvailable) assetLines.push('Exploit available: yes');
  sections.push(`Asset context:\n${assetLines.join('\n')}`);

  // "Prioritization:" -- only when already cached AND grounded. This phase
  // never triggers its own prioritization gap-fill (D-02 discretion: "lean:
  // include when cached" only).
  if (params.prioritization?.grounded) {
    sections.push(`Prioritization:\n${params.prioritization.summary}`);
  }

  // Sections joined by exactly one blank line (27-UI-SPEC.md section 3).
  return sections.join('\n\n');
}
