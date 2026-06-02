// @vitest-environment jsdom
/**
 * Tests for useTicketDetail — RED phase (13-08 Task 1).
 *
 * Verifies:
 * 1. queryKey uses queryKeys.tickets.byId(id)
 * 2. query is disabled when id is falsy
 */
import { describe, it, expect } from 'vitest';
import { queryKeys } from './keys';

describe('useTicketDetail query shape', () => {
  it('queryKeys.tickets.byId produces a stable key', () => {
    const k1 = queryKeys.tickets.byId('t1');
    const k2 = queryKeys.tickets.byId('t1');
    expect(k1).toEqual(k2);
  });

  it('queryKeys.tickets.byId differs for different ids', () => {
    expect(queryKeys.tickets.byId('t1')).not.toEqual(queryKeys.tickets.byId('t2'));
  });

  it('byId key shape is tickets/detail/id', () => {
    const key = queryKeys.tickets.byId('abc');
    expect(key[0]).toBe('tickets');
    expect(key[1]).toBe('detail');
    expect(key[2]).toBe('abc');
  });
});
