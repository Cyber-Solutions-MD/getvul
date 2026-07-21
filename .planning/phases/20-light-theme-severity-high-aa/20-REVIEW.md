---
phase: 20-light-theme-severity-high-aa
reviewed: 2026-07-21T10:40:30Z
depth: standard
files_reviewed: 46
files_reviewed_list:
  - .claude/skills/sketch-findings-getvul/references/foundation.md
  - .claude/skills/sketch-findings-getvul/references/visual-language.md
  - .claude/skills/sketch-findings-getvul/sources/themes/sunset.css
  - frontend/e2e/a11y-routes.spec.ts
  - frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx
  - frontend/src/app/globals.css
  - frontend/src/components/assets/asset-vulns-list.test.tsx
  - frontend/src/components/assets/asset-vulns-list.tsx
  - frontend/src/components/assets/assets-table.test.tsx
  - frontend/src/components/assets/assets-table.tsx
  - frontend/src/components/assets/owner-card.tsx
  - frontend/src/components/assets/reassign-combobox.tsx
  - frontend/src/components/assets/remediation-timeline.tsx
  - frontend/src/components/assets/risk-card.tsx
  - frontend/src/components/assets/severity-ribbon.test.tsx
  - frontend/src/components/assets/severity-ribbon.tsx
  - frontend/src/components/connectors/connector-card.tsx
  - frontend/src/components/connectors/connector-form.tsx
  - frontend/src/components/connectors/sync-status-pill.test.tsx
  - frontend/src/components/connectors/sync-status-pill.tsx
  - frontend/src/components/connectors/wizard/confirm-step.tsx
  - frontend/src/components/connectors/wizard/test-step.tsx
  - frontend/src/components/cspm/finding-drill-content.tsx
  - frontend/src/components/cspm/microcopy.ts
  - frontend/src/components/dashboard/top5-card.tsx
  - frontend/src/components/tickets/blocked-toggle.tsx
  - frontend/src/components/tickets/kanban-column.tsx
  - frontend/src/components/tickets/kanban-reason-prompt.tsx
  - frontend/src/components/tickets/severity-glyph.ts
  - frontend/src/components/tickets/sla-pill.test.tsx
  - frontend/src/components/tickets/sla-pill.tsx
  - frontend/src/components/tickets/status-pill.test.tsx
  - frontend/src/components/tickets/status-pill.tsx
  - frontend/src/components/tickets/ticket-asset-card.tsx
  - frontend/src/components/tickets/ticket-bulk-bar.tsx
  - frontend/src/components/tickets/ticket-drill-content.tsx
  - frontend/src/components/tickets/vuln-count.test.tsx
  - frontend/src/components/tickets/vuln-count.tsx
  - frontend/src/components/ui/ChipBar.test.tsx
  - frontend/src/components/ui/RiskRing.test.tsx
  - frontend/src/components/ui/RiskRing.tsx
  - frontend/src/components/ui/trend-chart.tsx
  - frontend/src/components/users/directory-table.tsx
  - frontend/src/components/vulnerabilities/chip-bar.tsx
  - frontend/src/components/vulnerabilities/drill-content.tsx
  - frontend/src/components/vulnerabilities/vuln-table.tsx
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-07-21T10:40:30Z
**Depth:** standard
**Files Reviewed:** 46
**Status:** issues_found

## Summary

Phase 20 is a low-risk, mechanical CSS-token phase: it adds two design tokens
(`--color-severity-high-on-soft`, `--color-severity-critical-on-soft`) with light/dark values,
reconciles them into the design-system skill, and migrates foreground `text-severity-high` /
`text-severity-critical` Tailwind utilities to `text-[var(--color-*-on-soft)]` across ~30
component/test files.

The migration is correct and disciplined. I verified:

