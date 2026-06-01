// Phase 13 — Shared ticket domain types.
// Exported for downstream reuse: provider-mark.tsx, status-pill.tsx, hooks, pages.

export type TicketProvider = 'jira' | 'asana' | 'github';
export type TicketStatus = 'open' | 'in_progress' | 'completed' | 'blocked';
