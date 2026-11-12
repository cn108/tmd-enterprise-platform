import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';

import { MasterDataLayout, resolveMasterDataLayout } from '../../core/feature-flags';
import { WorkspaceComponent } from '../workspace/workspace.component';
import { MasterDataComponent } from './master-data.component';

@Component({
  selector: 'app-master-data-page',
  imports: [MasterDataComponent, WorkspaceComponent],
  template: `
    @if (layout === 'v2') {
      <app-master-data />
    } @else {
      <app-workspace />
    }
  `,
})
export class MasterDataPageComponent {
  protected readonly layout: MasterDataLayout;

  constructor() {
    const router = inject(Router);
    const query = router.url.includes('?') ? router.url.slice(router.url.indexOf('?') + 1) : '';
    const requested = new URLSearchParams(query).get('layout');
    try {
      if (requested === 'v2') {
        sessionStorage.setItem('tmd-master-data-layout', 'v2');
      } else if (requested === 'legacy') {
        sessionStorage.removeItem('tmd-master-data-layout');
      }
    } catch {
      // Storage can be unavailable; the explicit query still controls this view.
    }
    const remembered = (() => {
      try {
        return sessionStorage.getItem('tmd-master-data-layout') === 'v2';
      } catch {
        return false;
      }
    })();
    this.layout = resolveMasterDataLayout(router.url, undefined, remembered);
  }
}