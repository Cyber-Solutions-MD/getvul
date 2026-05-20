---
phase: 10-dashboard
reviewed: 2026-05-18T12:00:00Z
depth: standard
files_reviewed: 75
files_reviewed_list:
  - backend/app/vulnerabilities/dashboard.py
  - backend/app/vulnerabilities/router.py
  - backend/app/vulnerabilities/schemas.py
  - backend/app/vulnerabilities/service.py
  - backend/app/vulnerabilities/trends.py
  - backend/tests/conftest.py
  - backend/tests/test_dashboard_tiles.py
  - backend/tests/test_onboarding_state.py
  - backend/tests/test_severity_trends.py
  - backend/tests/test_snooze.py
  - backend/tests/test_top_vuln.py
  - backend/tests/test_triage_sort.py
  - backend/tests/test_unsnooze.py
  - frontend/scripts/check-bundle.mjs
  - frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx
  - frontend/src/app/(authed)/dashboard/page.test.tsx
  - frontend/src/app/(authed)/dashboard/page.tsx
  - frontend/src/app/dev/primitives/page.tsx
  - frontend/src/app/layout.tsx
  - frontend/src/app/providers.tsx
  - frontend/src/components/dashboard/activity-rail.tsx
  - frontend/src/components/dashboard/hero.test.tsx
  - frontend/src/components/dashboard/hero.tsx
  - frontend/src/components/dashboard/microcopy.ts
  - frontend/src/components/dashboard/onboarding-panel.test.tsx
  - frontend/src/components/dashboard/onboarding-panel.tsx
  - frontend/src/components/dashboard/stat-strip-wired.test.tsx
  - frontend/src/components/dashboard/stat-strip-wired.tsx
  - frontend/src/components/dashboard/top5-card.test.tsx
  - frontend/src/components/dashboard/top5-card.tsx
  - frontend/src/components/dashboard/trend-section.test.tsx
  - frontend/src/components/dashboard/trend-section.tsx
  - frontend/src/components/shell/app-shell.test.tsx
  - frontend/src/components/shell/sidebar-cache.test.tsx
  - frontend/src/components/shell/sidebar.test.tsx
  - frontend/src/components/shell/sidebar.tsx
  - frontend/src/components/ui/Toast.tsx
  - frontend/src/components/ui/ToastProvider.tsx
  - frontend/src/components/ui/activity-feed.test.tsx
  - frontend/src/components/ui/activity-feed.tsx
  - frontend/src/components/ui/card.test.tsx
  - frontend/src/components/ui/card.tsx
  - frontend/src/components/ui/error-boundary.test.tsx
  - frontend/src/components/ui/error-boundary.tsx
  - frontend/src/components/ui/stat-strip.test.tsx
  - frontend/src/components/ui/stat-strip.tsx
  - frontend/src/components/ui/stat.test.tsx
  - frontend/src/components/ui/stat.tsx
  - frontend/src/components/ui/toast.test.tsx
  - frontend/src/components/ui/trend-chart-skeleton.tsx
  - frontend/src/components/ui/trend-chart.motion.test.tsx
  - frontend/src/components/ui/trend-chart.test.tsx
  - frontend/src/components/ui/trend-chart.tsx
  - frontend/src/hooks/use-document-title.test.ts
  - frontend/src/hooks/use-document-title.ts
  - frontend/src/hooks/use-prefers-reduced-motion.test.ts
  - frontend/src/hooks/use-prefers-reduced-motion.ts
  - frontend/src/hooks/use-url-state.test.ts
  - frontend/src/hooks/use-url-state.ts
  - frontend/src/lib/api.test.ts
  - frontend/src/lib/api.ts
  - frontend/src/lib/auth.logout.test.tsx
  - frontend/src/lib/auth.tsx
  - frontend/src/lib/mutations/use-snooze.test.tsx
  - frontend/src/lib/mutations/use-snooze.ts
  - frontend/src/lib/mutations/use-undo-snooze.test.tsx
  - frontend/src/lib/mutations/use-undo-snooze.ts
  - frontend/src/lib/queries/keys.ts
  - frontend/src/lib/queries/use-recent-notifications.test.tsx
  - frontend/src/lib/queries/use-recent-notifications.ts
  - frontend/src/lib/queries/use-stats.test.tsx
  - frontend/src/lib/queries/use-stats.ts
  - frontend/src/lib/queries/use-top-triage.test.tsx
  - frontend/src/lib/queries/use-top-triage.ts
  - frontend/src/lib/queries/use-trends.test.tsx
  - frontend/src/lib/queries/use-trends.ts
  - frontend/src/lib/query-client.ts
  - frontend/vitest.setup.ts
