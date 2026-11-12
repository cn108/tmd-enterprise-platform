/**
 * Declarative description of every portal section.
 *
 * The API is the source of truth: each tab names a real endpoint, its real
 * fields and the permission its backend action checks. Nothing here invents a
 * business rule. `permission` is omitted only where the backend itself requires
 * nothing more than an authenticated session (master-data writes, submissions).
 */

import { BANKING_MODULE } from './banking-config';
import { INVOICING_MODULE } from './invoicing-config';
import { LEASING_MODULE } from './leasing-config';
import { PROJECTS_MODULE } from './projects-config';
import { SERVICES_MODULE } from './services-config';

export type Row = Record<string, unknown>;

export interface ColumnConfig {
  key: string;
  label: string;
  kind?: 'text' | 'number' | 'boolean' | 'date' | 'status';
}

export type FieldType = 'text' | 'textarea' | 'number' | 'checkbox' | 'date' | 'select' | 'file';

export interface SelectOption {
  value: string | number;
  label: string;
}

export interface FieldConfig {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  help?: string;
  /** Static choices, used for backend `TextChoices`. */
  options?: SelectOption[];
  /** Load choices from a list endpoint that returns coded records. */
  optionsEndpoint?: string;
  /** Extra server filter applied when loading choices (e.g. approved only). */
  optionsQuery?: Record<string, string>;
  /** Read-only once the record exists (set by the workflow, not typed). */
  readOnlyOnEdit?: boolean;
  min?: number;
  step?: string;
  defaultValue?: string | number | boolean | null;
}

export interface LineConfig {
  label: string;
  addLabel: string;
  fields: FieldConfig[];
  /** Blank rows to start with; zero lets an action supply its own lines. */
  minLines?: number;
}

export interface ActionConfig {
  id: string;
  label: string;
  /** Appended to `{endpoint}{id}/`, e.g. `submit`. */
  path: string;
  /** Backend permission; omitted where any signed-in user may act. */
  permission?: string;
  confirm: string;
  success: string;
  /** Only offered for these record states. */
  statuses?: string[];
  /** Extra body field the backend needs (for example a rejection reason). */
  reason?: { label: string; required: boolean; key?: string };
  /** Fields shown in a dialog before the action is sent (e.g. a receipt). */
  fields?: FieldConfig[];
  /** Document lines the action needs (e.g. goods received). */
  lines?: LineConfig;
}

export interface FilterConfig {
  key: string;
  label: string;
  options: SelectOption[];
}

export interface ResourceConfig {
  id: string;
  label: string;
  singular: string;
  endpoint: string;
  /** The API accepts `?search=` for this list. */
  serverSearch: boolean;
  /** Report rows are computed in Python and do not support `ordering`. */
  serverSort?: boolean;
  columns: ColumnConfig[];
  detail: ColumnConfig[];
  fields?: FieldConfig[];
  lines?: LineConfig;
  /**
   * Permission needed to create or edit. Omitted means the backend accepts any
   * authenticated user, which is what its viewset actually enforces.
   */
  permission?: string;
  /** Permission needed to edit when it differs from the create permission. */
  editPermission?: string;
  create?: boolean;
  edit?: boolean;
  /** Only offer Edit while the record is in one of these states. */
  editableStatuses?: string[];
  deactivate?: boolean;
  actions?: ActionConfig[];
  /** Server-side equality filters, sent as query parameters. */
  filters?: FilterConfig[];
  /** GET path appended to the record URL for a private file download. */
  downloadPath?: string;
  /** GET path appended to the record URL for an inline PDF preview. */
  previewPath?: string;
  /** Lines shown in the detail dialog (journals, purchase requests). */
  detailLines?: ColumnConfig[];
  note?: string;
}

export interface ModuleConfig {
  title: string;
  intro: string;
  tabs: ResourceConfig[];
}

export type ModuleKey =
  | 'master-data'
  | 'procurement'
  | 'inventory'
  | 'accounting'
  | 'invoicing'
  | 'banking'
  | 'projects'
  | 'services'
  | 'leasing';

const ACTIVE: ColumnConfig = { key: 'is_active', label: 'Active', kind: 'boolean' };

const CURRENCY_OPTIONS: SelectOption[] = [{ value: 'NGN', label: 'NGN' }];

const SUPPLIER_FIELDS: FieldConfig[] = [
  { key: 'code', label: 'Code', type: 'text', required: true, help: 'Unique, e.g. SUP-001.' },
  { key: 'legal_name', label: 'Legal name', type: 'text', required: true },
  { key: 'trading_name', label: 'Trading name', type: 'text' },
  {
    key: 'supplier_category',
    label: 'Category',
    type: 'select',
    optionsEndpoint: '/api/v1/supplier-categories/',
    help: 'Categories are maintained under Master data.',
  },
  { key: 'payment_terms_days', label: 'Payment terms (days)', type: 'number', min: 0 },
  { key: 'default_currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
  { key: 'due_diligence_status', label: 'Due diligence status', type: 'text' },
  { key: 'email', label: 'Email', type: 'text' },
  { key: 'phone', label: 'Phone', type: 'text' },
  { key: 'website', label: 'Website', type: 'text' },
  { key: 'notes', label: 'Notes', type: 'textarea' },
  { key: 'is_active', label: 'Active', type: 'checkbox', defaultValue: true },
];

const CUSTOMER_FIELDS: FieldConfig[] = [
  { key: 'code', label: 'Code', type: 'text', required: true, help: 'Unique, e.g. CUS-001.' },
  { key: 'legal_name', label: 'Legal name', type: 'text', required: true },
  { key: 'trading_name', label: 'Trading name', type: 'text' },
  { key: 'payment_terms_days', label: 'Payment terms (days)', type: 'number', min: 0 },
  { key: 'default_currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
  {
    key: 'credit_limit',
    label: 'Credit limit',
    type: 'number',
    min: 0,
    step: '0.01',
    help: 'Leave blank until credit control sets a limit.',
  },
  { key: 'credit_hold', label: 'Credit hold', type: 'checkbox', defaultValue: false },
  { key: 'email', label: 'Email', type: 'text' },
  { key: 'phone', label: 'Phone', type: 'text' },
  { key: 'website', label: 'Website', type: 'text' },
  { key: 'notes', label: 'Notes', type: 'textarea' },
  { key: 'is_active', label: 'Active', type: 'checkbox', defaultValue: true },
];

const CATALOGUE_FIELDS: FieldConfig[] = [
  { key: 'code', label: 'Code', type: 'text', required: true },
  { key: 'name', label: 'Name', type: 'text', required: true },
  {
    key: 'kind',
    label: 'Kind',
    type: 'select',
    required: true,
    options: [
      { value: 'product', label: 'Product' },
      { value: 'service', label: 'Service' },
    ],
  },
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'category', label: 'Category', type: 'select', optionsEndpoint: '/api/v1/product-categories/' },
  { key: 'uom', label: 'Unit of measure', type: 'select', optionsEndpoint: '/api/v1/units-of-measure/' },
  { key: 'manufacturer', label: 'Manufacturer', type: 'select', optionsEndpoint: '/api/v1/manufacturers/' },
  { key: 'brand', label: 'Brand', type: 'text' },
  { key: 'specification_summary', label: 'Specification summary', type: 'textarea' },
  { key: 'tax_classification', label: 'Tax classification', type: 'text' },
  { key: 'tracks_batches', label: 'Tracks batches', type: 'checkbox', defaultValue: false },
  { key: 'tracks_serials', label: 'Tracks serial numbers', type: 'checkbox', defaultValue: false },
  { key: 'tracks_expiry', label: 'Tracks expiry', type: 'checkbox', defaultValue: false },
  { key: 'is_active', label: 'Active', type: 'checkbox', defaultValue: true },
];

const WAREHOUSE_FIELDS: FieldConfig[] = [
  { key: 'code', label: 'Code', type: 'text', required: true },
  { key: 'name', label: 'Name', type: 'text', required: true },
  { key: 'site_name', label: 'Site name', type: 'text' },
  { key: 'address', label: 'Address', type: 'textarea' },
  { key: 'is_active', label: 'Active', type: 'checkbox', defaultValue: true },
];

const PROJECT_FIELDS: FieldConfig[] = [
  { key: 'code', label: 'Code', type: 'text', required: true },
  { key: 'name', label: 'Name', type: 'text', required: true },
  { key: 'customer', label: 'Customer', type: 'select', optionsEndpoint: '/api/v1/customers/' },
  {
    key: 'status',
    label: 'Status',
    type: 'select',
    defaultValue: 'draft',
    options: [
      { value: 'draft', label: 'Draft' },
      { value: 'active', label: 'Active' },
      { value: 'on_hold', label: 'On hold' },
      { value: 'closed', label: 'Closed' },
    ],
    help: 'The backend allows only draft → active, active ↔ on hold and then closed.',
  },
  { key: 'start_date', label: 'Start date', type: 'date' },
  { key: 'end_date', label: 'End date', type: 'date' },
  { key: 'description', label: 'Description', type: 'textarea' },
];

const REQUEST_FIELDS: FieldConfig[] = [
  { key: 'destination', label: 'Destination', type: 'select', required: true, optionsEndpoint: '/api/v1/destinations/' },
  { key: 'department', label: 'Department', type: 'select', optionsEndpoint: '/api/v1/departments/' },
  { key: 'required_by', label: 'Required by', type: 'date' },
  { key: 'justification', label: 'Justification', type: 'textarea' },
];

const REQUEST_LINES: LineConfig = {
  label: 'Requested items',
  addLabel: 'Add item',
  fields: [
    { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
    { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
    { key: 'uom', label: 'Unit', type: 'select', optionsEndpoint: '/api/v1/units-of-measure/' },
    { key: 'cost_centre', label: 'Cost centre', type: 'select', optionsEndpoint: '/api/v1/cost-centres/' },
    { key: 'description', label: 'Line description', type: 'text' },
  ],
};

const ACTIVE_FIELD: FieldConfig = {
  key: 'is_active',
  label: 'Active',
  type: 'checkbox',
  defaultValue: true,
};

const PARTY_FIELD: FieldConfig = {
  key: 'party',
  label: 'Party',
  type: 'select',
  required: true,
  optionsEndpoint: '/api/v1/parties/',
};

const WAREHOUSE_FIELD: FieldConfig = {
  key: 'warehouse',
  label: 'Warehouse',
  type: 'select',
  required: true,
  optionsEndpoint: '/api/v1/warehouses/',
};

const PROJECT_FIELD: FieldConfig = {
  key: 'project',
  label: 'Project',
  type: 'select',
  required: true,
  optionsEndpoint: '/api/v1/projects/',
};

const REQUEST_STATUS: SelectOption[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

const ORDER_STATUS: SelectOption[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'approved', label: 'Approved' },
  { value: 'issued', label: 'Issued' },
  { value: 'partially_received', label: 'Partially received' },
  { value: 'received', label: 'Received' },
  { value: 'closed', label: 'Closed' },
];

const RFQ_STATUS: SelectOption[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'issued', label: 'Issued' },
  { value: 'closed', label: 'Closed' },
];

const TRANSFER_STATUS: SelectOption[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'dispatched', label: 'Dispatched' },
  { value: 'received', label: 'Received' },
  { value: 'cancelled', label: 'Cancelled' },
];

const JOURNAL_STATUS: SelectOption[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'approved', label: 'Approved' },
  { value: 'posted', label: 'Posted' },
];

