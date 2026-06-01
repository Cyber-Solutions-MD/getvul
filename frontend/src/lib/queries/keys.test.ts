import { describe, it, expect } from 'vitest';
import { queryKeys } from './keys';

describe('queryKeys.tickets namespace', () => {
  it('all is the prefix tuple [tickets]', () => {
    expect(queryKeys.tickets.all).toEqual(['tickets']);
  });

  it('list returns a stable tuple beginning with [tickets, list]', () => {
    const key = queryKeys.tickets.list({ filters: {}, page: 1, view: 'list' });
    expect(key[0]).toBe('tickets');
    expect(key[1]).toBe('list');
    // third element carries the opts object
    expect(key[2]).toEqual({ filters: {}, page: 1, view: 'list' });
  });

  it('byId returns [tickets, detail, id]', () => {
    const key = queryKeys.tickets.byId('x');
    expect(key).toEqual(['tickets', 'detail', 'x']);
  });

  it('comments returns [tickets, id, comments]', () => {
    const key = queryKeys.tickets.comments('x');
    expect(key).toEqual(['tickets', 'x', 'comments']);
  });

  it('watchers returns [tickets, id, watchers]', () => {
    const key = queryKeys.tickets.watchers('x');
    expect(key).toEqual(['tickets', 'x', 'watchers']);
  });

  it('rules returns [tickets, rules]', () => {
    const key = queryKeys.tickets.rules();
    expect(key).toEqual(['tickets', 'rules']);
  });

  it('all prefix-invalidates the full subtree (starts with tickets)', () => {
    // All sub-keys share the same first element as `all`
    const listKey = queryKeys.tickets.list({ filters: {}, page: 1, view: 'list' });
    expect(listKey[0]).toBe(queryKeys.tickets.all[0]);
    expect(queryKeys.tickets.byId('abc')[0]).toBe(queryKeys.tickets.all[0]);
  });

  it('existing assets.byId is not disturbed', () => {
    // Regression: adding tickets must not remove assets keys
    expect(queryKeys.assets.byId('y')).toEqual(['assets', 'detail', 'y']);
  });
});
