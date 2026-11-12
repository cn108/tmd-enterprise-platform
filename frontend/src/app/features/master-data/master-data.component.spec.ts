import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthService } from '../../core/auth.service';
import { TEST_USER } from '../../core/testing/auth.fixtures';
import { MasterDataComponent } from './master-data.component';

interface Internals {
  rows(): Record<string, unknown>[];
  count(): number;
  panelOpen(): boolean;
  panelMode(): string;
  onSearch(value: string): void;
  onPageSize(event: Event): void;
  sortBy(column: { key: string; label: string; sortable?: boolean; sortKey?: string }): void;
  openCreate(event?: Event): void;
  openView(row: Record<string, unknown>, event?: Event): void;
  toggleRow(row: Record<string, unknown>, event: Event): void;
  selectedCount(): number;
}

function internals(fixture: ComponentFixture<MasterDataComponent>): Internals {
  return fixture.componentInstance as unknown as Internals;
}

describe('MasterDataComponent', () => {
  let http: HttpTestingController;

  async function configure(permissions: string[] = [], entity = 'suppliers') {
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [MasterDataComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { data: { entity } } },
        },
        {
          provide: AuthService,
          useValue: { user: signal({ ...TEST_USER, permissions }).asReadonly() },
        },
        { provide: MatDialog, useValue: { open: vi.fn() } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    return TestBed.createComponent(MasterDataComponent);
  }

  afterEach(() => http?.verify());

  function expectList() {
    const request = http.expectOne((item) => item.url === '/api/v1/suppliers/');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('page')).toBe('1');
    expect(request.request.params.get('pageSize')).toBe('25');
    expect(request.request.params.get('sort')).toBe('updated_at');
    expect(request.request.params.get('order')).toBe('desc');
    return request;
  }

  it('loads supplier rows through the documented pageSize/sort contract', async () => {
    const fixture = await configure();
    fixture.detectChanges();

    expectList().flush({
      count: 1,
      results: [
        {
          id: 7,
          code: 'SUP-007',
          legal_name: 'Acme Limited',
          tin: 'TIN-123',
          region: 'Lagos',
          is_active: true,
          updated_at: '2026-11-12T10:00:00Z',
        },
      ],
    });
    fixture.detectChanges();

    expect(internals(fixture).rows()).toHaveLength(1);
    expect(internals(fixture).rows()[0]['legal_name']).toBe('Acme Limited');
    expect(internals(fixture).count()).toBe(1);
  });

  it('debounces search and keeps pagination server-side', async () => {
    const fixture = await configure();
    fixture.detectChanges();
    expectList().flush({ count: 0, results: [] });

    internals(fixture).onSearch('acme');
    await new Promise((resolve) => setTimeout(resolve, 350));
    fixture.detectChanges();

    const request = http.expectOne(
      (item) => item.url === '/api/v1/suppliers/' && item.params.get('search') === 'acme',
    );
    expect(request.request.params.get('page')).toBe('1');
    request.flush({ count: 0, results: [] });
  });

  it('changes page size and sort on the server', async () => {
    const fixture = await configure();
    fixture.detectChanges();
    expectList().flush({ count: 0, results: [] });

    const event = { target: { value: '50' } } as unknown as Event;
    internals(fixture).onPageSize(event);
    const sized = http.expectOne((item) => item.params.get('pageSize') === '50');
    sized.flush({ count: 0, results: [] });

    internals(fixture).sortBy({ key: 'legal_name', label: 'Name', sortable: true });
    const sorted = http.expectOne(
      (item) => item.params.get('sort') === 'legal_name' && item.params.get('order') === 'asc',
    );
    sorted.flush({ count: 0, results: [] });
  });

  it('opens the create panel with validated supplier fields', async () => {
    const fixture = await configure();
    fixture.detectChanges();
    expectList().flush({ count: 0, results: [] });
    fixture.detectChanges();

    internals(fixture).openCreate();
    fixture.detectChanges();

    http.expectOne((item) => item.url === '/api/v1/supplier-categories/').flush({
      count: 0,
      results: [],
    });

    expect(internals(fixture).panelOpen()).toBe(true);
    expect(internals(fixture).panelMode()).toBe('create');
    const panel = fixture.nativeElement.querySelector('.md-panel') as HTMLElement;
    expect(panel.textContent).toContain('New supplier');
    expect(panel.querySelector('#md-field-code')).not.toBeNull();
  });

  it('tracks selected rows for bulk actions', async () => {
    const fixture = await configure();
    fixture.detectChanges();
    expectList().flush({ count: 1, results: [{ id: 7, code: 'SUP-007', legal_name: 'Acme' }] });
    fixture.detectChanges();

    internals(fixture).toggleRow({ id: 7 }, { stopPropagation: vi.fn() } as unknown as Event);
    expect(internals(fixture).selectedCount()).toBe(1);
  });

  it('renders the empty state when the filtered register has no records', async () => {
    const fixture = await configure();
    fixture.detectChanges();
    expectList().flush({ count: 0, results: [] });
    fixture.detectChanges();

    const empty = fixture.nativeElement.querySelector('.md-empty') as HTMLElement;
    expect(empty.textContent).toContain('No suppliers found');
    expect(empty.textContent).toContain('Add first supplier');
  });

  it('renders a retryable error banner when the list request fails', async () => {
    const fixture = await configure();
    fixture.detectChanges();
    expectList().flush(
      { error: { code: 'server_error', message: 'Register unavailable.', details: null } },
      { status: 500, statusText: 'Server Error' },
    );
    fixture.detectChanges();

    const error = fixture.nativeElement.querySelector('.md-error') as HTMLElement;
    expect(error.textContent).toContain('Register unavailable.');
    expect(error.textContent).toContain('Retry');
  });

  it('offers bank-change decisions only for pending records', async () => {
    const fixture = await configure(['parties.approve_bankaccountchange'], 'bank-changes');
    fixture.detectChanges();
    http
      .expectOne((item) => item.url === '/api/v1/bank-account-change-requests/')
      .flush({
        count: 1,
        results: [
          {
            id: 5,
            supplier_code: 'SUP-001',
            proposed_bank_name: 'Example Bank',
            status: 'pending',
          },
        ],
      });
    fixture.detectChanges();

    internals(fixture).openView({ id: 5, status: 'pending' });
    http
      .expectOne((item) => item.url === '/api/v1/bank-account-change-requests/5/')
      .flush({ id: 5, supplier_code: 'SUP-001', proposed_bank_name: 'Example Bank', status: 'pending' });
    fixture.detectChanges();

    const panel = fixture.nativeElement.querySelector('.md-panel') as HTMLElement;
    expect(panel.textContent).toContain('Approve change');
    expect(panel.textContent).toContain('Reject change');
  });
});