const PERIOD_STATUS: SelectOption[] = [
  { value: 'open', label: 'Open' },
  { value: 'closed', label: 'Closed' },
];

const RECEIPT_LINES: LineConfig = {
  label: 'Received lines',
  addLabel: 'Add received line',
  fields: [
    {
      key: 'schedule',
      label: 'Delivery schedule',
      type: 'select',
      required: true,
      optionsEndpoint: '/api/v1/delivery-schedules/',
    },
    {
      key: 'order_line',
      label: 'Order line',
      type: 'select',
      required: true,
      optionsEndpoint: '/api/v1/purchase-order-lines/',
    },
    { key: 'quantity_delivered', label: 'Delivered', type: 'number', required: true, min: 0, step: '0.0001' },
    { key: 'quantity_accepted', label: 'Accepted', type: 'number', min: 0, step: '0.0001' },
    { key: 'quantity_rejected', label: 'Rejected', type: 'number', min: 0, step: '0.0001' },
    { key: 'quantity_damaged', label: 'Damaged', type: 'number', min: 0, step: '0.0001' },
    { key: 'rejection_reason', label: 'Rejection / damage reason', type: 'text' },
  ],
};

const ACCOUNT_FIELDS: FieldConfig[] = [
  { key: 'code', label: 'Code', type: 'text', required: true, help: 'Accountant-approved chart only.' },
  { key: 'name', label: 'Name', type: 'text', required: true },
  {
    key: 'account_type',
    label: 'Account type',
    type: 'select',
    required: true,
    options: [
      { value: 'asset', label: 'Asset' },
      { value: 'liability', label: 'Liability' },
      { value: 'equity', label: 'Equity' },
      { value: 'income', label: 'Income' },
      { value: 'expense', label: 'Expense' },
    ],
  },
  {
    key: 'normal_balance',
    label: 'Normal balance',
    type: 'select',
    required: true,
    options: [
      { value: 'debit', label: 'Debit' },
      { value: 'credit', label: 'Credit' },
    ],
  },
  { key: 'parent', label: 'Parent account', type: 'select', optionsEndpoint: '/api/v1/accounts/' },
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'is_active', label: 'Active', type: 'checkbox', defaultValue: true },
];

