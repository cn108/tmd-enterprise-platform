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
  {
    path: 'invoicing',
    title: 'Invoices and payments · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'invoicing' },
    loadComponent: workspace,
  },
  {
    path: 'banking',
    title: 'Banking and reconciliation · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'banking' },
    loadComponent: workspace,
  },
  {
    path: 'projects',
    title: 'Projects and costing · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'projects' },
    loadComponent: workspace,
  },
  {
    path: 'services',
    title: 'Engineering services · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'services' },
    loadComponent: workspace,
  },
  {
    path: 'leasing',
    title: 'Equipment leasing · TMD Platform',
    canActivate: [authGuard],
    data: { module: 'leasing' },
    loadComponent: workspace,
  },
  {
    path: 'reports',
    title: 'Reports · TMD Platform',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/reports/reports.component').then((m) => m.ReportsComponent),
  },
  {
    path: 'administration',
    title: 'Administration · TMD Platform',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/administration/administration.component').then(
        (m) => m.AdministrationComponent,
      ),
  },
  { path: '**', redirectTo: '' },
];
