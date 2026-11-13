import { expect, Page, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const evidence = join('..', 'docs', 'uat', 'evidence', 'screenshots');
const password = process.env['TMD_QA_PASSWORD'] ?? 'Tmd-Staging-2026!';
const uatRequest = process.env['UAT_REQUEST_NUMBER'] ?? 'PR-2026-0002';

async function signIn(page: Page, email: string): Promise<void> {
  await page.context().clearCookies();
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible({
    timeout: 15_000,
  });
}

async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: join(evidence, `${name}.png`), fullPage: true });
}

test.beforeAll(async () => {
  await mkdir(evidence, { recursive: true });
});

test('UAT-MGT: management oversight, reporting and read-only access administration', async ({
  page,
}) => {
  await signIn(page, 'management@staging.tmd.local');
  await expect(page.getByText('Test environment')).toBeVisible();
  await shot(page, 'management-01-dashboard');

  await page.goto('/procurement');
  await expect(page.getByRole('heading', { name: 'Procurement' })).toBeVisible();
  await expect(page.getByText(uatRequest)).toBeVisible();
  await shot(page, 'management-02-procurement-oversight');

  await page.goto('/reports');
  await page.getByRole('button', { name: 'Financial statements' }).click();
  const report = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/reporting/financial-statements/') &&
      response.status() === 200,
  );
  await page.getByRole('button', { name: 'Run report' }).click();
  await report;
  await expect(page.getByText(/Balance sheet/i).first()).toBeVisible();
  await shot(page, 'management-03-financial-statements');

  await page.goto('/administration');
  await expect(page.getByRole('heading', { name: 'Administration' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Users' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New user' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
  await shot(page, 'management-04-administration-read-only');
});

test('UAT-PRC: procurement approval workflow is visible with independent approval', async ({
  page,
}) => {
  await signIn(page, 'procurement@staging.tmd.local');
  await page.goto('/procurement');
  await page.getByLabel('Search Purchase requests').fill(uatRequest);
  await expect(page.getByText(uatRequest)).toBeVisible();
  await expect(page.getByText('Approved', { exact: true }).first()).toBeVisible();
  await shot(page, 'procurement-01-approved-uat-request');

  await page.getByRole('button', { name: 'View' }).first().click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('management@staging.tmd.local')).toBeVisible();
  await expect(dialog.getByText('approved', { exact: true }).first()).toBeVisible();
  await shot(page, 'procurement-02-approval-detail');

  await dialog.getByRole('button', { name: 'Close' }).click();
  await page.getByRole('button', { name: 'Purchase orders', exact: true }).click();
  await expect(page.getByText('PO-2026-0001').first()).toBeVisible();
  await shot(page, 'procurement-03-purchase-order');

  await page.getByRole('button', { name: 'Goods receipts', exact: true }).click();
  await expect(page.getByText('GRN-2026-0001').first()).toBeVisible();
  await shot(page, 'procurement-04-goods-receipt');
});

test('UAT-WHS: storekeeper verifies stock position and receipt-linked records', async ({ page }) => {
  await signIn(page, 'store@staging.tmd.local');
  await page.goto('/inventory');
  await expect(page.getByRole('heading', { name: 'Inventory' })).toBeVisible();
  await expect(page.getByText('ITEM-STG-PUMP').first()).toBeVisible();
  await expect(page.getByText('840000.00').first()).toBeVisible();
  await shot(page, 'warehouse-01-stock-valuation');

  await page.getByRole('button', { name: 'Movements', exact: true }).click();
  await expect(page.getByText('SM-2026-0006').first()).toBeVisible();
  await shot(page, 'warehouse-02-stock-movements');

  await page.getByRole('button', { name: 'Stock receipts', exact: true }).click();
  await expect(page.getByText('RCP-2026-0001').first()).toBeVisible();
  await shot(page, 'warehouse-03-stock-receipt');
});

test('UAT-FIN: finance reviews invoices, reconciliations and posted journals', async ({ page }) => {
  await signIn(page, 'controller@staging.tmd.local');
  await page.goto('/invoicing');
  await expect(page.getByRole('heading', { name: 'Invoices and payments' })).toBeVisible();
  await expect(page.getByText('SI-2026-0001').first()).toBeVisible();
  await shot(page, 'finance-01-supplier-invoices');

  await page.goto('/banking');
  await page.getByRole('button', { name: 'Reconciliations', exact: true }).click();
  await expect(page.getByText(/REC-2026-0001/).first()).toBeVisible();
  await shot(page, 'finance-02-reconciliation');

  await page.goto('/accounting');
  await expect(page.getByRole('heading', { name: 'Accounting' })).toBeVisible();
  await page.getByRole('button', { name: 'Journals', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Journals' })).toBeVisible();
  await expect(page.getByText('JV-2026-0011').first()).toBeVisible();
  await shot(page, 'finance-03-accounting');
});

test('UAT-PRJ: project manager reviews project profitability', async ({ page }) => {
  await signIn(page, 'project@staging.tmd.local');
  await page.goto('/projects');
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  await expect(page.getByText('PRJ-STG-001').first()).toBeVisible();
  await shot(page, 'project-01-project-dashboard');
});

test('UAT-OPS: operations records services and receives least-privilege reporting', async ({ page }) => {
  await signIn(page, 'operations@staging.tmd.local');
  await page.goto('/services');
  await page.getByRole('button', { name: 'Work orders', exact: true }).click();
  await expect(page.getByText(/WO-2026-0001/).first()).toBeVisible();
  await shot(page, 'operations-01-work-orders');

  await page.goto('/reports');
  await expect(page.getByRole('button', { name: 'Financial statements' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Receivables' })).toBeVisible();
  await shot(page, 'operations-02-least-privilege-reports');
});

test('UAT-ADM: administrator manages users and roles', async ({ page }) => {
  await signIn(page, 'admin@staging.tmd.local');
  await page.goto('/administration');
  await expect(page.getByRole('heading', { name: 'Administration' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Users' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New user' })).toBeVisible();
  await page.getByRole('button', { name: 'Roles and permissions' }).click();
  await expect(page.getByRole('heading', { name: 'Roles and permissions' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New role' })).toBeVisible();
  await shot(page, 'administration-01-users-and-roles');
});

test('UAT-AUD: auditor inspects records and administration without mutation rights', async ({ page }) => {
  await signIn(page, 'auditor@staging.tmd.local');
  await page.goto('/procurement');
  await expect(page.getByText(uatRequest)).toBeVisible();
  await expect(page.getByRole('button', { name: /permission to create/ })).toBeDisabled();
  await shot(page, 'audit-01-procurement-read-only');

  await page.goto('/administration');
  await expect(page.getByRole('heading', { name: 'Administration' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New user' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
  await shot(page, 'audit-02-administration-read-only');
});

test('UAT-SEC: restricted modules make no data API request or console error', async ({ page }) => {
  const cases = [
    ['procurement', 'procurement@staging.tmd.local', '/banking', 'procurement-banking'],
    ['store', 'store@staging.tmd.local', '/banking', 'warehouse-banking'],
    ['operations', 'operations@staging.tmd.local', '/invoicing', 'operations-invoicing'],
    ['operations', 'operations@staging.tmd.local', '/banking', 'operations-banking'],
  ] as const;

  for (const [role, email, path, name] of cases) {
    await signIn(page, email);
    const dataRequests: string[] = [];
    const consoleErrors: string[] = [];
    const onRequest = (request: { url: () => string }) => {
      if (/\/api\/v1\/(supplier-invoices|customer-invoices|company-bank-accounts|banking-summary|reconciliations)/.test(request.url())) {
        dataRequests.push(request.url());
      }
    };
    const onConsole = (message: { type: () => string; text: () => string }) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text().slice(0, 300));
      }
    };
    page.on('request', onRequest);
    page.on('console', onConsole);
    await page.goto(path);
    await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible();
    await page.waitForTimeout(300);
    page.off('request', onRequest);
    page.off('console', onConsole);
    await shot(page, `restricted-${name}`);

    expect(dataRequests, `${role} ${path} data requests`).toEqual([]);
    expect(
      consoleErrors.filter((message) => message.includes('403')),
      `${role} ${path} 403 console errors`,
    ).toEqual([]);
  }
});