export const MODULES: Record<ModuleKey, ModuleConfig> = {
  'master-data': {
    title: 'Master data',
    intro:
      'The records every procurement, stock and accounting transaction depends on. Changes are written to the live API and validated by the backend.',
    tabs: [
      {
        id: 'suppliers',
        label: 'Suppliers',
        singular: 'supplier',
        endpoint: '/api/v1/suppliers/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'legal_name', label: 'Supplier' },
          { key: 'email', label: 'Email' },
          { key: 'payment_terms_days', label: 'Terms (days)', kind: 'number' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'legal_name', label: 'Legal name' },
          { key: 'trading_name', label: 'Trading name' },
          { key: 'supplier_category', label: 'Category' },
          { key: 'payment_terms_days', label: 'Payment terms (days)' },
          { key: 'default_currency', label: 'Currency' },
          { key: 'due_diligence_status', label: 'Due diligence' },
          { key: 'email', label: 'Email' },
          { key: 'phone', label: 'Phone' },
          { key: 'website', label: 'Website' },
          { key: 'notes', label: 'Notes' },
          ACTIVE,
        ],
        fields: SUPPLIER_FIELDS,
      },
      {
        id: 'customers',
        label: 'Customers',
        singular: 'customer',
        endpoint: '/api/v1/customers/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'legal_name', label: 'Customer' },
          { key: 'email', label: 'Email' },
          { key: 'credit_limit', label: 'Credit limit', kind: 'number' },
          { key: 'credit_hold', label: 'Credit hold', kind: 'boolean' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'legal_name', label: 'Legal name' },
          { key: 'trading_name', label: 'Trading name' },
          { key: 'payment_terms_days', label: 'Payment terms (days)' },
          { key: 'default_currency', label: 'Currency' },
          { key: 'credit_limit', label: 'Credit limit' },
          { key: 'credit_hold', label: 'Credit hold' },
          { key: 'email', label: 'Email' },
          { key: 'phone', label: 'Phone' },
          { key: 'website', label: 'Website' },
          { key: 'notes', label: 'Notes' },
          ACTIVE,
        ],
        fields: CUSTOMER_FIELDS,
      },
      {
        id: 'catalogue',
        label: 'Catalogue',
        singular: 'catalogue item',
        endpoint: '/api/v1/catalogue-items/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Item' },
          { key: 'kind', label: 'Kind' },
          { key: 'brand', label: 'Brand' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'kind', label: 'Kind' },
          { key: 'description', label: 'Description' },
          { key: 'category', label: 'Category' },
          { key: 'uom', label: 'Unit of measure' },
          { key: 'manufacturer', label: 'Manufacturer' },
          { key: 'brand', label: 'Brand' },
          { key: 'specification_summary', label: 'Specification' },
          { key: 'tax_classification', label: 'Tax classification' },
          { key: 'tracks_batches', label: 'Tracks batches' },
          { key: 'tracks_serials', label: 'Tracks serials' },
          { key: 'tracks_expiry', label: 'Tracks expiry' },
          ACTIVE,
        ],
        fields: CATALOGUE_FIELDS,
      },
      {
        id: 'warehouses',
        label: 'Warehouses',
        singular: 'warehouse',
        endpoint: '/api/v1/warehouses/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Warehouse' },
          { key: 'site_name', label: 'Site' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'site_name', label: 'Site name' },
          { key: 'address', label: 'Address' },
          ACTIVE,
        ],
        fields: WAREHOUSE_FIELDS,
      },
      {
        id: 'projects',
        label: 'Projects',
        singular: 'project',
        endpoint: '/api/v1/projects/',
        serverSearch: true,
        create: true,
        edit: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Project' },
          { key: 'status', label: 'Status', kind: 'status' },
          { key: 'start_date', label: 'Starts', kind: 'date' },
          { key: 'end_date', label: 'Ends', kind: 'date' },
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'customer', label: 'Customer' },
          { key: 'status', label: 'Status' },
          { key: 'start_date', label: 'Start date' },
          { key: 'end_date', label: 'End date' },
          { key: 'description', label: 'Description' },
        ],
        fields: PROJECT_FIELDS,
        note: 'New projects start as draft. Status transitions stay with the backend workflow until their approval rules are agreed.',
      },
      {
        id: 'supplier-categories',
        label: 'Supplier categories',
        singular: 'supplier category',
        endpoint: '/api/v1/supplier-categories/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Category' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'description', label: 'Description' },
          ACTIVE,
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'description', label: 'Description', type: 'textarea' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'contacts',
        label: 'Contacts',
        singular: 'contact',
        endpoint: '/api/v1/contacts/',
        serverSearch: false,
        create: true,
        edit: true,
        columns: [
          { key: 'party_code', label: 'Party' },
          { key: 'name', label: 'Contact' },
          { key: 'role', label: 'Role' },
          { key: 'email', label: 'Email' },
          { key: 'is_primary', label: 'Primary', kind: 'boolean' },
        ],
        detail: [
          { key: 'party_code', label: 'Party' },
          { key: 'name', label: 'Name' },
          { key: 'role', label: 'Role' },
          { key: 'email', label: 'Email' },
          { key: 'phone', label: 'Phone' },
          { key: 'is_primary', label: 'Primary' },
        ],
        fields: [
          PARTY_FIELD,
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'role', label: 'Role', type: 'text' },
          { key: 'email', label: 'Email', type: 'text' },
          { key: 'phone', label: 'Phone', type: 'text' },
          { key: 'is_primary', label: 'Primary contact', type: 'checkbox', defaultValue: false },
        ],
        note: 'One party can be a supplier and a customer; contacts are shared by both roles.',
      },
      {
        id: 'addresses',
        label: 'Addresses',
        singular: 'address',
        endpoint: '/api/v1/addresses/',
        serverSearch: false,
        create: true,
        edit: true,
        columns: [
          { key: 'party_code', label: 'Party' },
          { key: 'label', label: 'Label' },
          { key: 'line1', label: 'Address' },
          { key: 'city', label: 'City' },
          { key: 'is_primary', label: 'Primary', kind: 'boolean' },
        ],
        detail: [
          { key: 'party_code', label: 'Party' },
          { key: 'label', label: 'Label' },
          { key: 'line1', label: 'Line 1' },
          { key: 'line2', label: 'Line 2' },
          { key: 'city', label: 'City' },
          { key: 'state', label: 'State' },
          { key: 'postcode', label: 'Postcode' },
          { key: 'country', label: 'Country' },
          { key: 'is_primary', label: 'Primary' },
        ],
        fields: [
          PARTY_FIELD,
          { key: 'label', label: 'Label', type: 'text', help: 'e.g. Registered office.' },
          { key: 'line1', label: 'Line 1', type: 'text', required: true },
          { key: 'line2', label: 'Line 2', type: 'text' },
          { key: 'city', label: 'City', type: 'text', required: true },
          { key: 'state', label: 'State', type: 'text' },
          { key: 'postcode', label: 'Postcode', type: 'text' },
          { key: 'country', label: 'Country', type: 'text', defaultValue: 'Nigeria' },
          { key: 'is_primary', label: 'Primary address', type: 'checkbox', defaultValue: false },
        ],
      },
      {
        id: 'tax-registrations',
        label: 'Tax registrations',
        singular: 'tax registration',
        endpoint: '/api/v1/tax-registrations/',
        serverSearch: false,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'party_code', label: 'Party' },
          { key: 'scheme', label: 'Scheme' },
          { key: 'number', label: 'Number' },
          ACTIVE,
        ],
        detail: [
          { key: 'party_code', label: 'Party' },
          { key: 'scheme', label: 'Scheme' },
          { key: 'number', label: 'Number' },
          { key: 'issued_on', label: 'Issued' },
          ACTIVE,
        ],
        fields: [
          PARTY_FIELD,
          { key: 'scheme', label: 'Scheme', type: 'text', required: true, help: 'e.g. TIN or VAT.' },
          { key: 'number', label: 'Registration number', type: 'text', required: true },
          { key: 'issued_on', label: 'Issued on', type: 'date' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'supplier-bank',
        label: 'Supplier bank accounts',
        singular: 'bank account',
        endpoint: '/api/v1/bank-accounts/',
        serverSearch: false,
        columns: [
          { key: 'supplier_code', label: 'Supplier' },
          { key: 'bank_name', label: 'Bank' },
          { key: 'masked_account', label: 'Account' },
          { key: 'currency', label: 'Currency' },
        ],
        detail: [
          { key: 'supplier_code', label: 'Supplier' },
          { key: 'supplier_name', label: 'Supplier name' },
          { key: 'bank_name', label: 'Bank' },
          { key: 'account_name', label: 'Account name' },
          { key: 'masked_account', label: 'Account number' },
          { key: 'sort_code', label: 'Sort code' },
          { key: 'currency', label: 'Currency' },
          ACTIVE,
        ],
        note: 'Accounts are read-only here. A change is proposed and approved by a second person under Bank changes.',
      },
      {
        id: 'bank-changes',
        label: 'Bank changes',
        singular: 'bank change request',
        endpoint: '/api/v1/bank-account-change-requests/',
        serverSearch: false,
        create: true,
        columns: [
          { key: 'supplier_code', label: 'Supplier' },
          { key: 'proposed_bank_name', label: 'Bank' },
          { key: 'proposed_masked_account', label: 'Account' },
          { key: 'status', label: 'Status', kind: 'status' },
        ],
        detail: [
          { key: 'supplier_code', label: 'Supplier' },
          { key: 'bank_account', label: 'Existing account' },
          { key: 'proposed_bank_name', label: 'Proposed bank' },
          { key: 'proposed_account_name', label: 'Proposed account name' },
          { key: 'proposed_masked_account', label: 'Proposed account' },
          { key: 'proposed_sort_code', label: 'Sort code' },
          { key: 'proposed_currency', label: 'Currency' },
          { key: 'reason', label: 'Reason' },
          { key: 'status', label: 'Status' },
          { key: 'requested_by', label: 'Requested by' },
          { key: 'reviewed_by', label: 'Reviewed by' },
          { key: 'review_note', label: 'Review note' },
        ],
        fields: [
          { key: 'supplier', label: 'Supplier', type: 'select', required: true, optionsEndpoint: '/api/v1/suppliers/' },
          { key: 'bank_account', label: 'Existing account', type: 'select', optionsEndpoint: '/api/v1/bank-accounts/' },
          { key: 'proposed_bank_name', label: 'Bank name', type: 'text', required: true },
          { key: 'proposed_account_name', label: 'Account name', type: 'text', required: true },
          { key: 'proposed_account_number', label: 'Account number', type: 'text', required: true },
          { key: 'proposed_sort_code', label: 'Sort code', type: 'text' },
          { key: 'proposed_currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
          { key: 'reason', label: 'Reason for change', type: 'text', required: true },
        ],
        actions: [
          {
            id: 'approve',
            label: 'Approve change',
            path: 'approve',
            permission: 'parties.approve_bankaccountchange',
            confirm: 'Approve this bank account change? The proposed details become the live account.',
            success: 'Bank account change approved.',
            statuses: ['pending'],
            reason: { label: 'Review note', required: false, key: 'review_note' },
          },
          {
            id: 'reject',
            label: 'Reject change',
            path: 'reject',
            permission: 'parties.approve_bankaccountchange',
            confirm: 'Reject this bank account change?',
            success: 'Bank account change rejected.',
            statuses: ['pending'],
            reason: { label: 'Review note', required: true, key: 'review_note' },
          },
        ],
        note: 'The account number is encrypted by the backend and never returned in clear text.',
      },
      {
        id: 'compliance',
        label: 'Compliance documents',
        singular: 'compliance document',
        endpoint: '/api/v1/compliance-documents/',
        serverSearch: false,
        create: true,
        edit: true,
        columns: [
          { key: 'party_code', label: 'Supplier' },
          { key: 'document_type', label: 'Type' },
          { key: 'expires_on', label: 'Expires', kind: 'date' },
          { key: 'is_verified', label: 'Verified', kind: 'boolean' },
        ],
        detail: [
          { key: 'party_code', label: 'Supplier' },
          { key: 'document_type', label: 'Document type' },
          { key: 'reference', label: 'Reference' },
          { key: 'issued_on', label: 'Issued' },
          { key: 'expires_on', label: 'Expires' },
          { key: 'is_verified', label: 'Verified' },
          { key: 'verified_by', label: 'Verified by' },
          { key: 'notes', label: 'Notes' },
        ],
        fields: [
          { key: 'supplier', label: 'Supplier', type: 'select', required: true, optionsEndpoint: '/api/v1/suppliers/' },
          { key: 'document_type', label: 'Document type', type: 'text', required: true },
          { key: 'reference', label: 'Reference', type: 'text' },
          { key: 'issued_on', label: 'Issued on', type: 'date' },
          { key: 'expires_on', label: 'Expires on', type: 'date' },
          { key: 'is_verified', label: 'Verified', type: 'checkbox', defaultValue: false },
          { key: 'document', label: 'Uploaded document', type: 'select', optionsEndpoint: '/api/v1/documents/' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
      },
      {
        id: 'document-categories',
        label: 'Document categories',
        singular: 'document category',
        endpoint: '/api/v1/document-categories/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Category' },
          { key: 'retention_months', label: 'Retention (months)', kind: 'number' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'retention_months', label: 'Retention months' },
          { key: 'description', label: 'Description' },
          ACTIVE,
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'retention_months', label: 'Retention (months)', type: 'number', min: 0, help: 'Leave blank until a retention rule is approved.' },
          { key: 'description', label: 'Description', type: 'textarea' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'documents',
        label: 'Documents',
        singular: 'document',
        endpoint: '/api/v1/documents/',
        serverSearch: true,
        create: true,
        edit: true,
        downloadPath: 'download',
        columns: [
          { key: 'title', label: 'Title' },
          { key: 'original_filename', label: 'File' },
          { key: 'version', label: 'Version' },
          { key: 'created_at', label: 'Uploaded', kind: 'date' },
        ],
        detail: [
          { key: 'title', label: 'Title' },
          { key: 'category', label: 'Category' },
          { key: 'original_filename', label: 'File name' },
          { key: 'mime_type', label: 'Type' },
          { key: 'size_bytes', label: 'Size (bytes)' },
          { key: 'checksum_sha256', label: 'SHA-256' },
          { key: 'version', label: 'Version' },
          { key: 'is_private', label: 'Private' },
          { key: 'retention_until', label: 'Retain until' },
          { key: 'notes', label: 'Notes' },
        ],
        fields: [
          { key: 'title', label: 'Title', type: 'text', required: true },
          { key: 'category', label: 'Category', type: 'select', optionsEndpoint: '/api/v1/document-categories/' },
          { key: 'file', label: 'File', type: 'file', help: 'Required for a new document. Private: downloads are authenticated and never served from a public URL.' },
          { key: 'is_private', label: 'Private', type: 'checkbox', defaultValue: true },
          { key: 'retention_until', label: 'Retain until', type: 'date' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        note: 'A document\'s bytes are immutable; upload a new version that supersedes the old record instead of replacing it.',
      },
      {
        id: 'product-categories',
        label: 'Product categories',
        singular: 'product category',
        endpoint: '/api/v1/product-categories/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Category' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'parent', label: 'Parent' },
          ACTIVE,
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'parent', label: 'Parent category', type: 'select', optionsEndpoint: '/api/v1/product-categories/' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'units',
        label: 'Units of measure',
        singular: 'unit of measure',
        endpoint: '/api/v1/units-of-measure/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Unit' },
          { key: 'conversion_factor', label: 'Factor', kind: 'number' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'base_uom', label: 'Base unit' },
          { key: 'conversion_factor', label: 'Conversion factor' },
          ACTIVE,
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'base_uom', label: 'Base unit', type: 'select', optionsEndpoint: '/api/v1/units-of-measure/' },
          { key: 'conversion_factor', label: 'Conversion factor', type: 'number', min: 0, step: '0.000001' },
          ACTIVE_FIELD,
        ],
        note: 'A conversion needs both a base unit and a factor; both are left blank when no conversion applies.',
      },
      {
        id: 'manufacturers',
        label: 'Manufacturers',
        singular: 'manufacturer',
        endpoint: '/api/v1/manufacturers/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Manufacturer' },
          { key: 'country', label: 'Country' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'website', label: 'Website' },
          { key: 'country', label: 'Country' },
          ACTIVE,
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'website', label: 'Website', type: 'text' },
          { key: 'country', label: 'Country', type: 'text' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'prices',
        label: 'Item prices',
        singular: 'item price',
        endpoint: '/api/v1/item-prices/',
        serverSearch: false,
        create: true,
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'amount', label: 'Amount', kind: 'number' },
          { key: 'currency', label: 'Currency' },
          { key: 'effective_from', label: 'From', kind: 'date' },
          { key: 'effective_to', label: 'To', kind: 'date' },
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'amount', label: 'Amount' },
          { key: 'currency', label: 'Currency' },
          { key: 'effective_from', label: 'Effective from' },
          { key: 'effective_to', label: 'Effective to' },
          { key: 'source_reference', label: 'Source' },
        ],
        fields: [
          { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
          { key: 'currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
          { key: 'amount', label: 'Amount', type: 'number', required: true, min: 0, step: '0.000001' },
          { key: 'effective_from', label: 'Effective from', type: 'date', required: true },
          { key: 'effective_to', label: 'Effective to', type: 'date' },
          { key: 'source_reference', label: 'Source reference', type: 'text' },
        ],
        note: 'A new price is a new record; effective periods cannot overlap.',
      },
      {
        id: 'specifications',
        label: 'Specifications',
        singular: 'specification',
        endpoint: '/api/v1/technical-specifications/',
        serverSearch: false,
        create: true,
        edit: true,
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'name', label: 'Specification' },
          { key: 'value', label: 'Value' },
          { key: 'unit', label: 'Unit' },
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'name', label: 'Name' },
          { key: 'value', label: 'Value' },
          { key: 'unit', label: 'Unit' },
          { key: 'sort_order', label: 'Sort order' },
        ],
        fields: [
          { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'value', label: 'Value', type: 'text', required: true },
          { key: 'unit', label: 'Unit', type: 'text' },
          { key: 'sort_order', label: 'Sort order', type: 'number', min: 0 },
        ],
      },
      {
        id: 'batches',
        label: 'Batches',
        singular: 'batch',
        endpoint: '/api/v1/item-batches/',
        serverSearch: false,
        create: true,
        edit: true,
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'batch_number', label: 'Batch' },
          { key: 'expires_on', label: 'Expires', kind: 'date' },
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'batch_number', label: 'Batch number' },
          { key: 'manufactured_on', label: 'Manufactured' },
          { key: 'expires_on', label: 'Expires' },
          { key: 'notes', label: 'Notes' },
        ],
        fields: [
          { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
          { key: 'batch_number', label: 'Batch number', type: 'text', required: true },
          { key: 'manufactured_on', label: 'Manufactured on', type: 'date' },
          { key: 'expires_on', label: 'Expires on', type: 'date' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
      },
      {
        id: 'serials',
        label: 'Serial numbers',
        singular: 'serial number',
        endpoint: '/api/v1/serial-numbers/',
        serverSearch: false,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'serial', label: 'Serial' },
          ACTIVE,
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'serial', label: 'Serial' },
          { key: 'batch', label: 'Batch' },
          { key: 'notes', label: 'Notes' },
          ACTIVE,
        ],
        fields: [
          { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
          { key: 'serial', label: 'Serial number', type: 'text', required: true },
          { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'certificates',
        label: 'Certificates',
        singular: 'certificate',
        endpoint: '/api/v1/certificates/',
        serverSearch: false,
        create: true,
        edit: true,
        columns: [
          { key: 'certificate_type', label: 'Type' },
          { key: 'item_code', label: 'Item' },
          { key: 'issuer', label: 'Issuer' },
          { key: 'expires_on', label: 'Expires', kind: 'date' },
        ],
        detail: [
          { key: 'certificate_type', label: 'Type' },
          { key: 'item_code', label: 'Item' },
          { key: 'batch', label: 'Batch' },
          { key: 'serial', label: 'Serial' },
          { key: 'issuer', label: 'Issuer' },
          { key: 'reference', label: 'Reference' },
          { key: 'issued_on', label: 'Issued' },
          { key: 'expires_on', label: 'Expires' },
          { key: 'notes', label: 'Notes' },
        ],
        fields: [
          { key: 'item', label: 'Item', type: 'select', optionsEndpoint: '/api/v1/catalogue-items/' },
          { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
          { key: 'serial', label: 'Serial number', type: 'select', optionsEndpoint: '/api/v1/serial-numbers/' },
          { key: 'certificate_type', label: 'Certificate type', type: 'text', required: true },
          { key: 'issuer', label: 'Issuer', type: 'text' },
          { key: 'reference', label: 'Reference', type: 'text' },
          { key: 'issued_on', label: 'Issued on', type: 'date' },
          { key: 'expires_on', label: 'Expires on', type: 'date' },
          { key: 'document', label: 'Uploaded document', type: 'select', optionsEndpoint: '/api/v1/documents/' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        note: 'A certificate needs an item, batch or serial reference.',
      },
      {
        id: 'storage-locations',
        label: 'Storage locations',
        singular: 'storage location',
        endpoint: '/api/v1/storage-locations/',
        serverSearch: false,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Location' },
          ACTIVE,
        ],
        detail: [
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          ACTIVE,
        ],
        fields: [
          WAREHOUSE_FIELD,
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'departments',
        label: 'Departments',
        singular: 'department',
        endpoint: '/api/v1/departments/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Department' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'parent', label: 'Parent' },
          ACTIVE,
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'parent', label: 'Parent department', type: 'select', optionsEndpoint: '/api/v1/departments/' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'cost-centres',
        label: 'Cost centres',
        singular: 'cost centre',
        endpoint: '/api/v1/cost-centres/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Cost centre' },
          ACTIVE,
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'parent', label: 'Parent' },
          { key: 'department', label: 'Department' },
          { key: 'description', label: 'Description' },
          ACTIVE,
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'parent', label: 'Parent cost centre', type: 'select', optionsEndpoint: '/api/v1/cost-centres/' },
          { key: 'department', label: 'Department', type: 'select', optionsEndpoint: '/api/v1/departments/' },
          { key: 'description', label: 'Description', type: 'textarea' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'destinations',
        label: 'Destinations',
        singular: 'destination',
        endpoint: '/api/v1/destinations/',
        serverSearch: false,
        create: true,
        edit: true,
        columns: [
          { key: 'kind', label: 'Type' },
          { key: 'project_code', label: 'Project' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'location_name', label: 'Location' },
        ],
        detail: [
          { key: 'kind', label: 'Type' },
          { key: 'project_code', label: 'Project' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'location_name', label: 'Location' },
          { key: 'notes', label: 'Notes' },
        ],
        fields: [
          {
            key: 'kind',
            label: 'Destination type',
            type: 'select',
            required: true,
            options: [
              { value: 'warehouse', label: 'Company warehouse' },
              { value: 'project', label: 'Direct project delivery' },
              { value: 'other', label: 'Other authorised location' },
            ],
          },
          { key: 'project', label: 'Project', type: 'select', optionsEndpoint: '/api/v1/projects/' },
          { key: 'warehouse', label: 'Warehouse', type: 'select', optionsEndpoint: '/api/v1/warehouses/' },
          { key: 'location_name', label: 'Other location name', type: 'text' },
          { key: 'notes', label: 'Notes', type: 'text' },
        ],
        note: 'Only the target that matches the chosen type may be filled.',
      },
      {
        id: 'project-locations',
        label: 'Project locations',
        singular: 'project location',
        endpoint: '/api/v1/project-locations/',
        serverSearch: false,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'project_code', label: 'Project' },
          { key: 'name', label: 'Location' },
          { key: 'is_primary', label: 'Primary', kind: 'boolean' },
          ACTIVE,
        ],
        detail: [
          { key: 'project_code', label: 'Project' },
          { key: 'name', label: 'Name' },
          { key: 'address', label: 'Address' },
          { key: 'is_primary', label: 'Primary' },
          ACTIVE,
        ],
        fields: [
          PROJECT_FIELD,
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'address', label: 'Address', type: 'textarea' },
          { key: 'is_primary', label: 'Primary location', type: 'checkbox', defaultValue: false },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'contracts',
        label: 'Customer contracts',
        singular: 'contract',
        endpoint: '/api/v1/customer-contracts/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'reference', label: 'Reference' },
          { key: 'project', label: 'Project' },
          { key: 'value', label: 'Value', kind: 'number' },
          { key: 'start_date', label: 'Starts', kind: 'date' },
        ],
        detail: [
          { key: 'reference', label: 'Reference' },
          { key: 'project', label: 'Project' },
          { key: 'customer', label: 'Customer' },
          { key: 'value', label: 'Value' },
          { key: 'currency', label: 'Currency' },
          { key: 'start_date', label: 'Start date' },
          { key: 'end_date', label: 'End date' },
          { key: 'terms', label: 'Terms' },
          ACTIVE,
        ],
        fields: [
          PROJECT_FIELD,
          { key: 'customer', label: 'Customer', type: 'select', required: true, optionsEndpoint: '/api/v1/customers/' },
          { key: 'reference', label: 'Reference', type: 'text', required: true },
          { key: 'value', label: 'Contract value', type: 'number', required: true, min: 0, step: '0.01' },
          { key: 'currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
          { key: 'start_date', label: 'Start date', type: 'date', required: true },
          { key: 'end_date', label: 'End date', type: 'date' },
          { key: 'terms', label: 'Terms', type: 'textarea' },
          ACTIVE_FIELD,
        ],
      },
      {
        id: 'contract-revisions',
        label: 'Contract revisions',
        singular: 'contract revision',
        endpoint: '/api/v1/contract-revisions/',
        serverSearch: false,
        create: true,
        columns: [
          { key: 'contract_reference', label: 'Contract' },
          { key: 'revision_number', label: 'Revision' },
          { key: 'value', label: 'Value', kind: 'number' },
          { key: 'reason', label: 'Reason' },
        ],
        detail: [
          { key: 'contract_reference', label: 'Contract' },
          { key: 'revision_number', label: 'Revision' },
          { key: 'value', label: 'Value' },
          { key: 'currency', label: 'Currency' },
          { key: 'start_date', label: 'Start date' },
          { key: 'end_date', label: 'End date' },
          { key: 'terms', label: 'Terms' },
          { key: 'reason', label: 'Reason' },
        ],
        fields: [
          { key: 'contract', label: 'Contract', type: 'select', required: true, optionsEndpoint: '/api/v1/customer-contracts/' },
          { key: 'value', label: 'Revised value', type: 'number', required: true, min: 0, step: '0.01' },
          { key: 'currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
          { key: 'start_date', label: 'Start date', type: 'date', required: true },
          { key: 'end_date', label: 'End date', type: 'date' },
          { key: 'terms', label: 'Terms', type: 'textarea' },
          { key: 'reason', label: 'Reason', type: 'text' },
        ],
        note: 'Revisions are append-only; the revision number is assigned by the backend.',
      },
      {
        id: 'budgets',
        label: 'Project budgets',
        singular: 'budget',
        endpoint: '/api/v1/project-budgets/',
        serverSearch: true,
        create: true,
        edit: true,
        columns: [
          { key: 'project_code', label: 'Project' },
          { key: 'version', label: 'Version' },
          { key: 'status', label: 'Status', kind: 'status' },
          { key: 'total_value', label: 'Total', kind: 'number' },
        ],
        detail: [
          { key: 'project_code', label: 'Project' },
          { key: 'version', label: 'Version' },
          { key: 'currency', label: 'Currency' },
          { key: 'status', label: 'Status' },
          { key: 'total_value', label: 'Total' },
          { key: 'approvals_required', label: 'Approvals required' },
          { key: 'approvals_recorded', label: 'Approvals recorded' },
          { key: 'approval_policy', label: 'Approval band' },
          { key: 'notes', label: 'Notes' },
          { key: 'approved_by', label: 'Approved by' },
          { key: 'approved_at', label: 'Approved at' },
        ],
        detailLines: [
          { key: 'description', label: 'Description' },
          { key: 'cost_centre', label: 'Cost centre' },
          { key: 'amount', label: 'Amount' },
        ],
        fields: [
          PROJECT_FIELD,
          { key: 'currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        lines: {
          label: 'Budget lines',
          addLabel: 'Add budget line',
          fields: [
            { key: 'cost_centre', label: 'Cost centre', type: 'select', optionsEndpoint: '/api/v1/cost-centres/' },
            { key: 'description', label: 'Description', type: 'text', required: true },
            { key: 'amount', label: 'Amount', type: 'number', required: true, min: 0, step: '0.01' },
          ],
        },
        actions: [
          {
            id: 'approve',
            label: 'Approve budget',
            path: 'approve',
            permission: 'projects.approve_projectbudget',
            confirm: 'Approve this budget version? Approved budgets cannot be edited.',
            success: 'Budget approved.',
            statuses: ['draft'],
          },
        ],
      },
      {
        id: 'milestones',
        label: 'Milestones',
        singular: 'milestone',
        endpoint: '/api/v1/project-milestones/',
        serverSearch: true,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'project_code', label: 'Project' },
          { key: 'name', label: 'Milestone' },
          { key: 'due_date', label: 'Due', kind: 'date' },
          { key: 'completed_on', label: 'Completed', kind: 'date' },
          ACTIVE,
        ],
        detail: [
          { key: 'project_code', label: 'Project' },
          { key: 'name', label: 'Name' },
          { key: 'due_date', label: 'Due date' },
          { key: 'completed_on', label: 'Completed on' },
          { key: 'notes', label: 'Notes' },
          ACTIVE,
        ],
        fields: [
          PROJECT_FIELD,
          { key: 'name', label: 'Name', type: 'text', required: true },
          { key: 'due_date', label: 'Due date', type: 'date' },
          { key: 'completed_on', label: 'Completed on', type: 'date' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
          ACTIVE_FIELD,
        ],
      },
    ],
  },
  procurement: {
    title: 'Procurement',
    intro:
      'Request, approve and track purchases. Every action below calls its lifecycle endpoint; the backend rejects an illegal transition whatever the screen offers.',
    tabs: [
      {
        id: 'requests',
        label: 'Purchase requests',
        singular: 'purchase request',
        endpoint: '/api/v1/purchase-requests/',
        permission: 'procurement.add_purchaserequest',
        editPermission: 'procurement.change_purchaserequest',
        serverSearch: true,
        create: true,
        edit: true,
        filters: [{ key: 'status', label: 'Status', options: REQUEST_STATUS }],
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'status', label: 'Status', kind: 'status' },
          { key: 'requester', label: 'Requester' },
          { key: 'required_by', label: 'Required by', kind: 'date' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'status', label: 'Status' },
          { key: 'requester', label: 'Requester' },
          { key: 'department_code', label: 'Department' },
          { key: 'destination_kind', label: 'Destination type' },
          { key: 'required_by', label: 'Required by' },
          { key: 'justification', label: 'Justification' },
          { key: 'submitted_at', label: 'Submitted' },
          { key: 'approved_by', label: 'Approved by' },
          { key: 'rejection_reason', label: 'Rejection reason' },
          { key: 'approvals_required', label: 'Approvals required' },
          { key: 'approvals_recorded', label: 'Approvals recorded' },
          { key: 'approval_policy', label: 'Approval band' },
        ],
        detailLines: [
          { key: 'item_code', label: 'Item' },
          { key: 'description', label: 'Description' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'uom_code', label: 'Unit' },
        ],
        fields: REQUEST_FIELDS,
        lines: REQUEST_LINES,
        actions: [
          {
            id: 'submit',
            label: 'Submit for approval',
            path: 'submit',
            confirm: 'Submit this request for approval? It can no longer be edited after submission.',
            success: 'Request submitted.',
            statuses: ['draft'],
          },
          {
            id: 'approve',
            label: 'Approve',
            path: 'approve',
            permission: 'procurement.approve_purchaserequest',
            confirm: 'Approve this purchase request?',
            success: 'Request approved.',
            statuses: ['submitted'],
          },
          {
            id: 'reject',
            label: 'Reject',
            path: 'reject',
            permission: 'procurement.approve_purchaserequest',
            confirm: 'Reject this purchase request?',
            success: 'Request rejected.',
            statuses: ['submitted'],
            reason: { label: 'Rejection reason', required: true },
          },
        ],
      },
      {
        id: 'orders',
        label: 'Purchase orders',
        singular: 'purchase order',
        endpoint: '/api/v1/purchase-orders/',
        serverSearch: true,
        create: true,
        edit: true,
        filters: [{ key: 'status', label: 'Status', options: ORDER_STATUS }],
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'status', label: 'Status', kind: 'status' },
          { key: 'supplier_name', label: 'Supplier' },
          { key: 'total_value', label: 'Total', kind: 'number' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'status', label: 'Status' },
          { key: 'supplier_name', label: 'Supplier' },
          { key: 'request_number', label: 'Request' },
          { key: 'revision', label: 'Revision' },
          { key: 'currency', label: 'Currency' },
          { key: 'total_value', label: 'Total' },
          { key: 'submitted_at', label: 'Submitted' },
          { key: 'approved_by', label: 'Approved by' },
          { key: 'approvals_required', label: 'Approvals required' },
          { key: 'approvals_recorded', label: 'Approvals recorded' },
          { key: 'approval_policy', label: 'Approval band' },
          { key: 'issued_at', label: 'Issued' },
          { key: 'closed_at', label: 'Closed' },
          { key: 'close_reason', label: 'Close reason' },
        ],
        detailLines: [
          { key: 'item_code', label: 'Item' },
          { key: 'description', label: 'Description' },
          { key: 'quantity', label: 'Ordered' },
          { key: 'quantity_accepted', label: 'Accepted' },
          { key: 'unit_price', label: 'Unit price' },
        ],
        fields: [
          { key: 'request', label: 'Approved request', type: 'select', required: true, optionsEndpoint: '/api/v1/purchase-requests/', optionsQuery: { status: 'approved' } },
          { key: 'supplier', label: 'Supplier', type: 'select', required: true, optionsEndpoint: '/api/v1/suppliers/' },
          { key: 'rfq', label: 'RFQ', type: 'select', optionsEndpoint: '/api/v1/rfqs/' },
          { key: 'selection', label: 'Selected quotation', type: 'select', optionsEndpoint: '/api/v1/supplier-selections/', help: 'Choosing a selection copies its priced lines.' },
          { key: 'destination', label: 'Destination', type: 'select', required: true, optionsEndpoint: '/api/v1/destinations/' },
          { key: 'currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
        ],
        lines: {
          label: 'Order lines',
          addLabel: 'Add order line',
          minLines: 0,
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'description', label: 'Description', type: 'text' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'unit_price', label: 'Unit price', type: 'number', required: true, min: 0, step: '0.000001' },
            { key: 'uom', label: 'Unit', type: 'select', optionsEndpoint: '/api/v1/units-of-measure/' },
            { key: 'cost_centre', label: 'Cost centre', type: 'select', optionsEndpoint: '/api/v1/cost-centres/' },
          ],
        },
        actions: [
          {
            id: 'submit',
            label: 'Submit',
            path: 'submit',
            confirm: 'Submit this order for approval?',
            success: 'Order submitted.',
            statuses: ['draft'],
          },
          {
            id: 'approve',
            label: 'Approve',
            path: 'approve',
            permission: 'procurement.approve_purchaseorder',
            confirm: 'Approve this purchase order?',
            success: 'Order approved.',
            statuses: ['submitted'],
          },
          {
            id: 'issue',
            label: 'Issue to supplier',
            path: 'issue',
            confirm: 'Mark this order as issued to the supplier?',
            success: 'Order issued.',
            statuses: ['approved'],
          },
          {
            id: 'close',
            label: 'Close',
            path: 'close',
            confirm: 'Close this order? Remaining quantities can no longer be delivered.',
            success: 'Order closed.',
            statuses: ['issued'],
            reason: { label: 'Close reason', required: false },
          },
          {
            id: 'receive',
            label: 'Record delivery',
            path: 'receive',
            confirm: 'Record goods received against this order?',
            success: 'Goods receipt recorded.',
            statuses: ['issued', 'partially_received'],
            fields: [
              { key: 'received_at', label: 'Received on', type: 'date', required: true },
              { key: 'notes', label: 'Notes', type: 'textarea' },
            ],
            lines: RECEIPT_LINES,
          },
        ],
        note: 'Orders are raised from an approved request, optionally from the selected quotation. Only a draft order can be amended; receiving goods posts accepted warehouse quantities to the stock ledger.',
      },
      {
        id: 'rfqs',
        label: 'RFQs',
        singular: 'RFQ',
        endpoint: '/api/v1/rfqs/',
        serverSearch: false,
        create: true,
        filters: [{ key: 'status', label: 'Status', options: RFQ_STATUS }],
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'request_number', label: 'Request' },
          { key: 'status', label: 'Status', kind: 'status' },
          { key: 'due_date', label: 'Due', kind: 'date' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'request_number', label: 'Request' },
          { key: 'status', label: 'Status' },
          { key: 'due_date', label: 'Due date' },
          { key: 'issued_at', label: 'Issued at' },
          { key: 'notes', label: 'Notes' },
        ],
        fields: [
          { key: 'request', label: 'Approved request', type: 'select', required: true, optionsEndpoint: '/api/v1/purchase-requests/', optionsQuery: { status: 'approved' } },
          { key: 'due_date', label: 'Quotes due', type: 'date' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        actions: [
          {
            id: 'issue',
            label: 'Issue RFQ',
            path: 'issue',
            confirm: 'Issue this RFQ to the invited suppliers?',
            success: 'RFQ issued.',
            statuses: ['draft'],
          },
        ],
        note: 'An RFQ can only be raised against an approved request and needs at least one invited supplier before issuing.',
      },
      {
        id: 'rfq-suppliers',
        label: 'RFQ invitations',
        singular: 'RFQ invitation',
        endpoint: '/api/v1/rfq-suppliers/',
        serverSearch: false,
        create: true,
        columns: [
          { key: 'rfq_number', label: 'RFQ' },
          { key: 'supplier_name', label: 'Supplier' },
        ],
        detail: [
          { key: 'rfq_number', label: 'RFQ' },
          { key: 'supplier_name', label: 'Supplier' },
        ],
        fields: [
          { key: 'rfq', label: 'RFQ', type: 'select', required: true, optionsEndpoint: '/api/v1/rfqs/' },
          { key: 'supplier', label: 'Supplier', type: 'select', required: true, optionsEndpoint: '/api/v1/suppliers/' },
        ],
      },
      {
        id: 'quotes',
        label: 'Quotations',
        singular: 'quotation',
        endpoint: '/api/v1/supplier-quotes/',
        serverSearch: false,
        create: true,
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'rfq_number', label: 'RFQ' },
          { key: 'supplier_name', label: 'Supplier' },
          { key: 'currency', label: 'Currency' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'rfq_number', label: 'RFQ' },
          { key: 'supplier_name', label: 'Supplier' },
          { key: 'reference', label: 'Supplier reference' },
          { key: 'received_at', label: 'Received' },
          { key: 'currency', label: 'Currency' },
        ],
        detailLines: [
          { key: 'request_line', label: 'Request line' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'unit_price', label: 'Unit price' },
          { key: 'lead_time_days', label: 'Lead time (days)' },
        ],
        fields: [
          { key: 'rfq', label: 'Issued RFQ', type: 'select', required: true, optionsEndpoint: '/api/v1/rfqs/', optionsQuery: { status: 'issued' } },
          { key: 'supplier', label: 'Invited supplier', type: 'select', required: true, optionsEndpoint: '/api/v1/suppliers/' },
          { key: 'reference', label: 'Supplier reference', type: 'text' },
          { key: 'received_at', label: 'Received on', type: 'date' },
          { key: 'currency', label: 'Currency', type: 'select', options: CURRENCY_OPTIONS },
        ],
        lines: {
          label: 'Quoted lines',
          addLabel: 'Add quoted line',
          fields: [
            { key: 'request_line', label: 'Request line', type: 'select', required: true, optionsEndpoint: '/api/v1/purchase-request-lines/' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'unit_price', label: 'Unit price', type: 'number', required: true, min: 0, step: '0.000001' },
            { key: 'lead_time_days', label: 'Lead time (days)', type: 'number', min: 0 },
          ],
        },
        note: 'A quotation can only be entered for an issued RFQ, by an invited supplier, and cannot exceed the requested quantity.',
      },
      {
        id: 'selections',
        label: 'Supplier selection',
        singular: 'supplier selection',
        endpoint: '/api/v1/supplier-selections/',
        serverSearch: false,
        create: true,
        permission: 'procurement.select_supplier',
        columns: [
          { key: 'rfq_number', label: 'RFQ' },
          { key: 'quote_number', label: 'Quotation' },
          { key: 'reason', label: 'Reason' },
        ],
        detail: [
          { key: 'rfq_number', label: 'RFQ' },
          { key: 'quote_number', label: 'Quotation' },
          { key: 'reason', label: 'Reason' },
        ],
        fields: [
          { key: 'rfq', label: 'RFQ', type: 'select', required: true, optionsEndpoint: '/api/v1/rfqs/', optionsQuery: { status: 'issued' } },
          { key: 'quote', label: 'Quotation', type: 'select', required: true, optionsEndpoint: '/api/v1/supplier-quotes/' },
          { key: 'reason', label: 'Selection reason', type: 'text', required: true },
        ],
        note: 'Selecting a supplier needs the procurement.select_supplier permission; the selection is then used to raise the order.',
      },
      {
        id: 'schedules',
        label: 'Delivery schedules',
        singular: 'delivery schedule',
        endpoint: '/api/v1/delivery-schedules/',
        serverSearch: false,
        create: true,
        columns: [
          { key: 'label', label: 'Schedule' },
          { key: 'due_date', label: 'Due', kind: 'date' },
          { key: 'quantity', label: 'Quantity', kind: 'number' },
          { key: 'quantity_delivered', label: 'Delivered', kind: 'number' },
        ],
        detail: [
          { key: 'label', label: 'Schedule' },
          { key: 'order_line', label: 'Order line' },
          { key: 'due_date', label: 'Due date' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'quantity_delivered', label: 'Delivered' },
          { key: 'destination', label: 'Destination' },
        ],
        fields: [
          { key: 'order_line', label: 'Order line', type: 'select', required: true, optionsEndpoint: '/api/v1/purchase-order-lines/' },
          { key: 'due_date', label: 'Due date', type: 'date', required: true },
          { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
          { key: 'destination', label: 'Destination', type: 'select', required: true, optionsEndpoint: '/api/v1/destinations/' },
        ],
        note: 'Scheduled quantities cannot exceed the ordered quantity; split deliveries are separate schedules.',
      },
      {
        id: 'receipts',
        label: 'Goods receipts',
        singular: 'goods receipt',
        endpoint: '/api/v1/goods-receipts/',
        serverSearch: true,
        columns: [
          { key: 'number', label: 'GRN' },
          { key: 'order_number', label: 'Order' },
          { key: 'received_at', label: 'Received', kind: 'date' },
          { key: 'received_by', label: 'Received by' },
        ],
        detail: [
          { key: 'number', label: 'GRN' },
          { key: 'order_number', label: 'Order' },
          { key: 'received_at', label: 'Received' },
          { key: 'received_by', label: 'Received by' },
          { key: 'notes', label: 'Notes' },
        ],
        detailLines: [
          { key: 'order_line', label: 'Order line' },
          { key: 'quantity_delivered', label: 'Delivered' },
          { key: 'quantity_accepted', label: 'Accepted' },
          { key: 'quantity_rejected', label: 'Rejected' },
          { key: 'quantity_damaged', label: 'Damaged' },
          { key: 'rejection_reason', label: 'Reason' },
        ],
        note: 'Receipts are recorded from the purchase order action; this tab keeps the full GRN history.',
      },
    ],
  },
  inventory: {
    title: 'Inventory',
    intro:
      'The permanent stock ledger. Balances are derived from recorded movements, never typed over; each posting is permission-checked by the API.',
    tabs: [
      {
        id: 'balances',
        label: 'Balances',
        singular: 'stock balance',
        endpoint: '/api/v1/stock-balances/',
        serverSearch: false,
        serverSort: false,
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'on_hand', label: 'On hand', kind: 'number' },
          { key: 'reserved', label: 'Reserved', kind: 'number' },
          { key: 'available', label: 'Available', kind: 'number' },
          { key: 'value', label: 'Value', kind: 'number' },
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'item_name', label: 'Item name' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'on_hand', label: 'On hand' },
          { key: 'reserved', label: 'Reserved' },
          { key: 'available', label: 'Available' },
          { key: 'unit_cost', label: 'Unit cost' },
          { key: 'value', label: 'Value' },
        ],
      },
      {
        id: 'movements',
        label: 'Movements',
        singular: 'movement',
        endpoint: '/api/v1/stock-movements/',
        serverSearch: true,
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'movement_type', label: 'Type' },
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'quantity', label: 'Quantity', kind: 'number' },
          { key: 'reference', label: 'Reference' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'movement_type', label: 'Type' },
          { key: 'item_code', label: 'Item' },
          { key: 'item_name', label: 'Item name' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'unit_cost', label: 'Unit cost' },
          { key: 'value_delta', label: 'Value change' },
          { key: 'reference', label: 'Reference' },
          { key: 'reason', label: 'Reason' },
          { key: 'movement_date', label: 'Movement date' },
          { key: 'occurred_at', label: 'Recorded at' },
        ],
      },
      {
        id: 'receipts',
        label: 'Stock receipts',
        singular: 'stock receipt',
        endpoint: '/api/v1/stock-receipts/',
        serverSearch: true,
        create: true,
        permission: 'inventory.receive_stock',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'supplier_name', label: 'Supplier' },
          { key: 'received_at', label: 'Received', kind: 'date' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'supplier_name', label: 'Supplier' },
          { key: 'received_at', label: 'Received' },
          { key: 'reference', label: 'Reference' },
          { key: 'notes', label: 'Notes' },
          { key: 'received_by', label: 'Received by' },
        ],
        detailLines: [
          { key: 'item_code', label: 'Item' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'unit_cost', label: 'Unit cost' },
        ],
        fields: [
          { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
          { key: 'supplier', label: 'Supplier', type: 'select', optionsEndpoint: '/api/v1/suppliers/' },
          { key: 'received_at', label: 'Received on', type: 'date', required: true },
          { key: 'reference', label: 'Reference', type: 'text' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        lines: {
          label: 'Received items',
          addLabel: 'Add item',
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'unit_cost', label: 'Unit cost', type: 'number', required: true, min: 0, step: '0.000001' },
          ],
        },
        actions: [],
        note: 'A receipt posts immutable stock movements. It needs the inventory.receive_stock permission.',
      },
      {
        id: 'alerts',
        label: 'Reorder alerts',
        singular: 'alert',
        endpoint: '/api/v1/reorder-alerts/',
        serverSearch: false,
        serverSort: false,
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'minimum_quantity', label: 'Minimum', kind: 'number' },
          { key: 'on_hand', label: 'On hand', kind: 'number' },
          { key: 'shortfall', label: 'Shortfall', kind: 'number' },
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'minimum_quantity', label: 'Minimum' },
          { key: 'reorder_quantity', label: 'Reorder quantity' },
          { key: 'on_hand', label: 'On hand' },
          { key: 'reserved', label: 'Reserved' },
          { key: 'available', label: 'Available' },
          { key: 'shortfall', label: 'Shortfall' },
        ],
      },
      {
        id: 'transfers',
        label: 'Transfers',
        singular: 'stock transfer',
        endpoint: '/api/v1/stock-transfers/',
        serverSearch: false,
        create: true,
        permission: 'inventory.transfer_stock',
        filters: [{ key: 'status', label: 'Status', options: TRANSFER_STATUS }],
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'from_warehouse_code', label: 'From' },
          { key: 'to_warehouse_code', label: 'To' },
          { key: 'status', label: 'Status', kind: 'status' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'from_warehouse_code', label: 'From warehouse' },
          { key: 'to_warehouse_code', label: 'To warehouse' },
          { key: 'status', label: 'Status' },
          { key: 'notes', label: 'Notes' },
          { key: 'dispatched_at', label: 'Dispatched' },
          { key: 'received_at', label: 'Received' },
        ],
        detailLines: [
          { key: 'item', label: 'Item' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'unit_cost', label: 'Unit cost' },
          { key: 'value', label: 'Value' },
        ],
        fields: [
          { key: 'from_warehouse', label: 'From warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
          { key: 'from_location', label: 'From location', type: 'select', optionsEndpoint: '/api/v1/storage-locations/' },
          { key: 'to_warehouse', label: 'To warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
          { key: 'to_location', label: 'To location', type: 'select', optionsEndpoint: '/api/v1/storage-locations/' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        lines: {
          label: 'Transfer lines',
          addLabel: 'Add transfer line',
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
            { key: 'serial', label: 'Serial', type: 'select', optionsEndpoint: '/api/v1/serial-numbers/' },
          ],
        },
        actions: [
          {
            id: 'dispatch',
            label: 'Dispatch',
            path: 'dispatch',
            permission: 'inventory.transfer_stock',
            confirm: 'Dispatch this transfer? Stock leaves the source warehouse now.',
            success: 'Transfer dispatched.',
            statuses: ['draft'],
          },
          {
            id: 'receive',
            label: 'Receive',
            path: 'receive',
            permission: 'inventory.transfer_stock',
            confirm: 'Confirm receipt into the destination warehouse?',
            success: 'Transfer received.',
            statuses: ['dispatched'],
          },
          {
            id: 'cancel',
            label: 'Cancel',
            path: 'cancel',
            permission: 'inventory.transfer_stock',
            confirm: 'Cancel this transfer? It must not have been dispatched.',
            success: 'Transfer cancelled.',
            statuses: ['draft'],
          },
        ],
      },
      {
        id: 'issues',
        label: 'Issues',
        singular: 'stock issue',
        endpoint: '/api/v1/stock-issues/',
        serverSearch: false,
        create: true,
        permission: 'inventory.issue_stock',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'project_code', label: 'Project' },
          { key: 'recipient', label: 'Recipient' },
          { key: 'issued_at', label: 'Issued', kind: 'date' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'project_code', label: 'Project' },
          { key: 'cost_centre', label: 'Cost centre' },
          { key: 'recipient', label: 'Recipient' },
          { key: 'issued_at', label: 'Issued at' },
          { key: 'issued_by', label: 'Issued by' },
          { key: 'notes', label: 'Notes' },
        ],
        detailLines: [
          { key: 'item', label: 'Item' },
          { key: 'warehouse', label: 'Warehouse' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'unit_cost', label: 'Unit cost' },
          { key: 'value', label: 'Value' },
        ],
        fields: [
          { key: 'project', label: 'Project', type: 'select', optionsEndpoint: '/api/v1/projects/' },
          { key: 'cost_centre', label: 'Cost centre', type: 'select', optionsEndpoint: '/api/v1/cost-centres/' },
          { key: 'recipient', label: 'Recipient', type: 'text' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        lines: {
          label: 'Issue lines',
          addLabel: 'Add issue line',
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
            { key: 'location', label: 'Location', type: 'select', optionsEndpoint: '/api/v1/storage-locations/' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
            { key: 'serial', label: 'Serial', type: 'select', optionsEndpoint: '/api/v1/serial-numbers/' },
            { key: 'reservation', label: 'Reservation', type: 'select', optionsEndpoint: '/api/v1/stock-reservations/' },
          ],
        },
        note: 'Issuing stock posts immutable outbound movements at the current valuation; negative stock is refused.',
      },
      {
        id: 'returns',
        label: 'Returns',
        singular: 'stock return',
        endpoint: '/api/v1/stock-returns/',
        serverSearch: false,
        create: true,
        permission: 'inventory.return_stock',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'project_code', label: 'Project' },
          { key: 'returned_at', label: 'Returned', kind: 'date' },
          { key: 'returned_by', label: 'Returned by' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'project_code', label: 'Project' },
          { key: 'returned_at', label: 'Returned at' },
          { key: 'returned_by', label: 'Returned by' },
          { key: 'notes', label: 'Notes' },
        ],
        detailLines: [
          { key: 'item', label: 'Item' },
          { key: 'warehouse', label: 'Warehouse' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'unit_cost', label: 'Unit cost' },
        ],
        fields: [
          { key: 'project', label: 'Project', type: 'select', optionsEndpoint: '/api/v1/projects/' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        lines: {
          label: 'Returned items',
          addLabel: 'Add returned item',
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'unit_cost', label: 'Unit cost', type: 'number', required: true, min: 0, step: '0.000001' },
            { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
            { key: 'serial', label: 'Serial', type: 'select', optionsEndpoint: '/api/v1/serial-numbers/' },
          ],
        },
      },
      {
        id: 'adjustments',
        label: 'Adjustments',
        singular: 'stock adjustment',
        endpoint: '/api/v1/stock-adjustments/',
        serverSearch: false,
        create: true,
        permission: 'inventory.adjust_stock',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'reason', label: 'Reason' },
          { key: 'adjusted_at', label: 'Adjusted', kind: 'date' },
          { key: 'adjusted_by', label: 'Adjusted by' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'reason', label: 'Reason' },
          { key: 'adjusted_at', label: 'Adjusted at' },
          { key: 'adjusted_by', label: 'Adjusted by' },
        ],
        detailLines: [
          { key: 'item', label: 'Item' },
          { key: 'warehouse', label: 'Warehouse' },
          { key: 'direction', label: 'Direction' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'unit_cost', label: 'Unit cost' },
        ],
        fields: [{ key: 'reason', label: 'Reason', type: 'text', required: true }],
        lines: {
          label: 'Adjustment lines',
          addLabel: 'Add adjustment line',
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            {
              key: 'direction',
              label: 'Direction',
              type: 'select',
              required: true,
              options: [
                { value: 'increase', label: 'Increase' },
                { value: 'decrease', label: 'Decrease' },
              ],
            },
            { key: 'unit_cost', label: 'Unit cost', type: 'number', min: 0, step: '0.000001' },
            { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
            { key: 'serial', label: 'Serial', type: 'select', optionsEndpoint: '/api/v1/serial-numbers/' },
          ],
        },
        note: 'Every adjustment needs a reason and is posted as an immutable movement.',
      },
      {
        id: 'damages',
        label: 'Damaged stock',
        singular: 'damage record',
        endpoint: '/api/v1/stock-damages/',
        serverSearch: false,
        create: true,
        permission: 'inventory.write_off_stock',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'reason', label: 'Reason' },
          { key: 'recorded_at', label: 'Recorded', kind: 'date' },
          { key: 'recorded_by', label: 'Recorded by' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'reason', label: 'Reason' },
          { key: 'recorded_at', label: 'Recorded at' },
          { key: 'recorded_by', label: 'Recorded by' },
        ],
        detailLines: [
          { key: 'item', label: 'Item' },
          { key: 'warehouse', label: 'Warehouse' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'value', label: 'Value' },
        ],
        fields: [{ key: 'reason', label: 'Reason', type: 'text', required: true }],
        lines: {
          label: 'Damaged lines',
          addLabel: 'Add damaged line',
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
            { key: 'location', label: 'Location', type: 'select', optionsEndpoint: '/api/v1/storage-locations/' },
            { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
            { key: 'serial', label: 'Serial', type: 'select', optionsEndpoint: '/api/v1/serial-numbers/' },
          ],
        },
      },
      {
        id: 'counts',
        label: 'Stock counts',
        singular: 'stock count',
        endpoint: '/api/v1/stock-counts/',
        serverSearch: false,
        create: true,
        permission: 'inventory.count_stock',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'status', label: 'Status', kind: 'status' },
          { key: 'counted_by', label: 'Counted by' },
          { key: 'posted_at', label: 'Posted', kind: 'date' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'status', label: 'Status' },
          { key: 'notes', label: 'Notes' },
          { key: 'counted_by', label: 'Counted by' },
          { key: 'posted_by', label: 'Posted by' },
          { key: 'posted_at', label: 'Posted at' },
        ],
        detailLines: [
          { key: 'item', label: 'Item' },
          { key: 'counted_quantity', label: 'Counted' },
          { key: 'system_quantity', label: 'System' },
          { key: 'variance', label: 'Variance' },
        ],
        fields: [
          { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        lines: {
          label: 'Counted lines',
          addLabel: 'Add counted line',
          fields: [
            { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
            { key: 'batch', label: 'Batch', type: 'select', optionsEndpoint: '/api/v1/item-batches/' },
            { key: 'counted_quantity', label: 'Counted quantity', type: 'number', required: true, min: 0, step: '0.0001' },
            { key: 'unit_cost', label: 'Unit cost', type: 'number', min: 0, step: '0.000001' },
          ],
        },
        actions: [
          {
            id: 'post',
            label: 'Post count',
            path: 'post',
            permission: 'inventory.count_stock',
            confirm: 'Post this count? Variances become ledger movements and cannot be edited.',
            success: 'Stock count posted.',
            statuses: ['draft'],
          },
        ],
      },
      {
        id: 'reservations',
        label: 'Reservations',
        singular: 'reservation',
        endpoint: '/api/v1/stock-reservations/',
        serverSearch: false,
        create: true,
        permission: 'inventory.reserve_stock',
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'quantity', label: 'Quantity', kind: 'number' },
          { key: 'quantity_fulfilled', label: 'Fulfilled', kind: 'number' },
          { key: 'status', label: 'Status', kind: 'status' },
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'project', label: 'Project' },
          { key: 'quantity', label: 'Quantity' },
          { key: 'quantity_fulfilled', label: 'Fulfilled' },
          { key: 'quantity_remaining', label: 'Remaining' },
          { key: 'status', label: 'Status' },
          { key: 'reference', label: 'Reference' },
          { key: 'notes', label: 'Notes' },
        ],
        fields: [
          { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
          { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
          { key: 'project', label: 'Project', type: 'select', optionsEndpoint: '/api/v1/projects/' },
          { key: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0, step: '0.0001' },
          { key: 'reference', label: 'Reference', type: 'text' },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        actions: [
          {
            id: 'release',
            label: 'Release',
            path: 'release',
            permission: 'inventory.reserve_stock',
            confirm: 'Release the remaining quantity on this reservation?',
            success: 'Reservation released.',
            statuses: ['open'],
          },
        ],
      },
      {
        id: 'reorder-levels',
        label: 'Reorder levels',
        singular: 'reorder level',
        endpoint: '/api/v1/reorder-levels/',
        serverSearch: false,
        create: true,
        edit: true,
        deactivate: true,
        columns: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'minimum_quantity', label: 'Minimum', kind: 'number' },
          { key: 'reorder_quantity', label: 'Reorder', kind: 'number' },
          ACTIVE,
        ],
        detail: [
          { key: 'item_code', label: 'Item' },
          { key: 'warehouse_code', label: 'Warehouse' },
          { key: 'minimum_quantity', label: 'Minimum quantity' },
          { key: 'reorder_quantity', label: 'Reorder quantity' },
          ACTIVE,
        ],
        fields: [
          { key: 'item', label: 'Item', type: 'select', required: true, optionsEndpoint: '/api/v1/catalogue-items/' },
          { key: 'warehouse', label: 'Warehouse', type: 'select', required: true, optionsEndpoint: '/api/v1/warehouses/' },
          { key: 'minimum_quantity', label: 'Minimum quantity', type: 'number', required: true, min: 0, step: '0.0001' },
          { key: 'reorder_quantity', label: 'Reorder quantity', type: 'number', required: true, min: 0, step: '0.0001' },
          ACTIVE_FIELD,
        ],
      },
    ],
  },
  accounting: {
    title: 'Accounting',
    intro:
      'The double-entry engine. No chart of accounts or posting rule is seeded: create only the accountant-approved accounts, then journals that the backend balances before they can be posted.',
    tabs: [
      {
        id: 'accounts',
        label: 'Chart of accounts',
        singular: 'account',
        endpoint: '/api/v1/accounts/',
        serverSearch: true,
        create: true,
        edit: true,
        permission: 'accounting.manage_accounts',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Account' },
          { key: 'account_type', label: 'Type' },
          { key: 'normal_balance', label: 'Normal balance' },
          { key: 'is_approved', label: 'Approved', kind: 'boolean' },
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'account_type', label: 'Type' },
          { key: 'normal_balance', label: 'Normal balance' },
          { key: 'parent', label: 'Parent account' },
          { key: 'description', label: 'Description' },
          { key: 'is_approved', label: 'Approved' },
          { key: 'approved_by', label: 'Approved by' },
          { key: 'approved_at', label: 'Approved at' },
          { key: 'is_active', label: 'Active' },
        ],
        fields: ACCOUNT_FIELDS,
        actions: [
          {
            id: 'approve',
            label: 'Approve account',
            path: 'approve',
            permission: 'accounting.approve_account',
            confirm: 'Approve this account for posting? Approval is a separate duty from creating it.',
            success: 'Account approved.',
          },
        ],
        note: 'Account creation needs accounting.manage_accounts; approval needs accounting.approve_account. Neither permission is assigned yet, so the API will refuse these actions.',
      },
      {
        id: 'journals',
        label: 'Journals',
        singular: 'journal',
        endpoint: '/api/v1/journals/',
        serverSearch: true,
        create: true,
        filters: [{ key: 'status', label: 'Status', options: JOURNAL_STATUS }],
        permission: 'accounting.create_journal',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'journal_date', label: 'Date', kind: 'date' },
          { key: 'description', label: 'Description' },
          { key: 'status', label: 'Status', kind: 'status' },
          { key: 'total_debit', label: 'Debit', kind: 'number' },
          { key: 'total_credit', label: 'Credit', kind: 'number' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'journal_date', label: 'Date' },
          { key: 'period', label: 'Period' },
          { key: 'description', label: 'Description' },
          { key: 'source_type', label: 'Source' },
          { key: 'reason', label: 'Reason' },
          { key: 'status', label: 'Status' },
          { key: 'total_debit', label: 'Total debit' },
          { key: 'total_credit', label: 'Total credit' },
          { key: 'created_by', label: 'Created by' },
          { key: 'submitted_by', label: 'Submitted by' },
          { key: 'approved_by', label: 'Approved by' },
          { key: 'posted_by', label: 'Posted by' },
          { key: 'posted_at', label: 'Posted at' },
        ],
        detailLines: [
          { key: 'account_code', label: 'Account' },
          { key: 'account_name', label: 'Account name' },
          { key: 'debit', label: 'Debit' },
          { key: 'credit', label: 'Credit' },
          { key: 'description', label: 'Description' },
        ],
        fields: [
          { key: 'journal_date', label: 'Journal date', type: 'date', required: true },
          { key: 'period', label: 'Accounting period', type: 'select', required: true, optionsEndpoint: '/api/v1/accounting-periods/' },
          { key: 'description', label: 'Description', type: 'text', required: true },
          {
            key: 'source_type',
            label: 'Source',
            type: 'select',
            options: [
              { value: 'manual', label: 'Manual' },
              { value: 'adjustment', label: 'Adjustment' },
            ],
          },
          { key: 'reason', label: 'Adjustment reason', type: 'text', help: 'Required for an adjustment journal.' },
        ],
        lines: {
          label: 'Journal lines',
          addLabel: 'Add line',
          fields: [
            { key: 'account', label: 'Account', type: 'select', required: true, optionsEndpoint: '/api/v1/accounts/' },
            { key: 'debit', label: 'Debit', type: 'number', min: 0, step: '0.01' },
            { key: 'credit', label: 'Credit', type: 'number', min: 0, step: '0.01' },
            { key: 'description', label: 'Line description', type: 'text' },
          ],
        },
        actions: [
          {
            id: 'submit',
            label: 'Submit',
            path: 'submit',
            permission: 'accounting.create_journal',
            confirm: 'Submit this journal for approval?',
            success: 'Journal submitted.',
            statuses: ['draft'],
          },
          {
            id: 'approve',
            label: 'Approve',
            path: 'approve',
            permission: 'accounting.approve_journal',
            confirm: 'Approve this journal?',
            success: 'Journal approved.',
            statuses: ['submitted'],
          },
          {
            id: 'post',
            label: 'Post',
            path: 'post',
            permission: 'accounting.post_journal',
            confirm: 'Post this journal to the ledger? Posted journals are immutable and can only be corrected by a reversal.',
            success: 'Journal posted.',
            statuses: ['approved'],
          },
          {
            id: 'reverse',
            label: 'Reverse',
            path: 'reverse',
            permission: 'accounting.reverse_journal',
            confirm: 'Create a linked reversal for this posted journal?',
            success: 'Reversal created.',
            statuses: ['posted'],
            reason: { label: 'Reversal reason', required: true },
          },
        ],
        note: 'Creation, approval and posting are three separate permissions; the backend enforces balancing, open periods and immutability.',
      },
      {
        id: 'fiscal-years',
        label: 'Fiscal years',
        singular: 'fiscal year',
        endpoint: '/api/v1/fiscal-years/',
        serverSearch: true,
        create: true,
        edit: true,
        permission: 'accounting.manage_fiscalyears',
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'start_date', label: 'Starts', kind: 'date' },
          { key: 'end_date', label: 'Ends', kind: 'date' },
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'start_date', label: 'Start date' },
          { key: 'end_date', label: 'End date' },
        ],
        fields: [
          { key: 'code', label: 'Code', type: 'text', required: true },
          { key: 'name', label: 'Name', type: 'text' },
          { key: 'start_date', label: 'Start date', type: 'date', required: true },
          { key: 'end_date', label: 'End date', type: 'date', required: true },
        ],
        actions: [
          {
            id: 'create-periods',
            label: 'Create monthly periods',
            path: 'create-periods',
            permission: 'accounting.manage_periods',
            confirm:
              'Create one accounting period for every calendar month in this fiscal year? Existing periods are kept.',
            success: 'Monthly periods created.',
          },
        ],
        note: 'No financial year is seeded; enter the year approved by the accountant.',
      },
      {
        id: 'periods',
        label: 'Accounting periods',
        singular: 'accounting period',
        endpoint: '/api/v1/accounting-periods/',
        serverSearch: true,
        create: true,
        edit: true,
        permission: 'accounting.manage_periods',
        filters: [{ key: 'status', label: 'Status', options: PERIOD_STATUS }],
        columns: [
          { key: 'fiscal_year', label: 'Fiscal year' },
          { key: 'name', label: 'Period' },
          { key: 'start_date', label: 'Starts', kind: 'date' },
          { key: 'end_date', label: 'Ends', kind: 'date' },
          { key: 'status', label: 'Status', kind: 'status' },
        ],
        detail: [
          { key: 'fiscal_year', label: 'Fiscal year' },
          { key: 'name', label: 'Name' },
          { key: 'start_date', label: 'Start date' },
          { key: 'end_date', label: 'End date' },
          { key: 'status', label: 'Status' },
          { key: 'closed_by', label: 'Closed by' },
          { key: 'closed_at', label: 'Closed at' },
        ],
        fields: [
          { key: 'fiscal_year', label: 'Fiscal year', type: 'select', required: true, optionsEndpoint: '/api/v1/fiscal-years/' },
          { key: 'name', label: 'Name', type: 'text', required: true, help: 'e.g. January 2026.' },
          { key: 'start_date', label: 'Start date', type: 'date', required: true },
          { key: 'end_date', label: 'End date', type: 'date', required: true },
        ],
        actions: [
          {
            id: 'close',
            label: 'Close period',
            path: 'close',
            permission: 'accounting.close_period',
            confirm: 'Close this period? It must have no unposted journals, and later journals cannot be dated inside it.',
            success: 'Period closed.',
            statuses: ['open'],
          },
        ],
      },
      {
        id: 'opening-balances',
        label: 'Opening balances',
        singular: 'opening balance',
        endpoint: '/api/v1/opening-balances/',
        serverSearch: false,
        create: true,
        permission: 'accounting.manage_openingbalance',
        columns: [
          { key: 'number', label: 'Number' },
          { key: 'fiscal_year', label: 'Fiscal year' },
          { key: 'as_of_date', label: 'As at', kind: 'date' },
          { key: 'status', label: 'Status', kind: 'status' },
        ],
        detail: [
          { key: 'number', label: 'Number' },
          { key: 'fiscal_year', label: 'Fiscal year' },
          { key: 'period', label: 'Period' },
          { key: 'as_of_date', label: 'As at' },
          { key: 'status', label: 'Status' },
          { key: 'notes', label: 'Notes' },
          { key: 'posted_journal_number', label: 'Posted journal' },
          { key: 'posted_by', label: 'Posted by' },
          { key: 'posted_at', label: 'Posted at' },
        ],
        detailLines: [
          { key: 'account_code', label: 'Account' },
          { key: 'account_name', label: 'Account name' },
          { key: 'debit', label: 'Debit' },
          { key: 'credit', label: 'Credit' },
          { key: 'description', label: 'Description' },
        ],
        fields: [
          { key: 'fiscal_year', label: 'Fiscal year', type: 'select', required: true, optionsEndpoint: '/api/v1/fiscal-years/' },
          { key: 'period', label: 'Period', type: 'select', required: true, optionsEndpoint: '/api/v1/accounting-periods/' },
          { key: 'as_of_date', label: 'As at', type: 'date', required: true },
          { key: 'notes', label: 'Notes', type: 'textarea' },
        ],
        lines: {
          label: 'Opening balance lines',
          addLabel: 'Add line',
          fields: [
            { key: 'account', label: 'Account', type: 'select', required: true, optionsEndpoint: '/api/v1/accounts/' },
            { key: 'debit', label: 'Debit', type: 'number', min: 0, step: '0.01' },
            { key: 'credit', label: 'Credit', type: 'number', min: 0, step: '0.01' },
            { key: 'description', label: 'Description', type: 'text' },
          ],
        },
        actions: [
          {
            id: 'post',
            label: 'Post opening balances',
            path: 'post',
            permission: 'accounting.post_journal',
            confirm: 'Post this opening balance? It becomes an immutable journal in the selected period.',
            success: 'Opening balances posted.',
            statuses: ['draft'],
          },
        ],
      },
      {
        id: 'rules',
        label: 'Posting rules',
        singular: 'posting rule',
        endpoint: '/api/v1/posting-rules/',
        serverSearch: true,
        columns: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Rule' },
          { key: 'is_active', label: 'Active', kind: 'boolean' },
          { key: 'approved_at', label: 'Approved' },
        ],
        detail: [
          { key: 'code', label: 'Code' },
          { key: 'name', label: 'Name' },
          { key: 'description', label: 'Description' },
          { key: 'is_active', label: 'Active' },
          { key: 'approved_by', label: 'Approved by' },
          { key: 'approved_at', label: 'Approved at' },
        ],
        detailLines: [
          { key: 'account_code', label: 'Account' },
          { key: 'direction', label: 'Direction' },
          { key: 'amount_key', label: 'Amount key' },
        ],
        note: 'Rules must follow the accountant-approved posting matrix; none is seeded.',
      },
    ],
  },
  invoicing: INVOICING_MODULE,
  banking: BANKING_MODULE,
  projects: PROJECTS_MODULE,
  services: SERVICES_MODULE,
  leasing: LEASING_MODULE,
};

