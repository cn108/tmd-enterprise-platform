#!/usr/bin/env node
/**
 * End-to-end verification of the portal's master-data slice against a real
 * Django/PostgreSQL stack.
 *
 * It reproduces exactly what the Angular screens do over HTTP: fetch a CSRF
 * token, sign in with a session cookie, create a supplier with the form's
 * payload, read it back through the list endpoint and deactivate it. It then
 * proves the backend refuses a privileged action the account does not hold, so
 * hiding a control is never the only defence.
 *
 * Usage (the caller creates the account and starts the server):
 *   TMD_BASE_URL=http://127.0.0.1:8001 \
 *   TMD_VERIFY_EMAIL=... TMD_VERIFY_PASSWORD=... \
 *   node scripts/verify-portal-master-data.mjs
 */
const BASE = process.env.TMD_BASE_URL ?? 'http://127.0.0.1:8001';
const EMAIL = process.env.TMD_VERIFY_EMAIL;
const PASSWORD = process.env.TMD_VERIFY_PASSWORD;

if (!EMAIL || !PASSWORD) {
  console.error('TMD_VERIFY_EMAIL and TMD_VERIFY_PASSWORD are required.');
  process.exit(2);
}

const cookies = new Map();
let failures = 0;

function cookieHeader() {
  return [...cookies.entries()].map(([name, value]) => `${name}=${value}`).join('; ');
}

function storeCookies(response) {
  const list =
    typeof response.headers.getSetCookie === 'function' ? response.headers.getSetCookie() : [];
  for (const raw of list) {
    const [pair] = raw.split(';');
    const index = pair.indexOf('=');
    if (index > 0) {
      cookies.set(pair.slice(0, index).trim(), pair.slice(index + 1).trim());
    }
  }
}

async function call(path, { method = 'GET', body, csrf } = {}) {
  const headers = { Accept: 'application/json', Cookie: cookieHeader() };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (csrf) {
    headers['X-CSRFToken'] = csrf;
  }
  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    redirect: 'manual',
  });
  storeCookies(response);
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }
  return { status: response.status, json, text };
}

function check(condition, message) {
  if (condition) {
    console.log(`  ok  ${message}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${message}`);
  }
}

const stamp = Date.now().toString(36);
const code = `ZZV-${stamp}`.toUpperCase();

console.log('Portal master-data flow');

const csrf = await call('/api/v1/auth/csrf/');
check(csrf.status === 200 && typeof csrf.json?.csrfToken === 'string', 'CSRF token issued');
const token = csrf.json?.csrfToken ?? '';

const login = await call('/api/v1/auth/login/', {
  method: 'POST',
  csrf: token,
  body: { email: EMAIL, password: PASSWORD },
});
check(login.status === 200, `sign-in accepted (status ${login.status})`);
check(Array.isArray(login.json?.permissions), 'session exposes a permissions array');

// Django rotates the CSRF token on sign-in; the pre-login header value is no
// longer valid, so the next request must echo the rotated cookie.
if (login.status !== 200) {
  console.log(login.text);
}
const rotatedToken = cookies.get('csrftoken') ?? token;

// The exact payload the "New supplier" form builds (blank text is '', not null).
const supplier = {
  code,
  legal_name: 'Portal verification supplier',
  trading_name: '',
  supplier_category: null,
  payment_terms_days: null,
  default_currency: 'NGN',
  due_diligence_status: '',
  email: 'verify@example.com',
  phone: '',
  website: '',
  notes: '',
  is_active: true,
};

const created = await call('/api/v1/suppliers/', {
  method: 'POST',
  csrf: rotatedToken,
  body: supplier,
});
check(created.status === 201, `supplier created (status ${created.status})`);
if (created.status !== 201) {
  console.log(created.text);
}
check(created.json?.code === code, 'backend echoed the submitted code');
const id = created.json?.id;

const search = await call(`/api/v1/suppliers/?q=${encodeURIComponent(code)}`);
check(search.status === 200, 'search request accepted');
const matches = Array.isArray(search.json)
  ? search.json
  : Array.isArray(search.json?.results)
    ? search.json.results
    : [];
check(matches.length === 1 && matches[0]?.id === id, 'record is returned by the list endpoint');

const deactivated = await call(`/api/v1/suppliers/${id}/`, {
  method: 'PATCH',
  csrf: rotatedToken,
  body: { is_active: false },
});
check(deactivated.status === 200 && deactivated.json?.is_active === false, 'deactivation persisted');
check(
  Array.isArray(deactivated.json?.is_active) === false &&
    deactivated.json?.is_active !== true,
  'record is not reported active after deactivation',
);

// Privileged action the verification account does not hold: the UI hides it,
// and the API must still refuse it.
const forbidden = await call('/api/v1/accounts/', {
  method: 'POST',
  csrf: rotatedToken,
  body: { code: '9999', name: 'Unapproved account', account_type: 'asset', normal_balance: 'debit' },
});
check(forbidden.status === 403, `unprivileged account creation rejected (status ${forbidden.status})`);

const duplicate = await call('/api/v1/suppliers/', {
  method: 'POST',
  csrf: rotatedToken,
  body: supplier,
});
check(duplicate.status === 400, `duplicate code rejected as a field error (status ${duplicate.status})`);

const logout = await call('/api/v1/auth/logout/', {
  method: 'POST',
  csrf: rotatedToken,
  body: {},
});
check(logout.status === 204 || logout.status === 200, 'sign-out accepted');

console.log(`\nCreated supplier id=${id} code=${code}`);

if (failures > 0) {
  console.error(`\n${failures} check(s) failed.`);
  process.exit(1);
}
console.log('All checks passed.');
