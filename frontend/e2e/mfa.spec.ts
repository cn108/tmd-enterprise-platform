import { createHmac } from 'node:crypto';

import { expect, Page, test, APIRequestContext } from '@playwright/test';

const password = process.env['TMD_QA_PASSWORD'] ?? 'Tmd-Staging-2026!';
const adminEmail = process.env['TMD_QA_ADMIN_EMAIL'] ?? 'admin@staging.tmd.local';
const mfaEmail = `mfa.e2e.${Date.now()}@staging.tmd.local`;

function decodeBase32(value: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const character of value.replace(/=+$/, '').toUpperCase()) {
    const index = alphabet.indexOf(character);
    if (index < 0) {
      throw new Error('Invalid base32 secret');
    }
    bits += index.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let offset = 0; offset + 8 <= bits.length; offset += 8) {
    bytes.push(Number.parseInt(bits.slice(offset, offset + 8), 2));
  }
  return Buffer.from(bytes);
}

function totp(secret: string, stepOffset = 0): string {
  const step = Math.floor(Date.now() / 1000 / 30) + stepOffset;
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac('sha1', decodeBase32(secret)).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const value = digest.readUInt32BE(offset) & 0x7fffffff;
  return `${value % 1_000_000}`.padStart(6, '0');
}

async function csrfToken(api: APIRequestContext): Promise<string> {
  await api.get('/api/v1/auth/csrf/');
  const cookie = (await api.storageState()).cookies.find((item) => item.name === 'csrftoken');
  if (!cookie) {
    throw new Error('CSRF cookie was not issued');
  }
  return cookie.value;
}

async function signIn(page: Page, email: string): Promise<void> {
  await page.context().clearCookies();
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

test('MFA enrolment, TOTP login, recovery code and replay refusal', async ({ page, request }) => {
  test.setTimeout(90_000);

  const login = await request.post('/api/v1/auth/login/', {
    data: { email: adminEmail, password },
  });
  expect(login.ok()).toBeTruthy();
  const csrf = await csrfToken(request);
  const create = await request.post('/api/v1/access/users/', {
    headers: { 'X-CSRFToken': csrf },
    data: {
      email: mfaEmail,
      full_name: 'MFA E2E User',
      password,
      is_active: true,
      must_change_password: false,
      mfa_required: true,
      roles: ['Finance Officer'],
    },
  });
  expect(create.status()).toBe(201);
  const userId = (await create.json()).id as number;

  try {
    await signIn(page, mfaEmail);
    await expect(page.getByRole('heading', { name: 'Set up your authenticator' })).toBeVisible();
    const secret = await page.locator('.mfa__details code').first().innerText();
    const recoveryCode = await page.locator('.mfa__recovery code').first().innerText();
    expect(secret.length).toBeGreaterThan(20);
    expect(recoveryCode).toMatch(/^[A-F0-9]{8}-[A-F0-9]{8}$/);

    await page.getByLabel('Authenticator or recovery code').fill(totp(secret));
    await page.getByRole('button', { name: 'Confirm and sign in' }).click();
    await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();

    // The current TOTP step was consumed by confirmation. Use the next accepted
    // step so the login challenge cannot be satisfied by a replayed code.
    await signIn(page, mfaEmail);
    await expect(page.getByRole('heading', { name: "Verify it's you" })).toBeVisible();
    await page.getByLabel('Authenticator or recovery code').fill(totp(secret, 1));
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();

    await signIn(page, mfaEmail);
    await page.getByLabel('Authenticator or recovery code').fill(recoveryCode);
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();

    await signIn(page, mfaEmail);
    await page.getByLabel('Authenticator or recovery code').fill(recoveryCode);
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByText(/not valid/i)).toBeVisible();
  } finally {
    const currentCsrf = await csrfToken(request);
    await request.patch(`/api/v1/access/users/${userId}/`, {
      headers: { 'X-CSRFToken': currentCsrf },
      data: { is_active: false },
    });
  }
});