findings:
  blocker: 6
  warning: 14
  total: 20
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-05-18T12:00:00Z
**Depth:** standard
**Files Reviewed:** 75
**Status:** issues_found

## Summary

The Phase-10 dashboard work is well-tested and largely correct on the security-critical paths the orchestrator flagged: tenant_id filters are present on both snooze and unsnooze, RBAC uses `require_analyst` correctly, V11 30-day bound is enforced server-side, audit events are emitted, and the XSS clamp in `useUrlState` is sound. Tests for these contracts exist and assert the right behaviors.

However, the implementation contains real defects that should not ship as-is:

1. **Type-contract drift between backend and frontend on `top_vuln`** — backend declares `host`, `path`, `cvss` as nullable, frontend types them as non-nullable, and the Hero renders crashy `null`-coerced values. This is a runtime UI bug masked by the type cast.
2. **The Top-5 hook deserializes the `VulnerabilitySummary` payload as a `TriageRow` schema that does not match the backend** — `host` (frontend) vs `asset_hostname` (backend) and `cvss_v3_score` is `Decimal` from a Pydantic schema that doesn't include `sla_due_at` or `host` on the list endpoint. Top5Card will render empty hosts and `null` CVSS columns against a real backend.
3. **`AuditLog` is added via `db.add()` inside a try/except that swallows every exception**, then snooze / unsnooze commit immediately after. If the audit insert fails (e.g., FK violation, DB error), the snooze succeeds without an audit trail — the test that asserts an audit row would pass on a happy path but the production guarantee in the docstring is not enforced.
4. **The `api()` 401-refresh retry path silently breaks AbortSignal contract** in one edge case: when `signal` is already aborted at refresh time, the retry will throw `AbortError` but `api()`'s retry path is not idempotent for mutations (snooze / unsnooze are POSTs that would have already partially succeeded server-side on the first call, then re-run after refresh — see WR-04).
5. **The `audit.audit()` helper does NOT commit on its own** — it only `db.add()`s; the router calls `await db.commit()` afterwards. If any code between `db.add(log)` and `db.commit()` raises (such as `compute_risk_scores`), the audit row is rolled back even though the user already saw the success path partially execute.
6. **The 7-day delta computation casts `prior_metrics.get(snapshot_key, 0)` to int but the JSONB column may legitimately contain `None`** — `int(None)` raises `TypeError`, which would crash `/stats` for any tenant whose 7-day-ago snapshot has a partial metric dict.

Quality issues: several minor hygiene items (unbounded notification page_size, fall-through patterns, type assertions hiding bugs, race in QueryClient unmount cleanup, untested 30-day boundary). Details below.

## Blockers

### BL-01: Frontend `TopVuln` type lies about nullability — `cvss.toFixed(1)` on `null` is `0.0`

**File:** `frontend/src/lib/queries/use-stats.ts:15-23`, `frontend/src/components/dashboard/hero.tsx:69-71`, `frontend/src/components/dashboard/microcopy.ts:15-23`
**Severity:** BLOCKER

**Issue:** The backend declares (correctly):
```python
class TopVuln(BaseModel):
    id: uuid.UUID
    cve_id: str | None = None      # nullable
    host: str | None = None         # nullable
    path: str | None = None         # nullable (mapped from affected_product)
    cvss: Decimal | None = None     # nullable
    ...
```
The frontend types it as **non-nullable** (`cvss: number`, `host: string`, `path: string`) and Hero unconditionally does:
```ts
microcopy.hero.subLineTemplate(topVuln.host, topVuln.path, Number(topVuln.cvss), topVuln.exploited)
```
Where `subLineTemplate` calls `cvss.toFixed(1)`. When the backend legitimately returns `cvss: null` (e.g., a CRITICAL vuln without a CVSS score), `Number(null)` is `0`, and the user sees the headline `"Top one is on null — null, CVSS 0.0, exploited in the wild."` — which is both wrong information and looks broken.

