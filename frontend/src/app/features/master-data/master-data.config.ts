import {
  ColumnConfig,
  FieldConfig,
  MODULES,
  ResourceConfig,
  SelectOption,
} from '../workspace/workspace-config';

export const ENTITY_ORDER = [
  'suppliers',
  'customers',
  'products',
  'tax-rates',
  'warehouses',
  'projects',
  'supplier-categories',
  'contacts',
  'addresses',
  'tax-registrations',
  'supplier-bank',
  'bank-changes',
  'compliance',
  'document-categories',
  'documents',
  'product-categories',
  'units',
  'manufacturers',
  'prices',
  'specifications',
  'batches',
  'serials',
  'certificates',
  'storage-locations',
  'departments',
  'cost-centres',
  'destinations',
  'project-locations',
  'contracts',
  'contract-revisions',
  'budgets',
  'milestones',
] as const;

export type EntityKey = (typeof ENTITY_ORDER)[number];

export interface MasterColumn extends ColumnConfig {
  sortable?: boolean;
  /** Server field used for `?sort=`; defaults to the column key. */
  sortKey?: string;
  /** Pinned identity column immediately after the checkbox/ID. */
  primary?: boolean;
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

const SORTABLE = new Set([
  'id',
  'code',
  'name',
  'legal_name',
  'title',
  'status',
  'kind',
  'amount',
  'value',
  'credit_limit',
  'retention_months',
  'conversion_factor',
  'total_value',
  'revision_number',
  'version',
  'start_date',
  'end_date',
  'due_date',
  'expires_on',
  'issue_date',
  'issued_on',
  'created_at',
  'updated_at',
  'reference',
  'certificate_type',
  'batch_number',
  'serial',
  'is_active',
]);

const PRIMARY_KEYS = [
  'legal_name',
  'name',
  'title',
  'reference',
  'certificate_type',
  'batch_number',
  'serial',
  'line1',
  'code',
];

const WIDTHS: Record<NonNullable<ColumnConfig['kind']> | 'text', string> = {
  text: '9rem',
  number: '7rem',
  boolean: '7rem',
  date: '8.5rem',
  status: '8rem',
};

function column(source: ColumnConfig, primary = false): MasterColumn {
  return {
    ...source,
    sortable: SORTABLE.has(source.key),
    primary,
  };
}

function columnsFor(source: ColumnConfig[]): MasterColumn[] {
  const id = source.find((item) => item.key === 'id');
  const withoutId = source.filter((item) => item.key !== 'id');
  const primaryIndex = PRIMARY_KEYS.map((key) =>
    withoutId.findIndex((item) => item.key === key),
  ).find((index) => index >= 0) ?? 0;
  const primary = withoutId.splice(primaryIndex, 1)[0];
  return [
    column(id ?? { key: 'id', label: 'ID' }),
    ...(primary ? [column(primary, true)] : []),
    ...withoutId.map((item) => column(item)),
  ];
}

function gridFor(columns: MasterColumn[]): string {
  const widths = columns.map((item, index) => {
    if (index === 0) {
      return '5rem';
    }
    if (item.primary) {
      return 'minmax(13rem,1.6fr)';
    }
    return WIDTHS[item.kind ?? 'text'];
  });
  return `2.75rem ${widths.join(' ')} 4.75rem`;
}

function titleCase(label: string): string {
  const small = new Set(['of', 'and', 'for']);
  return label.replace(/\w+/g, (word, index: number) =>
    index > 0 && small.has(word.toLowerCase())
      ? word.toLowerCase()
      : word.charAt(0).toUpperCase() + word.slice(1),
  );
}

const PROJECT_STATUS: SelectOption[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'on_hold', label: 'On hold' },
  { value: 'closed', label: 'Closed' },
];

