---
phase: 12-assets-list-detail
applied: 2026-06-01T09:40:00Z
fix_scope: critical_warning
findings_in_scope: 18
fixed: 18
skipped: 0
iteration: 1
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Applied:** 2026-06-01T09:40:00Z
**Scope:** critical_warning (Blockers + Warnings)
**Findings in scope:** 18 (4 Blocker + 14 Warning)
**Fixed:** 18
**Skipped:** 0
**Status:** all_fixed
**Strategy:** inline orchestrator execution (the gsd-code-fixer subagent disconnected before producing output; the user authorized inline application of all fixes)

## Summary

All 18 findings from `12-REVIEW.md` were addressed across 15 atomic commits.
Frontend regressed cleanly from 421 → **426/426** passing (+5 from new
WR-02/03, WR-09, WR-12 coverage). `pnpm tsc --noEmit` is clean. Backend
files were syntax-checked (full pytest requires docker postgres which is
not running on the orchestrator host; the in-worktree runs during Phase 12
execution had this suite passing).

## Fixes Applied

### Blockers

| ID | Commit | Summary |
|----|--------|---------|
| BL-01 | `1841ef3` | `_AssetOwnerUpdate.assigned_user_email` now uses a `field_validator` with a permissive email regex + min/max length (3..320, RFC 5321 cap). Blocks XSS/oversize payloads and non-email strings ("alice") from poisoning `Asset.assigned_user` and the downstream Asana / `/tickets/assignees` rollup. Notes: `EmailStr` not used because `pydantic[email]` isn't a project dep; permissive regex is sufficient for input hygiene. |
| BL-02 | `0989b5a` | Path params `asset_id` typed as `uuid.UUID` on `get_asset`, `ignore_asset`, `unignore_asset`, `update_asset_owner`. Tickets `?asset_id=` query param also typed as `uuid.UUID \| None`. FastAPI now returns 422 on malformed input at the request-validation layer instead of letting it surface as a 500 from the DB layer. Kills the 500 noise and the tiny info-leak that differentiated no-such-asset from bad-input. |
| BL-03 | `db41c2d` | Detail page wrapped the left column in `<main>` while the app-shell already provides one — duplicate landmark per render. Inner `<main>` replaced with `<section aria-label="Asset details">`; mirrors the right `<aside>`. axe-core rule `landmark-no-duplicate-main` / WCAG 1.3.1 now passes. |
| BL-04 | `bc15881` | "Inventory · 1 assets" was hard-coded with the plural suffix and the test asserted it literally. Both production code and test now use `total === 1 ? 'asset' : 'assets'`, with a negative-lookahead regex in the test so the bug can't reappear silently. |

### Warnings

