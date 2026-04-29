// @ts-check
/**
 * Tests for the main Overview dashboard (index.html).
 * Covers: KPI cards, ticker bar, sidebar toggle, equity period buttons,
 * quick-action buttons, pipeline funnel, agent grid, event table.
 */
const { test, expect } = require('/opt/node22/lib/node_modules/playwright/test.js');
const { goto, testSidebarToggle } = require('./helpers');

const PATH = '/dashboards/';

test.describe('Overview Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  // ── Layout ──────────────────────────────────────────────────────────────
  test('page title contains "Agent Trading Expert"', async ({ page }) => {
    await expect(page).toHaveTitle(/Agent Trading Expert/i);
  });

  test('sidebar toggle collapses and expands', async ({ page }) => {
    await testSidebarToggle(page);
  });

  test('topbar brand is visible', async ({ page }) => {
    await expect(page.locator('.brand')).toBeVisible();
    await expect(page.locator('.brand')).toContainText('AGENT TRADING EXPERT');
  });

  test('PAPER MODE pill is visible in topbar', async ({ page }) => {
    await expect(page.locator('.pill-paper')).toBeVisible();
    await expect(page.locator('.pill-paper')).toContainText('PAPER MODE');
  });

  // ── Ticker bar ───────────────────────────────────────────────────────────
  test('ticker bar shows AAPL, MSFT, GOOG, NVDA symbols', async ({ page }) => {
    for (const sym of ['AAPL', 'MSFT', 'GOOG', 'NVDA']) {
      await expect(page.locator(`.ticker-sym:text("${sym}")`)).toBeVisible();
    }
  });

  // ── KPI cards ────────────────────────────────────────────────────────────
  test('six KPI cards are visible', async ({ page }) => {
    const kpis = page.locator('.kpi');
    await expect(kpis).toHaveCount(6);
    for (const label of [
      'Portfolio Equity', 'Total Return', 'Sharpe Ratio',
      'Max Drawdown', 'VaR 95%', 'Active Strategies',
    ]) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── Equity chart period buttons ──────────────────────────────────────────
  test('equity period buttons are all visible', async ({ page }) => {
    for (const period of ['1D', '1W', '1M', '3M', '6M']) {
      await expect(page.locator(`.period-btn:text("${period}")`)).toBeVisible();
    }
  });

  test('clicking equity period buttons changes active state', async ({ page }) => {
    const periods = ['1D', '1W', '3M', '6M', '1M'];
    for (const p of periods) {
      const btn = page.locator(`.period-btn:text("${p}")`);
      await btn.click();
      await expect(btn).toHaveClass(/active/);
    }
  });

  test('equity chart canvas is rendered', async ({ page }) => {
    await expect(page.locator('#equityChart')).toBeAttached();
  });

  // ── Quick Actions ────────────────────────────────────────────────────────
  test('Quick Actions card has all five buttons', async ({ page }) => {
    const labels = [
      '▶ Run Full Pipeline',
      '◈ Run Research Agent',
      '◆ New Strategy',
      '◑ View Strategies',
      '◎ Backtest Analysis',
    ];
    for (const label of labels) {
      await expect(page.locator(`button.btn:has-text("${label}")`)).toBeVisible();
    }
  });

  test('"Run Full Pipeline" button triggers action message', async ({ page }) => {
    await page.locator('button.btn:has-text("Run Full Pipeline")').click();
    // Either success badge or error badge should appear within 10 s
    const msg = page.locator('#actionMsg');
    await expect(msg).not.toBeEmpty({ timeout: 10_000 });
  });

  test('"Run Research Agent" button triggers action message', async ({ page }) => {
    await page.locator('button.btn:has-text("Run Research Agent")').click();
    const msg = page.locator('#actionMsg');
    await expect(msg).not.toBeEmpty({ timeout: 10_000 });
  });

  test('"New Strategy" button navigates to builder', async ({ page }) => {
    await page.locator('button.btn:has-text("New Strategy")').click();
    await expect(page).toHaveURL(/dashboard_builder/);
  });

  test('"View Strategies" button navigates to strategy page', async ({ page }) => {
    await page.locator('button.btn:has-text("View Strategies")').click();
    await expect(page).toHaveURL(/strategy/);
  });

  test('"Backtest Analysis" button navigates to backtest page', async ({ page }) => {
    await page.locator('button.btn:has-text("Backtest Analysis")').click();
    await expect(page).toHaveURL(/dashboard_backtest/);
  });

  // ── Pipeline funnel ──────────────────────────────────────────────────────
  test('pipeline funnel container is present', async ({ page }) => {
    await expect(page.locator('#pipelineFunnel')).toBeAttached();
  });

  test('Human Review box is present', async ({ page }) => {
    await expect(page.locator('#hrBox')).toBeAttached();
  });

  // ── Agent grid ───────────────────────────────────────────────────────────
  test('agents grid container is present', async ({ page }) => {
    await expect(page.locator('#agentsGrid')).toBeAttached();
  });

  // ── Event stream table ───────────────────────────────────────────────────
  test('Live Event Stream table headers are present', async ({ page }) => {
    for (const header of ['Time', 'Agent', 'Status', 'Message']) {
      await expect(page.locator(`th:text("${header}")`)).toBeVisible();
    }
  });

  test('event rows container is present', async ({ page }) => {
    await expect(page.locator('#eventRows')).toBeAttached();
  });

  // ── Bottom bar ───────────────────────────────────────────────────────────
  test('bottombar shows auto-refresh interval', async ({ page }) => {
    await expect(page.locator('.bottombar')).toContainText('auto-refresh');
  });

  // ── Sidebar navigation links ─────────────────────────────────────────────
  test('sidebar is rendered with navigation items', async ({ page }) => {
    await expect(page.locator('nav.sidebar')).toBeVisible();
    const items = page.locator('.sidebar-item');
    await expect(items.first()).toBeVisible();
  });
});
