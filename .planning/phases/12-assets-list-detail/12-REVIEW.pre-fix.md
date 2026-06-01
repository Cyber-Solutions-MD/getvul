---
phase: 12-assets-list-detail
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 49
files_reviewed_list:
  - backend/alembic/versions/025_add_asset_tags.py
  - backend/app/assets/models.py
  - backend/app/assets/router.py
  - backend/app/assets/schemas.py
  - backend/app/ticketing/router.py
  - backend/app/ticketing/service.py
  - backend/tests/test_asset_owner_reassign.py
  - backend/tests/test_assets_tags_and_os_family.py
  - backend/tests/test_tickets_asset_id_filter.py
  - frontend/src/app/(authed)/dashboard/assets/[id]/page.test.tsx
  - frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx
  - frontend/src/app/(authed)/dashboard/assets/page.test.tsx
  - frontend/src/app/(authed)/dashboard/assets/page.tsx
  - frontend/src/components/assets/asset-vulns-list.test.tsx
  - frontend/src/components/assets/asset-vulns-list.tsx
  - frontend/src/components/assets/assets-chip-bar.test.tsx
  - frontend/src/components/assets/assets-chip-bar.tsx
  - frontend/src/components/assets/assets-table.test.tsx
  - frontend/src/components/assets/assets-table.tsx
  - frontend/src/components/assets/identity-metadata-rail.test.tsx
  - frontend/src/components/assets/identity-metadata-rail.tsx
  - frontend/src/components/assets/microcopy.ts
  - frontend/src/components/assets/owner-card.test.tsx
  - frontend/src/components/assets/owner-card.tsx
  - frontend/src/components/assets/reassign-combobox.test.tsx
  - frontend/src/components/assets/reassign-combobox.tsx
  - frontend/src/components/assets/remediation-timeline.test.tsx
  - frontend/src/components/assets/remediation-timeline.tsx
  - frontend/src/components/assets/risk-card.test.tsx
  - frontend/src/components/assets/risk-card.tsx
  - frontend/src/components/assets/severity-ribbon.test.tsx
  - frontend/src/components/assets/severity-ribbon.tsx
  - frontend/src/components/ui/Avatar.test.tsx
  - frontend/src/components/ui/Avatar.tsx
  - frontend/src/components/ui/Breadcrumb.test.tsx
  - frontend/src/components/ui/Breadcrumb.tsx
  - frontend/src/components/ui/ChipBar.test.tsx
  - frontend/src/components/ui/ChipBar.tsx
  - frontend/src/components/ui/RiskRing.test.tsx
  - frontend/src/components/ui/RiskRing.tsx
  - frontend/src/components/vulnerabilities/chip-bar.tsx
  - frontend/src/lib/queries/keys.ts
  - frontend/src/lib/queries/use-asset-detail.test.ts
  - frontend/src/lib/queries/use-asset-detail.ts
  - frontend/src/lib/queries/use-asset-remediations.test.ts
  - frontend/src/lib/queries/use-asset-remediations.ts
  - frontend/src/lib/queries/use-asset-vulnerabilities.test.ts
  - frontend/src/lib/queries/use-asset-vulnerabilities.ts
  - frontend/src/lib/queries/use-assets.test.ts
  - frontend/src/lib/queries/use-assets.ts
  - frontend/src/lib/queries/use-assignable-users.test.ts
  - frontend/src/lib/queries/use-assignable-users.ts
  - frontend/src/lib/queries/use-reassign-asset.test.tsx
  - frontend/src/lib/queries/use-reassign-asset.ts
  - frontend/src/lib/queries/use-vulnerabilities.ts
  - frontend/src/lib/util/os-family.test.ts
  - frontend/src/lib/util/os-family.ts
findings:
  blocker: 4
  warning: 14
  total: 18
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-05-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 49
**Status:** issues_found

## Summary

