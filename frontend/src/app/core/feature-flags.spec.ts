import { describe, expect, it } from 'vitest';

import { resolveMasterDataLayout } from './feature-flags';

describe('resolveMasterDataLayout', () => {
  it('keeps MASTER_DATA_V2 off by default', () => {
    expect(resolveMasterDataLayout('/master-data/suppliers')).toBe('legacy');
    expect(resolveMasterDataLayout('/master-data/suppliers', true)).toBe('v2');
  });

  it('allows an explicit preview and a legacy override', () => {
    expect(resolveMasterDataLayout('/master-data/suppliers?layout=v2')).toBe('v2');
    expect(resolveMasterDataLayout('/master-data/suppliers?layout=legacy', true)).toBe('legacy');
    expect(resolveMasterDataLayout('/master-data/suppliers', false, true)).toBe('v2');
  });
});