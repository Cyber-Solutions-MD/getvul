import { describe, it, expect } from 'vitest';
import { queryKeys } from './keys';

describe('useAsset query key', () => {
  it('byId produces a stable key per id', () => {
    const k1 = queryKeys.assets.byId('abc');
    const k2 = queryKeys.assets.byId('abc');
    expect(k1).toEqual(k2);
  });

  it('byId differs for different ids', () => {
    expect(queryKeys.assets.byId('a')).not.toEqual(queryKeys.assets.byId('b'));
  });
});