Phase 12 ships a substantial surface: a new ARRAY column on `assets` with a GIN index, an `os_family` allow-list filter, an `sla_breach` aggregation, a new `POST /assets/{id}/owner` route, a new `?asset_id=` filter on `GET /tickets`, four new TanStack hooks, two pages, and a generic descriptor-driven `<ChipBar>` primitive. Threat-model coverage is visible in the code (allow-list clamps, audit-before-commit, optimistic cache snapshot/rollback, T-12-* comments) and most listed mitigations hold up under inspection.

The defects that remain cluster around three weak spots:

1. **Input validation gaps on path/body params** — `asset_id` is typed `str` (not `uuid.UUID`) on three new/touched endpoints, and `assigned_user_email` has no format or length validation. The first surfaces as 500s on malformed UUIDs (the existing "unknown UUID returns empty" test only covers a well-formed zero UUID); the second lets arbitrary strings — including HTML/script payloads — be stored as `Asset.assigned_user` and propagated unsanitized into downstream surfaces (Asana task descriptions, audit logs, /tickets/assignees rollup).
2. **An accessibility blocker on the asset detail page** — `<main>` is nested inside the app-shell's own `<main>`, producing two `main` landmarks per page (axe rule `landmark-no-duplicate-main`).
3. **A cache-invalidation gap** — `useReassignAsset` invalidates `queryKeys.assets.all` but not the per-asset vuln list, which lives under `queryKeys.vulnerabilities.list({filters:{asset_id}, ...})`. After a reassign, the detail page's vulns list is stale until staleTime elapses or a manual refetch. Not currently a correctness issue (vulns don't carry owner), but the comment in the file claims the assets subtree is invalidated, which is misleading and brittle if vuln rows ever surface owner data.

A grammar bug ("1 assets") is encoded in both the page and its test, so the test is locking the defect in. Everything else is medium-severity polish / a11y refinement.

## Blocker Issues

### BL-01: `POST /assets/{id}/owner` accepts arbitrary email strings — no format validation, no length cap

