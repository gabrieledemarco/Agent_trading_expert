// @ts-check
/**
 * Tests for:
 *   • dashboard_models.html      — Models list, KPIs, chart
 *   • dashboard_backtest.html    — Backtest analysis with tabs
 *   • dashboard_backtest_live.html — Live backtest connect panel
 */
const { test, expect } = require('/opt/node22/lib/node_modules/playwright/test.js');
const { goto, testSidebarToggle } = require('./helpers');

// ═══════════════════════════════════════════════════════════════════════════
// MODELS
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Models Dashboard', () => {
  const PATH = '/dashboards/dashboard_models.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Models"', async ({ page }) => {
    await expect(page).toHaveTitle(/Models/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── KPI cards ────────────────────────────────────────────────────────────
  test('four KPI cards are visible', async ({ page }) => {
    for (const label of ['Total Models', 'Approved', 'Rejected', 'Pending']) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── Header Refresh button ────────────────────────────────────────────────
  test('Refresh button is visible and clickable', async ({ page }) => {
    const btn = page.locator('button.btn:has-text("Refresh")');
    await expect(btn).toBeVisible();
    await btn.click();
    await page.waitForTimeout(300);
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Chart canvas ─────────────────────────────────────────────────────────
  test('models chart canvas is in DOM', async ({ page }) => {
    await expect(page.locator('#modelsChart')).toBeAttached();
  });

  // ── Models table ─────────────────────────────────────────────────────────
  test('models results table body is in DOM', async ({ page }) => {
    await expect(page.locator('#rows')).toBeAttached();
  });

  // ── KPI value containers ─────────────────────────────────────────────────
  test('KPI value elements are present', async ({ page }) => {
    for (const id of ['kpiTotal', 'kpiApproved', 'kpiRejected', 'kpiPending']) {
      await expect(page.locator(`#${id}`)).toBeAttached();
    }
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// BACKTEST ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Backtest Analysis Dashboard', () => {
  const PATH = '/dashboards/dashboard_backtest.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Backtest"', async ({ page }) => {
    await expect(page).toHaveTitle(/Backtest/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── Model select dropdown ────────────────────────────────────────────────
  test('model select dropdown is visible', async ({ page }) => {
    await expect(page.locator('#modelSelect')).toBeVisible();
  });

  test('model select has at least one option', async ({ page }) => {
    const options = page.locator('#modelSelect option');
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  // ── Tab buttons ──────────────────────────────────────────────────────────
  test('five tab buttons are visible', async ({ page }) => {
    for (const tab of ['Overview', 'Validation Tests', 'Strategy Detail', 'Monte Carlo', 'Rejected Analysis']) {
      await expect(page.locator(`button.tab:has-text("${tab}")`)).toBeVisible();
    }
  });

  test('switching to "Validation Tests" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Validation Tests")').click();
    await expect(page.locator('#tab-tests')).toHaveClass(/active/);
  });

  test('switching to "Strategy Detail" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Strategy Detail")').click();
    await expect(page.locator('#tab-detail')).toHaveClass(/active/);
  });

  test('switching to "Monte Carlo" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Monte Carlo")').click();
    await expect(page.locator('#tab-montecarlo')).toHaveClass(/active/);
  });

  test('switching to "Rejected Analysis" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Rejected Analysis")').click();
    await expect(page.locator('#tab-rejected')).toHaveClass(/active/);
  });

  test('switching back to "Overview" tab works', async ({ page }) => {
    // Navigate away first
    await page.locator('button.tab:has-text("Monte Carlo")').click();
    await page.locator('button.tab:has-text("Overview")').click();
    await expect(page.locator('#tab-overview')).toHaveClass(/active/);
  });

  // ── Chart canvases ───────────────────────────────────────────────────────
  test('sharpe chart canvas is in DOM', async ({ page }) => {
    await expect(page.locator('#sharpeChart')).toBeAttached();
  });

  // ── Tables ───────────────────────────────────────────────────────────────
  test('overview table body is present', async ({ page }) => {
    await expect(page.locator('#overviewTable')).toBeAttached();
  });

  test('rejected table body is present', async ({ page }) => {
    await expect(page.locator('#rejectedTable')).toBeAttached();
  });

  // ── Detail panel hint message ────────────────────────────────────────────
  test('"Select a model" hint is visible initially', async ({ page }) => {
    await page.locator('button.tab:has-text("Strategy Detail")').click();
    await expect(page.locator('#noDetailMsg')).toBeVisible();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// BACKTEST LIVE (remote connect)
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Backtest Live Connect Page', () => {
  const PATH = '/dashboards/dashboard_backtest_live.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Backtest" or "Live"', async ({ page }) => {
    const title = await page.title();
    expect(title.toLowerCase()).toMatch(/backtest|live/);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  test('Connect button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Connect")').first()).toBeVisible();
  });

  test('Refresh button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Refresh")')).toBeVisible();
  });

  test('API URL input field is visible', async ({ page }) => {
    await expect(page.locator('#apiUrl')).toBeVisible();
  });

  test('API URL input accepts text', async ({ page }) => {
    const input = page.locator('#apiUrl');
    await input.fill('https://agent-trading-expert.onrender.com');
    await expect(input).toHaveValue('https://agent-trading-expert.onrender.com');
  });

  test('connection status label is present', async ({ page }) => {
    await expect(page.locator('#connLabel')).toBeAttached();
  });

  test('connection status element is present in form row', async ({ page }) => {
    await expect(page.locator('#connStatus')).toBeAttached();
  });

  test('KPI containers are present (hidden until connected)', async ({ page }) => {
    for (const id of ['kpiResearch', 'kpiValidated', 'kpiEquity', 'kpiReturn']) {
      await expect(page.locator(`#${id}`)).toBeAttached();
    }
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});
