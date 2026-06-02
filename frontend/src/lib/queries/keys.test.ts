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

// Phase 14 — Wave 0 namespace extension (14-00 Task 2)
describe('queryKeys.cspm namespace', () => {
  it('all is the prefix tuple [cspm]', () => {
    expect(queryKeys.cspm.all).toEqual(['cspm']);
  });

  it('list returns stable array beginning with [cspm, list]', () => {
    const key = queryKeys.cspm.list({ filters: {}, page: 1 });
    expect(key[0]).toBe('cspm');
    expect(key[1]).toBe('list');
    expect(key[2]).toEqual({ filters: {}, page: 1 });
  });

  it('detail returns [cspm, detail, id]', () => {
    const key = queryKeys.cspm.detail('abc');
    expect(key).toEqual(['cspm', 'detail', 'abc']);
  });

  it('stats returns [cspm, stats]', () => {
    const key = queryKeys.cspm.stats();
    expect(key).toEqual(['cspm', 'stats']);
  });

  it('compliance returns [cspm, compliance]', () => {
    const key = queryKeys.cspm.compliance();
    expect(key).toEqual(['cspm', 'compliance']);
  });

  it('all prefix-invalidates the cspm subtree', () => {
    const listKey = queryKeys.cspm.list({ filters: {}, page: 1 });
    expect(listKey[0]).toBe(queryKeys.cspm.all[0]);
    expect(queryKeys.cspm.detail('x')[0]).toBe(queryKeys.cspm.all[0]);
  });
});

describe('queryKeys.settings namespace', () => {
  it('all is the prefix tuple [settings]', () => {
    expect(queryKeys.settings.all).toEqual(['settings']);
  });

  it('tenant returns [settings, tenant]', () => {
    expect(queryKeys.settings.tenant()).toEqual(['settings', 'tenant']);
  });

  it('users returns [settings, users]', () => {
    expect(queryKeys.settings.users()).toEqual(['settings', 'users']);
  });

  it('auditLog returns [settings, audit-log, opts]', () => {
    const key = queryKeys.settings.auditLog({ page: 1 });
    expect(key[0]).toBe('settings');
    expect(key[1]).toBe('audit-log');
    expect(key[2]).toEqual({ page: 1 });
  });

  it('groups returns [settings, groups]', () => {
    expect(queryKeys.settings.groups()).toEqual(['settings', 'groups']);
  });

  it('all prefix-invalidates the settings subtree', () => {
    expect(queryKeys.settings.tenant()[0]).toBe(queryKeys.settings.all[0]);
  });
});

describe('queryKeys.directoryUsers namespace', () => {
  it('all is the prefix tuple [directory-users]', () => {
    expect(queryKeys.directoryUsers.all).toEqual(['directory-users']);
  });

  it('list returns stable array beginning with [directory-users, list]', () => {
    const key = queryKeys.directoryUsers.list({ filters: {}, page: 1, sort: 'display_name', order: 'asc' });
    expect(key[0]).toBe('directory-users');
    expect(key[1]).toBe('list');
    expect(key[2]).toEqual({ filters: {}, page: 1, sort: 'display_name', order: 'asc' });
  });

  it('stats returns [directory-users, stats]', () => {
    expect(queryKeys.directoryUsers.stats()).toEqual(['directory-users', 'stats']);
  });

  it('all prefix-invalidates the directoryUsers subtree', () => {
    const listKey = queryKeys.directoryUsers.list({ filters: {}, page: 1, sort: 'email', order: 'desc' });
    expect(listKey[0]).toBe(queryKeys.directoryUsers.all[0]);
  });

  it('existing tickets namespace is not disturbed', () => {
    // Regression: adding Phase 14 namespaces must not break Phase 13
    expect(queryKeys.tickets.all).toEqual(['tickets']);
    expect(queryKeys.tickets.byId('z')).toEqual(['tickets', 'detail', 'z']);
  });
});
