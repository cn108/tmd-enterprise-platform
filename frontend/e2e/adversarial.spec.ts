import { expect, Page, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const evidence = join('..', 'docs', 'reports', 'evidence', 'adversarial');
const password = process.env['TMD_QA_PASSWORD'] ?? 'Tmd-Staging-2026!';

const roles = [
  ['System Administrator', 'admin@staging.tmd.local'],
  ['Management', 'management@staging.tmd.local'],
  ['Accountant', 'accountant@staging.tmd.local'],
  ['Finance Controller', 'controller@staging.tmd.local'],
  ['Finance Officer', 'finance@staging.tmd.local'],
  ['Procurement Officer', 'procurement@staging.tmd.local'],
  ['Project Manager', 'project@staging.tmd.local'],
  ['Storekeeper', 'store@staging.tmd.local'],
  ['Operations / HSE', 'operations@staging.tmd.local'],
  ['Auditor', 'auditor@staging.tmd.local'],
] as const;

const workspaces = [
  ['Dashboard', '/'],
  ['Master data', '/master-data'],
  ['Procurement', '/procurement'],
  ['Inventory', '/inventory'],
  ['Accounting', '/accounting'],
  ['Invoices', '/invoicing'],
  ['Banking', '/banking'],
  ['Projects', '/projects'],
  ['Services', '/services'],
  ['Leasing', '/leasing'],
  ['Reports', '/reports'],
  ['Administration', '/administration'],
] as const;

const directApis = [
  '/api/v1/access/users/',
  '/api/v1/access/roles/',
  '/api/v1/accounting-settings/',
  '/api/v1/trial-balance/',
  '/api/v1/company-bank-accounts/',
  '/api/v1/supplier-invoices/',
  '/api/v1/customer-invoices/',
  '/api/v1/purchase-orders/',
  '/api/v1/stock-movements/',
  '/api/v1/equipment/',
] as const;

interface PageEvidence {
  label: string;
  requestedPath: string;
  finalPath: string;
  heading: string;
  restricted: boolean;
  rows: number;
  tabs: number;
  controls: {
    total: number;
    buttons: number;
    links: number;
    inputs: number;
    selects: number;
    disabled: number;
    labels: string[];
  };
  consoleErrors: string[];
  pageErrors: string[];
}

interface RoleEvidence {
  role: string;
  email: string;
  focus: string;
  permissions: number;
  dashboardHeading: string;
  pages: PageEvidence[];
  directApis: Record<string, number>;
}

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

async function collectControls(page: Page): Promise<PageEvidence['controls']> {
  return page.evaluate(() => {
    const elements = Array.from(
      document.querySelectorAll(
        'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"]',
      ),
    );
    const visible = elements.filter((element) => {
      const style = window.getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0;
    });
    const describe = (element: Element) =>
      (
        element.getAttribute('aria-label') ||
        element.textContent ||
        (element as HTMLInputElement).value ||
        element.getAttribute('name') ||
        element.tagName
      )
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120);
    return {
      total: visible.length,
      buttons: visible.filter((element) => element.tagName === 'BUTTON').length,
      links: visible.filter((element) => element.tagName === 'A').length,
      inputs: visible.filter((element) => element.tagName === 'INPUT').length,
      selects: visible.filter((element) => element.tagName === 'SELECT').length,
      disabled: visible.filter(
        (element) => (element as HTMLButtonElement).disabled === true,
      ).length,
      labels: visible.map((element) => describe(element)).filter(Boolean),
    };
  });
}

test.beforeAll(async () => {
  await mkdir(evidence, { recursive: true });
});

