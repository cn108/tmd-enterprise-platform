import { expect, Page, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const evidence = join('..', 'docs', 'reports', 'evidence', 'adversarial');
const password = process.env['TMD_QA_PASSWORD'] ?? 'Tmd-Staging-2026!';
const admin = 'admin@staging.tmd.local';

test.use({ trace: 'on' });

async function signIn(page: Page): Promise<void> {
  await page.context().clearCookies();
  await page.goto('/login');
  await page.getByLabel('Email address').fill(admin);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
}

function recordPosts(page: Page): string[] {
  const posts: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/api/v1/')) {
      posts.push(request.url());
    }
  });
  return posts;
}

async function screenshot(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: join(evidence, `${name}.png`),
    fullPage: false,
  });
}

test.beforeAll(async () => {
  await mkdir(evidence, { recursive: true });
});

test('required fields, stored XSS and confirmation cancellation are handled safely', async ({
  page,
}) => {
  test.setTimeout(90_000);
  await signIn(page);
  const posts = recordPosts(page);
  const dialogs: string[] = [];
  page.on('dialog', async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.dismiss();
  });

  await page.goto('/master-data?tab=suppliers');
  await expect(page.getByRole('heading', { name: 'Suppliers' })).toBeVisible();

  await page.getByRole('button', { name: 'New supplier' }).click();
  await expect(page.getByRole('heading', { name: 'New supplier' })).toBeVisible();
  await page.getByRole('button', { name: 'Create', exact: true }).click();
  await expect(page.getByText('Check the highlighted fields.')).toBeVisible();
  await expect(page.getByText('Code is required.')).toBeVisible();
  await expect(page.getByText('Legal name is required.')).toBeVisible();
  expect(posts).toHaveLength(0);
  await screenshot(page, 'form-01-required-fields');

  const code = `QA-UI-XSS-${Date.now()}`;
  const payload = '<script>window.__qaXss=1</script> QA Supplier';
  await page.getByLabel('Code').fill(code);
  await page.getByLabel('Legal name').fill(payload);
  await page.getByLabel('Notes').fill('"><img src=x onerror="window.__qaXss=2">');
  await page.getByRole('button', { name: 'Create', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Supplier created.' })).toBeVisible();

  await page.getByLabel('Search Suppliers').fill(code);
  const row = page.locator('tbody tr', { hasText: code });
  await expect(row).toContainText(payload);
  expect(await page.evaluate(() => (window as { __qaXss?: number }).__qaXss)).toBeUndefined();
  expect(dialogs).toHaveLength(0);

  await row.getByRole('button', { name: 'View', exact: true }).click();
  const detail = page.locator('mat-dialog-container');
  await expect(detail.getByRole('heading', { name: new RegExp(code) })).toBeVisible();
  await expect(detail).toContainText(payload);
  await screenshot(page, 'form-02-escaped-xss-detail');
  await detail.getByRole('button', { name: 'Close' }).click();

  await row.getByRole('button', { name: 'Deactivate', exact: true }).click();
  const confirm = page.locator('mat-dialog-container');
  await expect(confirm.getByRole('heading', { name: 'Deactivate supplier' })).toBeVisible();
  await confirm.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(row.getByRole('button', { name: 'Deactivate', exact: true })).toBeVisible();

  await row.getByRole('button', { name: 'Deactivate', exact: true }).click();
  await confirm.getByRole('button', { name: 'Deactivate', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'deactivated.' })).toBeVisible();

  expect(await page.evaluate(() => (window as { __qaXss?: number }).__qaXss)).toBeUndefined();
  expect(dialogs).toHaveLength(0);
});

test('negative customer credit limit is blocked in the browser without a request', async ({
  page,
}) => {
  test.setTimeout(60_000);
  await signIn(page);
  const posts = recordPosts(page);

  await page.goto('/master-data?tab=customers');
  await expect(page.getByRole('heading', { name: 'Customers' })).toBeVisible();
  await page.getByRole('button', { name: 'New customer' }).click();
  await page.getByLabel('Code').fill(`QA-UI-NEG-${Date.now()}`);
  await page.getByLabel('Legal name').fill('QA Negative Credit UI');
  await page.getByLabel('Credit limit').fill('-1');
  await page.getByRole('button', { name: 'Create', exact: true }).click();

  await expect(page.getByText('Credit limit is too low.')).toBeVisible();
  expect(posts).toHaveLength(0);
  await screenshot(page, 'form-03-negative-credit-blocked');

  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  const discard = page.locator('mat-dialog-container');
  await expect(discard.getByRole('heading', { name: 'Discard changes?' })).toBeVisible();
  await discard.getByRole('button', { name: 'Discard changes' }).click();
  await expect(page.getByRole('heading', { name: 'New customer' })).toHaveCount(0);
});

test('SQL-like search is treated as text and cannot alter the supplier query', async ({ page }) => {
  test.setTimeout(60_000);
  await signIn(page);

  await page.goto('/master-data?tab=suppliers');
  await expect(page.getByRole('heading', { name: 'Suppliers' })).toBeVisible();

  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/suppliers/') &&
      response.request().method() === 'GET' &&
      response.url().includes('search='),
  );
  await page.getByLabel('Search Suppliers').fill("' OR 1=1 --");
  const response = await responsePromise;

  expect(response.status()).toBe(200);
  await expect(page.getByText('No records match this search.')).toBeVisible();
  await expect(page.locator('p.error')).toHaveCount(0);
  await screenshot(page, 'form-04-sql-like-search');
});

test('impossible project dates are refused with a field error', async ({ page }) => {
  test.setTimeout(60_000);
  await signIn(page);
  const posts = recordPosts(page);

  await page.goto('/master-data?tab=projects');
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  await page.getByRole('button', { name: 'New project' }).click();
  await page.getByLabel('Code').fill(`QA-UI-DATE-${Date.now()}`);
  await page.getByLabel('Name').fill('QA Impossible Dates');
  await page.getByLabel('Start date').fill('2027-05-10');
  await page.getByLabel('End date').fill('2027-05-01');
  await page.getByRole('button', { name: 'Create', exact: true }).click();

  await expect(page.getByText(/end date cannot precede the start date/i)).toBeVisible();
  expect(posts.some((url) => url.endsWith('/projects/'))).toBe(true);
  await screenshot(page, 'form-05-impossible-project-dates');
});

test('empty purchase request is blocked and an executable upload is refused', async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page);
  const posts = recordPosts(page);

  await page.goto('/procurement');
  await expect(page.getByRole('heading', { name: 'Procurement' })).toBeVisible();
  await page.getByRole('button', { name: 'New purchase request' }).click();
  await page.getByRole('button', { name: 'Create', exact: true }).click();
  await expect(page.getByText('Destination is required.')).toBeVisible();
  await expect(page.getByText('Check the highlighted fields.')).toBeVisible();
  expect(posts).toHaveLength(0);
  await screenshot(page, 'form-06-empty-purchase-request');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();

  await page.goto('/master-data?tab=documents');
  await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();
  await page.getByRole('button', { name: 'New document' }).click();
  await page.getByLabel('Title').fill('QA executable upload');
  const upload = test.info().outputPath('qa-upload.exe');
  await writeFile(upload, Buffer.from('MZ QA harmless placeholder'));
  await page.locator('input[type="file"]').setInputFiles(upload);
  await page.getByRole('button', { name: 'Create', exact: true }).click();

  await expect(page.getByText(/Files of type \.exe are not accepted/)).toBeVisible();
  expect(posts.filter((url) => url.endsWith('/documents/'))).toHaveLength(1);
  await screenshot(page, 'form-07-executable-upload-refused');
});
