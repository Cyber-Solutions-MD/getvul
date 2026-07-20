/**
 * microcopy.ts — Connector domain copy strings.
 *
 * Aligned with copy-voice.md:
 *   - Sentence case, no title case
 *   - Verb phrases for buttons ("Add connector", "Sync now")
 *   - No "Are you sure?" — names the action instead
 *   - Empty state: headline + body + lightbulb suggestion
 */

// ——— Category sections ———

export type ConnectorCategory =
  | 'vulnerability_scanner'
  | 'ticketing'
  | 'identity_provider'
  | 'enrichment';

export const CATEGORY_LABELS: Record<ConnectorCategory, string> = {
  vulnerability_scanner: 'Vulnerability scanners',
  identity_provider: 'Identity',
  enrichment: 'MDM & enrichment',
  ticketing: 'Ticketing',
};

/** Display order for category sections */
export const CATEGORY_ORDER: ConnectorCategory[] = [
  'vulnerability_scanner',
  'identity_provider',
  'enrichment',
  'ticketing',
];

// ——— Empty state copy per category ———

export type EmptyCopy = {
  heading: string;
  body: string;
  cta: string;
  suggestion: string;
};

export const CATEGORY_EMPTY: Record<ConnectorCategory, EmptyCopy> = {
  vulnerability_scanner: {
    heading: 'No vulnerability scanners connected',
    body: 'Connect CrowdStrike, Nessus, Defender, Wiz, Qualys, or Rapid7 to start aggregating findings.',
    cta: 'Add connector',
    suggestion: 'Start with a vulnerability scanner.',
  },
  identity_provider: {
    heading: 'No identity providers connected',
    body: 'Connect Google Workspace, Azure Entra ID, or Okta to enrich assets with owner and group data.',
    cta: 'Add connector',
    suggestion: 'Identity data helps you route tickets to the right owner.',
  },
  enrichment: {
    heading: 'No MDM or enrichment connectors configured',
    body: 'Connect Jamf, Intune, or Humaans to add device management and HR data to your assets.',
    cta: 'Add connector',
    suggestion: 'MDM connectors improve asset classification accuracy.',
  },
  ticketing: {
    heading: 'No ticketing integrations connected',
    body: 'Connect Jira or Asana to create and track remediation tickets directly from vulnerability findings.',
    cta: 'Add connector',
    suggestion: 'Ticket creation is much faster once a ticketing connector is configured.',
  },
};

// ——— Delete confirm copy ———

/**
 * Returns the delete confirmation message for a connector.
 * Names the action; no "Are you sure?" (copy-voice.md).
 */
export function deleteConfirmMessage(connectorName: string): string {
  return `Delete ${connectorName}? Synced data from this connector may be affected.`;
}

// ——— Form copy ———

export const FORM_COPY = {
  saveLabel: 'Save connector',
  cancelLabel: 'Cancel',
  testLabel: 'Test connection',
  syncIntervalLabel: 'Sync interval',
  enabledLabel: 'Enabled',
  credentialSentinel: '••••••',
} as const;

// ——— Add-connector wizard copy (Phase 19, UI-SPEC "Copywriting Contract") ———
// New copy lives here, never inlined in wizard components.

export const WIZARD_COPY = {
  // stepper step labels (index 0 = Provider, shown complete)
  stepLabels: ['Provider', 'Credentials', 'Test', 'Confirm'] as const,
  // dialog heading builder — provider already picked on the grid (D-01)
  dialogHeading: (providerName: string) => `Add connector · ${providerName}`,
  nextLabel: 'Next',
  backLabel: 'Back',
  // step 2 has nowhere to go "back" inside the modal → left button is Cancel
  cancelLabel: 'Cancel',
  addLabel: 'Add connector', // step 4 primary gradient CTA
  testLabel: 'Test connection', // idle
  testingLabel: 'Testing…', // pending (names what loads, not "Loading…")
  credentialsGateHint: 'Fill every field to continue.', // UX-D-02-02 announce-why (credentials step)
  testGateHint: 'Test the connection to continue.',
  retestHint: 'Credentials changed — re-test to continue.', // D-08 verbatim
  confirmSectionProvider: 'Provider',
  confirmSectionConnection: 'Connection',
  confirmSectionAccess: 'Required access',
  confirmSectionSync: 'Sync interval',
  confirmConnectionOk: '✓ Connection verified',
  noScopes: 'No special scopes required.', // when permissions[] is empty
} as const;
