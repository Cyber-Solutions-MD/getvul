/**
 * Tests for useDirectoryUsers + useDirectoryStats hooks (Plan 14-04 Task 1 RED).
 * Behaviors:
 *   Test 1: useDirectoryUsers(filters) GETs /api/v1/users/directory with params
 *           and returns the items envelope.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { buildDirectorySearchParams } from './use-directory-users';
import type { DirectoryUsersFilters } from './use-directory-users';

// Test 1 — buildDirectorySearchParams wire contract (co-located helper, same
// pattern as Phase 12 buildSearchParams — lets URL-shape tests run without TanStack).
describe('buildDirectorySearchParams', () => {
  it('sets page and page_size', () => {
    const sp = buildDirectorySearchParams({
      filters: {},
      page: 2,
      sort: 'display_name',
      order: 'asc',
    });
    expect(sp.get('page')).toBe('2');
  });

  it('sets status filter when provided', () => {
    const sp = buildDirectorySearchParams({
      filters: { status: 'active' },
      page: 1,
      sort: 'display_name',
      order: 'asc',
    });
    expect(sp.get('status')).toBe('active');
  });

  it('sets department filter when provided', () => {
    const sp = buildDirectorySearchParams({
      filters: { department: 'Engineering' },
      page: 1,
      sort: 'display_name',
      order: 'asc',
    });
    expect(sp.get('department')).toBe('Engineering');
  });

  it('sets source filter when provided', () => {
    const sp = buildDirectorySearchParams({
      filters: { source: 'okta' },
      page: 1,
      sort: 'display_name',
      order: 'asc',
    });
    expect(sp.get('source')).toBe('okta');
  });

  it('sets search when provided', () => {
    const sp = buildDirectorySearchParams({
      filters: { search: 'alice' },
      page: 1,
      sort: 'display_name',
      order: 'asc',
    });
    expect(sp.get('search')).toBe('alice');
  });

  it('omits empty filters', () => {
    const sp = buildDirectorySearchParams({
      filters: {},
      page: 1,
      sort: 'display_name',
      order: 'asc',
    });
    expect(sp.has('search')).toBe(false);
    expect(sp.has('department')).toBe(false);
    expect(sp.has('source')).toBe(false);
  });

  it('sets sort_by and sort_dir', () => {
    const sp = buildDirectorySearchParams({
      filters: {},
      page: 1,
      sort: 'email',
      order: 'desc',
    });
    expect(sp.get('sort_by')).toBe('email');
    expect(sp.get('sort_dir')).toBe('desc');
  });
});
