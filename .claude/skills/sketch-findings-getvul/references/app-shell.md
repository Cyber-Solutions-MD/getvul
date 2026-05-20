# App Shell — Sidebar, Topbar, Breadcrumbs

The persistent UI chrome shared by every authenticated screen. Two screens use a different shell (login uses a split-screen with no sidebar). Everything else looks like this.

## Layout

```css
.app-shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}
```

Sidebar: **220px fixed** on desktop. Below 1000px, sidebar hides entirely (hamburger entry point — pattern deferred to mobile sketch).

Main: `padding: 22-28px 32px 48px` depending on screen. Topbar sticks below `padding-top`.

## Sidebar

Three sections, separated by gaps + section titles. Bottom section pinned to the bottom via `margin-top: auto`.

```html
<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark"><svg><use href="#i-shield"/></svg></div>
    <span class="brand-name">GetVul</span>
  </div>

  <nav class="sidebar-section">
    <div class="sidebar-section-title">Triage</div>
    <a class="nav-item" href="#"><svg><use href="#i-home"/></svg>Dashboard</a>
    <a class="nav-item active" href="#"><svg><use href="#i-bug"/></svg>Vulnerabilities<span class="count">1,247</span></a>
    <a class="nav-item" href="#"><svg><use href="#i-server"/></svg>Assets<span class="count">312</span></a>
    <a class="nav-item" href="#"><svg><use href="#i-cloud"/></svg>CSPM</a>
  </nav>

  <nav class="sidebar-section">
    <div class="sidebar-section-title">Workflow</div>
    <a class="nav-item" href="#"><svg><use href="#i-ticket"/></svg>Tickets<span class="count">23</span></a>
    <a class="nav-item" href="#"><svg><use href="#i-plug"/></svg>Connectors</a>
  </nav>

  <nav class="sidebar-section" style="margin-top: auto;">
    <a class="nav-item" href="#"><svg><use href="#i-users"/></svg>Users</a>
    <a class="nav-item" href="#"><svg><use href="#i-cog"/></svg>Settings</a>
  </nav>
</aside>
```

### Brand mark

Gradient-sunset rounded square (28×28, 8px radius) with shield SVG inside, plus glow. **This is the loudest "fancy" element in the shell.** Used once per screen.

```css
.brand-mark {
  width: 28px; height: 28px; border-radius: 8px;
  background: var(--gradient-sunset);
  display: grid; place-items: center;
  box-shadow: var(--glow-pink);
}
```

### Section titles

Small uppercase tracking-wide labels. NOT links. Used to group nav items semantically.

- `Triage` — Dashboard, Vulnerabilities, Assets, CSPM
- `Workflow` — Tickets, Connectors
- Unlabeled (bottom) — Users, Settings

### Nav items

Default: muted text + icon. Hover: surface background + brighter text. **Active state is a gradient strip on the left edge** with pink glow + brighter count. Counts on the right (mono).

```css
.nav-item.active::before {
  content: ''; position: absolute;
  left: -16px; top: 6px; bottom: 6px; width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--gradient-sunset-vertical);
  box-shadow: var(--glow-pink);
}
```

### Counts

Right-aligned in nav-item via `margin-left: auto`. Mono, faint by default, pink when item is active.

## Topbar

Single row above the page content. Doesn't fix-position by default (lives in the main padding zone).

```html
<div class="topbar">
  <div class="search">
    <svg><use href="#i-search"/></svg>
    <span>Search CVEs, assets, tickets…</span>
    <span class="kbd">⌘K</span>
  </div>
  <div class="actions">
    <button class="icon-btn"><svg><use href="#i-bell"/></svg></button>
    <button class="icon-btn"><svg><use href="#i-help"/></svg></button>
    <div class="user-chip"><div class="avatar">AS</div><span class="name">Ana</span></div>
  </div>
</div>
```

### Search input

Looks like an input but is a placeholder trigger for ⌘K command palette. Max width 480px. Surface bg, subtle border. Has the keyboard shortcut chip on the right (mono, dim).

### Icon buttons

34×34, rounded-md, surface bg. Bell (notifications), help. **Amber-tinted variant** when there's a system alert (used in 004 error variant for partial-failure).

### User chip

`padding: 4px 10px 4px 4px` — note the asymmetric padding. Sunset-gradient avatar (initials) + name. Rounded-full pill chrome.

## Breadcrumb

Above the page title on detail pages (and only on detail pages — list pages don't use it).

```html
<div class="breadcrumb">
  <a href="#">Assets</a>
  <span class="sep">/</span>
  <span class="current">prod-db-01</span>
</div>
```

Current item is in mono color (`var(--color-text)`). Parent link is `var(--color-text-muted)`. Separator is `/` at low opacity.

## Page head

Below the topbar (and below the breadcrumb on detail pages). Page title + subtitle on the left, action buttons on the right.

```html
<div class="page-head">
  <div>
    <h1>Vulnerabilities <span class="count">1,247</span></h1>
    <p class="subtitle">Filtered to 89 results — 14 critical, 28 SLA-at-risk.</p>
  </div>
  <div class="page-head-actions">
    <div class="view-toggle"><button class="active">By CVE</button><button>By host</button></div>
    <button class="btn-secondary"><svg><use href="#i-download"/></svg>Export</button>
    <button class="btn-cta"><svg><use href="#i-bolt"/></svg>Triage queue</button>
  </div>
</div>
```

- Page title: `text-3xl`, weight 700, `tracking-tight`. Optional mono count appended.
- Subtitle: text-sm, muted. Sentence-case. Often includes a pink-colored substring for emphasis.
- Actions: secondary buttons first (left), gradient CTA last (right) — primary action sits at the right edge.

## View toggle (when applicable)

Compact pill segmented control. Used for things like "By CVE / By host" or future "List / Board."

```css
.view-toggle {
  display: inline-flex; padding: 3px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
}
.view-toggle button {
  padding: 5px 12px; border-radius: var(--radius-sm);
  font-size: var(--text-xs); color: var(--color-text-muted);
}
.view-toggle button.active { background: var(--color-surface-2); color: var(--color-text); }
```

## What NOT to do in the shell

- Don't make the sidebar collapsible by default — it's the persistent way-finding aid. Only collapses on mobile.
- Don't fixed-position the topbar at the top of the viewport (the page-head sometimes needs the topbar's space when scrolling). It scrolls with content.
- Don't put the brand mark anywhere except the sidebar (it's a sigil, not a recurring graphic).
- Don't add a second "primary CTA" to the topbar — that lives in page-head.
- Don't use the gradient on more than one element per shell view at any time (the brand mark is enough).

## Origin

Synthesized from sketches 002, 003, 005, 006 (all share this shell). Source files in `sources/`.