- **Token definitions (globals.css):** light values (`#9A3412`, `#991B1B`) sit in the
  `:root[data-theme="light"]` block; dark no-op values (`#FB923C`, `#F87171`, byte-identical to the
  base `--color-severity-high` / `--color-severity-critical` dark tokens) sit in the
  `:root[data-theme="dark"]` block. No duplicate selectors, base severity tokens untouched.
- **Token resolution:** `layout.tsx` always stamps `data-theme` (SSR default `"dark"` on `<html>`,
  FOUC bootstrap overrides pre-paint), so the tokens — which the vendored `src/styles/sunset.css`
  does not define — always resolve via one of the two themed blocks. No un-themed fallback gap. This
  mirrors the working Phase-16 violet/pink/amber-on-soft pattern.
- **Foreground-only migration:** every migrated site swapped only the `text-*` utility.
  `border-severity-*`, `bg-severity-*/10`, `ring-*`, and glyph-fill `bg-severity-*` usages
  (hero dot, login dots, ConfirmModal fill) all correctly remain on the bare token.
- **No missed sites:** grep across `src/` returns zero remaining bare `text-severity-high` /
  `text-severity-critical` foreground occurrences.
- **No broken arbitrary-value syntax:** all rewrites are well-formed `text-[var(--color-*-on-soft)]`
  string literals that Tailwind JIT will detect.
- **Tests:** every assertion that referenced a migrated class was updated; no stale bare-token
  assertions remain. The substring selector `td[class*="severity-critical-on-soft"]`
  (assets-table.test) and `.toContain('text-[var(--color-severity-critical-on-soft)]')` checks all
  match the new class strings.

One genuine deviation from a pure class-name swap (a dropped `/80` opacity modifier) is flagged
below as a Warning.

## Warnings

### WR-01: Dropped `/80` opacity modifier on the blocked-reason text alters dark-mode rendering

**File:** `frontend/src/components/tickets/blocked-toggle.tsx:96`
**Issue:** Every other site in this phase was a pure `text-severity-* → text-[var(--color-*-on-soft)]`
swap, but this one also silently dropped an opacity modifier:

```
- <span className="font-normal text-severity-critical/80">— {blockedReason}</span>
+ <span className="font-normal text-[var(--color-severity-critical-on-soft)]">— {blockedReason}</span>
```

The `/80` intentionally de-emphasized the secondary reason text relative to the full-strength
"Blocked" label. In **light** mode dropping it is correct — the a11y fix requires the darker
full-opacity `#991B1B` to clear AA, and `#DC2626` at 80% fails anyway. But in **dark** mode the
on-soft token is a deliberate no-op (`#F87171` = base `--color-severity-critical`), so this site
changes from `#F87171` at 80% alpha to 100% — a rendering change in a theme that never had an AA
problem here. The intended visual hierarchy (dimmer reason text) is lost in dark mode.

**Fix:** If the de-emphasis is intended to survive, keep an opacity distinction that also holds in
light mode, e.g. wrap in a muted token or apply reduced opacity via a channel-safe approach. Note
that `text-[var(--color-severity-critical-on-soft)]/80` does not reliably emit alpha for `var()`
arbitrary values in Tailwind 3.4, which is likely why it was dropped. If the full-opacity result is
acceptable (simplest), leave as-is but record the dark-mode change intentionally rather than as a
silent side effect. Low visual impact; no correctness or a11y regression.

## Info

### IN-01: Unconditional `console.log` diagnostics added to the axe e2e spec

**File:** `frontend/e2e/a11y-routes.spec.ts:73, 138`
**Issue:** Two unconditional `console.log("[axe] ... sweep completed ...")` lines were added as
"reached-the-end proof" for the axe sweeps. They reference in-scope variables (`routes`), do not
affect assertions or test reliability, and are a deliberate diagnostic response to the documented
"axe sweep not actually run during execution" hazard. Flagged only as a debug-artifact note.
**Fix:** No action required. Optionally downgrade to Playwright's `testInfo.annotations` or a
`test.info().attach` if console noise in CI output becomes a concern.

---

_Reviewed: 2026-07-21T10:40:30Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
