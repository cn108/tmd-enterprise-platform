import { expect, Page, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const evidence = join('..', 'docs', 'reports', 'evidence', 'uiux');
const password = 'Tmd-Staging-2026!';

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/');
  await expect(page.getByRole('heading', { name: /Welcome,/ })).toBeVisible();
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: join(evidence, `${name}.png`), fullPage: true });
}

async function switchUser(page: Page, email: string) {
  await page.context().clearCookies();
  await signIn(page, email);
}

test.beforeAll(async () => {
  await mkdir(evidence, { recursive: true });
});

test('management dashboard shows company position and approvals without technical detail', async ({
  page,
}) => {
  await signIn(page, 'management@staging.tmd.local');
  await expect(page.getByText('Management overview')).toBeVisible();
  await expect(page.getByText('Outstanding customer invoices')).toBeVisible();
  await expect(page.getByText('₦2,500,000.00')).toBeVisible();
  await expect(page.getByText('Test environment')).toBeVisible();
  await expect(page.getByText('API reachable')).toHaveCount(0);
  await expect(page.getByText(/accounting\./)).toHaveCount(0);
  await expect(page.getByText(/invoicing\./)).toHaveCount(0);
  await shot(page, 'improved-dashboard-management');
});

test('role dashboards expose only their operational workspace', async ({ page }) => {
  await signIn(page, 'finance@staging.tmd.local');
  await expect(page.locator('.focus-title')).toHaveText('Finance workspace');
  await expect(page.getByText('Treasury workspace')).toBeVisible();
  await shot(page, 'dashboard-finance');

  await switchUser(page, 'procurement@staging.tmd.local');
  await expect(page.locator('.focus-title')).toHaveText('Procurement workspace');
  await expect(page.getByText('Financial overview')).toHaveCount(0);
  await expect(page.getByText('Outstanding customer invoices')).toHaveCount(0);
  await expect(page.getByText('Create purchase request')).toBeVisible();
  await expect(page.getByText('Upload bank statement')).toHaveCount(0);
  await expect(page.getByText('Payment allocated')).toHaveCount(0);
  await shot(page, 'dashboard-procurement');

  await switchUser(page, 'store@staging.tmd.local');
  await expect(page.locator('.focus-title')).toHaveText('Warehouse workspace');
  await expect(page.getByText('Stock value')).toBeVisible();
  await expect(page.getByText('Financial overview')).toHaveCount(0);
  await expect(page.getByText('Customer invoice approved')).toHaveCount(0);
  await shot(page, 'dashboard-warehouse');

  await switchUser(page, 'project@staging.tmd.local');
  await expect(page.locator('.focus-title')).toHaveText('Project workspace');
  await expect(page.getByRole('link', { name: /Your projects/ })).toBeVisible();
  await expect(page.getByText('Financial overview')).toHaveCount(0);
  await shot(page, 'dashboard-project');
});

test('accounting shows a polished read-only state and full controls to an authorised user', async ({
  page,
}) => {
  await signIn(page, 'management@staging.tmd.local');
  await page.goto('/accounting');
  await expect(page.getByText('View only')).toBeVisible();
  await expect(page.getByText('You have read-only access to this section.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'API reference' })).toHaveCount(0);
  const disabled = page.getByRole('button', { name: /You do not have permission to create/ });
  await expect(disabled).toBeDisabled();
  await expect(page.getByText(/accounting\.manage_accounts/)).toHaveCount(0);
  await shot(page, 'improved-accounting-readonly');

  await switchUser(page, 'admin@staging.tmd.local');
  await page.goto('/accounting');
  await expect(page.getByRole('button', { name: 'New account' })).toBeEnabled();
  await expect(page.getByText('View only')).toHaveCount(0);
  await expect(page.getByText('You have read-only access to this section.')).toHaveCount(0);
  await shot(page, 'accounting-authorized');
});

test('restricted page hides records and offers a route back to the dashboard', async ({ page }) => {
  await signIn(page, 'finance@staging.tmd.local');
  await page.goto('/administration');
  await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible();
  await expect(
    page.getByText('Your current account does not have permission to view access administration.'),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: 'Return to dashboard' })).toBeVisible();
  await expect(page.locator('table')).toHaveCount(0);
  await shot(page, 'access-restricted-administration');

  await page.getByRole('link', { name: 'Return to dashboard' }).click();
  await expect(page).toHaveURL(/\/$/);
});

test('auditor sees procurement records with no create control', async ({ page }) => {
  await signIn(page, 'auditor@staging.tmd.local');
  await page.goto('/procurement');
  await expect(page.getByText('PR-2026-0001')).toBeVisible();
  await expect(page.getByText('Limited actions')).toBeVisible();
  await expect(page.getByText('Some actions are restricted for your account.')).toBeVisible();
  await expect(page.getByRole('button', { name: /You do not have permission to create/ })).toBeDisabled();
  await expect(page.getByText(/procurement\./)).toHaveCount(0);
  await shot(page, 'procurement-auditor-readonly');
});