This is exactly the class of bug Open Question 2 + Warning 6 worked around for `mttr_30d` — but here it is not handled.

**Fix:**
```ts
// frontend/src/lib/queries/use-stats.ts
export type TopVuln = {
  id: string;
  cve_id: string | null;
  host: string | null;
  path: string | null;
  cvss: number | null;
  on_kev: boolean;
  exploited: boolean;
};
```
Then in `hero.tsx`:
```tsx
const subLine = topVuln && topVuln.cvss !== null && topVuln.host && topVuln.path
  ? microcopy.hero.subLineTemplate(topVuln.host, topVuln.path, Number(topVuln.cvss), topVuln.exploited)
  : null;
```
Or change `subLineTemplate` to accept `cvss: number | null` and render `'—'` for null.

### BL-02: `Top5Card` consumes a non-existent backend response shape

**File:** `frontend/src/lib/queries/use-top-triage.ts:5-14`, `frontend/src/components/dashboard/top5-card.tsx:65-96`
**Severity:** BLOCKER

**Issue:** The hook fetches `/api/v1/vulnerabilities?sort=triage&limit=5`, which returns `PaginatedResponse[VulnerabilitySummary]`. Inspect the actual backend `VulnerabilitySummary` (`backend/app/vulnerabilities/schemas.py:51-67`):
- It has `asset_hostname` (not `host`).
- It has no `cvss_v3_score` field at all (just `severity`).
- It has no `sla_due_at` field.

The frontend type declares the row as:
```ts
export type TriageRow = {
  id: string;
  cve_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  host: string;            // ❌ backend returns asset_hostname
  cvss_v3_score: number | null;  // ❌ backend doesn't include this in summary
  cisa_kev: boolean;
  sla_due_at: string | null;     // ❌ backend doesn't include this in summary
};
```
At runtime: `Top5Card` renders every row's CVSS as `—`, every host blank, every SLA pill stuck at the null branch (gray "—"). The acceptance tests pass because they mock `useTopTriage` directly — they never exercise the real wire format.

**Fix:** Either (a) extend `VulnerabilitySummary` server-side to include `cvss_v3_score`, `sla_due_at`, and rename the asset hostname → `host`, OR (b) adapt the response in `useTopTriage` similar to `useRecentNotifications`:
```ts
queryFn: ({ signal }) => api<BackendPaginatedSummary>(...),
select: (raw) => ({
  items: raw.items.map(r => ({
    id: r.id, cve_id: r.cve_id, severity: r.severity,
    host: r.asset_hostname,
    cvss_v3_score: r.cvss_v3_score ?? null,
    cisa_kev: r.cisa_kev,
    sla_due_at: r.sla_due_at ?? null,
  })),
  total: raw.total,
}),
```
Plus a wire-format integration test that does NOT mock the API.

### BL-03: `compute_dashboard_tiles_v10` will crash with `TypeError: int() argument must be...None` for partial snapshots

**File:** `backend/app/vulnerabilities/dashboard.py:239-247`
**Severity:** BLOCKER

**Issue:**
```python
def _tile(today_value: int, snapshot_key: str) -> TileValue:
    if prior_metrics is None:
        return TileValue(value=today_value, delta=None, delta_direction=None)
    prior = int(prior_metrics.get(snapshot_key, 0))
    ...
```
`prior_metrics` is a JSONB dict. If the metric key exists in the snapshot but its value is `None` (entirely possible — JSONB tolerates nulls, and `capture_daily_snapshot` does not guarantee all keys are present in old snapshots before this Phase landed — `kev_count` is the most recent addition per the inline comment "Old snapshots return 0 via .get default"), then `prior_metrics.get(snapshot_key, 0)` returns `None` (not the default 0, because the key is present with a null value). `int(None)` raises `TypeError`, which propagates up and `/stats` returns 500.

The comment "Old snapshots return 0 via .get default" assumes the key is *absent*, not present-but-null.

**Fix:**
```python
prior_raw = prior_metrics.get(snapshot_key)
prior = int(prior_raw) if prior_raw is not None else 0
```