export function initialValue(field: FieldConfig, row?: Row): string | number | boolean | null {
  if (row) {
    const current = row[field.key];
    if (typeof current === 'number' || typeof current === 'string' || typeof current === 'boolean') {
      return current;
    }
    if (current === null || current === undefined) {
      return field.type === 'checkbox' ? false : null;
    }
    // A related object: keep its id so the select can match it.
    if (typeof current === 'object' && current !== null && 'id' in current) {
      const id = (current as { id?: unknown }).id;
      if (typeof id === 'number' || typeof id === 'string') {
        return id;
      }
    }
    return null;
  }
  if (field.defaultValue !== undefined) {
    return field.defaultValue;
  }
  return field.type === 'checkbox' ? false : null;
}

export function columnText(row: Row, column: ColumnConfig): string {
  const value = row[column.key];
  return formatValue(value, column.kind);
}

export function formatValue(value: unknown, kind?: ColumnConfig['kind']): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'boolean' || kind === 'boolean') {
    return value === true || value === 'true' ? 'Yes' : 'No';
  }
  if (typeof value === 'object') {
    const record = value as Row;
    const label = record['name'] ?? record['legal_name'] ?? record['number'] ?? record['code'];
    return label === undefined || label === null ? '—' : String(label);
  }
  if (kind === 'date' && typeof value === 'string') {
    return value.slice(0, 10);
  }
  if (kind === 'status' && typeof value === 'string') {
    return value
      .split('_')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }
  return String(value);
}
