import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { AuthService } from '../../core/auth.service';
import { TEST_USER } from '../../core/testing/auth.fixtures';
import { DashboardComponent } from './dashboard.component';

const DASHBOARD = {
  generated_at: '2026-11-12T10:00:00Z',
  currency: 'NGN',
  period: { start: '2026-11-01', end: '2026-11-12' },
  focus: {
    id: 'management',
    title: 'Management overview',
    description: 'Company financial position, approvals and delivery commitments.',
  },
  issuance_authorised: false,
  test_mode: true,
  notices: ['Invoice issuance is in test mode.'],
  financial_overview: [
    {
      id: 'customer_outstanding',
      label: 'Outstanding customer invoices',
      amount: '2500000.00',
      count: 1,
      available: true,
      basis: 'Approved customer invoice balances, NGN',
      state: 'test',
      link: '/invoicing?tab=customer-invoices&status=approved',
      note: 'Document balances, not a posted ledger total.',
      tone: 'positive',
      change_percent: null,
    },
    {
      id: 'payments_received',
      label: 'Payments received',
      amount: null,
      count: 0,
      available: false,
      basis: 'Customer receipts recorded in the selected period, NGN',
      state: 'no_data',
      link: '/banking?tab=bank-transactions',
      note: '',
      tone: 'positive',
      change_percent: null,
    },
  ],
  financial_history: [
    { month: '2026-06-01', receipts: '2000000.00', payments: '1500000.00' },
    { month: '2026-07-01', receipts: '2200000.00', payments: '2400000.00' },
    { month: '2026-08-01', receipts: '2100000.00', payments: '2550000.00' },
    { month: '2026-09-01', receipts: '2350000.00', payments: '2050000.00' },
    { month: '2026-10-01', receipts: '2450000.00', payments: '2250000.00' },
    { month: '2026-11-01', receipts: '3100000.00', payments: '2750000.00' },
  ],
  invoice_management: [
    {
      id: 'supplier_drafts',
      label: 'Draft supplier invoices',
      amount: null,
      count: 2,
      available: true,
      basis: 'Supplier invoice drafts',
      state: 'test',
      link: '/invoicing?tab=supplier-invoices&status=draft',
      note: '',
      tone: 'neutral',
    },
  ],
  pending_actions: [
    {
      id: 'purchase_requests',
      label: 'Purchase requests awaiting your approval',
      count: 3,
      link: '/procurement?tab=requests&status=submitted',
      description: 'Approved requests can be used to raise purchase orders.',
      tone: 'attention',
    },
  ],
  module_access: [
    {
      id: 'master-data',
      label: 'Master data',
      path: '/master-data',
      description: 'Suppliers, customers, catalogue, warehouses and projects.',
      readable: true,
      access: 'full',
    },
    {
      id: 'administration',
      label: 'Administration',
      path: '/administration',
      description: 'Users, roles, permissions, settings and audit access.',
      readable: false,
      access: 'restricted',
    },
  ],
  procurement_activity: {
    title: 'Procurement activity',
    description: 'Open orders, approvals and deliveries from the procurement register.',
    cards: [
      {
        id: 'open_orders',
        label: 'Open purchase orders',
        value: 2,
        format: 'number',
        detail: 'Approved, issued or partly received',
        link: '/procurement?tab=orders',
      },
    ],
    recent_orders: [
      {
        id: 1,
        number: 'PO-2026-0001',
        supplier: 'Lagos Industrial Supply Ltd',
        status: 'issued',
        created_at: '2026-11-10T09:00:00Z',
        total_value: '125000.00',
        link: '/procurement?tab=orders&record=1',
      },
    ],
  },
  project_performance: {
    rows: [
      {
        id: 1,
        code: 'PRJ-001',
        name: 'Riverside works',
        status: 'active',
        budget_total: '1000000.00',
        actual_total: '250000.00',
        open_commitment: '150000.00',
        available_budget: '600000.00',
        utilisation_percent: '40.00',
        link: '/projects?tab=projects&record=1',
      },
    ],
    summary: {
      project_count: 1,
      budget_total: '1000000.00',
      actual_total: '250000.00',
      open_commitment: '150000.00',
      available_budget: '600000.00',
      used_total: '400000.00',
      utilisation_percent: '40.00',
    },
    note: 'Purchase orders remain commitments.',
  },
  quick_actions: [
    {
      id: 'create_purchase_request',
      label: 'Create purchase request',
      description: 'Raise a request for goods or services.',
      link: '/procurement?tab=requests&new=1',
    },
  ],
  operations: {
    id: 'portfolio',
    title: 'Portfolio and commitments',
    description: 'Company-wide delivery position.',
    cards: [
      {
        id: 'active_projects',
        label: 'Active projects',
        value: 2,
        format: 'number',
        detail: 'Projects in the register',
        link: '/projects?tab=projects&status=active',
      },
    ],
  },
  recent_activity: [
    {
      id: 1,
      action: 'Supplier invoice submitted',
      entity: 'Supplier invoice',
      reference: 'SI-2026-0001',
      user: 'UAT Finance Officer',
      occurred_at: '2026-11-12T09:30:00Z',
      link: '/invoicing?tab=supplier-invoices&record=1',
    },
  ],
};

describe('DashboardComponent', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: { user: signal(TEST_USER).asReadonly() } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  function flush(body: object = DASHBOARD): void {
    http
      .expectOne((request) => request.url === '/api/v1/dashboard/')
      .flush(body);
  }

  it('greets the signed-in user and names the role focus', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Welcome back, Ama!');
    expect(text).toContain('Management overview');
  });

  it('renders real API amounts, test state and an honest empty card', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('₦2,500,000.00');
    expect(text).toContain('Test');
    expect(text).toContain('No records in this period');
    expect(text).toContain('Draft supplier invoices');
  });

  it('does not show infrastructure status or raw permission identifiers', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).not.toContain('API reachable');
    expect(text).not.toContain('accounting.');
    expect(text).not.toContain('invoicing.');
    expect(text).not.toContain('procurement.');
  });

  it('shows only the quick actions returned for the role', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Create purchase request');
    expect(text).not.toContain('Upload bank statement');
  });

  it('marks a module this role cannot open without hiding it', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Restricted');
    expect(element.textContent).toContain('View access status');
    const cards = Array.from(element.querySelectorAll('.module-card'));
    const restricted = cards.find((card) => card.textContent?.includes('Administration'));
    expect(restricted?.textContent).toContain('Restricted');
  });

  it('renders authorised procurement and project performance summaries', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    const text = element.textContent ?? '';
    expect(text).toContain('Procurement Activity');
    expect(text).toContain('Project Performance');
    expect(text).toContain('PRJ-001');
    expect(text).toContain('40.0% used');
  });

  it('renders the six-month receipts and payments chart', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.chart__group').length).toBe(6);
    expect(element.querySelectorAll('.chart__bar').length).toBe(12);
    expect(element.textContent).toContain('Financial Overview');
    expect(element.textContent).toContain('Receipts');
    expect(element.textContent).toContain('Payments');
  });

  it('shows an empty pending-actions state instead of a false zero', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    flush({ ...DASHBOARD, pending_actions: [], recent_activity: [] });
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('No items need your attention');
    expect(text).toContain('No recent activity');
  });

  it('keeps a retryable error when the dashboard cannot be loaded', () => {
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    http
      .expectOne((request) => request.url === '/api/v1/dashboard/')
      .flush(
        { error: { code: 'server_error', message: 'Dashboard unavailable.', details: null } },
        { status: 500, statusText: 'Server Error' },
      );
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Dashboard unavailable.');
    expect(text).toContain('Try again');
  });
});
