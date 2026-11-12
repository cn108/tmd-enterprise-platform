/**
 * MASTER_DATA_V2 is deliberately off by default until TMD signs off UAT.
 * `?layout=v2` previews the new workspace and `?layout=legacy` pins the old one.
 */
export const MASTER_DATA_V2 = false;

export type MasterDataLayout = 'v2' | 'legacy';

export function resolveMasterDataLayout(
  url: string,
  flagEnabled: boolean = MASTER_DATA_V2,
  rememberedPreview = false,
): MasterDataLayout {
  const query = url.includes('?') ? url.slice(url.indexOf('?') + 1) : '';
  const requested = new URLSearchParams(query).get('layout');
  if (requested === 'legacy') {
    return 'legacy';
  }
  if (requested === 'v2') {
    return 'v2';
  }
  return flagEnabled || rememberedPreview ? 'v2' : 'legacy';
}