import { describe, it, expect } from 'vitest';
import { queryKeys } from './keys';

describe('useAssetRemediations query key', () => {
  it('keys differ per assetId', () => {
    expect(queryKeys.assets.remediations('a')).not.toEqual(
      queryKeys.assets.remediations('b')
    );
  });
  it('key includes the literal segments', () => {
    const k = queryKeys.assets.remediations('abc');
    expect(k).toContain('remediations');
    expect(k).toContain('abc');
  });
});
