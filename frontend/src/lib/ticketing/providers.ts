// TicketProvider — the single frontend source of truth for the
// ASANA/JIRA/GITHUB provider identifier (D-23), matching the backend
// `TicketProvider` str-Enum (backend/app/ticketing/providers.py).
//
// Wire convention (CR-06): uppercase on the wire/backend; PROVIDER_LABELS
// below is the only place this module renders a human-facing label.
export type TicketProvider = 'ASANA' | 'JIRA' | 'GITHUB';

export const PROVIDER_LABELS: Record<TicketProvider, string> = {
  ASANA: 'Asana',
  JIRA: 'Jira',
  GITHUB: 'GitHub',
};
