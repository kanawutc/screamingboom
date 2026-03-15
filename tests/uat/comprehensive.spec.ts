import { test, expect, type Page } from '@playwright/test';

const API = '/api/v1';

/** Helper: make a JSON API request from within the browser context. */
async function api(page: Page, method: string, path: string, body?: unknown) {
  return page.evaluate(
    async ({ method, url, body }) => {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (res.status === 204) return null;
      return res.json();
    },
    { method, url: `${API}${path}`, body },
  );
}

/** Helper: poll crawl status until terminal (or timeout). */
async function waitForCrawlDone(page: Page, crawlId: string, timeoutMs = 180_000) {
  const terminal = ['completed', 'cancelled', 'failed'];
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const crawl = await api(page, 'GET', `/crawls/${crawlId}`);
    if (terminal.includes(crawl.status)) return crawl;
    await page.waitForTimeout(2000);
  }
  throw new Error(`Crawl ${crawlId} did not complete within ${timeoutMs}ms`);
}

test.describe.serial('SEO Spider — Comprehensive UAT', () => {
  let spiderCrawlId: string;
  let listCrawlId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage({ baseURL: 'http://localhost' });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Stop any active crawls
    const crawlsResp = await api(page, 'GET', '/crawls?limit=200');
    const crawls = crawlsResp?.items ?? crawlsResp ?? [];
    for (const c of crawls) {
      if (['crawling', 'queued', 'paused', 'completing'].includes(c.status)) {
        await api(page, 'POST', `/crawls/${c.id}/stop`).catch(() => {});
      }
    }
    // Wait a moment for stops to settle
    await page.waitForTimeout(2000);

    // Delete all crawls
    const crawlsResp2 = await api(page, 'GET', '/crawls?limit=200');
    const crawls2 = crawlsResp2?.items ?? crawlsResp2 ?? [];
    for (const c of crawls2) {
      await api(page, 'DELETE', `/crawls/${c.id}`).catch(() => {});
    }

    // Delete all projects
    const projResp = await api(page, 'GET', '/projects?limit=200');
    const projects = projResp?.items ?? projResp ?? [];
    for (const p of projects) {
      await api(page, 'DELETE', `/projects/${p.id}`).catch(() => {});
    }

    await page.close();
  });

  // ─── Test 1: Dashboard loads with empty state ─────────────────────
  test('1 — Dashboard loads with empty state', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    // Stat cards — each is a CardTitle with class "text-sm font-medium"
    const statGrid = page.locator('.grid.md\\:grid-cols-5');
    for (const label of ['Projects', 'Total Crawls', 'URLs Crawled', 'Active Crawls', 'Total Errors']) {
      await expect(statGrid.getByText(label, { exact: true })).toBeVisible();
    }

    // Empty-state message
    await expect(page.getByText('No crawls yet')).toBeVisible();
  });

  // ─── Test 2: Start spider-mode crawl ──────────────────────────────
  test('2 — Start spider-mode crawl', async ({ page }) => {
    await page.goto('/crawls/new');
    await expect(page.getByRole('heading', { name: 'New Crawl' })).toBeVisible();

    // Spider Mode tab should be active by default
    const spiderTab = page.getByRole('tab', { name: 'Spider Mode' });
    await expect(spiderTab).toHaveAttribute('data-state', 'active');

    // Fill URL
    await page.getByPlaceholder('https://example.com').fill('https://books.toscrape.com/');

    // Set Max URLs to 20
    const maxUrlsInput = page.locator('label:has-text("Max URLs") + input, label:has-text("Max URLs") ~ input').first();
    // Fallback: find the input in the grid near "Max URLs" label
    const maxUrlsSection = page.locator('div:has(> label:has-text("Max URLs"))').first();
    const maxInput = maxUrlsSection.locator('input[type="number"]');
    await maxInput.fill('20');

    // Click Start Crawl
    await page.getByRole('button', { name: 'Start Crawl' }).click();

    // Wait for redirect to /crawls/[uuid]
    await page.waitForURL(/\/crawls\/[0-9a-f-]+/, { timeout: 30_000 });
    spiderCrawlId = page.url().split('/crawls/')[1].split(/[?#]/)[0];
    expect(spiderCrawlId).toMatch(/^[0-9a-f-]{36}$/);
  });

  // ─── Test 3: Watch crawl progress and wait for completion ─────────
  test('3 — Watch crawl progress, wait for completion', async ({ page }) => {
    await page.goto(`/crawls/${spiderCrawlId}`);

    // Status badge should show Queued or Crawling initially
    const badge = page.locator('[data-slot="badge"]');
    await expect(
      badge.filter({ hasText: /Queued|Crawling/ }).first(),
    ).toBeVisible({ timeout: 15_000 });

    // Progress bar exists
    await expect(page.locator('.bg-\\[\\#6cc04a\\]').first()).toBeVisible({ timeout: 15_000 });

    // Status bar shows URLs crawled
    await expect(page.locator('.sf-status-bar')).toContainText('URLs crawled');

    // Wait for Completed badge (crawl of 20 URLs should finish fairly quickly)
    await expect(
      badge.filter({ hasText: 'Completed' }),
    ).toBeVisible({ timeout: 180_000 });
  });

  // ─── Test 4: Pause, resume, stop a crawl ──────────────────────────
  test('4 — Pause, resume, stop a crawl', async ({ page }) => {
    // Start a slow crawl via API so we have time to pause/resume/stop
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Create or find project for books.toscrape.com
    const projResp = await api(page, 'GET', '/projects?limit=100');
    const projects = projResp?.items ?? projResp ?? [];
    let project = projects.find((p: { domain: string }) => p.domain === 'books.toscrape.com');
    if (!project) {
      project = await api(page, 'POST', '/projects', {
        name: 'books.toscrape.com',
        domain: 'books.toscrape.com',
      });
    }

    // Start slow crawl
    const crawl = await api(page, 'POST', `/projects/${project.id}/crawls`, {
      start_url: 'https://books.toscrape.com/',
      mode: 'spider',
      config: { max_urls: 500, rate_limit_rps: 1, max_depth: 2, max_threads: 1 },
    });

    await page.goto(`/crawls/${crawl.id}`);

    // Wait for "Crawling" status badge
    const badge = page.locator('[data-slot="badge"]');
    await expect(badge.filter({ hasText: 'Crawling' })).toBeVisible({ timeout: 30_000 });

    // Pause
    await page.locator('button[title="Pause"]').click();
    await expect(badge.filter({ hasText: 'Paused' })).toBeVisible({ timeout: 15_000 });

    // Resume
    await page.locator('button[title="Resume"]').click();
    await expect(badge.filter({ hasText: 'Crawling' })).toBeVisible({ timeout: 15_000 });

    // Stop
    await page.locator('button[title="Stop"]').click();
    await expect(badge.filter({ hasText: 'Cancelled' })).toBeVisible({ timeout: 15_000 });

    // Clean up — delete this crawl
    await api(page, 'DELETE', `/crawls/${crawl.id}`).catch(() => {});
  });

  // ─── Test 5: Browse all 13 tabs on completed crawl ────────────────
  test('5 — Browse all 13 tabs on completed crawl', async ({ page }) => {
    await page.goto(`/crawls/${spiderCrawlId}`);
    await page.waitForLoadState('networkidle');

    const tabNames = [
      'Internal', 'External', 'Response Codes', 'Page Titles',
      'Meta Description', 'H1', 'H2', 'Images', 'Canonicals',
      'Directives', 'Structured Data', 'Custom Extraction', 'Issues',
    ];

    for (const tabName of tabNames) {
      // Click the tab
      const tab = page.locator('.sf-tab', { hasText: tabName }).first();
      await tab.click();

      // Verify the tab becomes active
      await expect(page.locator('.sf-tab.active', { hasText: tabName })).toBeVisible({ timeout: 5_000 });

      // Wait for content to load — either a table appears or an empty-state message
      // Use page.waitForFunction to avoid strict mode issues
      await page.waitForFunction(
        () => {
          const hasTable = document.querySelector('table.sf-table') !== null;
          const text = document.body.innerText;
          const hasEmptyMsg = /No .* found|No issues found|no external links|No URLs found|No pages with|No custom extraction/i.test(text);
          return hasTable || hasEmptyMsg;
        },
        { timeout: 15_000 },
      );
    }
  });

  // ─── Test 6: Sub-filters within tabs ──────────────────────────────
  test('6 — Sub-filters within tabs', async ({ page }) => {
    await page.goto(`/crawls/${spiderCrawlId}`);
    await page.waitForLoadState('networkidle');

    // Response Codes tab → 2xx Success filter
    await page.locator('.sf-tab', { hasText: 'Response Codes' }).click();
    await page.waitForTimeout(500);
    await page.locator('.sf-filter-btn', { hasText: '2xx Success' }).click();
    await expect(page.locator('.sf-filter-btn.active', { hasText: '2xx Success' })).toBeVisible();

    // Page Titles tab → Missing filter
    await page.locator('.sf-tab', { hasText: 'Page Titles' }).click();
    await page.waitForTimeout(500);
    await page.locator('.sf-filter-btn', { hasText: 'Missing' }).click();
    await expect(page.locator('.sf-filter-btn.active', { hasText: 'Missing' })).toBeVisible();

    // Issues tab → Warning filter
    await page.locator('.sf-tab', { hasText: 'Issues' }).click();
    await page.waitForTimeout(500);
    await page.locator('.sf-filter-btn', { hasText: 'Warning' }).click();
    await expect(page.locator('.sf-filter-btn.active', { hasText: 'Warning' })).toBeVisible();
  });

  // ─── Test 7: Search URLs ──────────────────────────────────────────
  test('7 — Search URLs', async ({ page }) => {
    await page.goto(`/crawls/${spiderCrawlId}`);
    await page.waitForLoadState('networkidle');

    // Make sure we're on Internal tab
    await page.locator('.sf-tab', { hasText: 'Internal' }).first().click();
    await page.waitForTimeout(500);

    // Fill search
    const searchInput = page.getByPlaceholder('Filter URLs...');
    await searchInput.fill('catalogue');
    await searchInput.press('Enter');

    // Verify matching text appears in pagination area
    await expect(page.getByText('matching "catalogue"')).toBeVisible({ timeout: 10_000 });

    // Clear search (click the X button)
    const clearBtn = page.locator('button').filter({ has: page.locator('svg.h-3.w-3') }).last();
    // Alternative: look for the clear button near the search
    await page.locator('.sf-filter-bar button').filter({ has: page.locator('svg') }).last().click();
    await page.waitForTimeout(500);

    // After clearing, "matching" text should be gone
    await expect(page.getByText('matching')).not.toBeVisible({ timeout: 5_000 });
  });

  // ─── Test 8: URL detail drawer ────────────────────────────────────
  test('8 — URL detail drawer', async ({ page }) => {
    await page.goto(`/crawls/${spiderCrawlId}`);
    await page.waitForLoadState('networkidle');

    // Click Internal tab
    await page.locator('.sf-tab', { hasText: 'Internal' }).first().click();
    await page.waitForTimeout(1000);

    // Click first table row
    const firstRow = page.locator('.sf-table tbody tr').first();
    await firstRow.click();

    // Verify detail panel opens with URL Details and SEO Data tabs
    await expect(page.getByText('URL Details')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('SEO Data')).toBeVisible();

    // Verify labels in URL Details
    await expect(page.getByText('Status Code').last()).toBeVisible();
    await expect(page.getByText('Content Type').last()).toBeVisible();

    // Click SEO Data tab
    await page.getByText('SEO Data').click();
    await page.waitForTimeout(500);

    // Verify SEO Data labels
    await expect(page.getByText('Title').last()).toBeVisible();
    await expect(page.getByText('Meta Description').last()).toBeVisible();
  });

  // ─── Test 9: Export buttons (CSV, Excel, Sitemap) ─────────────────
  test('9 — Export buttons (CSV, Excel, Sitemap)', async ({ page }) => {
    await page.goto(`/crawls/${spiderCrawlId}`);
    await page.waitForLoadState('networkidle');

    const exportTests = [
      { title: 'Export CSV', pathContains: '/export' },
      { title: 'Export Excel', pathContains: '/export-xlsx' },
      { title: 'Download Sitemap XML', pathContains: '/sitemap.xml' },
    ];

    for (const { title, pathContains } of exportTests) {
      // Intercept window.open to capture the URL without actually opening a popup
      const openedUrl = await page.evaluate((btnTitle) => {
        return new Promise<string>((resolve) => {
          const origOpen = window.open;
          window.open = (url?: string | URL, ...args: unknown[]) => {
            window.open = origOpen as typeof window.open;
            resolve(String(url ?? ''));
            return null;
          };
          const btn = document.querySelector(`button[title="${btnTitle}"]`) as HTMLElement;
          btn?.click();
        });
      }, title);
      expect(openedUrl).toContain(pathContains);
    }
  });

  // ─── Test 10: Crawls list page ────────────────────────────────────
  test('10 — Crawls list page', async ({ page }) => {
    await page.goto('/crawls');
    await expect(page.getByRole('heading', { name: 'Crawls' })).toBeVisible();

    // Table has rows
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10_000 });

    // Status filter: use native <select>
    const statusSelect = page.locator('select').first();
    await statusSelect.selectOption('completed');
    await page.waitForTimeout(1000);

    // Verify filtered results — should show "(filtered)" text
    await expect(page.getByText('(filtered)')).toBeVisible({ timeout: 5_000 });

    // Clear Filters
    await page.getByRole('button', { name: 'Clear Filters' }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText('(filtered)')).not.toBeVisible({ timeout: 5_000 });

    // Pagination text
    await expect(page.getByText(/Page \d+ of \d+/)).toBeVisible();
  });

  // ─── Test 11: Start list-mode crawl ───────────────────────────────
  test('11 — Start list-mode crawl', async ({ page }) => {
    await page.goto('/crawls/new');

    // Click List Mode tab
    await page.getByRole('tab', { name: 'List Mode' }).click();
    await expect(page.getByRole('tab', { name: 'List Mode' })).toHaveAttribute('data-state', 'active');

    // Fill textarea with 3 URLs
    const textarea = page.locator('textarea');
    await textarea.fill(
      'https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html\nhttps://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html\nhttps://books.toscrape.com/catalogue/soumission_998/index.html',
    );

    // Verify URL count
    await expect(page.getByText('3 URLs')).toBeVisible();

    // Click Start Crawl
    await page.getByRole('button', { name: 'Start Crawl' }).click();

    // Wait for redirect
    await page.waitForURL(/\/crawls\/[0-9a-f-]+/, { timeout: 30_000 });
    listCrawlId = page.url().split('/crawls/')[1].split(/[?#]/)[0];
    expect(listCrawlId).toMatch(/^[0-9a-f-]{36}$/);

    // Wait for completion
    await expect(page.locator('[data-slot="badge"]').filter({ hasText: 'Completed' })).toBeVisible({ timeout: 180_000 });
  });

  // ─── Test 12: Compare two crawls ──────────────────────────────────
  test('12 — Compare two crawls', async ({ page }) => {
    await page.goto('/crawls/compare');
    await expect(page.getByRole('heading', { name: 'Compare Crawls' })).toBeVisible();

    // Wait for selects to be populated
    await page.waitForTimeout(2000);

    // Select project (first native select — "Project (optional)")
    const projectSelect = page.locator('select').nth(0);
    // Pick the first non-empty option (a real project)
    const projectOptions = await projectSelect.locator('option').allTextContents();
    if (projectOptions.length > 1) {
      await projectSelect.selectOption({ index: 1 });
      await page.waitForTimeout(1000);
    }

    // Select Crawl A (second select)
    const crawlASelect = page.locator('select').nth(1);
    await crawlASelect.selectOption({ index: 1 });
    await page.waitForTimeout(1000);

    // Select Crawl B (third select)
    const crawlBSelect = page.locator('select').nth(2);
    await crawlBSelect.selectOption({ index: 1 });
    await page.waitForTimeout(2000);

    // Wait for URL Differences heading
    await expect(page.getByText('URL Differences')).toBeVisible({ timeout: 30_000 });

    // Verify summary cards
    for (const cardLabel of ['Added', 'Removed', 'Changed', 'Unchanged']) {
      await expect(page.getByText(cardLabel, { exact: true }).first()).toBeVisible();
    }
  });

  // ─── Test 13: Settings page ───────────────────────────────────────
  test('13 — Settings page', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Verify config cards (use exact match on card titles)
    await expect(page.getByText('Default Crawl Configuration')).toBeVisible();
    await expect(page.getByText('User Agent', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Crawl Behavior')).toBeVisible();

    // Modify Max URLs
    const maxUrlsInput = page.locator('#maxUrls');
    await maxUrlsInput.fill('5000');

    // Save
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await expect(page.getByText('Saved!')).toBeVisible({ timeout: 5_000 });

    // Reload and verify persisted
    await page.reload();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#maxUrls')).toHaveValue('5000');

    // Reset to defaults
    await page.locator('#maxUrls').fill('10000');
    await page.locator('#maxDepth').fill('10');
    await page.locator('#concurrency').fill('5');
    await page.locator('#rateLimit').fill('2');
    await page.getByRole('button', { name: 'Save Settings' }).click();
    await expect(page.getByText('Saved!')).toBeVisible({ timeout: 5_000 });
  });

  // ─── Test 14: Delete a crawl ──────────────────────────────────────
  test('14 — Delete a crawl', async ({ page }) => {
    // We'll create a throwaway crawl via API to delete
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const projResp = await api(page, 'GET', '/projects?limit=100');
    const projects = projResp?.items ?? projResp ?? [];
    let project = projects.find((p: { domain: string }) => p.domain === 'books.toscrape.com');
    if (!project) {
      project = await api(page, 'POST', '/projects', {
        name: 'books.toscrape.com',
        domain: 'books.toscrape.com',
      });
    }

    // Start a small crawl and wait for it to complete
    const crawl = await api(page, 'POST', `/projects/${project.id}/crawls`, {
      start_url: 'https://books.toscrape.com/',
      mode: 'spider',
      config: { max_urls: 3, max_depth: 1, max_threads: 1, rate_limit_rps: 5 },
    });
    await waitForCrawlDone(page, crawl.id, 60_000);

    // Navigate to crawl detail
    await page.goto(`/crawls/${crawl.id}`);
    await page.waitForLoadState('networkidle');

    // Click delete button
    await page.locator('button[title="Delete Crawl"]').click();

    // Click inline Confirm button
    await page.getByRole('button', { name: 'Confirm' }).click();

    // Verify redirect to /crawls
    await page.waitForURL(/\/crawls\/?$/, { timeout: 15_000 });
  });

  // ─── Test 15: Delete a project ────────────────────────────────────
  test('15 — Delete a project', async ({ page }) => {
    // Create a test project via API
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const testProject = await api(page, 'POST', '/projects', {
      name: 'test-delete-project.example.com',
      domain: 'test-delete-project.example.com',
    });

    // Reload dashboard to see the new project
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Find the project row and its delete button
    const projectRow = page.locator('tr', { hasText: 'test-delete-project.example.com' });
    await expect(projectRow).toBeVisible({ timeout: 10_000 });

    // Handle window.confirm() dialog
    page.on('dialog', (dialog) => dialog.accept());

    // Click delete button
    await projectRow.locator('button[title="Delete project"]').click();

    // Verify project row disappears
    await expect(projectRow).not.toBeVisible({ timeout: 10_000 });
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage({ baseURL: 'http://localhost' });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Clean up remaining test data
    const crawlsResp = await api(page, 'GET', '/crawls?limit=200');
    const crawls = crawlsResp?.items ?? crawlsResp ?? [];
    for (const c of crawls) {
      if (['crawling', 'queued', 'paused', 'completing'].includes(c.status)) {
        await api(page, 'POST', `/crawls/${c.id}/stop`).catch(() => {});
      }
    }
    await page.waitForTimeout(2000);
    for (const c of crawls) {
      await api(page, 'DELETE', `/crawls/${c.id}`).catch(() => {});
    }

    const projResp = await api(page, 'GET', '/projects?limit=200');
    const projects = projResp?.items ?? projResp ?? [];
    for (const p of projects) {
      await api(page, 'DELETE', `/projects/${p.id}`).catch(() => {});
    }

    await page.close();
  });
});
