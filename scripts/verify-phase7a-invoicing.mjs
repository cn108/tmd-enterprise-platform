#!/usr/bin/env node
/**
 * Stage 7A end-to-end verification against a real Django/PostgreSQL stack.
 *
 * It signs in through the session API, creates a test supplier/customer and tax
 * codes, creates and approves an invoice, allocates a recorded payment, checks
 * the PDF and proves that Stage 7B posting/activation and NRS remain refused.
 *
 * Usage:
 *   TMD_BASE_URL=http://127.0.0.1:8000 \
 *   TMD_VERIFY_EMAIL=admin@tmd.local TMD_VERIFY_PASSWORD=... \
 *   TMD_APPROVER_EMAIL=e2e.approver@tmd.local TMD_APPROVER_PASSWORD=... \
 *   node scripts/verify-phase7a-invoicing.mjs
 */
const BASE = process.env.TMD_BASE_URL ?? 'http://127.0.0.1:8000';
const EMAIL = process.env.TMD_VERIFY_EMAIL;
const PASSWORD = process.env.TMD_VERIFY_PASSWORD;
const APPROVER_EMAIL = process.env.TMD_APPROVER_EMAIL;
const APPROVER_PASSWORD = process.env.TMD_APPROVER_PASSWORD;

if (!EMAIL || !PASSWORD || !APPROVER_EMAIL || !APPROVER_PASSWORD) {
  console.error('Creator and approver credentials are required.');
  process.exit(2);
}

class Session {
  cookies = new Map();

  header() {
    return [...this.cookies.entries()].map(([name, value]) => `${name}=${value}`).join('; ');
  }

  store(response) {
    const list =
      typeof response.headers.getSetCookie === 'function' ? response.headers.getSetCookie() : [];
    for (const raw of list) {
      const [pair] = raw.split(';');
      const index = pair.indexOf('=');
      if (index > 0) {
        this.cookies.set(pair.slice(0, index).trim(), pair.slice(index + 1).trim());
      }
    }
  }

  async call(path, { method = 'GET', body, csrf, raw = false, headers: extra = {} } = {}) {
    const headers = { Accept: 'application/json', Cookie: this.header() };
    Object.assign(headers, extra);
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (csrf) headers['X-CSRFToken'] = csrf;
    const response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      redirect: 'manual',
    });
    this.store(response);
    if (raw) {
      return { status: response.status, headers: response.headers, body: await response.arrayBuffer() };
    }
    const text = await response.text();
    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }
    return { status: response.status, json, text, headers: response.headers };
  }

  async login(email, password) {
    const csrf = await this.call('/api/v1/auth/csrf/');
    const token = csrf.json?.csrfToken ?? '';
    const login = await this.call('/api/v1/auth/login/', {
      method: 'POST',
      csrf: token,
      body: { email, password },
    });
    if (login.status !== 200) {
      console.log(login.text);
      throw new Error(`Sign-in failed for ${email}: ${login.status}`);
    }
    this.csrf = this.cookies.get('csrftoken') ?? token;
    return login.json;
  }
}

let failures = 0;
function check(condition, message) {
  if (condition) console.log(`  ok  ${message}`);
  else {
    failures += 1;
    console.log(`  FAIL ${message}`);
  }
}

const stamp = Date.now().toString(36).toUpperCase();
const creator = new Session();
const approver = new Session();

console.log('Phase 7A invoice and payment flow');
const creatorSession = await creator.login(EMAIL, PASSWORD);
const approverSession = await approver.login(APPROVER_EMAIL, APPROVER_PASSWORD);
check(Array.isArray(creatorSession.permissions), 'creator session exposes permissions');
check(Array.isArray(approverSession.permissions), 'approver session exposes permissions');

const supplierCode = `E2E-SUP-${stamp}`;
const customerCode = `E2E-CUS-${stamp}`;
const vatCode = `E2E-VAT-${stamp}`;
const whtCode = `E2E-WHT-${stamp}`;

