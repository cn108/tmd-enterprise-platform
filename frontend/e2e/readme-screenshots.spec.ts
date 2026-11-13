/**
 * Captures the screenshots used in README.md. Run on demand against a signed-in
 * staging portal:
 *
 *   README_SHOTS=1 UAT_BASE_URL=http://127.0.0.1:49630 npx playwright test e2e/readme-screenshots.spec.ts
 */
import { expect, Page, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const images = join('..', 'docs', 'images');
const password = 'Tmd-Staging-2026!';

async function signIn(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('admin@staging.tmd.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
}

async function capture(page: Page, path: string, name: string) {
  await page.goto(path);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(images, `${name}.png`), fullPage: true });
}

test.skip(!process.env['README_SHOTS'], 'Set README_SHOTS=1 to capture README screenshots.');

test('capture README screenshots', async ({ page }) => {
  test.setTimeout(5 * 60_000);
  await page.setViewportSize({ width: 1440, height: 960 });
  await mkdir(images, { recursive: true });
  await signIn(page);

  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(images, 'dashboard.png'), fullPage: true });
  await capture(page, '/procurement', 'procurement');
  await capture(page, '/invoicing', 'invoices');
  await capture(page, '/banking', 'banking');
  await capture(page, '/reports', 'reports');
  await capture(page, '/master-data/suppliers', 'master-data');
  await capture(page, '/administration', 'administration');
});