### BL-04: `audit()` failure silently produces snooze without audit log

**File:** `backend/app/audit.py:130-149`, `backend/app/vulnerabilities/router.py:364-367` (and `397-400`)
**Severity:** BLOCKER

**Issue:** The `audit()` helper:
```python
try:
    log = AuditLog(...)
    db.add(log)
except Exception:
    pass
```
The `try` only wraps `db.add()` — the rollback risk lives at `db.commit()` time which the router calls afterwards. But more importantly, `db.add()` does not detect FK violations, type errors in JSONB serialization, etc. — those surface at `db.flush()` / `db.commit()` time. If `audit()` swallows an exception (the comment says "Non-blocking — swallows errors") but `commit()` later fails because of the bad audit row, the snooze itself never commits.

Conversely, the router commits regardless of whether the audit row made it in. There is **no test** that asserts `audit.snooze` is fail-safe (i.e., audit failure must not block snooze, AND snooze must not commit without an audit row). One of these has to be the policy and currently the code is ambiguous.

For a compliance-sensitive vulnerability triage product (the AUDIT-01 threat model item), "snooze succeeded without an audit row" is a regulatory hazard.

**Fix:** Pick one policy explicitly:
1. **Audit is required** — wrap the `db.add(log)` outside any try/except, let exceptions propagate; the router's `await db.commit()` will roll back the snooze atomically.
2. **Audit is best-effort with structured logging** — if `db.add()` fails, emit a structured WARN log that monitoring can alert on; do not silently swallow.

Either way, add a test like:
```python
async def test_snooze_audit_failure_does_not_silently_lose_audit(...):
    # inject failure into audit.add and assert that either snooze fails OR
    # a WARN log surfaces.
```

### BL-05: `dev/primitives/page.tsx` short-circuit happens AFTER React hooks — `useState` runs in production

**File:** `frontend/src/app/dev/primitives/page.tsx:70-78`
**Severity:** BLOCKER

**Issue:**
```tsx
export default function DevPrimitivesPage() {
  if (process.env.NODE_ENV === 'production') {
    notFound();
  }
  const [boom, setBoom] = useState(false);
  ...
}
```
`notFound()` throws to interrupt rendering, but in React 19, `useState` must be called unconditionally before any conditional return. The early-return is fine for `notFound()` specifically (it throws), but the more pressing concern is:

- `process.env.NODE_ENV` is replaced at build time by Next, so this **does** dead-code-eliminate the rest. In dev / staging where NODE_ENV is `development`, it correctly skips the `notFound()`. Good.
- However, the comment claims "production builds 404 via notFound() at the top of the page. Simpler than manifest tricks; route exists in build output but short-circuits before rendering any primitive surface." This is true for visiting `/dev/primitives` directly. But the **JavaScript bundle for this page still ships** in production — including all the demo Cards, lucide icons, the `Bomb` component, etc. The route entry is in the manifest. So the bundle-budget check on `/dashboard` is unaffected, but `/dev/primitives` adds dead code to the production deploy that doesn't serve any traffic.

Worse, **the page imports actual production primitives** (`Card`, `Stat`, `StatStrip`, `ActivityFeed`, `ErrorBoundary`). Those are already used by `/dashboard` so the imports don't bloat anything. But the **lucide icon imports** (`Bell`, `Plus`, `ChevronDown`, `ShieldAlert`, `Clock`, `Flame`, `TrendingDown`) and `Bomb` / `Section` / `Row` components ship to production.

**Fix:** Either exclude this route from the production build entirely via `next.config.js` (e.g., a custom webpack rule or `unstable_excludeFiles`), or guard it with `if (process.env.NEXT_PUBLIC_DEV_PRIMITIVES !== '1') notFound();` and exclude the route file from the build output. The cleanest fix is to move this file to a separate package or `__tests__/` directory and load it via a dev-only `next.config.js` rewrite.

### BL-06: `api.ts` 401-refresh retry triggers on snooze POST without idempotency guard

**File:** `frontend/src/lib/api.ts:54-70`, `frontend/src/lib/mutations/use-snooze.ts:10-18`
**Severity:** BLOCKER

