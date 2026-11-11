import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Observable, forkJoin, map } from 'rxjs';

import { apiErrorMessage } from '../../core/auth.models';

type Row = Record<string, unknown>;

interface Column {
  key: string;
  label: string;
}

interface Tab {
  id: string;
  label: string;
  endpoint: string;
  columns: Column[];
}

interface ModuleConfig {
  title: string;
  intro: string;
  tabs: Tab[];
}

type ModuleKey = 'master-data' | 'procurement' | 'inventory' | 'accounting';

const MODULES: Record<ModuleKey, ModuleConfig> = {
  'master-data': {
    title: 'Master data',
    intro:
      'Suppliers, customers, catalogue items, warehouses and projects. These records feed every procurement, stock and accounting transaction.',
    tabs: [
      {
        id: 'suppliers',
        label: 'Suppliers',
        endpoint: '/api/v1/suppliers/',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'legal_name', label: 'Supplier' },
          { key: 'is_active', label: 'Active' },
        ],
      },
      {
        id: 'customers',
        label: 'Customers',
        endpoint: '/api/v1/customers/',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'legal_name', label: 'Customer' },
          { key: 'is_active', label: 'Active' },
        ],
      },
      {
        id: 'catalogue',
        label: 'Catalogue',
        endpoint: '/api/v1/catalogue-items/',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Item' },
          { key: 'kind', label: 'Kind' },
        ],
      },
      {
        id: 'warehouses',
        label: 'Warehouses',
        endpoint: '/api/v1/warehouses/',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Warehouse' },
          { key: 'site_name', label: 'Site' },
        ],
      },
      {
        id: 'projects',
        label: 'Projects',
        endpoint: '/api/v1/projects/',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Project' },
          { key: 'status', label: 'Status' },
        ],
      },
    ],
  },
  procurement: {
    title: 'Procurement',
    intro:
      'The purchase lifecycle from request to receipt, including quotations, approvals, split destinations and partial deliveries.',
    tabs: [
      {
        id: 'requests',
        label: 'Purchase requests',
        endpoint: '/api/v1/purchase-requests/',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'status', label: 'Status' },
          { key: 'requester', label: 'Requester' },
          { key: 'required_by', label: 'Required by' },
        ],
      },
      {
        id: 'orders',
        label: 'Purchase orders',
        endpoint: '/api/v1/purchase-orders/',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'status', label: 'Status' },
          { key: 'supplier', label: 'Supplier' },
          { key: 'total_value', label: 'Total' },
        ],
      },
      {
        id: 'receipts',
        label: 'Goods receipts',
        endpoint: '/api/v1/goods-receipts/',
        columns: [
          { key: 'number', label: 'GRN' },
          { key: 'order', label: 'Order' },
          { key: 'received_at', label: 'Received' },
          { key: 'received_by', label: 'Received by' },
        ],
      },
    ],
  },
  inventory: {
    title: 'Inventory',
    intro:
      'The permanent stock ledger. Balances are derived from recorded movements, never typed over.',
    tabs: [
      {
        id: 'balances',
        label: 'Balances',
        endpoint: '/api/v1/stock-balances/',
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'on_hand', label: 'On hand' },
          { key: 'reserved', label: 'Reserved' },
          { key: 'available', label: 'Available' },
          { key: 'value', label: 'Value (NGN)' },
        ],
      },
      {
        id: 'movements',
        label: 'Movements',
        endpoint: '/api/v1/stock-movements/',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'movement_type', label: 'Type' },
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'reference', label: 'Reference' },
        ],
      },
      {
        id: 'alerts',
        label: 'Reorder alerts',
        endpoint: '/api/v1/reorder-alerts/',
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'minimum_quantity', label: 'Minimum' },
          { key: 'on_hand', label: 'On hand' },
          { key: 'shortfall', label: 'Shortfall' },
        ],
      },
    ],
  },
  accounting: {
    title: 'Accounting',
    intro:
      'The double-entry engine: chart of accounts, journals and the approved posting rules that turn business events into balanced entries.',
    tabs: [
      {
        id: 'accounts',
        label: 'Chart of accounts',
        endpoint: '/api/v1/accounts/',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Account' },
          { key: 'account_type', label: 'Type' },
          { key: 'is_approved', label: 'Approved' },
        ],
      },
      {
        id: 'journals',
        label: 'Journals',
        endpoint: '/api/v1/journals/',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'journal_date', label: 'Date' },
          { key: 'description', label: 'Description' },
          { key: 'status', label: 'Status' },
          { key: 'total_debit', label: 'Debit' },
          { key: 'total_credit', label: 'Credit' },
        ],
      },
      {
        id: 'rules',
        label: 'Posting rules',
        endpoint: '/api/v1/posting-rules/',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Rule' },
          { key: 'is_active', label: 'Active' },
          { key: 'approved_at', label: 'Approved' },
        ],
      },
    ],
  },
};

function isRow(value: unknown): value is Row {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalize(body: unknown): Row[] {
  if (Array.isArray(body)) {
    return body.filter(isRow);
  }
  if (isRow(body) && Array.isArray(body['rows'])) {
    return body['rows'].filter(isRow);
  }
  return [];
}

@Component({
  selector: 'app-workspace',
  templateUrl: './workspace.component.html',
  styleUrl: './workspace.scss',
})
export class WorkspaceComponent {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);

  private readonly key = this.route.snapshot.data['module'] as ModuleKey;
  protected readonly config = MODULES[this.key];
  protected readonly activeTab = signal(this.config.tabs[0].id);
  protected readonly records = signal<Record<string, Row[]>>({});
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly activeConfig = computed(() =>
    this.config.tabs.find((tab) => tab.id === this.activeTab()),
  );
  protected readonly activeRows = computed(() => this.records()[this.activeTab()] ?? []);

  constructor() {
    this.load();
  }

  protected reload(): void {
    this.load();
  }

  protected format(value: unknown): string {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (typeof value === 'string' || typeof value === 'number') {
      return String(value);
    }
    return '—';
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    const requests: Record<string, Observable<Row[]>> = {};
    for (const tab of this.config.tabs) {
      requests[tab.id] = this.http
        .get<unknown>(tab.endpoint)
        .pipe(map((body) => normalize(body)));
    }
    forkJoin(requests).subscribe({
      next: (records) => {
        this.records.set(records);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(apiErrorMessage(error));
        this.loading.set(false);
      },
    });
  }
}