const supplier = await creator.call('/api/v1/suppliers/', {
  method: 'POST',
  csrf: creator.csrf,
  body: {
    code: supplierCode,
    legal_name: `E2E supplier ${stamp}`,
    trading_name: '',
    supplier_category: null,
    payment_terms_days: 30,
    default_currency: 'NGN',
    due_diligence_status: 'test',
    email: 'e2e@example.com',
    phone: '',
    website: '',
    notes: 'Stage 7A verification record',
    is_active: true,
  },
});
check(supplier.status === 201, `supplier created (${supplier.status})`);

const customer = await creator.call('/api/v1/customers/', {
  method: 'POST',
  csrf: creator.csrf,
  body: {
    code: customerCode,
    legal_name: `E2E customer ${stamp}`,
    trading_name: '',
    payment_terms_days: 30,
    default_currency: 'NGN',
    credit_limit: null,
    credit_hold: false,
    email: 'e2e-customer@example.com',
    phone: '',
    website: '',
    notes: 'Stage 7A verification record',
    is_active: true,
  },
});
check(customer.status === 201, `customer created (${customer.status})`);

const vat = await creator.call('/api/v1/governance/tax-configuration/', {
  method: 'POST',
  csrf: creator.csrf,
  body: {
    code: vatCode,
    name: 'E2E VAT',
    tax_type: 'vat',
    rate: '7.5000',
    jurisdiction: 'Nigeria',
    effective_from: '2026-01-01',
  },
});
check(vat.status === 201, `VAT configuration created (${vat.status})`);
if (vat.status !== 201) console.log(vat.text);
const wht = await creator.call('/api/v1/governance/tax-configuration/', {
  method: 'POST',
  csrf: creator.csrf,
  body: {
    code: whtCode,
    name: 'E2E WHT',
    tax_type: 'wht',
    rate: '5.0000',
    jurisdiction: 'Nigeria',
    effective_from: '2026-01-01',
  },
});
check(wht.status === 201, `WHT configuration created (${wht.status})`);
if (wht.status !== 201) console.log(wht.text);

const invoice = await creator.call('/api/v1/supplier-invoices/', {
  method: 'POST',
  csrf: creator.csrf,
  body: {
    supplier: supplier.json.id,
    supplier_invoice_number: `SUP-${stamp}`,
    invoice_date: '2026-11-12',
    due_date: '2026-12-12',
    currency: 'NGN',
    match_exempt_reason: 'E2E service invoice without a purchase order',
    lines: [
      {
        description: 'E2E service',
        quantity: '2.0000',
        unit_price: '100.000000',
        vat_tax: vat.json.id,
        wht_tax: wht.json.id,
      },
    ],
  },
});
check(invoice.status === 201, `supplier invoice created (${invoice.status})`);
if (invoice.status !== 201) console.log(invoice.text);
check(invoice.json?.subtotal === '200.00', 'subtotal calculated');
check(invoice.json?.vat_total === '15.00', 'VAT calculated from configuration');
check(invoice.json?.wht_total === '10.00', 'WHT calculated from configuration');
check(invoice.json?.payment_due === '205.00', 'payment due nets WHT');
check(invoice.json?.test_document === true, 'invoice is explicitly a test document');

const invoiceId = invoice.json?.id;
const submitted = await creator.call(`/api/v1/supplier-invoices/${invoiceId}/submit/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: {},
});
check(submitted.status === 200 && submitted.json?.status === 'submitted', 'invoice submitted');

const ownApproval = await creator.call(`/api/v1/supplier-invoices/${invoiceId}/approve/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: {},
});
check(ownApproval.status === 409, 'creator cannot approve their own invoice');

const approved = await approver.call(`/api/v1/supplier-invoices/${invoiceId}/approve/`, {
  method: 'POST',
  csrf: approver.csrf,
  body: {},
});
check(approved.status === 200 && approved.json?.status === 'approved', 'independent approval succeeds');

