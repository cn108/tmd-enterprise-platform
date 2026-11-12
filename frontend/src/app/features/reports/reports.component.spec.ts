import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth.service';
import { TEST_USER } from '../../core/testing/auth.fixtures';
import { ReportsComponent } from './reports.component';

const OVERVIEW = {
  start: '2026-11-01',
  end: '2026-11-12',
  actual: {
    revenue: '1000.00',
    expenses: '400.00',
    net_result: '600.00',
    source: 'posted_journal_lines',
  },
  cash: { available: false, gl_closing_cash: '', recorded_bank_opening_balances: '0.00', reason: 'No bank GL link' },
  receivables: { total: '250.00', overdue: '50.00' },
  payables: { total: '100.00', overdue: '0.00' },
  inventory: { available: false, value: '', quantity: '', reason: 'No valuation method' },
  projects: { active: 2, total_budget: '5000.00', actual_cost: '1000.00', open_commitments: '500.00' },
  procurement: { committed_value: '500.00', orders: 2, outstanding_deliveries: 1 },
  operations: { open_work_orders: 1, overdue_returns: 0, equipment_utilisation_rows: 0 },
  warnings: ['No inventory valuation method is configured.'],
  definitions: { actual: 'Posted ledger figures.' },
};

const fullPermissions = signal({
  ...TEST_USER,
  permissions: [
    'reporting.view_reporting',
    'reporting.view_financialreporting',
    'reporting.export_reporting',
  ],
});

describe('ReportsComponent', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    fullPermissions.set({
      ...TEST_USER,
      permissions: [
        'reporting.view_reporting',
        'reporting.view_financialreporting',
        'reporting.export_reporting',
      ],
    });
    await TestBed.configureTestingModule({
      imports: [ReportsComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            user: fullPermissions.asReadonly(),
          },
        },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  function create() {
    const fixture = TestBed.createComponent(ReportsComponent);
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts/?page_size=100').flush({ results: [] });
    const overview = http.expectOne((request) => request.url.startsWith('/api/v1/reporting/overview/'));
    overview.flush(OVERVIEW);
    fixture.detectChanges();
    return fixture;
  }

  it('renders posted ledger figures and completeness warnings from the API', () => {
    const fixture = create();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('₦1,000.00');
    expect(text).toContain('₦600.00');
    expect(text).toContain('No inventory valuation method is configured.');
    expect(text).toContain('No bank GL link');
  });

  it('switches to receivables and shows document basis and buckets', () => {
    const fixture = create();
    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('.tabs button') as NodeListOf<HTMLButtonElement>,
    );
    buttons.find((button) => button.textContent?.includes('Receivables'))?.click();
    fixture.detectChanges();

    const request = http.expectOne((item) => item.url.startsWith('/api/v1/reporting/receivables-ageing/'));
    request.flush({
      source: 'approved_customer_invoices',
      total: '250.00',
      overdue: '50.00',
      buckets: [
        { bucket: 'Current', amount: '200.00' },
        { bucket: '1–30 days', amount: '50.00' },
      ],
      rows: [
        {
          number: 'CI-1',
          customer: 'Acme',
          invoice_date: '2026-10-01',
          due_date: '2026-10-31',
          balance: '50.00',
          days_overdue: 12,
          bucket: '1–30 days',
          project: '',
        },
      ],
    });
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('document balances, not ledger receivables or payables');
    expect(text).toContain('CI-1');
    expect(text).toContain('1–30 days');
  });

  it('shows a report error instead of presenting an empty dataset as zero', () => {
    const fixture = TestBed.createComponent(ReportsComponent);
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts/?page_size=100').flush({ results: [] });
    http
      .expectOne((request) => request.url.startsWith('/api/v1/reporting/overview/'))
      .flush(
        { error: { code: 'invalid_filter', message: 'Dates must use YYYY-MM-DD.' } },
        { status: 400, statusText: 'Bad Request' },
      );
    fixture.detectChanges();

    const alert = fixture.nativeElement.querySelector('[role="alert"]') as HTMLElement;
    expect(alert.textContent).toContain('Dates must use YYYY-MM-DD.');
  });

  it('opens the server export for the selected report', () => {
    const fixture = create();
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);

    const exportButton = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Export CSV'));
    exportButton?.click();

    expect(open).toHaveBeenCalledOnce();
    expect(open.mock.calls[0][0]).toContain('/api/v1/reporting/overview/export/');
    expect(open.mock.calls[0][0]).toContain('output=csv');
    open.mockRestore();
  });

  it('hides financial reports from an operational-only reader', () => {
    fullPermissions.set({
      ...TEST_USER,
      permissions: ['reporting.view_reporting'],
    });
    const fixture = TestBed.createComponent(ReportsComponent);
    fixture.detectChanges();
    http.expectOne('/api/v1/accounts/?page_size=100').flush({ results: [] });
    http
      .expectOne((request) => request.url.startsWith('/api/v1/reporting/receivables-ageing/'))
      .flush({
        source: 'approved_customer_invoices',
        total: '0.00',
        overdue: '0.00',
        buckets: [],
        rows: [],
      });
    fixture.detectChanges();

    const tabs = Array.from(
      fixture.nativeElement.querySelectorAll('.tabs button') as NodeListOf<HTMLButtonElement>,
    ).map((button) => button.textContent?.trim());
    expect(tabs).not.toContain('Financial statements');
    expect(tabs).not.toContain('Executive');
  });
});
