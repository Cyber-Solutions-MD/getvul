# Deferred Items — Phase 09 / Plan 01

Pre-existing issues found during execution that are out of scope for this plan.
Each entry includes the task it was found during and why it was deferred.

## Pre-existing type errors in src/app/dashboard/cspm/page.tsx

**Found during:** Task 1 verification (`npx tsc --noEmit`)
**Errors:**
- `src/app/dashboard/cspm/page.tsx(571,19): error TS2339: Property 'name' does not exist on type 'ComplianceFramework'`
- `src/app/dashboard/cspm/page.tsx(580,68): error TS2339: Property 'name' does not exist on type 'ComplianceFramework'`

**Why deferred:** Pre-existing errors in code untouched by this plan. Plan 09-01 is the token/theme/test-infra foundation — it does not modify CSPM. Per Rule 3 SCOPE BOUNDARY, pre-existing failures in unrelated files are out of scope.

**Reference commit on rolled-back branch:** `c3ae8fc fix: CSPM compliance tab — use fw.name not fw.framework (matches API)` — fix may need to be re-applied (or the `ComplianceFramework` type needs to add `name`).

**Suggested follow-up:** Apply the rolled-back CSPM fix or update the `ComplianceFramework` type definition. Will be addressed by a later vertical-slice phase that touches /dashboard/cspm (likely Phase 14 — Remaining Screens).

## `npm run lint` requires interactive eslint setup

**Found during:** Task 3 / overall plan §verification step 3
**Issue:** `npm run lint` (next lint) drops into an interactive ESLint setup wizard on first run because the project has no eslint config file (no `.eslintrc.json`, no `eslint.config.mjs`). The Next.js CLI even prints a deprecation warning: `next lint is deprecated and will be removed in Next.js 16. Migrate to the ESLint CLI`.

**Why deferred:** Pre-existing project state at base commit `10d5842`. Plan 09-01's scope is token system + theme + test infrastructure. The eslint migration is a separate concern (and Next 16 migration). Per Rule 3 SCOPE BOUNDARY, the lint tooling is out of scope.

**Suggested follow-up:** In a later wave (or before any lint-gated CI), either:
- Run `npx @next/codemod@canary next-lint-to-eslint-cli .` to migrate
- Add a stub `eslint.config.mjs` shipping the Next.js eslint plugin
- Replace the `lint` script entirely with `eslint .`

The plan's other verification gates (test, tsc, !important count, vendoring, no-HSL) all PASS.
