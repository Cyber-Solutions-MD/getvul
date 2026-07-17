import { describe, it, expect } from 'vitest';
import { bucketTickets, COLUMN_ORDER, COLUMN_LABELS } from './bucket-tickets';
import type { TicketSummary } from '@/lib/queries/use-tickets';

function makeTicket(overrides: Partial<TicketSummary> = {}): TicketSummary {
  return {
    id: 't1',
    provider: 'jira',
    external_ticket_id: 'JIRA-1',
    title: 'Test ticket',
    external_status: null,
    blocked: false,
    blocked_reason: null,
    sla_due_at: null,
    assignee: null,
    max_severity: null,
    vuln_count: 0,
    critical_count: 0,
    high_count: 0,
    external_ticket_url: 'https://example.com',
    ...overrides,
  };
}

describe('bucketTickets', () => {
  it('returns 4 empty columns for empty input', () => {
    expect(bucketTickets([])).toEqual({
      open: [],
      in_progress: [],
      completed: [],
      blocked: [],
    });
  });

  it('D-COL-01: blocked=true wins regardless of external_status', () => {
    const t = makeTicket({ id: 't-blocked', blocked: true, external_status: 'open' });
    const result = bucketTickets([t]);
    expect(result.blocked).toEqual([t]);
    expect(result.open).toEqual([]);
  });

  it('maps external_status "open" to the open column', () => {
    const t = makeTicket({ id: 't-open', external_status: 'open' });
    const result = bucketTickets([t]);
    expect(result.open).toEqual([t]);
  });

  it('maps "in_progress" and "in progress" (space variant) to in_progress', () => {
    const a = makeTicket({ id: 't-ip1', external_status: 'in_progress' });
    const b = makeTicket({ id: 't-ip2', external_status: 'in progress' });
    const result = bucketTickets([a, b]);
    expect(result.in_progress).toEqual([a, b]);
  });

  it('maps "completed" to the completed column', () => {
    const t = makeTicket({ id: 't-done', external_status: 'completed' });
    const result = bucketTickets([t]);
    expect(result.completed).toEqual([t]);
  });

  it('maps null, empty string, or unrecognized external_status to open', () => {
    const nullStatus = makeTicket({ id: 't-null', external_status: null });
    const emptyStatus = makeTicket({ id: 't-empty', external_status: '' });
    const unknownStatus = makeTicket({ id: 't-unknown', external_status: 'weird-value' });
    const result = bucketTickets([nullStatus, emptyStatus, unknownStatus]);
    expect(result.open).toEqual([nullStatus, emptyStatus, unknownStatus]);
  });

  it('matches external_status case-insensitively', () => {
    const upperOpen = makeTicket({ id: 't-OPEN', external_status: 'OPEN' });
    const mixedCompleted = makeTicket({ id: 't-Completed', external_status: 'Completed' });
    const result = bucketTickets([upperOpen, mixedCompleted]);
    expect(result.open).toEqual([upperOpen]);
    expect(result.completed).toEqual([mixedCompleted]);
  });

  it('COLUMN_ORDER is the locked flow order (D-COL-04)', () => {
    expect(COLUMN_ORDER).toEqual(['open', 'in_progress', 'completed', 'blocked']);
  });

  it('COLUMN_LABELS maps each key to its display string', () => {
    expect(COLUMN_LABELS).toEqual({
      open: 'Open',
      in_progress: 'In progress',
      completed: 'Completed',
      blocked: 'Blocked',
    });
  });
});