**File:** `backend/app/assets/router.py:21-26, 417-474`
**Issue:** `_AssetOwnerUpdate.assigned_user_email` is typed as a raw `str`. The handler only strips, lowercases, and rejects empty payloads. There is no `EmailStr` (or regex) check and no `max_length`, so:
- A POST body of `{"assigned_user_email": "<img src=x onerror=alert(1)>"}` is accepted and written to `Asset.assigned_user` as-is. The frontend rendering path is React-text-escaped today, but `Asset.assigned_user` is also interpolated into Asana task descriptions in `ticketing/service.py:200` (`f"  Assigned User: {assigned_user}"`) and into the per-host rollup at `ticketing/router.py:143` (`{"name": r.assigned_user, "email": r.email}`) which is consumed by the assignee combobox — both are uncontrolled re-emission points.
- A 100MB email string is accepted and written to the DB (Postgres `String` is unbounded TEXT in SQLAlchemy's default mapping). Starlette enforces request-body size at the server, but the handler has no application-level cap.
- Plain non-email strings (e.g. `"alice"`) are also stored as `Asset.assigned_user`, then bypass `_get_directory_user` because that helper only matches when the value contains `@` (line 37). The audit row records the change as `from→to` regardless, so an analyst can poison `assigned_user` with arbitrary content and lose the directory-resolution path silently.

**Fix:**
```python
from pydantic import EmailStr, Field

class _AssetOwnerUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    assigned_user_email: EmailStr = Field(..., max_length=320)  # RFC 5321 cap
```
Also assert the input contains `@` in the handler if you keep `str` for any reason, and lower-bound the audit details with the original value before writing.

---

### BL-02: `asset_id` typed `str` on three asset endpoints — malformed UUIDs surface as 500s

**File:** `backend/app/assets/router.py:259, 362, 394, 419`
**Issue:** `get_asset`, `ignore_asset`, `unignore_asset`, and `update_asset_owner` all declare `asset_id: str`. The handler then does `Asset.id == asset_id`. Asset.id is a `UUID(as_uuid=True)` column; when asyncpg/SQLAlchemy serializes a non-UUID string it raises `DBAPIError` / `DataError`, which FastAPI converts to a 500. The unit test `test_tickets_asset_id_unknown_returns_empty` uses a well-formed zero UUID (`"00000000-..."`) so this path is uncovered. The same issue exists in `ticketing/service.py:628` (`Vulnerability.asset_id == asset_id`) used by `GET /tickets?asset_id=...`.

This becomes a denial-of-observation issue (each malformed probe is a 500 in the logs/alerting pipeline) and a tiny info-leak (the 500 stack trace differentiates the no-such-asset path from the bad-input path, which the prior author tried to avoid in `T-12-20`).

**Fix:**
```python
import uuid
async def get_asset(
    asset_id: uuid.UUID,  # FastAPI returns 422 on malformed UUIDs
    ...
)
```
Apply the same change to `ignore_asset`, `unignore_asset`, `update_asset_owner`, and the `asset_id` query param on `list_all_tickets` in `ticketing/router.py:103-106` (currently `str | None`). For the query param case, return `400` (not 422) on parse failure to preserve existing client error semantics, or coerce via a Pydantic field validator.

---

### BL-03: Duplicate `<main>` landmark on /assets/[id] — a11y violation

**File:** `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx:119`
**Issue:** The detail page wraps the left column in `<main className="space-y-6">`, but the app-shell at `frontend/src/components/shell/app-shell.tsx:14` already wraps page content in `<main className="px-6 py-6 lg:px-8 lg:py-8">{children}</main>`. The result is two nested `<main>` elements on every render of the asset detail page. axe-core rule `landmark-no-duplicate-main` (WCAG 1.3.1) flags this; assistive tech that skips to the main landmark will land on the outer wrapper while the inner `<main>` becomes an orphan. CLAUDE.md ranks state coverage / a11y as the audit's top pain point, so this is a regression against the project's own bar.

**Fix:** Replace the inner `<main>` with a semantically neutral wrapper (`<div>` or `<section aria-label="…"`):
```tsx
<section className="space-y-6" aria-label="Asset details">
```
Mirror the rest of the page: the right rail already uses `<aside>`, which is correct. Detail-page test (`page.test.tsx:138`) doesn't assert on `<main>`, so no test regression.

---

### BL-04: Pluralization bug locked in by test — "Inventory · 1 assets"

**File:** `frontend/src/app/(authed)/dashboard/assets/page.tsx:130-131`
**Issue:** The list page renders `{microcopy.page.eyebrow} · {total} assets` unconditionally — when `total === 1` the eyebrow reads "Inventory · 1 assets". The unit test at `frontend/src/app/(authed)/dashboard/assets/page.test.tsx:78` matches `Inventory · 1 assets` literally, so the defect is locked in — any future fix breaks CI. CLAUDE.md `copy-voice.md` says "peer, not butler"; broken pluralization is the opposite tone. This is the kind of "generic SaaS copy" the CLAUDE.md "what NOT to do" list calls out.

**Fix:**
```tsx
<div className="text-xs uppercase tracking-wide text-text-muted">
  {microcopy.page.eyebrow} · {total} {total === 1 ? 'asset' : 'assets'}
</div>
```
Update the test assertion to match the new copy. Consider co-locating an `inventoryEyebrow(n)` helper in `microcopy.ts` so the rule lives once.

---

## Warnings

### WR-01: `useReassignAsset` doesn't invalidate per-asset vulnerability list — comment is misleading

**File:** `frontend/src/lib/queries/use-reassign-asset.ts:71-77`
**Issue:** On success the hook invalidates `queryKeys.assets.byId(id)` and `queryKeys.assets.all`. The latter is `['assets']` — TanStack prefix-matches, so it correctly invalidates `assets.list`, `assets.detail`, `assets.vulnerabilities`, and `assets.remediations`. **However**, `useAssetVulnerabilities` does **not** key under `queryKeys.assets.*` — it wraps `useVulnerabilities`, which keys under `queryKeys.vulnerabilities.list({filters:{asset_id}, ...})` (verified at `keys.ts:14-21` and `use-vulnerabilities.ts:98-105`). After a reassign, that cache entry stays warm for the full `staleTime` of 30s. The header comment says "onSuccess: invalidate `queryKeys.assets.byId(id)` + `queryKeys.assets.all`" — which is accurate to what it does, but the surrounding prose implies the assets subtree covers everything on the detail page. It doesn't.

Today this isn't a correctness bug (vulns don't depend on owner), but the comment misleads future maintainers and the invariant breaks the moment a vuln row surfaces owner data (e.g. a future "owner" column on the vuln list).