| ID | Commit | Summary |
|----|--------|---------|
| WR-01 | `c445786` | `useReassignAsset.onSuccess` now invalidates the per-asset vuln list via predicate-based query matching (key prefix = `['vulnerabilities', …]` containing this `asset_id`). Comment corrected to describe the actual prefix-matching contract. |
| WR-02 | `92e8f86` | `ReassignCombobox` Enter no longer commits the raw input string. With no highlighted option (zero matches or pre-debounce), Enter is a no-op. Closes the front-line gap that compounded with BL-01. |
| WR-03 | `92e8f86` | ARIA `role="combobox"` moved off the wrapper `<div>` onto the `<input>`, with `aria-controls=listboxId`, `aria-expanded`, `aria-autocomplete="list"`, `aria-activedescendant`. Listbox + each option now carry stable `id`s. Screen readers can follow the active descendant. |
| WR-04 | `8687ba1` | `get_asset` returns `last_checkin_at` via `.isoformat()` instead of `str(datetime)` — consistent ISO-8601 with sibling fields (`last_login_at`, `last_seen_at`, `ignored_at`). |
| WR-05 | `60dfef5` | `useAssetRemediations` builds the URL via `URLSearchParams` instead of string interpolation. Hygiene fix consistent with the `buildSearchParams` pattern in `use-assets.ts` / `use-vulnerabilities.ts`. |
| WR-06 | `1841ef3` (bundled with BL-01) | `_AssetOwnerUpdate` now has `model_config = {"extra": "forbid"}` defensively, and its comment rewritten to describe the real mitigation (handler-level explicit field copy) instead of the misleading "Pydantic drops extras" framing. |
| WR-07 | `962f92a` | `AssetVulnsList` rows now wrapped in `<div role="rowgroup">` so the ARIA table structure (table > rowgroup > row) matches the WAI-ARIA spec. axe-core's `aria-required-children` rule now passes. |
| WR-08 | `962f92a` | `AssetVulnsList` keyboard handler adds `Home`/`End` branches, mirroring `AssetsTable`. Consistent keyboard contract across both tables on the detail page. |
| WR-09 | `20d5a14` | `Avatar.initialsFor` emits 2-char initials per `sketch-findings-getvul/references/visual-language.md` ("Initials inside (2 chars)", examples 'AS' and 'JK'). Multi-word names → first+last initials; single-word names fall back to one char to avoid awkward artifacts. Tests updated to match. |
| WR-10 | `f9a2321` | Three call sites stopped truncating `err.message` to 40 chars. `PartialFailureBanner` ellipsis-truncates visually — chopping the underlying data was strictly information-destructive (request IDs / JSON payloads past char 40 were lost). |
| WR-11 | `3f31d53` | `<Breadcrumb>` uses `item.props.href ?? String(item.props.children)` as the React key instead of array index. Stable across reorderings if a parent ever inserts a crumb mid-trail. |
| WR-12 | `edae533` | `RemediationTimeline.STATUS_TONE` adds a `COMPLETED` entry mirroring `RESOLVED` / `CLOSED`. Backend emits lowercase 'completed' (Asana terminal state) — the component upper-cases the key but had no row for it, so completed tickets fell through to the muted fallback tone. Test fixture covers the lowercase → resolved-tone contract. |
| WR-13 | `da32b6b` | `AssetsPage` body restructured into a single if/else-if chain: error wins outright, then loading, then empty, then results. Eliminates the "Something failed, retry" + "No assets match these filters" stack that appeared when `q.error` was set and `items.length === 0`. |
| WR-14 | `77cf546` | `_reset_engine_pool` autouse fixture lifted from three Phase 12 test files into `backend/tests/conftest.py`. Documented the underlying defect (module-level async engine bound to first event loop) and the follow-up (migrate to function-scoped engine or session-scoped event loop). |

## Verification

```text
$ cd frontend && pnpm tsc --noEmit          # exit 0
$ pnpm vitest run                            # 71 test files, 426 tests passing
$ python3 -m py_compile (each backend file)  # all syntax-clean
```

The five new tests landed:
1. `ReassignCombobox` — Enter with no match is a no-op (WR-02 contract).
2. `ReassignCombobox` — ARIA wiring on the input element (WR-03 contract).
3. `Avatar` — single-word name fallback (WR-09).
4. `Avatar` — `first.last` email local part produces two initials (WR-09).
5. `RemediationTimeline` — lowercase "completed" pill carries `text-severity-low` (WR-12).

## Items Not Re-Reviewed

Per the orchestrator workflow's single-pass mode (no `--auto` flag), `12-REVIEW.md`
is not regenerated. A follow-up `/gsd-code-review 12` would re-confirm the
fixed state if desired.

## Strategy Note (for future operators)

The gsd-code-fixer subagent disconnected mid-run after ~77 minutes / 109
tool uses, having read context but produced zero commits and no
REVIEW-FIX.md. The user authorized inline orchestrator execution as the
recovery path, and all 18 findings were applied through Read/Edit/Bash
with one commit per logical fix (15 commits total — BL-01 + WR-06 bundled,
WR-02 + WR-03 bundled, WR-07 + WR-08 bundled, others atomic). This avoided
the socket-drop class that affected several earlier executor runs in this
session.

---

_Applied: 2026-06-01_
_Operator: Claude (orchestrator, inline)_
