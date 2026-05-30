import { describe, it, expect } from 'vitest';
import { queryKeys } from './keys';

describe('useAssignableUsers query key', () => {
  it('keys differ per search term', () => {
    expect(queryKeys.assignableUsers.search('al')).not.toEqual(
      queryKeys.assignableUsers.search('bo')
    );
  });
  it('empty search still produces a valid key', () => {
    expect(queryKeys.assignableUsers.search('')).toEqual([
      'assignable-users',
      'search',
      '',
    ]);
  });
});