const pdf = await creator.call(`/api/v1/supplier-invoices/${invoiceId}/pdf/`, { raw: true });
const pdfText = Buffer.from(pdf.body).toString('latin1');
check(pdf.status === 200, 'invoice PDF returned');
check(pdf.headers.get('content-type')?.includes('application/pdf'), 'PDF content type');
check(pdfText.startsWith('%PDF'), 'PDF signature');
check(pdfText.includes('TEST DOCUMENT'), 'PDF carries test banner');

const payment = await creator.call('/api/v1/supplier-payments/', {
  method: 'POST',
  csrf: creator.csrf,
  body: {
    supplier: supplier.json.id,
    payment_date: '2026-11-14',
    currency: 'NGN',
    amount: '205',
    method: 'bank_transfer',
    external_reference: `E2E-REF-${stamp}`,
  },
});
check(payment.status === 201, `payment record created (${payment.status})`);
const paymentId = payment.json?.id;
await creator.call(`/api/v1/supplier-payments/${paymentId}/submit/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: {},
});
const paymentApproved = await approver.call(`/api/v1/supplier-payments/${paymentId}/approve/`, {
  method: 'POST',
  csrf: approver.csrf,
  body: {},
});
check(paymentApproved.status === 200, 'payment independently approved');
const recorded = await creator.call(`/api/v1/supplier-payments/${paymentId}/record/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: {},
  headers: { 'Idempotency-Key': `e2e-${stamp}` },
});
check(recorded.status === 200, 'external payment recorded');
check(recorded.json?.execution_status === 'recorded', 'execution status is recorded, not executed');

const allocation = await creator.call(`/api/v1/supplier-payments/${paymentId}/allocate/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: { supplier_invoice: invoiceId, amount: '205' },
});
check(allocation.status === 201, `payment allocated (${allocation.status})`);
const refreshed = await creator.call(`/api/v1/supplier-invoices/${invoiceId}/`);
check(refreshed.json?.payment_status === 'paid', 'invoice reports paid after allocation');

const posting = await creator.call(`/api/v1/supplier-invoices/${invoiceId}/post/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: {},
});
check(posting.status === 409 && posting.text.includes('Stage 7B'), 'ledger posting remains blocked');

const settings = await creator.call('/api/v1/invoice-settings/');
const activation = await creator.call(`/api/v1/invoice-settings/${settings.json?.[0]?.id}/activate/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: { activation_checklist: {}, notes: 'E2E must not activate.' },
});
check(activation.status === 409, 'activation remains blocked');

const customerInvoice = await creator.call('/api/v1/customer-invoices/', {
  method: 'POST',
  csrf: creator.csrf,
  body: {
    customer: customer.json.id,
    invoice_date: '2026-11-12',
    due_date: '2026-12-12',
    currency: 'NGN',
    lines: [
      { description: 'E2E customer service', quantity: '1.0000', unit_price: '500.000000' },
    ],
  },
});
check(customerInvoice.status === 201, `customer invoice drafted (${customerInvoice.status})`);
check(customerInvoice.json?.test_document === true, 'customer invoice is a test document');
const customerInvoiceId = customerInvoice.json?.id;
await creator.call(`/api/v1/customer-invoices/${customerInvoiceId}/submit/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: {},
});
const customerApproved = await approver.call(
  `/api/v1/customer-invoices/${customerInvoiceId}/approve/`,
  { method: 'POST', csrf: approver.csrf, body: {} },
);
check(customerApproved.status === 200, 'customer invoice approved');
const nrs = await creator.call(`/api/v1/customer-invoices/${customerInvoiceId}/submit-nrs/`, {
  method: 'POST',
  csrf: creator.csrf,
  body: {},
});
check(nrs.status === 409, 'NRS submission remains disabled');

console.log(`\nCreated E2E supplier=${supplierCode}, customer=${customerCode}, invoice=${invoice.json?.number}`);
if (failures > 0) {
  console.error(`\n${failures} check(s) failed.`);
  process.exit(1);
}
console.log('All Stage 7A checks passed.');
