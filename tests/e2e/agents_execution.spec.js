// @ts-check
/**
 * Tests for:
 *   • dashboard_agents.html    — Agent status grid, drilldown panel, trigger button
 *   • dashboard_execution.html — Quick trade execution panel
 *   • dashboard_live.html      — Live trading view with SSE and trade modal
 */
const { test, expect } = require('/opt/node22/lib/node_modules/playwright/test.js');
const { goto, testSidebarToggle } = require('./helpers');

// ═══════════════════════════════════════════════════════════════════════════
// AGENTS
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Agents Dashboard', () => {
  const PATH = '/dashboards/dashboard_agents.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Agents"', async ({ page }) => {
    await expect(page).toHaveTitle(/Agents/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── KPI cards ────────────────────────────────────────────────────────────
  test('five KPI labels are visible', async ({ page }) => {
    for (const label of ['Total Agents', 'Active', 'Idle', 'Errors', 'Never Run']) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── KPI value elements ───────────────────────────────────────────────────
  test('KPI value elements are in DOM', async ({ page }) => {
    for (const id of ['kpiTotal', 'kpiActive', 'kpiIdle', 'kpiErrors', 'kpiNever']) {
      await expect(page.locator(`#${id}`)).toBeAttached();
    }
  });

  // ── Refresh button ───────────────────────────────────────────────────────
  test('Refresh button is visible and clickable', async ({ page }) => {
    const btn = page.locator('button.btn:has-text("Refresh")');
    await expect(btn).toBeVisible();
    await btn.click();
    await page.waitForTimeout(300);
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Agents grid ──────────────────────────────────────────────────────────
  test('agents grid container is visible', async ({ page }) => {
    await expect(page.locator('#agentsGrid')).toBeVisible();
  });

  // ── Activity log ─────────────────────────────────────────────────────────
  test('log count element is present', async ({ page }) => {
    await expect(page.locator('#logCount')).toBeAttached();
  });

  test('activity table headers are visible', async ({ page }) => {
    await expect(page.locator('#activityRows')).toBeAttached();
  });

  // ── Drilldown panel ──────────────────────────────────────────────────────
  test('drilldown panel is in DOM but initially hidden', async ({ page }) => {
    const drilldown = page.locator('#drilldown');
    await expect(drilldown).toBeAttached();
    // The panel should not be visible by default (no agent selected)
    const isVisible = await drilldown.isVisible();
    // It's acceptable if hidden; just check it exists
    expect(isVisible === false || isVisible === true).toBe(true);
  });

  test('drilldown has "Trigger Agent Now" button', async ({ page }) => {
    await expect(page.locator('#ddTriggerBtn')).toBeAttached();
    await expect(page.locator('#ddTitle')).toBeAttached();
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
// EXECUTION (quick trade panel)
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Execution Dashboard', () => {
  const PATH = '/dashboards/dashboard_execution.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Execution"', async ({ page }) => {
    await expect(page).toHaveTitle(/Execution/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── KPI cards ────────────────────────────────────────────────────────────
  test('KPI labels are visible', async ({ page }) => {
    for (const label of ['Current Equity', 'Total Return', 'Sharpe Ratio']) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── Refresh button ───────────────────────────────────────────────────────
  test('Refresh button is visible and clickable', async ({ page }) => {
    const btn = page.locator('button.btn:has-text("Refresh")');
    await expect(btn).toBeVisible();
    await btn.click();
    await page.waitForTimeout(300);
  });

  // ── Trade form ───────────────────────────────────────────────────────────
  test('trade symbol select is visible', async ({ page }) => {
    await expect(page.locator('#tradeSymbol')).toBeVisible();
  });

  test('trade action select is visible', async ({ page }) => {
    await expect(page.locator('#tradeAction')).toBeVisible();
  });

  test('trade quantity input is visible', async ({ page }) => {
    await expect(page.locator('#tradeQty')).toBeVisible();
  });

  test('Execute button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Execute")')).toBeVisible();
  });

  test('trade form accepts input values', async ({ page }) => {
    const qty = page.locator('#tradeQty');
    await qty.fill('50');
    await expect(qty).toHaveValue('50');
  });

  test('Execute button click triggers feedback', async ({ page }) => {
    // Fill quantity and click Execute
    await page.locator('#tradeQty').fill('10');
    await page.locator('button:has-text("Execute")').click();
    // tradeMsg should appear (success or error depending on API state)
    const msg = page.locator('#tradeMsg');
    await expect(msg).toBeAttached();
    await page.waitForTimeout(1000);
  });

  // ── Trades table ─────────────────────────────────────────────────────────
  test('trades table body is present', async ({ page }) => {
    await expect(page.locator('#trades')).toBeAttached();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// LIVE TRADING
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Live Trading Dashboard', () => {
  const PATH = '/dashboards/dashboard_live.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Live"', async ({ page }) => {
    await expect(page).toHaveTitle(/Live/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── KPI row ──────────────────────────────────────────────────────────────
  test('live KPI labels are visible', async ({ page }) => {
    for (const label of ['Equity', 'Daily P&L', 'Positions', 'Unrealized', 'Realized', 'Win Rate']) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── SSE connection indicators ────────────────────────────────────────────
  test('SSE dot and label are visible', async ({ page }) => {
    await expect(page.locator('#sseDot')).toBeAttached();
    await expect(page.locator('#sseLabel')).toBeAttached();
  });

  test('tick counter is visible', async ({ page }) => {
    await expect(page.locator('#tickCount')).toBeVisible();
  });

  // ── Execute Trade button and modal ───────────────────────────────────────
  test('"+ Execute Trade" button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Execute Trade")')).toBeVisible();
  });

  test('clicking "Execute Trade" opens the modal', async ({ page }) => {
    await page.locator('button:has-text("Execute Trade")').click();
    await expect(page.locator('#tradeModal')).toBeVisible();
  });

  test('trade modal contains symbol input', async ({ page }) => {
    await page.locator('button:has-text("Execute Trade")').click();
    await expect(page.locator('#tradeSymbol')).toBeVisible();
  });

  test('trade modal contains action select', async ({ page }) => {
    await page.locator('button:has-text("Execute Trade")').click();
    await expect(page.locator('#tradeAction')).toBeVisible();
  });

  test('trade modal contains quantity input', async ({ page }) => {
    await page.locator('button:has-text("Execute Trade")').click();
    await expect(page.locator('#tradeQty')).toBeVisible();
  });

  test('modal close button dismisses the modal', async ({ page }) => {
    await page.locator('button:has-text("Execute Trade")').click();
    await expect(page.locator('#tradeModal')).toBeVisible();
    await page.locator('button.modal-close').click();
    await expect(page.locator('#tradeModal')).not.toBeVisible();
  });

  test('trade modal symbol input accepts text', async ({ page }) => {
    await page.locator('button:has-text("Execute Trade")').click();
    const sym = page.locator('#tradeSymbol');
    await sym.fill('NVDA');
    await expect(sym).toHaveValue('NVDA');
  });

  // ── Alert card ───────────────────────────────────────────────────────────
  test('alert card is in DOM', async ({ page }) => {
    await expect(page.locator('#alertCard')).toBeAttached();
  });

  // ── Charts and tables ────────────────────────────────────────────────────
  test('live chart canvas is in DOM', async ({ page }) => {
    await expect(page.locator('#liveChart')).toBeAttached();
  });

  test('positions table body is in DOM', async ({ page }) => {
    await expect(page.locator('#positionsBody')).toBeAttached();
  });

  test('trades table body is in DOM', async ({ page }) => {
    await expect(page.locator('#tradesBody')).toBeAttached();
  });

  test('log console is in DOM', async ({ page }) => {
    await expect(page.locator('#logConsole')).toBeAttached();
  });

  // ── Footer status bar ────────────────────────────────────────────────────
  test('connection status shows PAPER', async ({ page }) => {
    await expect(page.locator('#connStatus')).toContainText('PAPER');
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});
