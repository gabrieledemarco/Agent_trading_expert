// @ts-check
/**
 * Tests for:
 *   • dashboard_pipeline.html  — Pipeline Kanban board
 *   • dashboard_validation.html — Validation dashboard
 */
const { test, expect } = require('/opt/node22/lib/node_modules/playwright/test.js');
const { goto, testSidebarToggle } = require('./helpers');

// ═══════════════════════════════════════════════════════════════════════════
// PIPELINE
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Pipeline Dashboard', () => {
  const PATH = '/dashboards/dashboard_pipeline.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Pipeline"', async ({ page }) => {
    await expect(page).toHaveTitle(/Pipeline/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── KPI cards ────────────────────────────────────────────────────────────
  test('five KPI cards are visible', async ({ page }) => {
    for (const label of [
      'Total Strategies', 'Approved', 'In Progress', 'Human Review', 'Deployed',
    ]) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── Header action buttons ────────────────────────────────────────────────
  test('Refresh button is visible and clickable', async ({ page }) => {
    const btn = page.locator('button.btn:has-text("Refresh")');
    await expect(btn).toBeVisible();
    await btn.click();
  });

  test('"Run Full Pipeline" button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Run Full Pipeline")')).toBeVisible();
  });

  test('"Run Full Pipeline" triggers a pipeline message', async ({ page }) => {
    await page.locator('button:has-text("Run Full Pipeline")').click();
    const msg = page.locator('#pipelineMsg');
    // Message element should eventually become visible (success or error)
    await expect(msg).toBeVisible({ timeout: 15_000 });
  });

  // ── Phase buttons ────────────────────────────────────────────────────────
  test('all five phase buttons are visible', async ({ page }) => {
    for (const phase of ['Research', 'Spec', 'ML Train', 'Validate', 'Improve']) {
      await expect(page.locator(`button.btn:has-text("${phase}")`)).toBeVisible();
    }
  });

  test('phase buttons are clickable', async ({ page }) => {
    const phases = ['Research', 'Spec', 'ML Train', 'Validate', 'Improve'];
    for (const phase of phases) {
      await page.locator(`button.btn:has-text("${phase}")`).click();
      // Small pause so any triggered async doesn't interfere with next click
      await page.waitForTimeout(300);
    }
  });

  // ── Kanban board ─────────────────────────────────────────────────────────
  test('kanban board container is present', async ({ page }) => {
    await expect(page.locator('#board')).toBeAttached();
  });

  test('board meta footer is visible', async ({ page }) => {
    await expect(page.locator('#boardMeta')).toBeVisible();
    await expect(page.locator('#boardMeta')).toContainText('Kanban');
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// VALIDATION
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Validation Dashboard', () => {
  const PATH = '/dashboards/dashboard_validation.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Validation"', async ({ page }) => {
    await expect(page).toHaveTitle(/Validation/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── KPI cards ────────────────────────────────────────────────────────────
  test('KPI labels are rendered', async ({ page }) => {
    for (const label of ['Total', 'Approved', 'Pending', 'Warning', 'Human Review']) {
      await expect(page.locator(`.kpi-label:text("${label}")`)).toBeVisible();
    }
  });

  // ── Header buttons ───────────────────────────────────────────────────────
  test('Refresh button is visible and clickable', async ({ page }) => {
    const btn = page.locator('button.btn:has-text("Refresh")');
    await expect(btn).toBeVisible();
    await btn.click();
  });

  test('"Run Validation" button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Run Validation")')).toBeVisible();
  });

  test('"Run Validation" button is clickable', async ({ page }) => {
    const btn = page.locator('button:has-text("Run Validation")');
    await expect(btn).toBeEnabled();
    await btn.click();
    // Wait briefly and verify no crash
    await page.waitForTimeout(500);
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Validation table ─────────────────────────────────────────────────────
  test('validation results table is present', async ({ page }) => {
    await expect(page.locator('#vrows')).toBeAttached();
  });

  // ── Human Review card ────────────────────────────────────────────────────
  test('human review card is in DOM', async ({ page }) => {
    await expect(page.locator('#humanReviewCard')).toBeAttached();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});
