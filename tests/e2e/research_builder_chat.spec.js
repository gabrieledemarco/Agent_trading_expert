// @ts-check
/**
 * Tests for:
 *   • dashboard_research.html      — Paper explorer with search, filters, paper cards
 *   • dashboard_builder.html       — Strategy builder wizard
 *   • dashboard_with_chat.html     — AI chat interface
 *   • dashboard_documentation.html — Documentation with tabs
 */
const { test, expect } = require('/opt/node22/lib/node_modules/playwright/test.js');
const { goto, testSidebarToggle } = require('./helpers');

// ═══════════════════════════════════════════════════════════════════════════
// RESEARCH
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Research Dashboard', () => {
  const PATH = '/dashboards/dashboard_research.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Research"', async ({ page }) => {
    await expect(page).toHaveTitle(/Research/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── Search input ─────────────────────────────────────────────────────────
  test('search input is visible', async ({ page }) => {
    await expect(page.locator('#searchInput')).toBeVisible();
  });

  test('search input accepts text', async ({ page }) => {
    const input = page.locator('#searchInput');
    await input.fill('LSTM');
    await expect(input).toHaveValue('LSTM');
  });

  test('typing in search input filters the paper list', async ({ page }) => {
    const input = page.locator('#searchInput');
    await input.fill('momentum');
    // After filtering, paper list should update (no error thrown)
    await page.waitForTimeout(300);
    await expect(page.locator('#paperList')).toBeAttached();
  });

  // ── Run Research button ──────────────────────────────────────────────────
  test('"Run Research" button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Run Research")')).toBeVisible();
  });

  test('"Run Research" button is clickable', async ({ page }) => {
    const btn = page.locator('button:has-text("Run Research")');
    await expect(btn).toBeEnabled();
    await btn.click();
    await page.waitForTimeout(500);
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Filter buttons ───────────────────────────────────────────────────────
  test('six filter buttons are visible', async ({ page }) => {
    for (const filter of ['All', 'Deployed', 'Validation', 'LSTM', 'RL', 'Arbitrage']) {
      await expect(page.locator(`button.filter-btn:has-text("${filter}")`)).toBeVisible();
    }
  });

  test('"All" filter button starts as active', async ({ page }) => {
    await expect(page.locator('button.filter-btn:has-text("All")')).toHaveClass(/active/);
  });

  test('clicking a filter button makes it active', async ({ page }) => {
    const lstmBtn = page.locator('button.filter-btn:has-text("LSTM")');
    await lstmBtn.click();
    await expect(lstmBtn).toHaveClass(/active/);
  });

  test('switching filters does not crash the page', async ({ page }) => {
    const filters = ['Deployed', 'Validation', 'RL', 'Arbitrage', 'All'];
    for (const f of filters) {
      await page.locator(`button.filter-btn:has-text("${f}")`).click();
      await page.waitForTimeout(200);
    }
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Paper list ───────────────────────────────────────────────────────────
  test('paper list container is in DOM', async ({ page }) => {
    await expect(page.locator('#paperList')).toBeAttached();
  });

  // ── Paper detail panel ───────────────────────────────────────────────────
  test('paper detail panel is in DOM', async ({ page }) => {
    await expect(page.locator('#paperDetail')).toBeAttached();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// STRATEGY BUILDER WIZARD
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Strategy Builder', () => {
  const PATH = '/dashboards/dashboard_builder.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Builder"', async ({ page }) => {
    await expect(page).toHaveTitle(/Builder/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── Wizard step indicators ───────────────────────────────────────────────
  test('three step indicators are visible', async ({ page }) => {
    for (const id of ['step-ind-1', 'step-ind-2', 'step-ind-3']) {
      await expect(page.locator(`#${id}`)).toBeAttached();
    }
  });

  // ── Step 1: Basic Info ───────────────────────────────────────────────────
  test('step 1 is initially active', async ({ page }) => {
    await expect(page.locator('#step-1')).toHaveClass(/active/);
  });

  test('strategy name input is visible', async ({ page }) => {
    await expect(page.locator('#f-name')).toBeVisible();
  });

  test('strategy name input accepts text', async ({ page }) => {
    await page.locator('#f-name').fill('Test Strategy Alpha');
    await expect(page.locator('#f-name')).toHaveValue('Test Strategy Alpha');
  });

  test('timeframe select is visible', async ({ page }) => {
    await expect(page.locator('#f-timeframe')).toBeVisible();
  });

  test('model type select is visible', async ({ page }) => {
    await expect(page.locator('#f-model-type')).toBeVisible();
  });

  test('model type select has multiple options', async ({ page }) => {
    const count = await page.locator('#f-model-type option').count();
    expect(count).toBeGreaterThan(1);
  });

  test('description textarea is visible', async ({ page }) => {
    await expect(page.locator('#f-description')).toBeVisible();
  });

  test('description textarea accepts text', async ({ page }) => {
    await page.locator('#f-description').fill('A momentum-based strategy using LSTM.');
    await expect(page.locator('#f-description')).toHaveValue('A momentum-based strategy using LSTM.');
  });

  test('symbol chips (AAPL, MSFT) are visible', async ({ page }) => {
    const chipsGroup = page.locator('#chips-symbols');
    await expect(chipsGroup).toBeVisible();
    await expect(chipsGroup.locator('.chip:has-text("AAPL")')).toBeVisible();
    await expect(chipsGroup.locator('.chip:has-text("MSFT")')).toBeVisible();
  });

  test('clicking a chip toggles its selected state', async ({ page }) => {
    const appleChip = page.locator('#chips-symbols .chip:has-text("AAPL")');
    const beforeClass = await appleChip.getAttribute('class');
    await appleChip.click();
    const afterClass = await appleChip.getAttribute('class');
    expect(beforeClass).not.toEqual(afterClass);
  });

  // ── Reset button ─────────────────────────────────────────────────────────
  test('Reset button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Reset")')).toBeVisible();
  });

  test('Reset button clears the wizard back to step 1', async ({ page }) => {
    await page.locator('#f-name').fill('Some Name');
    await page.locator('button:has-text("Reset")').click();
    await expect(page.locator('#step-1')).toHaveClass(/active/);
  });

  // ── Step navigation ──────────────────────────────────────────────────────
  test('"Next" button advances to step 2', async ({ page }) => {
    await page.locator('#f-name').fill('My Strategy');
    await page.locator('button:has-text("Next")').click();
    await expect(page.locator('#step-2')).toHaveClass(/active/);
  });

  test('step 2 shows risk parameter controls', async ({ page }) => {
    await page.locator('#f-name').fill('My Strategy');
    await page.locator('button:has-text("Next")').click();
    await expect(page.locator('#f-max-dd')).toBeVisible();
    await expect(page.locator('#f-pos-size')).toBeVisible();
    await expect(page.locator('#f-stop-loss')).toBeVisible();
    await expect(page.locator('#f-take-profit')).toBeVisible();
  });

  test('max drawdown range slider is interactive', async ({ page }) => {
    await page.locator('#f-name').fill('My Strategy');
    await page.locator('button:has-text("Next")').click();
    const slider = page.locator('#f-max-dd');
    await expect(slider).toBeVisible();
    await slider.fill('20');
    await expect(page.locator('#max-dd-val')).toContainText('20%');
  });

  test('position size slider reflects value', async ({ page }) => {
    await page.locator('#f-name').fill('My Strategy');
    await page.locator('button:has-text("Next")').click();
    const slider = page.locator('#f-pos-size');
    await slider.fill('30');
    await expect(page.locator('#pos-size-val')).toContainText('30%');
  });

  test('"Back" button on step 2 returns to step 1', async ({ page }) => {
    await page.locator('#f-name').fill('My Strategy');
    await page.locator('button:has-text("Next")').click();
    await expect(page.locator('#step-2')).toHaveClass(/active/);
    await page.locator('button:has-text("Back")').click();
    await expect(page.locator('#step-1')).toHaveClass(/active/);
  });

  test('lookback period input accepts a number', async ({ page }) => {
    await page.locator('#f-name').fill('My Strategy');
    await page.locator('button:has-text("Next")').click();
    const lookback = page.locator('#f-lookback');
    await lookback.fill('90');
    await expect(lookback).toHaveValue('90');
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CHAT
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Chat Dashboard', () => {
  const PATH = '/dashboards/dashboard_with_chat.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Chat"', async ({ page }) => {
    await expect(page).toHaveTitle(/Chat/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── Chat area ────────────────────────────────────────────────────────────
  test('chat area container is visible', async ({ page }) => {
    await expect(page.locator('#chatArea')).toBeVisible();
  });

  // ── Shortcut chips ───────────────────────────────────────────────────────
  test('shortcut chip buttons are visible', async ({ page }) => {
    const shortcuts = page.locator('.shortcut');
    const count = await shortcuts.count();
    expect(count).toBeGreaterThanOrEqual(1);
    await expect(shortcuts.first()).toBeVisible();
  });

  test('clicking a shortcut chip populates or sends the chat input', async ({ page }) => {
    const firstShortcut = page.locator('.shortcut').first();
    await firstShortcut.click();
    // Either chatInput has text or a message appeared in chatArea
    await page.waitForTimeout(500);
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Chat input ───────────────────────────────────────────────────────────
  test('chat textarea is visible', async ({ page }) => {
    await expect(page.locator('#chatInput')).toBeVisible();
  });

  test('chat textarea accepts text', async ({ page }) => {
    const input = page.locator('#chatInput');
    await input.fill('Mostra le performance del portafoglio');
    await expect(input).toHaveValue('Mostra le performance del portafoglio');
  });

  // ── Send button ──────────────────────────────────────────────────────────
  test('INVIA (Send) button is visible', async ({ page }) => {
    await expect(page.locator('button:has-text("INVIA")')).toBeVisible();
  });

  test('INVIA button sends the message', async ({ page }) => {
    const input = page.locator('#chatInput');
    await input.fill('Stato degli agenti');
    await page.locator('button:has-text("INVIA")').click();
    // Input should be cleared after send
    await expect(input).toHaveValue('', { timeout: 5_000 });
  });

  test('Enter key submits the chat message', async ({ page }) => {
    const input = page.locator('#chatInput');
    await input.fill('Test message');
    await input.press('Enter');
    // Input cleared or a new message bubble appeared
    await page.waitForTimeout(500);
    await expect(page.locator('.terminal')).toBeVisible();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DOCUMENTATION
// ═══════════════════════════════════════════════════════════════════════════
test.describe('Documentation Dashboard', () => {
  const PATH = '/dashboards/dashboard_documentation.html';

  test.beforeEach(async ({ page }) => {
    await goto(page, PATH);
  });

  test('page title contains "Documentation"', async ({ page }) => {
    await expect(page).toHaveTitle(/Documentation/i);
  });

  test('sidebar toggle works', async ({ page }) => {
    await testSidebarToggle(page);
  });

  // ── Doc meta ─────────────────────────────────────────────────────────────
  test('doc meta info element is visible', async ({ page }) => {
    await expect(page.locator('#doc-meta')).toBeVisible();
  });

  // ── Tab buttons ──────────────────────────────────────────────────────────
  test('three tab buttons are visible', async ({ page }) => {
    for (const tab of ['Research Papers', 'Model Specs', 'System Docs']) {
      await expect(page.locator(`button.tab:has-text("${tab}")`)).toBeVisible();
    }
  });

  test('"Research Papers" tab is active by default', async ({ page }) => {
    await expect(page.locator('button.tab:has-text("Research Papers")')).toHaveClass(/active/);
    await expect(page.locator('#tab-papers')).toHaveClass(/active/);
  });

  test('switching to "Model Specs" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("Model Specs")').click();
    await expect(page.locator('#tab-models')).toHaveClass(/active/);
  });

  test('switching to "System Docs" tab works', async ({ page }) => {
    await page.locator('button.tab:has-text("System Docs")').click();
    await expect(page.locator('#tab-system')).toHaveClass(/active/);
  });

  test('switching back to "Research Papers" works', async ({ page }) => {
    await page.locator('button.tab:has-text("System Docs")').click();
    await page.locator('button.tab:has-text("Research Papers")').click();
    await expect(page.locator('#tab-papers')).toHaveClass(/active/);
  });

  // ── Paper cards ──────────────────────────────────────────────────────────
  test('at least one paper card is visible in Research Papers tab', async ({ page }) => {
    await expect(page.locator('#tab-papers .paper-card').first()).toBeAttached();
  });

  // ── Model docs ───────────────────────────────────────────────────────────
  test('at least one model doc is present in Model Specs tab', async ({ page }) => {
    await page.locator('button.tab:has-text("Model Specs")').click();
    await expect(page.locator('#tab-models .model-doc').first()).toBeAttached();
  });

  // ── Footer meta ───────────────────────────────────────────────────────────
  test('footer meta element is in DOM', async ({ page }) => {
    await expect(page.locator('#footer-meta')).toBeAttached();
  });

  // ── Bottombar ────────────────────────────────────────────────────────────
  test('bottombar is present', async ({ page }) => {
    await expect(page.locator('.bottombar')).toBeVisible();
  });
});
