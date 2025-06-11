// Then run with "npx playwright test --project=Firefox"
// or all of them "npx playwright test"

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  projects: [
    { name: 'Chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'Firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'WebKit', use: { ...devices['Desktop Safari'] } },
  ],
});