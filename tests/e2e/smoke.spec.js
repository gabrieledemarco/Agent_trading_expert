// @ts-check
/**
 * Smoke tests — every dashboard page must:
 *   • load with HTTP 200
 *   • have a non-empty <title>
 *   • render the .terminal grid container
 *   • render the sidebar toggle button
 *   • render the .bottombar footer
 *
 * These run against the live Render deployment.
 * Render free tier may cold-start: first navigation can take ~30 s.
 */
const { test, expect } = require('/opt/node22/lib/node_modules/playwright/test.js');
const { PAGES } = require('./helpers');

for (const { path, title } of PAGES) {
  test(`[smoke] ${title} page loads: ${path}`, async ({ page }) => {
    const response = await page.goto(path, { waitUntil: 'domcontentloaded' });

    // HTTP status must be 200
    expect(response?.status(), `HTTP status for ${path}`).toBe(200);

    // Page title contains something meaningful
    const pageTitle = await page.title();
    expect(pageTitle.length, `Page title should not be empty: ${path}`).toBeGreaterThan(0);

    // Core layout elements must be present in DOM
    await expect(page.locator('.terminal').first()).toBeAttached();
    await expect(page.locator('button.sidebar-toggle').first()).toBeAttached();
    await expect(page.locator('.bottombar').first()).toBeAttached();

    // No uncaught JS errors that prevent render — check body is not blank
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length, `Body should not be empty: ${path}`).toBeGreaterThan(0);
  });
}