**Fix:** Either narrow the comment to match reality, or invalidate explicitly:
```ts
onSuccess: (data) => {
  qc.invalidateQueries({ queryKey: queryKeys.assets.byId(assetId) });
  qc.invalidateQueries({ queryKey: queryKeys.assets.all });
  // Per-asset vuln list lives under the vulnerabilities subtree, not assets.
  qc.invalidateQueries({
    predicate: (q) =>
      Array.isArray(q.queryKey) &&
      q.queryKey[0] === 'vulnerabilities' &&
      JSON.stringify(q.queryKey).includes(`"asset_id":"${assetId}"`),
  });
  ...
}
```

---

### WR-02: `ReassignCombobox` commits raw input on Enter when no option is highlighted

**File:** `frontend/src/components/assets/reassign-combobox.tsx:86-90`
**Issue:** When the user presses Enter, the code does `commit(target?.email ?? input)`. If the directory call returned zero matches (or the user hasn't waited for results) and pressed Enter, the raw input string is sent to the mutation. Combined with BL-01 (no backend email validation), a user can commit `Bob` or `<script>` as a literal asset owner. The combobox should require selection from the directory list (the whole point of the combobox primitive over a free-text field).

**Fix:**
```ts
} else if (e.key === 'Enter') {
  e.preventDefault();
  const target = items[highlightIdx];
  if (!target) return;  // require selection — no free-text commit
  commit(target.email);
}
```
If free-text is genuinely desired (e.g. for external contractors not in the directory), validate the input matches an email regex before commit, and emit a different audit action so the two paths are distinguishable.

---

### WR-03: `<input>` is not the combobox — ARIA wiring on the wrong element

**File:** `frontend/src/components/assets/reassign-combobox.tsx:104-125`
**Issue:** Per WAI-ARIA Authoring Practices 1.2+ combobox pattern, the **input** element carries `role="combobox"`, `aria-controls` (referencing the listbox id), `aria-expanded`, `aria-activedescendant` (referencing the highlighted option's id), and `aria-autocomplete`. Here the **outer `<div>`** carries `role="combobox"` and the input is just `<input aria-label="...">`. Screen readers won't announce the popup state, won't follow the active descendant, and the keyboard contract is invisible to AT.

The `<li role="option">` elements lack `id` attributes, so `aria-activedescendant` wiring isn't possible without a refactor.

**Fix:** Move the combobox role onto the input, give listbox + options ids, and wire `aria-activedescendant`:
```tsx
<input
  ref={inputRef}
  role="combobox"
  aria-controls="reassign-listbox"
  aria-expanded={items.length > 0}
  aria-autocomplete="list"
  aria-activedescendant={items[highlightIdx] ? `reassign-opt-${highlightIdx}` : undefined}
  ...
/>
<ul id="reassign-listbox" role="listbox" ...>
  {items.map((u, idx) => (
    <li id={`reassign-opt-${idx}`} role="option" ...>
  ))}
</ul>
```
Drop `role="combobox"` from the wrapper `<div>`.

---

### WR-04: `last_checkin_at` rendered via Python `str()` not `.isoformat()` — inconsistent with sibling timestamp fields

**File:** `backend/app/assets/router.py:324`
**Issue:** `get_asset` returns `"last_checkin_at": str(asset.last_checkin_at) if asset.last_checkin_at else None`. Every other timestamp field in the same dict uses `.isoformat()` (`last_login_at:315`, `last_seen_at:316`, `ignored_at:339`). `str(datetime)` produces `"2026-05-20 10:00:00+00:00"` (space, no `T`), `.isoformat()` produces `"2026-05-20T10:00:00+00:00"`. Frontend `IdentityMetadataRail` renders it raw in mono, so analysts see one timestamp in a different format than the others on the same card.

**Fix:**
```python
"last_checkin_at": asset.last_checkin_at.isoformat() if asset.last_checkin_at else None,
```
A frontend formatter (e.g. a `relativeTimestamp` helper akin to `RemediationTimeline`'s) would be a cleaner long-term fix.

---

### WR-05: `useAssetRemediations` interpolates `assetId` into URL without `encodeURIComponent`

**File:** `frontend/src/lib/queries/use-asset-remediations.ts:36-40`
**Issue:** The query URL is `\`/api/v1/tickets?asset_id=${assetId}&page=1\``. `assetId` comes from `useParams<{id: string}>()`, which is router-provided and almost always a UUID, but the function signature accepts `string | null | undefined` — i.e. anything. If a caller ever passes a value containing `&`, `#`, `?`, or whitespace, the URL is silently corrupted. UUIDs are safe; the issue is hygiene, not exploit.

**Fix:**
```ts
queryFn: ({ signal }) => {
  const sp = new URLSearchParams();
  sp.set('asset_id', assetId!);
  sp.set('page', '1');
  return api<RemediationsResponse>(`/api/v1/tickets?${sp.toString()}`, { signal });
},
```
Consistent with the `buildSearchParams` pattern in `use-assets.ts` and `use-vulnerabilities.ts`.

---

### WR-06: `_AssetOwnerUpdate` lacks `extra="forbid"` — T-12-08 mitigation comment is technically inaccurate

**File:** `backend/app/assets/router.py:21-26`
**Issue:** The docstring claims "Pydantic drops unknown extra keys silently, killing T-12-08 (mass assignment via the reassign body)." That's *describing* the default behaviour but isn't actually a mitigation — the mitigation here is that the handler explicitly reads `body.assigned_user_email` and writes it to one column only (`asset.assigned_user = new_email`), so extras can't reach the ORM regardless. The comment's framing implies Pydantic is doing defensive work that it isn't. If a future change ever does `for k, v in body.dict(): setattr(asset, k, v)`, the lack of `extra="forbid"` becomes a real gap.

**Fix:** Add the config defensively (zero cost, future-proofs the threat model):
```python
class _AssetOwnerUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    assigned_user_email: str
```
And update the docstring to describe the actual mitigation (explicit field copy at the handler level).

---

### WR-07: `AssetVulnsList` violates ARIA `table` role structure — missing `rowgroup`

**File:** `frontend/src/components/assets/asset-vulns-list.tsx:57-90`
**Issue:** The wrapper has `role="table"` and direct children carry `role="row"`. WAI-ARIA spec requires an intervening `role="rowgroup"` (mirroring `<tbody>`) between `table` and `row`. axe-core flags this as `aria-required-children`. Compare with `AssetsTable` which uses semantic `<table>`/`<tbody>` and avoids the role overlay entirely.

**Fix:** Either wrap rows in a `role="rowgroup"` div, or switch to semantic HTML for this surface as the column-style assets table does. The simpler fix:
```tsx
<div role="table" aria-label="Vulnerabilities on this host" ref={tbodyRef}>
  <div role="rowgroup">
    {rows.map((r, idx) => (
      <div role="row" tabIndex={0} ...>
```

---

### WR-08: `AssetVulnsList` keyboard handler missing `Home`/`End` — inconsistent with sibling `AssetsTable`

**File:** `frontend/src/components/assets/asset-vulns-list.tsx:30-48`
**Issue:** `AssetsTable.tsx:51-75` handles `ArrowDown`/`ArrowUp`/`Home`/`End`/`Enter`/`Space`. `AssetVulnsList` only handles `ArrowDown`/`ArrowUp`/`Enter`/`Space`. Keyboard users navigating between the two tables on the detail page encounter inconsistent contracts.

**Fix:** Mirror the AssetsTable handler — add `Home` (focus first row) and `End` (focus last row) branches.

---

### WR-09: `Avatar.initialsFor` only emits the first letter — "alice carter" → "A", not "AC"

**File:** `frontend/src/components/ui/Avatar.tsx:14-20, 31`
**Issue:** Tests (Avatar.test.tsx:10) lock the behavior to `"A"` for `name="alice carter"`. Most avatar conventions use the first letter of first + last name ("AC"). The sketch reference at `.claude/skills/sketch-findings-getvul/references/visual-language.md` isn't viewable from this review, but the project owner card in `owner-card.tsx:78-82` passes `name={du?.display_name}` and a single-letter initial may look sparse next to the role + email. Worth a sketch-spec confirmation before shipping; the current implementation is intentional but minimalist.

**Fix:** If two-letter initials are desired:
```ts
function initialsFor(name?: string, email?: string): string {
  const trimmedName = (name ?? '').trim();
  if (trimmedName) {
    const parts = trimmedName.split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return parts[0][0].toUpperCase();
  }
  ...
}
```
If single-letter is the locked sketch choice, leave it but add a comment citing the sketch decision so the next reviewer doesn't second-guess.

---

### WR-10: `pageErrorFallback` truncates `err.message` to 40 chars — silently drops the rest, including request IDs longer than that

**File:** `frontend/src/app/(authed)/dashboard/assets/page.tsx:60-67`
**Issue:** `requestId: err.message.slice(0, 40) || 'unknown'` — if `err.message` is a JSON-blob with a request id past character 40, the analyst loses traceability. Same pattern at `page.tsx:142-145` and `[id]/page.tsx:90-95`. The slice masquerades as a request id but actually contains arbitrary error prefix. Either parse the error properly or pass the full message.

**Fix:** Add a `getRequestId(err: Error): string | undefined` helper that pulls a `requestId` field from a structured error (define an `ApiError` class in `@/lib/api`), or pass `err.message` in full and let `PartialFailureBanner` truncate visually with `text-overflow: ellipsis`.

---

### WR-11: `Crumb` uses array index as React key

**File:** `frontend/src/components/ui/Breadcrumb.tsx:56-67`
**Issue:** `<span key={idx} ...>` keys children by position. Breadcrumb trails are typically stable per render but if a parent ever conditionally renders crumbs (e.g. inserting a "Settings" crumb mid-trail), React would reconcile the wrong nodes. Idiomatic React prefers a stable key — even `key={crumb.props.href ?? crumb.props.children}` would be more robust.

**Fix:**
```tsx
{items.map((item, idx) => {
  const child = item as ReactElement<CrumbProps>;
  const k = child.props.href ?? String(child.props.children);
  return (
    <span key={k} ...>
```

---

### WR-12: `RemediationTimeline` STATUS_TONE table doesn't cover Asana's lowercase status strings

**File:** `frontend/src/components/assets/remediation-timeline.tsx:26-58`
**Issue:** Backend `Ticket.external_status` is set to `"open"` and `"completed"` in the ticketing service (`service.py:149, 806, 859, 945`) — lowercase. The component upper-cases and normalizes (`statusKey = (t.external_status ?? '').toUpperCase().replace(/[ -]+/g, '_')`) which converts `"open"` → `"OPEN"` (matched ✓) and `"completed"` → `"COMPLETED"` (NOT in STATUS_TONE — only OPEN, IN_PROGRESS, RESOLVED, CLOSED are mapped). Completed tickets render with the fallback `"border-border-subtle bg-surface-2 text-text-faint"` instead of the resolved/closed green. The remediation timeline test at `remediation-timeline.test.tsx:79-83` checks `"OPEN"` and `"IN_PROGRESS"` only — completed tickets are uncovered.

**Fix:**
```ts
const STATUS_TONE: Record<string, string> = {
  OPEN: 'border-violet/40 bg-violet-soft text-violet',
  IN_PROGRESS: 'border-severity-high/40 bg-severity-high/10 text-severity-high',
  RESOLVED: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
  CLOSED: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
  COMPLETED: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
};
```
Add a `"completed"` ticket to the test fixture and assert it renders with the resolved tone.

---

### WR-13: AssetsPage `q.error` path renders BOTH the banner AND the EmptyState when `items.length === 0`

**File:** `frontend/src/app/(authed)/dashboard/assets/page.tsx:138-170`
**Issue:** When `q.error` is set, the banner renders above the body. The body then falls into `items.length === 0 ? <EmptyState>` because `q.data?.items ?? []` returns `[]` on error. The user sees both "Something failed, retry" and "No assets match these filters" — contradictory copy. Use a guard:

**Fix:**
```tsx
{q.error ? (
  <PartialFailureBanner errors={[...]} onRetry={() => q.refetch()} />
) : isLoading ? (
  <SkeletonTable ... />
) : items.length === 0 ? (
  <EmptyState>...</EmptyState>
) : (
  <>
    <AssetsTable ... />
    ...
  </>
)}
```

---

### WR-14: `_reset_engine_pool` autouse fixture documents a pre-existing bug but ships as a permanent workaround

**File:** `backend/tests/test_assets_tags_and_os_family.py:36-39`, `backend/tests/test_asset_owner_reassign.py:37-40`, `backend/tests/test_tickets_asset_id_filter.py:28-32`
**Issue:** Three test files newly added in Phase 12 each ship the same autouse fixture that disposes the engine pool before every test. The docstrings explain the pre-existing infra defect (module-level async engine binds to the first event loop; pytest-asyncio creates a fresh loop per function). The workaround is fine for unblocking Phase 12 but copying it into three places ensures the next test author copies it into a fourth, and the underlying issue never gets root-caused. The right home is `conftest.py` so the workaround applies once.

**Fix:** Move the fixture to `backend/tests/conftest.py` with the same comment, and delete the three local copies. File a follow-up issue to migrate to a function-scoped engine (or `scope="session"` event loop) so the workaround can eventually be removed entirely.

---

## Notes / non-findings reviewed and cleared

- **SQL injection via `os_family`** — Cleared. Patterns are hardcoded server-side; user input is clamped through an allow-list intersection (`router.py:121-136`). The CSV split is fed into a set membership test, not interpolated.
- **SQL injection via `sort_by`** — Cleared. Allow-list at `router.py:143-144` limits sort columns to a known set.
- **Cross-tenant access on `/tickets?asset_id`** — Cleared. The subquery is unscoped by tenant, but the outer `Ticket.tenant_id == tenant_id` constraint binds the result set. Cross-tenant probes return empty pages (T-12-21 is correctly mitigated, and the test suite covers it).
- **XSS via Avatar.name** — Cleared. React text escaping prevents element injection; the test at `Avatar.test.tsx:37-42` confirms.
- **XSS via reflected URL state** — Cleared. `useUrlStateList` clamps reflected values on both read and write through hardcoded allow-lists at each call site (T-12-05, T-12-13).
- **Mass assignment on owner reassign** — Cleared. The handler explicitly assigns only `asset.assigned_user`; even if Pydantic accepted extras, they couldn't reach the ORM. (See WR-06 for a clarification of the misleading comment.)
- **404 vs 403 on cross-tenant asset reassign** — Cleared. `update_asset_owner` returns 404 (T-12-20) and the test at `test_asset_owner_reassign.py:111-144` covers it.
- **Audit row written without commit** — Cleared. Audit + mutation are in the same transaction; an audit failure short-circuits the commit (T-12-09).
- **Optimistic update rollback** — Cleared. `useReassignAsset.onError` restores the snapshot and emits an error toast; test at `use-reassign-asset.test.tsx:100-116` covers it.

---

_Reviewed: 2026-05-30T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
