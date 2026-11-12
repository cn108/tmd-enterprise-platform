import { describe, expect, it } from 'vitest';

import { routes } from '../../app.routes';
import { MODULES } from '../workspace/workspace-config';
import { ENTITY_ORDER, MASTER_ENTITIES } from './master-data.config';

describe('master-data configuration', () => {
  it('maps every legacy master-data register plus tax rates into V2', () => {
    const legacyIds = MODULES['master-data'].tabs.map((tab) => tab.id);
    expect(ENTITY_ORDER).toHaveLength(legacyIds.length + 1);
    expect(new Set(ENTITY_ORDER).size).toBe(ENTITY_ORDER.length);
    expect(new Set(Object.values(MASTER_ENTITIES).map((entity) => entity.endpoint)).size).toBe(
      legacyIds.length + 1,
    );
  });

  it('gives every register a pinned identity column, grid and usable endpoint', () => {
    for (const key of ENTITY_ORDER) {
      const entity = MASTER_ENTITIES[key];
      expect(entity.key, key).toBe(key);
      expect(entity.endpoint, key).toMatch(/^\/api\/v1\//);
      expect(entity.columns[0]?.key, key).toBe('id');
      expect(entity.columns[1]?.primary, key).toBe(true);
      expect(entity.grid, key).toContain('minmax(13rem,1.6fr)');
      expect(entity.grid, key).toMatch(/4\.75rem$/);
    }
  });

  it('publishes a V2 route for every register', () => {
    const masterRoutes = routes.filter(
      (route) => route.path?.startsWith('master-data/') === true,
    );
    const paths = masterRoutes.map((route) => route.path!);
    expect(paths).toHaveLength(ENTITY_ORDER.length);
    expect(new Set(paths).size).toBe(ENTITY_ORDER.length);
    expect(paths).toContain('master-data/warehouses');
    expect(paths).toContain('master-data/budgets');
    expect(paths).toContain('master-data/milestones');
    for (const route of masterRoutes) {
      const key = route.path!.split('/')[1];
      expect(ENTITY_ORDER).toContain(key);
      expect(route.data?.['entity']).toBe(key);
    }
  });
});