import { describe, it, expect } from 'vitest';
import { buildSearchParams } from './use-assets';

describe('useAssets buildSearchParams', () => {
  it('serializes empty filters with just page', () => {
    const sp = buildSearchParams({ filters: {}, page: 1, sort: '', order: 'desc' });
    expect(sp.toString()).toBe('page=1');
  });

  it('translates risk_band to min_risk using the lowest selected threshold', () => {
    const sp = buildSearchParams({
      filters: { risk_band: ['critical', 'medium'] },
      page: 1,
      sort: '',
      order: 'desc',
    });
    // min(80, 20) = 20
    expect(sp.get('min_risk')).toBe('20');
  });

  it('joins category as CSV (device_category param)', () => {
    const sp = buildSearchParams({
      filters: { category: ['WORKSTATION', 'SERVER'] },
      page: 1,
      sort: '',
      order: 'desc',
    });
    expect(sp.get('device_category')).toBe('WORKSTATION,SERVER');
  });

  it('joins source as CSV (scanner param)', () => {
    const sp = buildSearchParams({
      filters: { source: ['QUALYS', 'TENABLE'] },
      page: 1,
      sort: '',
      order: 'desc',
    });
    expect(sp.get('scanner')).toBe('QUALYS,TENABLE');
  });

  it('joins multi-select os_family values with comma (W4)', () => {
    const sp = buildSearchParams({
      filters: { os_family: ['linux', 'windows'] },
      page: 1,
      sort: '',
      order: 'desc',
    });
    expect(sp.get('os_family')).toBe('linux,windows');
  });

  it('passes through single os_family value unchanged', () => {
    const sp = buildSearchParams({
      filters: { os_family: ['macos'] },
      page: 1,
      sort: '',
      order: 'desc',
    });
    expect(sp.get('os_family')).toBe('macos');
  });

  it('threads search + sort + order', () => {
    const sp = buildSearchParams({
      filters: { search: 'prod' },
      page: 2,
      sort: 'risk_score',
      order: 'desc',
    });
    expect(sp.get('search')).toBe('prod');
    expect(sp.get('sort_by')).toBe('risk_score');
    expect(sp.get('sort_dir')).toBe('desc');
    expect(sp.get('page')).toBe('2');
  });
});
