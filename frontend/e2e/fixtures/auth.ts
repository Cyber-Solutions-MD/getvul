// Auth fixture re-export — authed specs import test/expect from here.
// storageState is wired per-project in playwright.config.ts (not in this fixture),
// so this file is a thin re-export providing a single import point for specs.
export { test, expect } from '@playwright/test';
