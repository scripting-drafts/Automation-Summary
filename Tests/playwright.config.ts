import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30 * 1000,
  retries: 0,
  workers: process.env.CI ? 2 : undefined, // Parallel in CI
  use: {
    headless: true,
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  reporter: [['html', { outputFolder: 'playwright-report', open: 'never' }]],
});
