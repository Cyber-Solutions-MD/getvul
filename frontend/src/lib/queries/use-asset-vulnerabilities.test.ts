import { describe, it, expect } from 'vitest';
import { buildSearchParams } from './use-vulnerabilities';

describe('useAssetVulnerabilities indirect — buildSearchParams threads asset_id', () => {
  it('emits asset_id=... when filters.asset_id is set', () => {
    const sp = buildSearchParams({
      filters: { asset_id: 'abc-123' },
      group: 'cve',
      page: 1,
      sort: '',
      order: 'desc',
    });
    expect(sp.get('asset_id')).toBe('abc-123');
  });

  it('does NOT emit asset_id when filters.asset_id is undefined', () => {
    const sp = buildSearchParams({
      filters: {},
      group: 'cve',
      page: 1,
      sort: '',
      order: 'desc',
    });
    expect(sp.has('asset_id')).toBe(false);
  });
});
