import {
  ColumnConfig,
  FieldConfig,
  MODULES,
  ResourceConfig,
  SelectOption,
} from '../workspace/workspace-config';

export type EntityKey = 'suppliers' | 'customers' | 'products' | 'tax-rates';

export interface MasterColumn extends ColumnConfig {
  sortable?: boolean;
  /** Server field used for `?sort=`; defaults to the column key. */
  sortKey?: string;
}

export interface EntityFilter {
  key: string;
  label: string;
  options: SelectOption[];
}

export interface MasterEntity {
  key: EntityKey;
  label: string;
  title: string;
  singular: string;
  endpoint: string;
  resource: ResourceConfig;
  columns: MasterColumn[];
  detail: ColumnConfig[];
  fields: FieldConfig[];
  filters: EntityFilter[];
  grid: string;
  canDeactivate: boolean;
  createPermission?: string;
  editPermission?: string;
}

const MASTER = MODULES['master-data'];
const supplier = MASTER.tabs.find((tab) => tab.id === 'suppliers')!;
const customer = MASTER.tabs.find((tab) => tab.id === 'customers')!;
const catalogue = MASTER.tabs.find((tab) => tab.id === 'catalogue')!;

const ACTIVE_FILTER: EntityFilter = {
  key: 'is_active',
  label: 'Status',
  options: [
    { value: 'true', label: 'Active' },
    { value: 'false', label: 'Inactive' },
  ],
};

const TAX_TYPE: SelectOption[] = [
  { value: 'vat', label: 'VAT' },
  { value: 'wht', label: 'Withholding tax' },
  { value: 'other', label: 'Other' },
];

const TAX_FIELDS: FieldConfig[] = [
  { key: 'code', label: 'Code', type: 'text', required: true, help: 'Unique rate code, e.g. VAT-7.5.' },
  { key: 'name', label: 'Name', type: 'text', required: true },
  {
    key: 'tax_type',
    label: 'Tax type',
    type: 'select',
    required: true,
    options: TAX_TYPE,
    defaultValue: 'vat',
  },
  {
    key: 'rate',
    label: 'Rate (%)',
    type: 'number',
    required: true,
    min: 0,
    step: '0.0001',
    help: 'A rate is effective-dated and reviewed by a second person.',
  },
  { key: 'jurisdiction', label: 'Jurisdiction', type: 'text', defaultValue: 'Nigeria' },
  { key: 'registration_number', label: 'Registration number', type: 'text' },
  { key: 'effective_from', label: 'Effective from', type: 'date', required: true },
  { key: 'effective_to', label: 'Effective to', type: 'date' },
  { key: 'notes', label: 'Notes', type: 'textarea' },
];

const TAX_RESOURCE: ResourceConfig = {
  id: 'tax-rates',
  label: 'Tax rates',
  singular: 'tax rate',
  endpoint: '/api/v1/governance/tax-configuration/',
  serverSearch: true,
  create: true,
  edit: true,
  permission: 'core.add_taxconfiguration',
  editPermission: 'core.change_taxconfiguration',
  columns: [],
  detail: [],
  fields: TAX_FIELDS,
  note: 'Reviewed tax configurations are superseded by a new effective-dated rate, not edited.',
};

const SUPPLIER_COLUMNS: MasterColumn[] = [
  { key: 'id', label: 'ID', sortable: true },
  { key: 'legal_name', label: 'Name', sortable: true, sortKey: 'legal_name' },
  { key: 'tin', label: 'TIN' },
  { key: 'region', label: 'Region' },
  { key: 'is_active', label: 'Status', kind: 'status', sortable: true },
  { key: 'updated_at', label: 'Last updated', kind: 'date', sortable: true },
];

const CUSTOMER_COLUMNS: MasterColumn[] = [
  { key: 'id', label: 'ID', sortable: true },
  { key: 'legal_name', label: 'Name', sortable: true, sortKey: 'legal_name' },
  { key: 'email', label: 'Email' },
  { key: 'region', label: 'Region' },
  { key: 'is_active', label: 'Status', kind: 'status', sortable: true },
  { key: 'updated_at', label: 'Last updated', kind: 'date', sortable: true },
];

const PRODUCT_COLUMNS: MasterColumn[] = [
  { key: 'id', label: 'ID', sortable: true },
  { key: 'name', label: 'Name', sortable: true },
  { key: 'kind', label: 'Kind', kind: 'status', sortable: true },
  { key: 'brand', label: 'Brand' },
  { key: 'is_active', label: 'Status', kind: 'status', sortable: true },
  { key: 'updated_at', label: 'Last updated', kind: 'date', sortable: true },
];

