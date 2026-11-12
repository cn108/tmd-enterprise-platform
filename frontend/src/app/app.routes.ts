import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth.guard';

const workspace = () =>
  import('./features/workspace/workspace.component').then((m) => m.WorkspaceComponent);

const masterDataPage = () =>
  import('./features/master-data/master-data-page.component').then(
    (m) => m.MasterDataPageComponent,
  );

const masterDataRoutes: Routes = [
  ['suppliers', 'suppliers', 'Suppliers'],
  ['customers', 'customers', 'Customers'],
  ['products', 'catalogue', 'Products'],
  ['tax-rates', 'suppliers', 'Tax rates'],
  ['warehouses', 'warehouses', 'Warehouses'],
  ['projects', 'projects', 'Projects'],
  ['supplier-categories', 'supplier-categories', 'Supplier categories'],
  ['contacts', 'contacts', 'Contacts'],
  ['addresses', 'addresses', 'Addresses'],
  ['tax-registrations', 'tax-registrations', 'Tax registrations'],
  ['supplier-bank', 'supplier-bank', 'Supplier bank accounts'],
  ['bank-changes', 'bank-changes', 'Bank changes'],
  ['compliance', 'compliance', 'Compliance documents'],
  ['document-categories', 'document-categories', 'Document categories'],
  ['documents', 'documents', 'Documents'],
  ['product-categories', 'product-categories', 'Product categories'],
  ['units', 'units', 'Units of measure'],
  ['manufacturers', 'manufacturers', 'Manufacturers'],
  ['prices', 'prices', 'Item prices'],
  ['specifications', 'specifications', 'Specifications'],
  ['batches', 'batches', 'Batches'],
  ['serials', 'serials', 'Serial numbers'],
  ['certificates', 'certificates', 'Certificates'],
  ['storage-locations', 'storage-locations', 'Storage locations'],
  ['departments', 'departments', 'Departments'],
  ['cost-centres', 'cost-centres', 'Cost centres'],
  ['destinations', 'destinations', 'Destinations'],
  ['project-locations', 'project-locations', 'Project locations'],
  ['contracts', 'contracts', 'Customer contracts'],
  ['contract-revisions', 'contract-revisions', 'Contract revisions'],
  ['budgets', 'budgets', 'Project budgets'],
  ['milestones', 'milestones', 'Milestones'],
].map(([entity, tab, title]) => ({
  path: `master-data/${entity}`,
  title: `${title} · TMD Platform`,
  canActivate: [authGuard],
  data: { module: 'master-data', entity, tab },
  loadComponent: masterDataPage,
}));

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
    pathMatch: 'full',
    redirectTo: 'master-data/suppliers',
  },
  ...masterDataRoutes,
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
