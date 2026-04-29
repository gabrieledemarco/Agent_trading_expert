// @ts-check
const { expect } = require('/opt/node22/lib/node_modules/playwright/test.js');

const BASE = '/dashboards';

/**
 * All dashboard pages with their expected title fragment and path.
 */
const PAGES = [
  { path: `${BASE}/`,                            title: 'Overview' },
  { path: `${BASE}/dashboard_models.html`,       title: 'Models' },
  { path: `${BASE}/dashboard_pipeline.html`,     title: 'Pipeline' },
  { path: `${BASE}/dashboard_validation.html`,   title: 'Validation' },
  { path: `${BASE}/dashboard_backtest.html`,     title: 'Backtest' },
  { path: `${BASE}/dashboard_performance.html`,  title: 'Performance' },
  { path: `${BASE}/dashboard_risk.html`,         title: 'Risk' },
  { path: `${BASE}/dashboard_agents.html`,       title: 'Agents' },
  { path: `${BASE}/strategy.html`,               title: 'Strategy' },
  { path: `${BASE}/dashboard_builder.html`,      title: 'Builder' },
  { path: `${BASE}/dashboard_live.html`,         title: 'Live' },
  { path: `${BASE}/dashboard_execution.html`,    title: 'Execution' },
  { path: `${BASE}/dashboard_with_chat.html`,    title: 'Chat' },
  { path: `${BASE}/dashboard_documentation.html`,title: 'Documentation' },
  { path: `${BASE}/dashboard_research.html`,     title: 'Research' },
  { path: `${BASE}/dashboard_backtest_live.html`,title: 'Backtest' },
];

/**
 * Navigate to a page and wait for it to be interactive.
 * @param {import('@playwright/test').Page} page
 * @param {string} path
 */
async function goto(page, path) {
  await page.goto(path, { waitUntil: 'domcontentloaded' });
}

/**
 * Toggle the sidebar and verify the layout class changes.
 * @param {import('@playwright/test').Page} page
 */
async function testSidebarToggle(page) {
  const terminal = page.locator('.terminal');
  const toggleBtn = page.locator('button.sidebar-toggle').first();
  await expect(toggleBtn).toBeVisible();

  const before = await terminal.getAttribute('class');
  await toggleBtn.click();
  const after = await terminal.getAttribute('class');
  // The class list should have changed
  expect(before).not.toEqual(after);

  // Toggle back
  await toggleBtn.click();
}

/**
 * Assert that a button is visible and clickable.
 * Optionally wait for a response trigger (API calls).
 * @param {import('@playwright/test').Page} page
 * @param {import('@playwright/test').Locator} btn
 */
async function clickButton(page, btn) {
  await expect(btn).toBeVisible();
  await expect(btn).toBeEnabled();
  await btn.click();
}

/**
 * Click a tab button and verify its active state.
 * @param {import('@playwright/test').Page} page
 * @param {string} tabText
 * @param {string} panelId  id of the tab panel that should become visible
 */
async function switchTab(page, tabText, panelId) {
  const tab = page.locator('button, .tab').filter({ hasText: tabText }).first();
  await expect(tab).toBeVisible();
  await tab.click();
  if (panelId) {
    await expect(page.locator(`#${panelId}`)).toBeVisible();
  }
}

module.exports = { PAGES, goto, testSidebarToggle, clickButton, switchTab };
