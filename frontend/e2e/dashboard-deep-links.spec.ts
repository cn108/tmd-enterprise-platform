import { expect, Page, test } from '@playwright/test';

const password = process.env['TMD_QA_PASSWORD'] ?? 'Tmd-Staging-2026!';

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

test('dashboard KPI and quick-action links open the intended workspace tabs', async ({ page }) => {
  await signIn(page, 'admin@staging.tmd.local');

  const outstandingCustomers = page
    .locator('article.kpi')
    .filter({ has: page.getByRole('heading', { name: 'Outstanding Customer Invoices' }) });
  await outstandingCustomers.getByRole('link', { name: 'View details' }).click();

  await expect(page).toHaveURL(/\/invoicing\?tab=customer-invoices&status=approved$/);
  await expect(page.getByRole('heading', { name: 'Invoices and payments' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Customer invoices' })).toHaveAttribute(
    'aria-current',
    'page',
  );

  await page.goto('/');
  await page.getByRole('link', { name: 'Create supplier invoice' }).click();

  await expect(page).toHaveURL(/\/invoicing\?tab=supplier-invoices&new=1$/);
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'New supplier invoice' })).toBeVisible();
});
