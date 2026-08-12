/**
 * use-tickets.test.ts — TDD RED tests for buildSearchParams (no TanStack spin-up).
 *
 * Tests assert the wire-query-string contract without TanStack instantiation,
 * following the Phase 11 D-D-03 pattern (co-located + exported buildSearchParams).
 */
import { describe, it, expect } from 'vitest';
import { buildSearchParams } from './use-tickets';

describe('useTickets buildSearchParams', () => {
  it('serializes empty filters with just page', () => {
    const sp = buildSearchParams({ filters: {}, page: 1 });
    expect(sp.get('page')).toBe('1');
  });

  it('maps status array to comma-separated status param', () => {
    const sp = buildSearchParams({
      filters: { status: ['open', 'in_progress'] },
      page: 1,
    });
    expect(sp.get('status')).toBe('open,in_progress');
  });

  it('maps provider array to comma-separated provider param', () => {
    const sp = buildSearchParams({
      filters: { provider: ['jira', 'asana'] },
      page: 1,
    });
    expect(sp.get('provider')).toBe('jira,asana');
  });

  it('maps severity array to comma-separated severity param', () => {
    const sp = buildSearchParams({
      filters: { severity: ['critical', 'high'] },
      page: 1,
    });
    expect(sp.get('severity')).toBe('critical,high');
  });

  it('maps sla single-select to sla param', () => {
    const sp = buildSearchParams({
      filters: { sla: ['overdue'] },
      page: 1,
    });
    expect(sp.get('sla')).toBe('overdue');
  });

  it('passes search param through', () => {
    const sp = buildSearchParams({
      filters: { search: 'AUTH-42' },
      page: 1,
    });
    expect(sp.get('search')).toBe('AUTH-42');
  });

  it('allow-list clamp — out-of-list status value is dropped', () => {
    const sp = buildSearchParams({
      filters: { status: ['open', 'invalid_status'] as unknown as string[] },
      page: 1,
    });
    // 'invalid_status' not in allowList — only 'open' should appear
    expect(sp.get('status')).toBe('open');
  });

  it('sets page param correctly for page > 1', () => {
    const sp = buildSearchParams({ filters: {}, page: 3 });
    expect(sp.get('page')).toBe('3');
  });

  it('does not emit status param when array is empty', () => {
    const sp = buildSearchParams({ filters: { status: [] }, page: 1 });
    expect(sp.has('status')).toBe(false);
  });

  // Phase 35 SRC-02 — real server-filtering source axis (repeated params,
  // not comma-joined, matching the backend's `list[str] Query(None)` shape).
  it('appends source as repeated params (not comma-joined)', () => {
    const sp = buildSearchParams({
      filters: { source: ['QUALYS', 'RAPID7'] },
      page: 1,
    });
    expect(sp.getAll('source')).toEqual(['QUALYS', 'RAPID7']);
  });

  it('allow-list clamp — out-of-list source value is dropped', () => {
    const sp = buildSearchParams({
      filters: { source: ['QUALYS', 'TENABLE'] as unknown as string[] },
      page: 1,
    });
    expect(sp.getAll('source')).toEqual(['QUALYS']);
  });

  it('does not emit source param when array is empty', () => {
    const sp = buildSearchParams({ filters: { source: [] }, page: 1 });
    expect(sp.has('source')).toBe(false);
  });
});
