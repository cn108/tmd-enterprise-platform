import { expect, Page, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const evidence = join('..', 'docs', 'reports', 'evidence', 'adversarial');
const password = process.env['TMD_QA_PASSWORD'] ?? 'Tmd-Staging-2026!';

const workspaces = [
  ['Master data', '/master-data'],
  ['Procurement', '/procurement'],
  ['Inventory', '/inventory'],
  ['Accounting', '/accounting'],
  ['Invoices', '/invoicing'],
  ['Banking', '/banking'],
  ['Projects', '/projects'],
  ['Services', '/services'],
  ['Leasing', '/leasing'],
] as const;

interface TabEvidence {
  module: string;
  tab: string;
  heading: string;
  rows: number;
  create: 'opened' | 'disabled' | 'absent';
  sortClicked: boolean;
  viewOpened: boolean;
  controlsExercised: number;
}

async function signIn(page: Page): Promise<void> {
  await page.context().clearCookies();
  await page.goto('/login');
  await page.getByLabel('Email address').fill('admin@staging.tmd.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
}

test('administrator safely exercises every workspace tab, create dialog, sort and view', async ({
  page,
}) => {
  test.setTimeout(600_000);
  await mkdir(evidence, { recursive: true });
  await signIn(page);

  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message.slice(0, 500)));
  const results: TabEvidence[] = [];
  let controlsExercised = 0;

  for (const [module, path] of workspaces) {
    await page.goto(path, { waitUntil: 'domcontentloaded' });
    await page.locator('main h1').first().waitFor({ state: 'visible' });
    const tabCount = await page.locator('nav[aria-label="Sections"] button').count();
    expect(tabCount, `${module} has tabs`).toBeGreaterThan(0);

    for (let index = 0; index < tabCount; index += 1) {
      const tabButton = page.locator('nav[aria-label="Sections"] button').nth(index);
      const tab = (await tabButton.textContent())?.trim() ?? `tab-${index}`;
      await tabButton.click();
      controlsExercised += 1;
      await page.locator('main h2').first().waitFor({ state: 'visible' });
      await page.waitForTimeout(100);

      let create: TabEvidence['create'] = 'absent';
      const createButton = page.getByRole('button', { name: /^New / }).first();
      if ((await createButton.count()) > 0 && (await createButton.isVisible())) {
        if (await createButton.isDisabled()) {
          create = 'disabled';
        } else {
          await createButton.click();
          controlsExercised += 1;
          const dialog = page.locator('mat-dialog-container');
          await expect(dialog, `${module}/${tab} create dialog`).toBeVisible();
          create = 'opened';
          await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
          controlsExercised += 1;
          await expect(dialog).toHaveCount(0);
        }
      }

      let sortClicked = false;
      const sortButton = page.locator('th button.sort').first();
      if ((await sortButton.count()) > 0) {
        const response = page
          .waitForResponse(
            (item) => item.url().includes('/api/v1/') && item.request().method() === 'GET',
            { timeout: 5_000 },
          )
          .catch(() => null);
        await sortButton.click();
        controlsExercised += 1;
        await response;
        sortClicked = true;
      }

      let viewOpened = false;
      const viewButton = page
        .locator('tbody tr')
        .first()
        .getByRole('button', { name: 'View', exact: true });
      if ((await viewButton.count()) > 0 && (await viewButton.isVisible())) {
        await viewButton.click();
        controlsExercised += 1;
        const dialog = page.locator('mat-dialog-container');
        await expect(dialog, `${module}/${tab} detail dialog`).toBeVisible();
        await expect(dialog.getByRole('heading').first()).toBeVisible();
        viewOpened = true;
        await dialog.getByRole('button', { name: 'Close' }).click();
        controlsExercised += 1;
        await expect(dialog).toHaveCount(0);
      }

      results.push({
        module,
        tab,
        heading: (await page.locator('main h2').first().textContent())?.trim() ?? '',
        rows: await page.locator('tbody tr').count(),
        create,
        sortClicked,
        viewOpened,
        controlsExercised,
      });
    }
  }

  await page.goto('/');
  await page.screenshot({ path: join(evidence, 'interaction-sweep-complete.png') });
  await writeFile(
    join(evidence, 'browser-control-interactions.json'),
    JSON.stringify({ controlsExercised, tabs: results, pageErrors }, null, 2),
    'utf8',
  );

  expect(results.length).toBeGreaterThanOrEqual(100);
  expect(results.filter((result) => result.create === 'opened').length).toBeGreaterThan(20);
  expect(results.filter((result) => result.viewOpened).length).toBeGreaterThan(30);
  expect(pageErrors).toEqual([]);
});
