// Phase 14 — Connector domain types.
// Exported for downstream reuse: connector-mark.tsx, sync-status-pill.tsx, connector-card.tsx, pages.
//
// ConnectorProvider covers all 14 connector types:
//   - 6 vulnerability scanners: crowdstrike, nessus, defender, wiz, qualys, rapid7
//   - 3 identity providers: google_workspace, azure_entra_id, okta
//   - 3 enrichment/MDM: jamf, intune, humaans
//   - 3 ticketing (shared with Phase 13 TicketProvider): jira, asana, github
//
// The page-layer caller lowercases the backend connector_type string before passing
// (e.g. backend "CROWDSTRIKE" → "crowdstrike"). See connector-mark.tsx.

export type ConnectorProvider =
  | 'crowdstrike'
  | 'nessus'
  | 'defender'
  | 'wiz'
  | 'qualys'
  | 'rapid7'
  | 'google_workspace'
  | 'azure_entra_id'
  | 'okta'
  | 'jamf'
  | 'intune'
  | 'humaans'
  | 'jira'
  | 'asana'
  | 'github';
