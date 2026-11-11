import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth.guard';

const workspace = () =>
  import('./features/workspace/workspace.component').then((m) => m.WorkspaceComponent);

export const routes: Routes = [
  {
    path: 'login',
    title: 'Sign in · TMD Platform',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    title: 'Dashboard · TMD Platform',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
  },
  {
    path: 'master-data',
    title: 'Master data · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'master-data' },
    loadComponent: workspace,
  },
  {
    path: 'procurement',
    title: 'Procurement · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'procurement' },
    loadComponent: workspace,
  },
  {
    path: 'inventory',
    title: 'Inventory · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'inventory' },
    loadComponent: workspace,
  },
  {
    path: 'accounting',
    title: 'Accounting · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'accounting' },
    loadComponent: workspace,
  },
  { path: '**', redirectTo: '' },
];