**Issue:** The retry-on-401 logic in `api.ts`:
```ts
let res = await fetch(`${API_URL}${path}`, { headers, signal, ...rest });
if (res.status === 401 && !token) {
  const refreshed = await tryRefreshToken();
  if (refreshed) {
    headers.Authorization = `Bearer ${getToken()}`;
    res = await fetch(`${API_URL}${path}`, { headers, signal, ...rest });
  }
  ...
}
```
This retries **every request method** on 401 — including POST. If the snooze POST returns 401 (token expired between the time the dashboard mounted and the user clicked Snooze 1h), `api()` transparently refreshes and retries. The first POST may have already committed server-side if the 401 was returned by middleware after `db.commit()` (it shouldn't, but the surface area is large) — or, more realistically, the snooze request gets 401 because the user is logged out, the token refresh succeeds against a NEW user's session on a shared machine (because `getToken()` reads fresh from localStorage), and the retry then snoozes a foreign tenant's vuln. The IDOR filter saves us in that case (404), but the retry happens in the user's NEW session, not the session whose token expired — meaning **the audit log records the wrong user**.

Plus: 401 retry should be limited to safe methods (GET, HEAD) by convention. Mutating methods are not idempotent in general.

**Fix:**
```ts
if (res.status === 401 && !token) {
  const method = (rest.method ?? 'GET').toUpperCase();
  const safe = method === 'GET' || method === 'HEAD';
  if (!safe) {
    // Don't silently retry mutations — surface the auth failure to the caller
    // so the mutation hook can decide (re-prompt, dispatch logout, etc.).
    throw new Error('Session expired during mutation. Please retry.');
  }
  const refreshed = await tryRefreshToken();
  // ... existing retry path for safe methods only
}
```
Also add a test asserting POST + 401 does NOT retry transparently.

## Warnings

### WR-01: `audit.audit()` swallows ALL exceptions including dev-time bugs

**File:** `backend/app/audit.py:135-149`
**Severity:** WARNING

**Issue:** The catch-all `except Exception: pass` will hide programming errors (typos in field names, wrong types, etc.) that should surface during development. Production-grade audit-failure swallowing should be explicit and metered.

**Fix:** Log structured error before swallowing:
```python
except Exception:
    logger.warning("audit_failed", action=action, resource_id=str(resource_id) if resource_id else None, exc_info=True)
```

### WR-02: `useRecentNotifications` hardcodes `page=1&page_size=5` — no pagination UX exists yet

**File:** `frontend/src/lib/queries/use-recent-notifications.ts:73-81`
**Severity:** WARNING

**Issue:** Page size is hardcoded. If the activity rail later supports "Show more" (a likely next iteration), this hook needs to be parametric. Trivial now, awkward later.

**Fix:** Accept an optional `limit` arg defaulting to 5 (mirrors `useTopTriage`):
```ts
export function useRecentNotifications(limit = 5) {
  return useQuery({
    queryKey: queryKeys.notifications.recent(limit),
    queryFn: ({ signal }) =>
      api<BackendResponse>(`/api/v1/notifications?page=1&page_size=${limit}`, { signal }),
    ...
  });
}
```

### WR-03: `mttr_30d_raw` truthiness check misclassifies 0.0 MTTR as "no data"

**File:** `backend/app/vulnerabilities/dashboard.py:225-227`
**Severity:** WARNING

**Issue:**
```python
mttr_30d_value: int | str = (
    f"{round(float(mttr_30d_raw), 1)}d" if mttr_30d_raw else "—"
)
```
A 0.0-day MTTR (vulns detected and remediated on the same day) is a perfectly valid value, but `if 0.0:` is falsy, so it renders `—` instead of `0.0d`. Same bug exists at `backend/app/vulnerabilities/service.py:315`.

**Fix:**
```python
mttr_30d_value: int | str = (
    f"{round(float(mttr_30d_raw), 1)}d" if mttr_30d_raw is not None else "—"
)
```

### WR-04: `useUrlState` allow-list check accepts empty string as valid value

**File:** `frontend/src/hooks/use-url-state.ts:20-23`
**Severity:** WARNING

**Issue:**
```ts
const raw = params?.get(key) ?? null;
const value: T = (allowed as readonly string[]).includes(raw ?? '')
  ? (raw as T)
  : defaultValue;
```
If `allowed` ever contains `''` (currently it doesn't for `range`, but the API is generic), `raw=null` → `raw ?? ''` → `''` → passes the includes check → `(raw as T)` casts `null` to `T`. This is a latent footgun. A clearer pattern:
```ts
const value: T = raw !== null && (allowed as readonly string[]).includes(raw)
  ? (raw as T)
  : defaultValue;
```

### WR-05: `cisa_kev` is sorted as boolean DESC but Postgres boolean DESC = TRUE first — confirm intent; SQL injection risk in `cve_id` ilike

**File:** `backend/app/vulnerabilities/service.py:36, 43-50, 86-91`
**Severity:** WARNING

**Issue:** Two issues in `_apply_filters`:
1. The triage sort uses `desc(Vulnerability.cisa_kev)`, which in Postgres orders TRUE before FALSE — correct. (No bug, but the comment in router.py line 60 says "KEV → CVSS desc → SLA-due asc" which matches.)
2. `Vulnerability.cve_id.ilike(f"%{filters.cve_id}%")` — SQLAlchemy parameterizes this safely. But the user-supplied `filters.cve_id` is not bound-checked for length. A 10 MB CVE search string would still hit Postgres, which the index can't help. Add `max_length=200` (or similar) to the Pydantic field.

**Fix:**
```python
# backend/app/vulnerabilities/schemas.py
cve_id: str | None = Field(None, max_length=200)
search: str | None = Field(None, max_length=200, description="...")
```

### WR-06: `Hero.onSnooze` mutateAsync `try/catch` does not handle abort

**File:** `frontend/src/components/dashboard/hero.tsx:73-93`
**Severity:** WARNING

**Issue:** The snooze CTA calls `await snooze.mutateAsync({...})`. If the underlying fetch is aborted (e.g., user navigates away), `mutateAsync` rejects with `AbortError`. The catch block does:
```ts
const status = (e as { status?: number } | null)?.status ?? 'unknown';
toast({ message: microcopy.snooze.toastError(status), variant: 'error' });
```
So an `AbortError` from a navigation-cancelled request shows the user a confusing "Couldn't snooze. HTTP unknown · Retry" toast. The user already left the page; the toast may be invisible. But on a stale page in the background tab, the user sees a bogus error.

**Fix:** Detect `AbortError` and silently dismiss:
```ts
} catch (e) {
  if ((e as { name?: string })?.name === 'AbortError') return;
  ...
}
```

### WR-07: `relativeTime()` Intl.RelativeTimeFormat construction allocates per item; suppressHydrationWarning hides a real bug

**File:** `frontend/src/components/ui/activity-feed.tsx:69-83, 115-120`
**Severity:** WARNING

**Issue:** `relativeTime` constructs a fresh `Intl.RelativeTimeFormat` on every call (and is called for every row, every render). Cheap, but pointless — hoist it once. More importantly, the `suppressHydrationWarning` is masking the real bug: relative-time strings WILL differ between SSR and CSR if any element of `Date.now()` shifts between server and client (which it always does — they run at different wall-clock instants). The right fix is to not render the relative time until after hydration:
```ts
const [hydrated, setHydrated] = useState(false);
useEffect(() => setHydrated(true), []);
return <p>{hydrated ? relativeTime(item.occurred_at) : '—'}</p>;
```
Or to compute relative time only client-side and render an absolute timestamp on the server.

`suppressHydrationWarning` should be a last resort, not a strategy.

### WR-08: `Stat` component renders both default `hint` and delta-coupled `hint` — duplicate render path

**File:** `frontend/src/components/ui/stat.tsx:87-94`
**Severity:** WARNING

**Issue:**
```tsx
{hint && delta === undefined && (
  <div className="mt-2 text-xs text-text-faint">{hint}</div>
)}
{hint && delta !== undefined && (
  <div className="mt-1 text-xs text-text-faint">{hint}</div>
)}
```
These are mutually exclusive but share the same content. The two branches differ only by `mt-2` vs `mt-1`. Easier to consolidate:
```tsx
{hint && (
  <div className={cn('text-xs text-text-faint', delta === undefined ? 'mt-2' : 'mt-1')}>
    {hint}
  </div>
)}
```

### WR-09: `check-bundle.mjs` LAST-token heuristic misreads rows where "First Load JS" is not last

**File:** `frontend/scripts/check-bundle.mjs:65-103`
**Severity:** WARNING

**Issue:** The parser does:
```js
const tokens = [...line.matchAll(/(\d+(?:\.\d+)?)\s*(kB|MB|B)\b/gi)];
if (tokens.length >= 1) {
  const last = tokens[tokens.length - 1];
  ...
}
```
This assumes the LAST size token on the line is "First Load JS". Next.js 15 build output typically follows this convention, but Next.js has shipped variants where the route line includes additional metadata (e.g., revalidation interval `(ISR) - 60s`, prerender size). If Next ever appends more columns, this parser silently reads the wrong number. Add a defensive sanity check (e.g., warn if more than 2 size tokens on a single line) or anchor on column position. Also, the regex `/(\d+(?:\.\d+)?)\s*(kB|MB|B)\b/gi` matches `B` after `kB` — `1.2 kB` matches both `1.2 kB` and `2 B` (the `B` inside `kB`). Verify with a real Next.js 15 output before relying on it.

**Fix:** Tighten the regex to disallow `B` immediately after a letter:
```js
/(?<![a-zA-Z])(\d+(?:\.\d+)?)\s*(kB|MB|B)\b/gi
```

### WR-10: `dev/primitives/page.tsx` imports `notFound` but the early-return triggers `useState` to never run — confirm React rules

**File:** `frontend/src/app/dev/primitives/page.tsx:74-78`
**Severity:** WARNING

**Issue:** This pattern looks suspicious to React's rules-of-hooks:
```tsx
export default function DevPrimitivesPage() {
  if (process.env.NODE_ENV === 'production') {
    notFound();
  }
  const [boom, setBoom] = useState(false);
  ...
}
```
`notFound()` throws — React expects the component to either render OR throw. Because `NODE_ENV` is statically replaced at build time, the dead-code branch is eliminated, and in dev `useState` is always reached. So functionally this works. But it violates the spirit of rules-of-hooks: an automated lint scan (`eslint-plugin-react-hooks`) will flag a conditional call before a hook. Suppress with a comment or guard differently.

**Fix:** Restructure to a wrapper:
```tsx
function DevPrimitivesPageInner() { /* hooks + JSX */ }
export default function DevPrimitivesPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <DevPrimitivesPageInner />;
}
```

### WR-11: `ErrorBoundary` does not capture or report errors to a monitoring service in production

**File:** `frontend/src/components/ui/error-boundary.tsx:26-31`
**Severity:** WARNING

**Issue:**
```tsx
componentDidCatch(error: Error, info: unknown) {
  if (process.env.NODE_ENV !== 'production') {
    console.error('[ErrorBoundary]', error, info);
  }
}
```
In production, the boundary catches, the fallback renders, and the original error vanishes silently. For a dashboard that recommends remediation, a silent UI crash that gives an analyst the wrong information is a real risk. There should be a hook to a Sentry/Rollbar/structured logger:
```tsx
componentDidCatch(error: Error, info: unknown) {
  if (process.env.NODE_ENV !== 'production') console.error('[ErrorBoundary]', error, info);
  // Hook: notify monitoring
  reportError?.(error, { boundary: this.props.boundaryName, info });
}
```
At minimum, wire a `boundaryName` prop and a stub `reportError` for now. The threat model item T-10-18 (PII in error logs) is correctly handled, but the OBSERVABILITY side is missing.

### WR-12: `audit()` `db.add(log)` happens INSIDE the try/except — if the row construction itself throws, no audit is recorded, but no error either

**File:** `backend/app/audit.py:135-149`
**Severity:** WARNING

**Issue:** This is a different concern than BL-04. The try/except is too broad and silently captures `AttributeError` (e.g., `user.tenant_id` if `user` is somehow None), `ValueError`, etc. Most of these are programmer bugs, not "audit row didn't fit." Make the catch specific:
```python
try:
    db.add(AuditLog(...))
except (sqlalchemy.exc.SQLAlchemyError, TypeError) as e:
    logger.warning("audit_add_failed", ...)
```

### WR-13: `tests/conftest.py` `analyst_user_b` is created in `tenant_b` but `db_session` rollback truncation discards them between tests — confirm

**File:** `backend/tests/conftest.py:138-153, 232-235`
**Severity:** WARNING

**Issue:** The `db_session` fixture yields a session that rolls back on exit. But the dependency-overridden FastAPI `client` opens its OWN session via `async_session_factory()` inside the request handler — that session is independent from `db_session`. If a test seeds via `db_session.add(); db_session.commit()` (which several tests do), the commit lands in the database and is visible to the route handler's session. After the test, the seeded rows ARE NOT rolled back because they were committed.

So:
- `test_dashboard_tiles.py` calls `await db_session.commit()` (line 47, 85, 108, 123, etc.) → these rows persist after the test.
- `tenant_a` fixture seeds a Tenant and flushes (not commits) — these get rolled back.
- But the `Vulnerability` rows committed by tests persist.

This means subsequent tests see leftover state from earlier tests. The fact that the tests work today is luck or the order doesn't matter — but `pytest -p no:randomly` ordering may mask order-dependent flakes.

**Fix:** Either (a) the tests should not commit and instead use `flush()` so the rollback discards them, or (b) the fixture should TRUNCATE the seeded tables after each test. The current pattern is fragile.

### WR-14: `OnboardingPanel`'s `new Date(lastSyncAt).toLocaleString()` produces SSR/CSR hydration mismatch

**File:** `frontend/src/components/dashboard/onboarding-panel.tsx:44-48`
**Severity:** WARNING

**Issue:** `toLocaleString()` is locale-dependent and TIME-ZONE-dependent. On SSR (Node) and CSR (browser) the result differs unless they share the same TZ. This will produce a React hydration warning in production logs, and the user briefly sees a flicker. Same root cause as the `relativeTime()` issue in WR-07.

**Fix:** Render only after mount, or render an ISO string and let the browser format it in a `useEffect`:
```tsx
const [formatted, setFormatted] = useState(lastSyncAt ?? '');
useEffect(() => {
  if (lastSyncAt) setFormatted(new Date(lastSyncAt).toLocaleString());
}, [lastSyncAt]);
```

---

## Notes on what was checked and looks correct

For completeness — these focus areas from the brief were verified to be CORRECT:

- **IDOR filter on snooze/unsnooze**: present on both routes (`router.py:355-358`, `390-393`). Tests assert 404 on cross-tenant attempts.
- **V11 30-day bound enforcement**: server-side via `if until > now + timedelta(days=30): raise HTTPException(400, ...)`. Test exists and passes the boundary at 31 days. (Note: no test for the exact `30 days + 0 seconds` boundary — see WR-15 below.)
- **RBAC on snooze/unsnooze**: both routes use `Depends(require_analyst)`. Viewer → 403 tests exist.
- **Audit event emission**: both routes call `audit(db, user, 'vuln.snooze', ...)` and `'vuln.unsnooze', ...)`. Tests assert audit rows are written (subject to the policy ambiguity flagged in BL-04).
- **XSS clamp in `useUrlState`**: `(allowed as readonly string[]).includes(raw ?? '')` correctly rejects arbitrary strings (subject to WR-04's edge case).
- **AbortSignal pass-through**: `api.ts` explicitly destructures `signal` and passes to both initial fetch and retry. Test exists. (Subject to BL-06.)
- **QueryClient cache clear on logout**: `qc.clear()` is called inside the `logout` callback between `clearAuth()` and `router.replace('/login')` — Providers is hoisted at root layout so the hook resolves. Test exists.
- **React 19 ErrorBoundary**: class component pattern with `getDerivedStateFromError` is correct. Subject to WR-11 monitoring gap.
- **Hex literal usage in chart files**: `trend-chart.tsx` consistently uses `var(--color-severity-*)` CSS variables; `SEVERITY_FILLS` exported for source-grep contract enforcement. No hex literals found.
- **Sr-only table in TrendChart**: `<table className="sr-only">` with caption, thead, tbody covering all 30 rows + total column.
- **Test isolation**: `vi.mock` calls are at module top before imports, `beforeEach` resets `apiMock`/`mockReplace`, localStorage stubs are reset.

_Reviewed: 2026-05-18T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
