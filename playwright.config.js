// @ts-check
const { defineConfig, devices } = require('/opt/node22/lib/node_modules/playwright/test.js');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: [['html', { open: 'never' }], ['list']],

  use: {
    baseURL: 'https://agent-trading-expert.onrender.com',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    // Render free tier can cold-start slowly — give it room
    navigationTimeout: 60_000,
    actionTimeout: 15_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
