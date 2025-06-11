# E2E test suite using Playwright + TypeScript + Cucumber
  
Developed on Windows for Linux  
Find the ![Github Actions](.github/workflows/e2e.yml) including part of the deployment stript  

Includes:  
 - Test parallelization  
 - Report generation (video/screenshots)
  
Project structure example:  
```
/e2e-tests
│
├── features/
│   ├── login.feature
│
├── step-definitions/
│   └── login.steps.ts
│
├── support/
│   ├── world.ts
│   └── hooks.ts
│
├── playwright.config.ts
├── cucumber.ts
├── tsconfig.json
```
