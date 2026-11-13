/**
 * Administrator sweep: visits every module, every tab and every master-data
 * register as the platform administrator, then records console errors, failed
 * requests, visible error messages and any build-tracking copy that survived on
 * the page. It produces evidence rather than asserting each page, because the
 * point of the run is to find out what is broken.
 */
import { expect, Page, test } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const evidence = join('..', 'docs', 'reports', 'evidence');
const password = 'Tmd-Staging-2026!';

const MODULES: Array<[string, string]> = [
  ['Procurement', '/procurement'],
  ['Inventory', '/inventory'],
  ['Accounting', '/accounting'],
  ['Invoices and payments', '/invoicing'],
  ['Banking', '/banking'],
  ['Projects', '/projects'],
  ['Services', '/services'],
  ['Leasing', '/leasing'],
  ['Reports', '/reports'],
  ['Administration', '/administration'],
];

const MASTER_DATA = [
  'suppliers',
  'customers',
  'catalogue',
  'warehouses',
  'projects',
  'supplier-categories',
  'contacts',
  'addresses',
  'tax-registrations',
  'supplier-bank',
  'bank-changes',
  'compliance',
  'document-categories',
  'documents',
  'product-categories',
  'units',
  'manufacturers',
  'prices',
  'specifications',
  'batches',
  'serials',
  'certificates',
  'storage-locations',
  'departments',
  'cost-centres',
  'destinations',
  'project-locations',
  'contracts',
  'contract-revisions',
  'budgets',
  'milestones',
];

/** Copy that reads as a note to the developer rather than to the user. */
const SUSPICIOUS = [
  /stage\s*\d/i,
  /uat\s*synthetic/i,
  /test environment/i,
  /test mode/i,
  /test document/i,
  /provisional/i,
  /the backend/i,
  /backend/i,
  /endpoint/i,
  /\bapi\b/i,
  /not yet/i,
  /remains? blank/i,
  /no [a-z ]+ is (executed|posted)/i,
  /until (finance|management|activation|approved)/i,
  /synthetic/i,
];

type Finding = {
  page: string;
  tab?: string;
  consoleErrors: string[];
  failedRequests: string[];
  visibleErrors: string[];
  suspiciousCopy: string[];
  rows: number;
  heading: string;
};

async function signIn(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('admin@staging.tmd.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back/ })).toBeVisible();
}

// The sweep visits more than a hundred page states, so it only runs on demand:
// ADMIN_SWEEP=1 UAT_BASE_URL=http://127.0.0.1:49630 npx playwright test e2e/admin-sweep.spec.ts
test.skip(!process.env['ADMIN_SWEEP'], 'Set ADMIN_SWEEP=1 to run the full administrator sweep.');

test('administrator sweep of every page and feature', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  const findings: Finding[] = [];
  let current: Finding = {
    page: '',
    consoleErrors: [],
    failedRequests: [],
    visibleErrors: [],
    suspiciousCopy: [],
    rows: 0,
    heading: '',
  };

  page.on('console', (message) => {
    if (message.type() === 'error') {
      current.consoleErrors.push(message.text().slice(0, 300));
    }
  });
  page.on('pageerror', (error) => {
    current.consoleErrors.push(`uncaught: ${error.message}`.slice(0, 300));
  });
  page.on('response', (response) => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && url.includes('/api/')) {
      current.failedRequests.push(`${status} ${url.replace(/^https?:\/\/[^/]+/, '')}`);
    }
  });

  async function inspect(label: string, tab?: string) {
    await page.waitForTimeout(900);
    current.heading = (await page.locator('main h1').first().textContent().catch(() => '')) ?? '';
    const text = (await page.locator('main').first().innerText().catch(() => '')) ?? '';
    current.rows = await page.locator('main table tbody tr').count();
    current.visibleErrors = await page
      .locator('[role="alert"], .error, .notice')
      .allInnerTexts()
      .catch(() => []);
    current.suspiciousCopy = SUSPICIOUS.filter((pattern) => pattern.test(text)).map(
      (pattern) => pattern.source,
    );
    findings.push({ ...current, page: label, tab, consoleErrors: [...current.consoleErrors] });
    current = {
      page: label,
      consoleErrors: [],
      failedRequests: [],
      visibleErrors: [],
      suspiciousCopy: [],
      rows: 0,
      heading: '',
    };
  }

  await signIn(page);

  // Dashboard
  current.page = 'Dashboard';
  await page.waitForTimeout(1200);
  await inspect('Dashboard');

  // Modules: every tab.
  for (const [label, path] of MODULES) {
    await page.goto(path);
    await page.waitForTimeout(1200);
    const tabs = page.locator('nav[aria-label="Sections"] button');
    const tabCount = await tabs.count();
    if (tabCount === 0) {
      await inspect(label);
      continue;
    }
    for (let index = 0; index < tabCount; index += 1) {
      const tab = tabs.nth(index);
      const name = ((await tab.textContent()) ?? '').trim();
      await tab.click();
      await page.waitForTimeout(700);
      await inspect(label, name);
    }
  }

  // Every master-data register.
  for (const entity of MASTER_DATA) {
    await page.goto(`/master-data/${entity}`);
    await page.waitForTimeout(900);
    await inspect('Master data', entity);
  }

  await mkdir(evidence, { recursive: true });
  await writeFile(
    join(evidence, 'admin-sweep.json'),
    JSON.stringify({ generatedAt: new Date().toISOString(), findings }, null, 2),
  );

  const broken = findings.filter(
    (finding) =>
      finding.consoleErrors.length ||
      finding.failedRequests.length ||
      (finding.visibleErrors ?? []).some((message) => message.trim().length > 0),
  );
  // eslint-disable-next-line no-console
  console.log(
    `SWEEP pages=${findings.length} broken=${broken.length} suspicious=${findings.filter((f) => f.suspiciousCopy.length).length}`,
  );
  for (const finding of broken) {
    // eslint-disable-next-line no-console
    console.log(
      `BROKEN ${finding.page}${finding.tab ? ' / ' + finding.tab : ''}: ` +
        JSON.stringify({
          consoleErrors: finding.consoleErrors,
          failedRequests: finding.failedRequests,
          visibleErrors: finding.visibleErrors,
        }),
    );
  }
});
