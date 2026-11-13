import { expect, Page, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const evidence = join('..', 'docs', 'reports', 'evidence', 'screenshots');
const password = 'Tmd-Staging-2026!';

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
}

async function shot(page: Page, name: string) {
  await mkdir(evidence, { recursive: true });
  await page.screenshot({ path: join(evidence, `${name}.png`), fullPage: true });
}

test.beforeAll(async () => {
  await mkdir(evidence, { recursive: true });
});

test('employee signs in and reaches every business module', async ({ page }) => {
  await signIn(page, 'management@staging.tmd.local');
  await shot(page, '01-dashboard-management');

  const modules = [
    ['Procurement', '/procurement'],
    ['Inventory', '/inventory'],
    ['Accounting', '/accounting'],
    ['Invoices', '/invoicing'],
    ['Banking', '/banking'],
    ['Projects', '/projects'],
    ['Services', '/services'],
    ['Leasing', '/leasing'],
    ['Reports', '/reports'],
    ['Master data', '/master-data'],
  ] as const;
  for (const [label, path] of modules) {
    await page.getByRole('link', { name: label, exact: true }).click();
    await page.waitForURL((url) => url.pathname.startsWith(path));
    await expect(page.locator('main h1').first()).toBeVisible();
  }
});

test('procurement, inventory, banking, services and leasing show seeded UAT records', async ({
  page,
}) => {
  await signIn(page, 'management@staging.tmd.local');

  await page.goto('/procurement');
  await expect(page.getByText('PR-2026-0001')).toBeVisible();
  await expect(page.getByText('Approved', { exact: true }).first()).toBeVisible();
  await shot(page, '02-procurement-purchase-request');

  await page.goto('/inventory');
  await expect(page.locator('main h1').first()).toBeVisible();
  await expect(page.getByText('ITEM-STG-PUMP').first()).toBeVisible();
  await expect(page.getByText('840000.00').first()).toBeVisible();
  await shot(page, '03-inventory-valuation');

  await page.goto('/banking');
  await expect(page.locator('main h1').first()).toBeVisible();
  await page.getByRole('button', { name: 'Reconciliations', exact: true }).click();
  await expect(page.getByText(/REC-2026-0001/).first()).toBeVisible();
  await shot(page, '04-banking-reconciliation');

  await page.goto('/services');
  await expect(page.locator('main h1').first()).toBeVisible();
  await page.getByRole('button', { name: 'Work orders', exact: true }).click();
  await expect(page.getByText(/WO-2026-0001/).first()).toBeVisible();
  await shot(page, '05-services-work-order');

  await page.goto('/leasing');
  await expect(page.locator('main h1').first()).toBeVisible();
  await page.getByRole('button', { name: 'Rental agreements', exact: true }).click();
  await expect(page.getByText(/RA-2026-0001/).first()).toBeVisible();
  await shot(page, '06-leasing-rental-agreement');
});

test('management report runs and exports CSV from posted journals', async ({ page }) => {
  await signIn(page, 'management@staging.tmd.local');
  await page.goto('/reports');
  await page.getByRole('button', { name: 'Financial statements' }).click();
  await page.getByRole('button', { name: 'Run report' }).click();
  await expect(page.getByText(/2,485,000/).first()).toBeVisible();
  await shot(page, '07-reports-financial-statements');

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV (Excel)' }).click();
  expect((await download).suggestedFilename()).toMatch(/\.csv$/i);
});

test('operational role has no formal financial report access', async ({ page }) => {
  await signIn(page, 'operations@staging.tmd.local');
  await page.goto('/reports');
  await expect(page.getByRole('button', { name: 'Financial statements' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Receivables' })).toBeVisible();
  await shot(page, '08-reports-operations-least-privilege');
});

test('auditor can inspect records but cannot create a purchase request', async ({ page }) => {
  await signIn(page, 'auditor@staging.tmd.local');
  await page.goto('/procurement');
  await expect(page.getByText('PR-2026-0001')).toBeVisible();
  await expect(page.getByRole('button', { name: /permission to create/ })).toBeDisabled();
  await shot(page, '09-procurement-auditor-read-only');
});
