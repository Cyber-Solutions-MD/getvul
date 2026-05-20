# State Patterns — Loading, Empty, Error

The v1 audit flagged "no empty/loading/error states" as the top UX pain. **No production screen ships without all three implemented.** These patterns are mandatory.

## Universal principle: informative + actionable

Every state should answer:
1. **What's happening?** (or, what isn't, and why)
2. **What can I do about it?** (concrete next step, never a dead end)
3. **What data DO I have?** (always show what's available — never replace the screen with a generic message when partial data exists)

## 1. Loading

**Skeleton screens + per-source progress** — not black screens, not spinners-only.

```html
<!-- Loading banner at the top of the page -->
<div class="loading-banner">
  <div class="spinner"></div>
  <div class="text">
    <div>Fetching vulnerabilities from <span style="color: pink;">3 of 4 sources</span>…</div>
    <div class="sub">312 found so far · this usually takes 2–3 seconds</div>
  </div>
  <div class="progress">
    <span class="conn-dot done">✓ Qualys · 287</span>
    <span class="conn-dot done">✓ AWS · 18</span>
    <span class="conn-dot loading"><span class="pulse"></span>Tenable · 7</span>
    <span class="conn-dot">Rapid7 · waiting</span>
  </div>
</div>

<!-- Skeleton chip bar -->
<div class="filter-bar">
  <span class="skeleton" style="width:200px;height:28px;"></span>
  <span class="skel-pill" style="width:88px;height:22px;"></span>
  …
</div>

<!-- Skeleton table rows -->
<table class="vuln-table">
  <thead><tr><th>Severity</th><th>CVE</th>…</tr></thead>
  <tbody>
    <tr>
      <td><span class="skel-pill" style="width:80px;height:20px;"></span></td>
      <td><span class="skeleton" style="width:130px;height:14px;"></span></td>
      <!-- … -->
    </tr>
    <!-- ~8 rows with varying widths -->
  </tbody>
</table>
```

### Skeleton CSS

```css
.skeleton {
  background: linear-gradient(90deg, var(--color-surface-2) 0%, var(--color-border) 50%, var(--color-surface-2) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.6s linear infinite;
  border-radius: 4px;
  display: inline-block;
}
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }

/* Pill-shaped placeholders use sunset-tinted shimmer */
.skel-pill {
  background: linear-gradient(90deg, rgba(236, 72, 153, 0.08) 0%, rgba(167, 139, 250, 0.12) 50%, rgba(236, 72, 153, 0.08) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.6s linear infinite;
  border: 1px solid var(--color-border-subtle);
  border-radius: 999px;
}
```

### Per-source progress strip rules

- Each known source gets a "conn-dot" — a small pill showing source name + current row count
- States: pending (gray), loading (pink, pulsing dot), done (green, ✓ check)
- Counts update as data streams in (mock with periodic updates)
- This component is **GetVul-specific** — it tells the analyst which connectors have responded, which are still talking, and how many vulns each has contributed. Generic spinners don't communicate this.

### When to use simpler loading

- Single API request, <300ms expected: don't skeleton, just delay the render briefly
- Background sync (silent): subtle "Syncing…" text in topbar, no full skeleton
- After user action (sort/filter): keep showing prior data with a thin progress bar at the top

## 2. Empty (filtered to zero)

**Centered card with sunset-gradient icon + explanation + 3-tier actions + opportunity hint.**

```html
<!-- Active filters still shown above so user sees what they applied -->
<div class="filter-bar">
  <input class="filter-search" value="hyperion" />
  <span class="sep"></span>
  <div class="chip active">Critical</div>
  <div class="chip active">High</div>
  <span class="sep"></span>
  <div class="chip active">CISA KEV</div>
  <div class="chip active">Exploit available</div>
  <div class="chip active">Source: Tenable</div>
  <a class="clear-link">Clear all</a>
</div>

<!-- Empty card -->
<div class="empty-card">
  <div class="empty-icon">
    <!-- 72×72 circle with sunset gradient, glow, sparkles icon inside, blur halo behind -->
    <svg><use href="#i-sparkles"/></svg>
  </div>
  <h2>Nothing matches all 5 filters</h2>
  <p class="empty-sub">No vulnerabilities are simultaneously Critical or High <em>and</em> on CISA KEV <em>and</em> have an active exploit <em>and</em> from Tenable <em>and</em> contain "hyperion." That's a tight net — relax one or two and try again.</p>

  <div class="filter-summary">
    <span class="lbl">Currently filtered by</span>
    <!-- All active chips repeated for clarity -->
  </div>

  <div class="empty-actions">
    <button class="btn-cta">Clear all filters</button>
    <button class="btn-secondary">Include Medium severity</button>
    <button class="btn-secondary">Search all sources</button>
  </div>

  <div class="secondary-suggestion">
    <div class="icon"><svg><use href="#i-lightbulb"/></svg></div>
    <div>This is a sharp query. <a href="#">Save it as "Hyperion KEV watch"</a> — you'll be notified when anything matches.</div>
  </div>
</div>
```

### Empty rules

- **Icon: 72×72 circle with sunset gradient + glow + a `::after` blur halo behind.** Don't reuse the standard brand mark; this is its own variant.
- **Body explains WHY**, listing the conjunction that produced zero. Don't just say "no results."
- **Three CTAs at three tiers:**
  1. Clear all (gradient primary) — escape hatch
  2. Broaden one axis (secondary) — minimum effort
  3. Broaden everything (secondary) — explore fully
- **Lightbulb suggestion at the bottom** turns the empty state into an opportunity. Save the filter as a watch / alert.
- The icon glow uses `box-shadow: var(--glow-pink)` plus an absolute `::after` with blur.

### Variants of empty (not the filtered-to-zero case)

These are *deferred* (not sketched, but flagged for production):

- **First-time-empty (no connectors yet):** Onboarding-flavored. "Connect a scanner to see your first vulnerabilities" + CTA to /connectors.
- **Quiet/win empty (all critical resolved or snoozed):** Friendly tone. "Quiet here. Nothing critical right now."
- **Total empty (no data ever, no connectors, brand-new install):** Onboarding wizard, separate from the standard empty pattern.

When implementing, follow the same shell (gradient icon + heading + body + actions + optional suggestion), but the COPY changes.

## 3. Error (partial failure — the realistic case)

**Show what data you have. Mark what's stale. Name what failed. Offer a fix.**

```html
<!-- Persistent amber alert in topbar -->
<div class="topbar">
  <div class="search">…</div>
  <div class="actions">
    <button class="icon-btn" style="border-color: rgba(251, 146, 60, 0.4); color: var(--color-amber);">
      <svg><use href="#i-alert"/></svg>
    </button>
    <!-- … -->
  </div>
</div>

<!-- Page header subtitle gains a partial-data warning -->
<div class="page-head">
  <h1>Vulnerabilities <span class="count">935</span></h1>
  <p class="subtitle">
    <span style="color: var(--color-amber);">⚠ Partial data</span>
    · 3 of 4 sources returned · 312 hidden
  </p>
</div>

<!-- Inline error banner — amber, NOT red (degraded ≠ down) -->
<div class="error-banner">
  <div class="icon"><svg><use href="#i-alert"/></svg></div>
  <div class="text">
    <div class="title">Tenable connector is unreachable</div>
    <div class="sub">
      Last successful sync: <span class="mono">2h 14m ago</span>
      · HTTP <span class="mono">503 Service Unavailable</span>
      · Tried 3 times
      · Request ID <span class="mono">req_8f2a91c</span>
    </div>
  </div>
  <div class="actions">
    <button class="btn-secondary sm">View trace</button>
    <button class="btn-secondary sm"><svg><use href="#i-refresh"/></svg>Retry now</button>
  </div>
</div>

<!-- Per-source status cards in a row -->
<div class="source-status">
  <div class="source-card">
    <div class="head"><span class="name">Qualys</span><span class="status-pill ok">ok</span></div>
    <div class="meta">487 vulns · synced 4m ago</div>
  </div>
  <div class="source-card failed">  <!-- red-tinted -->
    <div class="head"><span class="name">Tenable</span><span class="status-pill fail">503</span></div>
    <div class="meta">stale · 312 vulns · 2h 14m ago</div>
    <a class="retry-link">Retry → or view connector settings</a>
  </div>
  <!-- … other sources -->
</div>

<!-- Table shows data we DO have. Rows from stale sources tinted amber. -->
<table class="vuln-table">
  <tr><!-- normal row, fresh from Qualys --></tr>
  <tr class="stale-row">  <!-- amber-tinted background -->
    <!-- source column shows: Tenable [stale] -->
  </tr>
</table>

<!-- Footer of table repeats the caveat -->
<div class="table-foot">
  ⚠ Some results may be incomplete because Tenable hasn't responded since
  <span class="mono">2h 14m ago</span>.
  <a>Retry Tenable</a> or <a>view connector logs</a>.
</div>
```

### Error rules

- **Amber, not red.** Partial failure is "degraded," not "down." Red is reserved for critical severity. Amber says: this works, but with caveats.
- **Request ID + HTTP code displayed by default.** Saves a support ticket round-trip. Mono font.
- **Per-source status cards** in a row above (or beside) the table — show all sources' health at a glance, not just the one that failed.
- **Stale rows in the table get amber background + `stale` pill** on the source column. The user can see *which* rows are from the failed connector.
- **Topbar gets a persistent amber alert** (the icon button) so the issue is visible even when the user scrolls off the banner.
- Actions on the banner: "View trace" (opens a modal/page with the full stacktrace + headers) + "Retry now" (re-fetches just the failed source).
- Table foot repeats the caveat so users who jump straight to data don't miss the warning.

### Total failure (all sources down) — deferred

Not sketched. The expected pattern: a full empty-card variant with retry. Different visual shell from the partial-failure case. Will sketch if it becomes blocking.

### Network / auth errors (not just connector failures)

- 401/403: redirect to /login, no error UI (handled at the route level)
- 500: full-page error card with retry — pattern similar to total-failure empty
- Network offline: persistent banner at top of viewport, "You're offline. Showing cached data."

## Toast notifications

**Not yet sketched.** Will live at the bottom-right of the viewport. Sunset variants:
- Success: green-tinted, success-soft background, check icon, 4s auto-dismiss
- Error: red-tinted, danger-soft, alert icon, manual-dismiss
- Info: violet-tinted, info icon, 6s auto-dismiss

Used for: ticket created · filter saved · connector retried · row resolved.

## Origin

Synthesized from sketch 004 (all three patterns approved as complementary; partial-failure error is the lead pattern).
