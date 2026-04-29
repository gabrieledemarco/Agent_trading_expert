// @ts-check
/**
 * Tests for:
 *   • dashboard_performance.html  — Portfolio performance with tabs and charts
 *   • dashboard_risk.html         — Risk analysis with tabs and stress tests
 *   • strategy.html               — Per-strategy view with tabs and resize buttons
 */
const { test, expect } = require('/opt/node22/lib/node_modules/playwright/test.js');
const { goto, testSidebarToggle } = require('./helpers');

// ═══════════════════════════════════════════════════════════════════════════
// PERFORMANCE
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Performance Dashboard', () => {
  const PATH = '/dashboards/dashboard_performance.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Performance"', async ({ page }) => {
    await expect(page).toHaveTitle(/Performance/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── KPI row ──────────────────────────────────────────────────────────────
  test('eight KPI labels are present', async ({ page }) => {
    for (const label of [
      'Total Trades', 'Win Rate', 'Sharpe Ratio', 'Sortino',
      'Calmar', 'Max DD', 'VaR 95%', 'Volatility',
    ]) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── Refresh button ───────────────────────────────────────────────────────
  test('Refresh button is visible and clickable', async ({ page }) => {
    const btn = page.locator('button[onclick="refreshAll()"]').first();
    await expect(btn).toBeVisible();
    await btn.click();
    await page.waitForTimeout(300);
  });

  // ── Tab buttons ──────────────────────────────────────────────────────────
  test('three tab buttons are visible', async ({ page }) => {
    for (const tab of ['Portfolio', 'Per-Model', 'Trade Log']) {
      await expect(page.locator(`button.tab-btn:has-text("${tab}")`)).toBeVisible();
    }
  });

  test('switching to "Per-Model" tab shows the panel', async ({ page }) => {
    await page.locator('button.tab-btn:has-text("Per-Model")').click();
    await expect(page.locator('#tab-models')).toHaveClass(/active/);
  });

  test('switching to "Trade Log" tab shows the panel', async ({ page }) => {
    await page.locator('button.tab-btn:has-text("Trade Log")').click();
    await expect(page.locator('#tab-trades')).toHaveClass(/active/);
  });

  test('switching back to "Portfolio" tab shows the panel', async ({ page }) => {
    await page.locator('button.tab-btn:has-text("Trade Log")').click();
    await page.locator('button.tab-btn:has-text("Portfolio")').click();
    await expect(page.locator('#tab-portfolio')).toHaveClass(/active/);
  });

  // ── Period buttons ───────────────────────────────────────────────────────
  test('equity period buttons are visible', async ({ page }) => {
    for (const p of ['1D', '1W', '1M', '3M', '6M']) {
      await expect(page.locator(`button.period-btn:text("${p}")`)).toBeVisible();
    }
  });

  test('clicking equity period buttons changes active state', async ({ page }) => {
    const btn1D = page.locator('button.period-btn:text("1D")');
    await btn1D.click();
    await expect(btn1D).toHaveClass(/active/);
  });

  // ── Chart canvases ───────────────────────────────────────────────────────
  test('equity and drawdown chart canvases are in DOM', async ({ page }) => {
    await expect(page.locator('#equityChart')).toBeAttached();
    await expect(page.locator('#ddChart')).toBeAttached();
  });

  // ── Last update indicator ────────────────────────────────────────────────
  test('last update element is present', async ({ page }) => {
    await expect(page.locator('#lastUpdate')).toBeAttached();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// RISK
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Risk Dashboard', () => {
  const PATH = '/dashboards/dashboard_risk.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Risk"', async ({ page }) => {
    await expect(page).toHaveTitle(/Risk/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── Last calc indicator ──────────────────────────────────────────────────
  test('last risk calc label is present', async ({ page }) => {
    await expect(page.locator('#lastCalc')).toBeAttached();
  });

  // ── Tab buttons ──────────────────────────────────────────────────────────
  test('four tab buttons are visible', async ({ page }) => {
    for (const tab of ['Portfolio Risk', 'Position Sizing', 'Correlation', 'Stress Tests']) {
      await expect(page.locator(`button.tab:has-text("${tab}")`)).toBeVisible();
    }
  });

  test('switching to "Position Sizing" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Position Sizing")').click();
    await expect(page.locator('#tab-positions')).toHaveClass(/active/);
  });

  test('switching to "Correlation" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Correlation")').click();
    await expect(page.locator('#tab-correlation')).toHaveClass(/active/);
  });

  test('switching to "Stress Tests" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Stress Tests")').click();
    await expect(page.locator('#tab-stress')).toHaveClass(/active/);
  });

  test('switching back to "Portfolio Risk" works', async ({ page }) => {
    await page.locator('button.tab:has-text("Stress Tests")').click();
    await page.locator('button.tab:has-text("Portfolio Risk")').click();
    await expect(page.locator('#tab-portfolio')).toHaveClass(/active/);
  });

  // ── Chart canvases ───────────────────────────────────────────────────────
  test('VaR and Volatility chart canvases are in DOM', async ({ page }) => {
    await expect(page.locator('#varChart')).toBeAttached();
    await expect(page.locator('#volChart')).toBeAttached();
  });

  test('correlation chart canvas is in DOM', async ({ page }) => {
    await expect(page.locator('#corrChart')).toBeAttached();
  });

  test('stress chart canvas is in DOM', async ({ page }) => {
    await expect(page.locator('#stressChart')).toBeAttached();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// STRATEGY VIEW
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Strategy View', () => {
  const PATH = '/dashboards/strategy.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Strategy"', async ({ page }) => {
    await expect(page).toHaveTitle(/Strategy/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── Strategy select dropdown ─────────────────────────────────────────────
  test('strategy select dropdown is visible', async ({ page }) => {
    await expect(page.locator('#stratSelect')).toBeVisible();
  });

  test('strategy select has at least one option', async ({ page }) => {
    const options = page.locator('#stratSelect option');
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  // ── Stat boxes ───────────────────────────────────────────────────────────
  test('key stat boxes are visible', async ({ page }) => {
    await expect(page.locator('#stratName')).toBeVisible();
    await expect(page.locator('#riskBadge')).toBeVisible();
  });

  // ── Performance metrics ──────────────────────────────────────────────────
  test('performance stat elements are present', async ({ page }) => {
    for (const id of ['expReturn', 'actReturn', 'sharpe', 'sortino', 'maxdd', 'winrate']) {
      await expect(page.locator(`#${id}`)).toBeAttached();
    }
  });

  // ── Tab buttons ──────────────────────────────────────────────────────────
  test('four tab buttons are visible', async ({ page }) => {
    for (const tab of ['Performance', 'Risk Management', 'Positions', 'Documentation']) {
      await expect(page.locator(`button.tab:has-text("${tab}")`)).toBeVisible();
    }
  });

  test('switching to "Risk Management" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Risk Management")').click();
    await expect(page.locator('#tab-risk')).toHaveClass(/active/);
  });

  test('switching to "Positions" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Positions")').click();
    await expect(page.locator('#tab-pos')).toHaveClass(/active/);
  });

  test('switching to "Documentation" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Documentation")').click();
    await expect(page.locator('#tab-doc')).toHaveClass(/active/);
  });

  test('documentation tab shows strategy doc items', async ({ page }) => {
    await page.locator('button.tab:has-text("Documentation")').click();
    await expect(page.locator('#tab-doc')).toBeVisible();
    // At least one doc-item should exist
    await expect(page.locator('.doc-item').first()).toBeAttached();
  });

  // ── Resize buttons ───────────────────────────────────────────────────────
  test('resize buttons are visible on Performance tab', async ({ page }) => {
    const resizeBtns = page.locator('button.resize-btn');
    const count = await resizeBtns.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('resize button toggles chart minimization', async ({ page }) => {
    const firstResize = page.locator('button.resize-btn').first();
    await expect(firstResize).toBeVisible();
    // Click to minimize
    await firstResize.click();
    await page.waitForTimeout(300);
    // Click again to expand
    await firstResize.click();
    await page.waitForTimeout(300);
    // Page should still be functional
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Chart canvases ───────────────────────────────────────────────────────
  test('equity chart canvas is in DOM', async ({ page }) => {
    await expect(page.locator('#eqChart')).toBeAttached();
  });

  // ── Positions table ──────────────────────────────────────────────────────
  test('positions table is present', async ({ page }) => {
    await page.locator('button.tab:has-text("Positions")').click();
    await expect(page.locator('#posTable')).toBeVisible();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});
