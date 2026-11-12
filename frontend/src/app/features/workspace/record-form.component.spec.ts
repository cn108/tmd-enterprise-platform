import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialog, MatDialogRef } from '@angular/material/dialog';
import { FormArray, FormControl, FormGroup } from '@angular/forms';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MODULES } from './workspace-config';
import { RecordFormComponent } from './record-form.component';

const SUPPLIER_RESOURCE = MODULES['master-data'].tabs[0];

interface FormInternals {
  form: FormGroup;
  lines: FormArray;
  submit(): void;
}

describe('RecordFormComponent', () => {
  let http: HttpTestingController;
  let close: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    close = vi.fn();
    await TestBed.configureTestingModule({
      imports: [RecordFormComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: MAT_DIALOG_DATA, useValue: { resource: SUPPLIER_RESOURCE } },
        { provide: MatDialogRef, useValue: { close } },
        { provide: MatDialog, useValue: { open: vi.fn() } },
      ],
    }).compileComponents();
  });

  function createForm() {
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(RecordFormComponent);
    fixture.detectChanges();
    http.expectOne('/api/v1/supplier-categories/?page_size=100').flush([
      { id: 3, code: 'CAT-1', name: 'Packaging' },
    ]);
    fixture.detectChanges();
    return {
      fixture,
      internals: fixture.componentInstance as unknown as FormInternals,
    };
  }

  function fill(internals: FormInternals, values: Record<string, unknown>): void {
    for (const [key, value] of Object.entries(values)) {
      (internals.form.get(key) as FormControl).setValue(value);
    }
  }

  it('refuses to submit while required fields are empty', () => {
    const { internals } = createForm();

    internals.submit();

    http.expectNone('/api/v1/suppliers/');
    expect(close).not.toHaveBeenCalled();
  });

  it('creates the record through the API and closes with the saved row', () => {
    const { internals } = createForm();
    fill(internals, {
      code: 'SUP-900',
      legal_name: 'Acme Limited',
      supplier_category: 3,
      is_active: true,
    });

    internals.submit();

    const request = http.expectOne('/api/v1/suppliers/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toMatchObject({
      code: 'SUP-900',
      legal_name: 'Acme Limited',
      supplier_category: 3,
      is_active: true,
    });

    const saved = { id: 12, code: 'SUP-900', legal_name: 'Acme Limited' };
    request.flush(saved);
    expect(close).toHaveBeenCalledWith(saved);
  });

  it('shows the backend field error beside the control and stays open', () => {
    const { fixture, internals } = createForm();
    fill(internals, { code: 'SUP-900', legal_name: 'Acme Limited' });

    internals.submit();
    http.expectOne('/api/v1/suppliers/').flush(
      {
        error: {
          code: 'invalid_request',
          message: 'One or more fields are invalid.',
          details: { code: ['A party with this code already exists.'] },
          request_id: 'req-9',
        },
      },
      { status: 400, statusText: 'Bad Request' },
    );
    fixture.detectChanges();

    expect(close).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'A party with this code already exists.',
    );
  });

  it('sends a write-off style rejection reason only when the action requires one', () => {
    // Guard rail: the form's payload must never invent a workflow field that the
    // create serializer does not accept.
    const { internals } = createForm();
    fill(internals, { code: 'SUP-901', legal_name: 'Beta Supplies' });
    internals.submit();

    const request = http.expectOne('/api/v1/suppliers/');
    expect(Object.keys(request.request.body as object)).not.toContain('reason');
    request.flush({ id: 13, code: 'SUP-901' });
  });

  it('registers line controls and posts them with the parent record', () => {
    TestBed.overrideProvider(MAT_DIALOG_DATA, {
      useValue: { resource: MODULES['invoicing'].tabs[0] },
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(RecordFormComponent);
    fixture.detectChanges();
    for (const endpoint of [
      '/api/v1/suppliers/?page_size=100',
      '/api/v1/purchase-orders/?page_size=100',
      '/api/v1/purchase-order-lines/?page_size=100',
      '/api/v1/goods-receipt-lines/?page_size=100',
      '/api/v1/catalogue-items/?page_size=100',
      '/api/v1/governance/tax-configuration/?page_size=100',
    ]) {
      http.expectOne(endpoint).flush([]);
    }
    fixture.detectChanges();
    const internals = fixture.componentInstance as unknown as FormInternals;

    expect(internals.form.get('lines')).toBe(internals.lines);
    fill(internals, {
      supplier: 7,
      supplier_invoice_number: 'SUP-LINES-1',
      invoice_date: '2026-11-12',
      currency: 'NGN',
    });
    internals.lines.at(0).patchValue({
      description: 'Service',
      quantity: 1,
      unit_price: 100,
      tax_treatment: 'taxable',
      vat_recoverable: true,
    });

    internals.submit();

    const request = http.expectOne('/api/v1/supplier-invoices/');
    expect((request.request.body as { lines: unknown[] }).lines).toHaveLength(1);
    request.flush({ id: 99, number: 'SI-2026-0099' });
  });
});
