import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { PageEvent } from '@angular/material/paginator';
import { of } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth.service';
import { TEST_USER } from '../../core/testing/auth.fixtures';
import { WorkspaceComponent } from './workspace.component';

interface WorkspaceInternals {
  onSearch(value: string): void;
  onPage(event: PageEvent): void;
  create(): void;
  sortBy(column: { key: string; label: string }): void;
}

function internals(fixture: ComponentFixture<WorkspaceComponent>): WorkspaceInternals {
  return fixture.componentInstance as unknown as WorkspaceInternals;
}

function text(fixture: ComponentFixture<WorkspaceComponent>): string {
  return (fixture.nativeElement as HTMLElement).textContent ?? '';
}

const PAGE = '?page=1&page_size=25';

describe('WorkspaceComponent', () => {
  let http: HttpTestingController;
  let open: ReturnType<typeof vi.fn>;

  async function configure(module: string, permissions: string[] = []) {
    TestBed.resetTestingModule();
    open = vi.fn(() => ({ afterClosed: () => of(null) }));
    await TestBed.configureTestingModule({
      imports: [WorkspaceComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { data: { module }, queryParamMap: { get: () => null } },
          },
        },
        {
          provide: AuthService,
          useValue: {
            user: signal({ ...TEST_USER, permissions }).asReadonly(),
          },
        },
        { provide: MatDialog, useValue: { open } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    return TestBed.createComponent(WorkspaceComponent);
  }

  afterEach(() => {
    http?.verify();
    vi.restoreAllMocks();
  });

  it('loads a server-paginated page and renders the supplier table', async () => {
    const fixture = await configure('master-data');
    fixture.detectChanges();

    const request = http.expectOne(`/api/v1/suppliers/${PAGE}`);
    expect(request.request.method).toBe('GET');
    request.flush({
      count: 1,
      results: [
        {
          id: 1,
          code: 'SUP-001',
          legal_name: 'Acme Limited',
          email: 'sales@acme.example',
          payment_terms_days: 30,
          is_active: true,
        },
      ],
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(text(fixture)).toContain('Acme Limited');
    expect(text(fixture)).toContain('30');
  });

  it('asks the server for the chosen page instead of slicing a full download', async () => {
    const fixture = await configure('master-data');
    fixture.detectChanges();
    http.expectOne(`/api/v1/suppliers/${PAGE}`).flush({ count: 60, results: [] });
    fixture.detectChanges();

    internals(fixture).onPage({ pageIndex: 1, pageSize: 25, length: 60 } as PageEvent);

    http.expectOne('/api/v1/suppliers/?page=2&page_size=25').flush({ count: 60, results: [] });
  });

  it('orders server-side when a column header is chosen', async () => {
    const fixture = await configure('master-data');
    fixture.detectChanges();
    http.expectOne(`/api/v1/suppliers/${PAGE}`).flush({
      count: 2,
      results: [
        { id: 1, code: 'SUP-200', legal_name: 'Zeta', is_active: true },
        { id: 2, code: 'SUP-100', legal_name: 'Alpha', is_active: true },
      ],
    });
    fixture.detectChanges();

    internals(fixture).sortBy({ key: 'code', label: 'Code' });
    http.expectOne('/api/v1/suppliers/?page=1&page_size=25&ordering=code').flush({
      count: 2,
      results: [
        { id: 2, code: 'SUP-100', legal_name: 'Alpha', is_active: true },
        { id: 1, code: 'SUP-200', legal_name: 'Zeta', is_active: true },
      ],
    });
    fixture.detectChanges();

    const firstCode = fixture.nativeElement.querySelector('tbody tr td') as HTMLElement;
    expect(firstCode.textContent?.trim()).toBe('SUP-100');
  });

  it('sends search to the API rather than filtering the page silently', async () => {
    const fixture = await configure('master-data');
    fixture.detectChanges();
    http.expectOne(`/api/v1/suppliers/${PAGE}`).flush({ count: 0, results: [] });
    fixture.detectChanges();

    internals(fixture).onSearch('acme');
    await new Promise((resolve) => setTimeout(resolve, 350));
    fixture.detectChanges();

    http.expectOne('/api/v1/suppliers/?page=1&page_size=25&search=acme').flush({
      count: 0,
      results: [],
    });
  });

  it('does not offer an approval the account cannot perform', async () => {
    const fixture = await configure('procurement');
    fixture.detectChanges();
    http.expectOne(`/api/v1/purchase-requests/${PAGE}`).flush({
      count: 1,
      results: [
        { id: 7, number: 'PR-0007', status: 'submitted', requester: 'ama@example.com' },
      ],
    });
    fixture.detectChanges();

    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('tbody button') as NodeListOf<HTMLButtonElement>,
    ).map((button) => button.textContent?.trim());

    expect(buttons).not.toContain('Approve');
    expect(text(fixture)).toContain('Limited actions');
    expect(text(fixture)).not.toContain('procurement.approve_purchaserequest');
  });

  it('posts the approval to the lifecycle endpoint when the permission is held', async () => {
    const fixture = await configure('procurement', ['procurement.approve_purchaserequest']);
    fixture.detectChanges();
    http.expectOne(`/api/v1/purchase-requests/${PAGE}`).flush({
      count: 1,
      results: [
        { id: 7, number: 'PR-0007', status: 'submitted', requester: 'ama@example.com' },
      ],
    });
    fixture.detectChanges();

    const approve = Array.from(
      fixture.nativeElement.querySelectorAll('tbody button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.trim() === 'Approve');
    expect(approve).toBeDefined();

    open.mockReturnValue({ afterClosed: () => of({ reason: '' }) });
    approve?.click();
    fixture.detectChanges();

    const request = http.expectOne('/api/v1/purchase-requests/7/approve/');
    expect(request.request.method).toBe('POST');
    request.flush({ id: 7, number: 'PR-0007', status: 'approved' });
    http.expectOne(`/api/v1/purchase-requests/${PAGE}`).flush({ count: 0, results: [] });
    fixture.detectChanges();

    expect(text(fixture)).toContain('Request approved.');
  });

  it('disables accounting creation when the permission is missing', async () => {
    const fixture = await configure('accounting');
    fixture.detectChanges();
    http.expectOne(`/api/v1/accounts/${PAGE}`).flush({ count: 0, results: [] });
    fixture.detectChanges();

    const createButton = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.trim() === 'New account');

    expect(createButton?.disabled).toBe(true);
    expect(text(fixture)).toContain('View only');
    expect(text(fixture)).toContain('You have read-only access to this section.');
    expect(text(fixture)).not.toContain('accounting.manage_accounts');
  });

  it('shows a polished access-restricted state without leaking records', async () => {
    const fixture = await configure('accounting');
    fixture.detectChanges();
    http.expectOne(`/api/v1/accounts/${PAGE}`).flush(
      { error: { code: 'permission_denied', message: 'Denied.', details: null } },
      { status: 403, statusText: 'Forbidden' },
    );
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Access restricted');
    expect(text).toContain('Return to dashboard');
    expect(text).not.toContain('accounting.manage_accounts');
    expect(fixture.nativeElement.querySelector('tbody')).toBeNull();
  });

  it('opens the create dialog for master data and reloads after a save', async () => {
    const fixture = await configure('master-data');
    fixture.detectChanges();
    http.expectOne(`/api/v1/suppliers/${PAGE}`).flush({ count: 0, results: [] });
    fixture.detectChanges();

    open.mockReturnValue({ afterClosed: () => of({ id: 9, code: 'SUP-009' }) });
    internals(fixture).create();
    fixture.detectChanges();

    expect(open).toHaveBeenCalledOnce();
    const options = open.mock.calls[0][1] as {
      data: { resource: { endpoint: string } };
      disableClose: boolean;
    };
    expect(options.data.resource.endpoint).toBe('/api/v1/suppliers/');
    expect(options.disableClose).toBe(true);

    http.expectOne(`/api/v1/suppliers/${PAGE}`).flush({ count: 0, results: [] });
    fixture.detectChanges();
    expect(text(fixture)).toContain('supplier created.');
  });

  it.each([
    ['banking', '/api/v1/banking-summary/'],
    ['projects', '/api/v1/project-dashboard/'],
    ['services', '/api/v1/work-orders/'],
    ['leasing', '/api/v1/equipment/'],
  ])('loads the %s module from its own API endpoint', async (module, endpoint) => {
    const fixture = await configure(module);
    fixture.detectChanges();

    http.expectOne(`${endpoint}${PAGE}`).flush({ count: 0, results: [] });
    fixture.detectChanges();

    expect(text(fixture)).toContain('No records yet.');
  });

  it('opens the private attachment form for a service work order', async () => {
    const fixture = await configure('services', ['services.change_workorder']);
    fixture.detectChanges();
    http.expectOne(`/api/v1/work-orders/${PAGE}`).flush({
      count: 1,
      results: [
        {
          id: 11,
          number: 'WO-2026-0011',
          title: 'Pump overhaul',
          status: 'in_progress',
          progress_percent: 50,
        },
      ],
    });
    fixture.detectChanges();

    const attach = Array.from(
      fixture.nativeElement.querySelectorAll('tbody button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.trim() === 'Attach document');
    expect(attach).toBeDefined();
    attach?.click();
    fixture.detectChanges();

    expect(open).toHaveBeenCalledOnce();
    const options = open.mock.calls[0][1] as {
      data: { action: { path: string; fields: { key: string; type: string }[] } };
    };
    expect(options.data.action.path).toBe('attach');
    expect(options.data.action.fields).toEqual(
      expect.arrayContaining([expect.objectContaining({ key: 'file', type: 'file' })]),
    );
  });

  it('shows the server error and keeps the failed load retryable', async () => {
    const fixture = await configure('inventory');
    fixture.detectChanges();
    http
      .expectOne(`/api/v1/stock-balances/${PAGE}`)
      .flush(
        { error: { code: 'conflict', message: 'Valuation is not configured.', details: null } },
        { status: 409, statusText: 'Conflict' },
      );
    fixture.detectChanges();

    expect(text(fixture)).toContain('Valuation is not configured.');
    expect(text(fixture)).toContain('Retry');
  });
});