const BANK_CHANGE_STATUS: SelectOption[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

const BUDGET_STATUS: SelectOption[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
];

const STATUS_FILTERS: Partial<Record<EntityKey, SelectOption[]>> = {
  projects: PROJECT_STATUS,
  'bank-changes': BANK_CHANGE_STATUS,
  budgets: BUDGET_STATUS,
};

const PRIMARY_ENTITIES: Partial<Record<EntityKey, MasterEntity>> = {
  suppliers: {
    key: 'suppliers',
    label: 'Suppliers',
    title: 'Supplier Registry',
    singular: 'supplier',
    endpoint: supplier.endpoint,
    resource: supplier,
    columns: columnsFor([
      { key: 'id', label: 'ID' },
      { key: 'legal_name', label: 'Name' },
      { key: 'tin', label: 'TIN' },
      { key: 'region', label: 'Region' },
      { key: 'is_active', label: 'Status', kind: 'status' },
      { key: 'updated_at', label: 'Last updated', kind: 'date' },
    ]),
    detail: [
      ...supplier.detail.slice(0, 1),
      { key: 'tin', label: 'TIN' },
      { key: 'region', label: 'Region' },
      ...supplier.detail.slice(1),
    ],
    fields: supplier.fields ?? [],
    filters: [ACTIVE_FILTER],
    grid: '',
    canDeactivate: true,
  },
  customers: {
    key: 'customers',
    label: 'Customers',
    title: 'Customer Directory',
    singular: 'customer',
    endpoint: customer.endpoint,
    resource: customer,
    columns: columnsFor([
      { key: 'id', label: 'ID' },
      { key: 'legal_name', label: 'Name' },
      { key: 'email', label: 'Email' },
      { key: 'region', label: 'Region' },
      { key: 'is_active', label: 'Status', kind: 'status' },
      { key: 'updated_at', label: 'Last updated', kind: 'date' },
    ]),
    detail: [
      ...customer.detail.slice(0, 1),
      { key: 'region', label: 'Region' },
      ...customer.detail.slice(1),
    ],
    fields: customer.fields ?? [],
    filters: [
      {
        key: 'credit_hold',
        label: 'Credit hold',
        options: [
          { value: 'true', label: 'On hold' },
          { value: 'false', label: 'Not on hold' },
        ],
      },
      ACTIVE_FILTER,
    ],
    grid: '',
    canDeactivate: true,
  },
  products: {
    key: 'products',
    label: 'Products',
    title: 'Product Catalogue',
    singular: 'product',
    endpoint: catalogue.endpoint,
    resource: { ...catalogue, label: 'Products', singular: 'product' },
    columns: columnsFor([
      { key: 'id', label: 'ID' },
      { key: 'name', label: 'Name' },
      { key: 'kind', label: 'Kind', kind: 'status' },
      { key: 'brand', label: 'Brand' },
      { key: 'is_active', label: 'Status', kind: 'status' },
      { key: 'updated_at', label: 'Last updated', kind: 'date' },
    ]),
    detail: catalogue.detail,
    fields: catalogue.fields ?? [],
    filters: [
      {
        key: 'kind',
        label: 'Kind',
        options: [
          { value: 'product', label: 'Products' },
          { value: 'service', label: 'Services' },
        ],
      },
      ACTIVE_FILTER,
    ],
    grid: '',
    canDeactivate: true,
  },
  'tax-rates': {
    key: 'tax-rates',
    label: 'Tax Rates',
    title: 'Tax Rate Register',
    singular: 'tax rate',
    endpoint: TAX_RESOURCE.endpoint,
    resource: TAX_RESOURCE,
    columns: columnsFor([
      { key: 'id', label: 'ID' },
      { key: 'code', label: 'Code' },
      { key: 'name', label: 'Name' },
      { key: 'tax_type', label: 'Type', kind: 'status' },
      { key: 'rate', label: 'Rate', kind: 'number' },
      { key: 'jurisdiction', label: 'Jurisdiction' },
      { key: 'review_status', label: 'Review', kind: 'status' },
      { key: 'updated_at', label: 'Last updated', kind: 'date' },
    ]),
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
    grid: '',
    canDeactivate: false,
    createPermission: 'core.add_taxconfiguration',
    editPermission: 'core.change_taxconfiguration',
  },
};

const GENERIC_RESOURCES: [EntityKey, string][] = [
  ['warehouses', 'warehouses'],
  ['projects', 'projects'],
  ['supplier-categories', 'supplier-categories'],
  ['contacts', 'contacts'],
  ['addresses', 'addresses'],
  ['tax-registrations', 'tax-registrations'],
  ['supplier-bank', 'supplier-bank'],
  ['bank-changes', 'bank-changes'],
  ['compliance', 'compliance'],
  ['document-categories', 'document-categories'],
  ['documents', 'documents'],
  ['product-categories', 'product-categories'],
  ['units', 'units'],
  ['manufacturers', 'manufacturers'],
  ['prices', 'prices'],
  ['specifications', 'specifications'],
  ['batches', 'batches'],
  ['serials', 'serials'],
  ['certificates', 'certificates'],
  ['storage-locations', 'storage-locations'],
  ['departments', 'departments'],
  ['cost-centres', 'cost-centres'],
  ['destinations', 'destinations'],
  ['project-locations', 'project-locations'],
  ['contracts', 'contracts'],
  ['contract-revisions', 'contract-revisions'],
  ['budgets', 'budgets'],
  ['milestones', 'milestones'],
];

function genericEntity(key: EntityKey, resourceId: string): MasterEntity {
  const resource = MASTER.tabs.find((tab) => tab.id === resourceId);
  if (!resource) {
    throw new Error(`Unknown master-data resource: ${resourceId}`);
  }
  const columns = columnsFor(resource.columns);
  const filters: EntityFilter[] = [];
  if (resource.deactivate) {
    filters.push(ACTIVE_FILTER);
  }
  const status = STATUS_FILTERS[key];
  if (status) {
    filters.push({ key: 'status', label: 'Status', options: status });
  }
  return {
    key,
    label: resource.label,
    title: titleCase(resource.label),
    singular: resource.singular,
    endpoint: resource.endpoint,
    resource,
    columns,
    detail: resource.detail,
    fields: resource.fields ?? [],
    filters,
    grid: '',
    canDeactivate: resource.deactivate === true,
  };
}

const GENERIC_ENTITIES = Object.fromEntries(
  GENERIC_RESOURCES.map(([key, resourceId]) => [key, genericEntity(key, resourceId)]),
) as Record<EntityKey, MasterEntity>;

export const MASTER_ENTITIES: Record<EntityKey, MasterEntity> = Object.fromEntries(
  ENTITY_ORDER.map((key) => [
    key,
    PRIMARY_ENTITIES[key] ?? GENERIC_ENTITIES[key],
  ]),
) as Record<EntityKey, MasterEntity>;

for (const entity of Object.values(MASTER_ENTITIES)) {
  entity.grid = gridFor(entity.columns);
}