test('all QA roles traverse every workspace and direct API', async ({ page }) => {
  test.setTimeout(600_000);
  const roleEvidence: RoleEvidence[] = [];

  for (const [role, email] of roles) {
    await signIn(page, email);
    const dashboardHeading =
      (await page.locator('main h1').first().textContent())?.trim() ?? '';
    const focus = (await page.locator('.focus-chip').textContent())?.trim() ?? '';
    await page.screenshot({
      path: join(evidence, `role-${role.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.png`),
      fullPage: false,
    });

    const me = await page.evaluate(async () => {
      const response = await fetch('/api/v1/auth/me/');
      return { status: response.status, body: response.ok ? await response.json() : null };
    });
    expect(me.status).toBe(200);
    const permissions = Array.isArray(me.body?.permissions) ? me.body.permissions.length : 0;

    const directApiStatuses: Record<string, number> = {};
    for (const endpoint of directApis) {
      directApiStatuses[endpoint] = await page.evaluate(async (url) => {
        const response = await fetch(url);
        return response.status;
      }, endpoint);
    }

    const pages: PageEvidence[] = [];
    for (const [label, path] of workspaces) {
      const consoleErrors: string[] = [];
      const pageErrors: string[] = [];
      const onConsole = (message: { type: () => string; text: () => string }) => {
        if (message.type() === 'error') {
          consoleErrors.push(message.text().slice(0, 500));
        }
      };
      const onPageError = (error: Error) => pageErrors.push(error.message.slice(0, 500));
      page.on('console', onConsole);
      page.on('pageerror', onPageError);

      await page.goto(path, { waitUntil: 'domcontentloaded' });
      await page
        .locator('main h1, app-access-restricted h1')
        .first()
        .waitFor({ state: 'visible', timeout: 15_000 });
      await page.waitForTimeout(150);

      const bodyText = await page.locator('body').innerText();
      const heading = (await page.locator('main h1').first().textContent())?.trim() ?? '';
      pages.push({
        label,
        requestedPath: path,
        finalPath: new URL(page.url()).pathname,
        heading,
        restricted:
          bodyText.includes('Access restricted') ||
          bodyText.includes('does not have permission to view access'),
        rows: await page.locator('tbody tr').count(),
        tabs: await page.locator('nav[aria-label="Sections"] button').count(),
        controls: await collectControls(page),
        consoleErrors,
        pageErrors,
      });
      page.off('console', onConsole);
      page.off('pageerror', onPageError);
    }

    roleEvidence.push({
      role,
      email,
      focus,
      permissions,
      dashboardHeading,
      pages,
      directApis: directApiStatuses,
    });
  }

  await writeFile(
    join(evidence, 'browser-role-matrix.json'),
    JSON.stringify({ roles: roleEvidence, workspaces, directApis }, null, 2),
    'utf8',
  );

  expect(roleEvidence).toHaveLength(roles.length);
  expect(roleEvidence.every((role) => role.permissions >= 0)).toBeTruthy();
  expect(roleEvidence.flatMap((role) => role.pages).some((page) => page.rows > 0)).toBeTruthy();
  expect(
    roleEvidence
      .flatMap((role) => role.pages)
      .every((page) => page.pageErrors.length === 0 && !page.heading.includes('500')),
  ).toBeTruthy();
});

test('administrator traverses every workspace tab', async ({ page }) => {
  test.setTimeout(300_000);
  await signIn(page, 'admin@staging.tmd.local');
  const results: Array<{
    module: string;
    tab: string;
    heading: string;
    rows: number;
    controls: PageEvidence['controls'];
    consoleErrors: string[];
  }> = [];

  for (const [label, path] of workspaces) {
    if (path === '/' || path === '/reports' || path === '/administration') {
      continue;
    }
    await page.goto(path, { waitUntil: 'domcontentloaded' });
    await page.locator('main h1').first().waitFor({ state: 'visible' });
    const count = await page.locator('nav[aria-label="Sections"] button').count();
    for (let index = 0; index < count; index += 1) {
      const tab = page.locator('nav[aria-label="Sections"] button').nth(index);
      const tabName = (await tab.textContent())?.trim() ?? '';
      await tab.click();
      await page.locator('main h2').first().waitFor({ state: 'visible' });
      await page.waitForTimeout(150);
      results.push({
        module: label,
        tab: tabName,
        heading: (await page.locator('main h2').first().textContent())?.trim() ?? '',
        rows: await page.locator('tbody tr').count(),
        controls: await collectControls(page),
        consoleErrors: [],
      });
    }
  }

  await writeFile(
    join(evidence, 'browser-tab-inventory.json'),
    JSON.stringify(results, null, 2),
    'utf8',
  );
  expect(results.length).toBeGreaterThan(20);
});