const TAX_COLUMNS: MasterColumn[] = [
  { key: 'id', label: 'ID', sortable: true },
  { key: 'code', label: 'Code', sortable: true },
  { key: 'name', label: 'Name', sortable: true },
  { key: 'tax_type', label: 'Type', kind: 'status', sortable: true },
  { key: 'rate', label: 'Rate', kind: 'number', sortable: true },
  { key: 'jurisdiction', label: 'Jurisdiction', sortable: true },
  { key: 'review_status', label: 'Review', kind: 'status', sortable: true },
  { key: 'updated_at', label: 'Last updated', kind: 'date', sortable: true },
];

export const MASTER_ENTITIES: Record<EntityKey, MasterEntity> = {
  suppliers: {
    key: 'suppliers',
    label: 'Suppliers',
    title: 'Supplier Registry',
    singular: 'supplier',
    endpoint: supplier.endpoint,
    resource: supplier,
    columns: SUPPLIER_COLUMNS,
    detail: [
      ...supplier.detail.slice(0, 1),
      { key: 'tin', label: 'TIN' },
      { key: 'region', label: 'Region' },
      ...supplier.detail.slice(1),
    ],
    fields: supplier.fields ?? [],
    filters: [ACTIVE_FILTER],
    grid: '2.75rem 5rem minmax(13rem,1.6fr) 8rem 7rem 7rem 8.5rem 4.75rem',
    canDeactivate: true,
  },
  customers: {
    key: 'customers',
    label: 'Customers',
    title: 'Customer Directory',
    singular: 'customer',
    endpoint: customer.endpoint,
    resource: customer,
    columns: CUSTOMER_COLUMNS,
    detail: [
      ...customer.detail.slice(0, 1),
      { key: 'region', label: 'Region' },
      ...customer.detail.slice(1),
    ],
    fields: customer.fields ?? [],
    filters: [
      ACTIVE_FILTER,
      {
        key: 'credit_hold',
        label: 'Credit hold',
        options: [
          { value: 'true', label: 'On hold' },
          { value: 'false', label: 'Not on hold' },
        ],
      },
    ],
    grid: '2.75rem 5rem minmax(13rem,1.6fr) 10rem 8rem 7rem 8.5rem 4.75rem',
    canDeactivate: true,
  },
  products: {
    key: 'products',
    label: 'Products',
    title: 'Product Catalogue',
    singular: 'product',
    endpoint: catalogue.endpoint,
    resource: { ...catalogue, label: 'Products', singular: 'product' },
    columns: PRODUCT_COLUMNS,
    detail: catalogue.detail,
    fields: catalogue.fields ?? [],
    filters: [
      ACTIVE_FILTER,
      {
        key: 'kind',
        label: 'Kind',
        options: [
          { value: 'product', label: 'Products' },
          { value: 'service', label: 'Services' },
        ],
      },
    ],
    grid: '2.75rem 5rem minmax(14rem,1.6fr) 7rem 8rem 7rem 8.5rem 4.75rem',
    canDeactivate: true,
  },
  'tax-rates': {
    key: 'tax-rates',
    label: 'Tax Rates',
    title: 'Tax Rate Register',
    singular: 'tax rate',
    endpoint: TAX_RESOURCE.endpoint,
    resource: TAX_RESOURCE,
    columns: TAX_COLUMNS,
    detail: [
      { key: 'code', label: 'Code' },
      { key: 'name', label: 'Name' },
      { key: 'tax_type', label: 'Tax type' },
      { key: 'rate', label: 'Rate (%)' },
      { key: 'jurisdiction', label: 'Jurisdiction' },
      { key: 'registration_number', label: 'Registration number' },
      { key: 'effective_from', label: 'Effective from' },
      { key: 'effective_to', label: 'Effective to' },
      { key: 'review_status', label: 'Review status', kind: 'status' },
      { key: 'notes', label: 'Notes' },
    ],
    fields: TAX_FIELDS,
    filters: [
      {
        key: 'review_status',
        label: 'Review',
        options: [
          { value: 'provisional', label: 'Provisional' },
          { value: 'reviewed', label: 'Reviewed' },
          { value: 'rejected', label: 'Rejected' },
        ],
      },
    ],
    grid:
      '2.75rem 4.5rem 6.5rem minmax(13rem,1.4fr) 5.5rem 6rem 8rem 8rem 8.5rem 4.75rem',
    canDeactivate: false,
    createPermission: 'core.add_taxconfiguration',
    editPermission: 'core.change_taxconfiguration',
  },
};

export const ENTITY_ORDER: EntityKey[] = ['suppliers', 'customers', 'products', 'tax-rates'];