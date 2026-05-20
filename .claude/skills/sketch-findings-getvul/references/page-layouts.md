# Page Layouts — Hero, List, Detail

Four distinct page-layout patterns validated across the 6 sketches. Each maps to a *kind* of screen, not a specific route.

## 1. Hero split-screen (Login)

Used only for unauthenticated / marketing-adjacent surfaces (login, signup, password reset). No sidebar.

```html
<div class="var-a">
  <div class="visual">         <!-- left: gradient mesh + tagline + product peek -->
    <div class="brand">…</div>
    <h1>See your security posture <span class="accent">without opening another tool.</span></h1>
    <p>Subtitle…</p>
    <div class="preview">      <!-- a peek of the actual product (vuln rows) -->
      <!-- 3 vuln preview rows with severity dots + CVE IDs + asset + score -->
    </div>
    <div class="footer-row">SOC 2 · Self-hosted or SaaS · v0.1</div>
  </div>
  <div class="form-side">      <!-- right: clean form panel -->
    <h2>Sign in</h2>
    <button class="sso-btn">Continue with Google</button>
    <button class="sso-btn">Continue with Microsoft</button>
    <div class="or-divider">or with email</div>
    <input class="field-input" />  <!-- email -->
    <input class="field-input" type="password" />
    <button class="cta-primary">Sign in</button>
  </div>
</div>
```

Key rules:
- 1.05fr / 1fr split (visual slightly wider than form). Below 900px the panels stack — visual on top (shorter), form below.
- Visual side uses `--gradient-mesh` with a slow 24s drift animation + `radial-gradient` darkening at one corner. The animation is `transform: scale + translate` of a `::before`. Subtle.
- Tagline uses the sunset gradient as background-clip on emphasis words ("without opening another tool"). Rest of headline is `color-text`.
- Form side is bare — no extra chrome, no gradient. Just inputs + the gradient CTA at the bottom.
- SSO buttons go ABOVE the password fields. SSO is the primary path.
- The "or with email" divider has horizontal lines via `::before`/`::after`.
- Show a real product peek in the visual side (vuln list rows in a glass-ish container). Builds product narrative; doesn't oversell.

## 2. Action-first dashboard hero

Used on `/dashboard` and any "what should I do now?" landing surface.

```html
<div class="hero-card">
  <div>
    <div class="eyebrow">
      <span class="pulse"></span>
      Today's priority
    </div>
    <h1><span class="num">3 critical</span> CVEs need your eyes</h1>
    <p class="sub">Top one is on <span class="mono">prod-db-01</span> — Postgres path, CVSS 9.8, exploited in the wild. Triage them in &lt; 15 min.</p>
  </div>
  <div class="hero-actions">
    <button class="btn-secondary">Snooze 1h</button>
    <button class="btn-cta"><svg><use href="#i-zap"/></svg>Start triage</button>
  </div>
</div>
```

Key rules:
- Card uses two soft radial gradients in opposing corners (`pink-soft` from bottom-left, `amber-soft` from top-right) for a subtle ambient warmth. Not the full mesh.
- **Pulsing dot** (`@keyframes pulse` — 2s loop, box-shadow grows + fades) is the only animated affordance. Signals urgency.
- Eyebrow text is pink, uppercase, tracking-wide — distinct from the body type scale.
- Headline mixes color: the urgency number in pink, the rest in `color-text`.
- Sub-line includes mono-formatted hostnames inline.
- Primary action on the far right is the gradient CTA. A secondary "Snooze" sits left of it.
- BELOW this hero: a thin strip of 4 stat tiles (Critical · SLA risk · CISA KEV · MTTR). Secondary, not the hero.
- BESIDE the strip + chart: a **right sidebar** for the activity feed (~340px). Sticky on scroll.

## 3. List with side-panel drill-down

Used for `/vulnerabilities` and `/tickets`. Same pattern across all list routes.

```html
<!-- Chip-bar filter ABOVE the table — no persistent left drawer -->
<div class="filter-bar">
  <input class="filter-search" placeholder="Search…" />
  <span class="sep"></span>
  <div class="chip active">Critical</div>
  <div class="chip active">High</div>
  <span class="sep"></span>
  <div class="chip active">CISA KEV</div>
  <span class="saved-pill">★ Today's triage</span>
  <a class="clear-link">Clear all</a>
</div>

<div class="work-area" id="work">  <!-- becomes 1fr 420px when drilled -->
  <div class="table-wrap">
    <table class="vuln-table">
      <thead><tr>
        <th>Severity</th><th>CVE / ID</th><th>Title / Product</th>
        <th>Asset</th><th style="text-align:right;">Score</th>
        <th>Status</th><th style="text-align:right;">SLA</th>
      </tr></thead>
      <tbody>
        <tr onclick="rowClick(idx)">…</tr>
      </tbody>
    </table>
    <div class="table-foot">
      Showing 1–10 of 89  ·  pagination buttons (mono)
    </div>
  </div>

  <aside class="drill-panel">  <!-- only display when drilled -->
    <div class="drill-head">
      <div class="drill-title">CVE-2024-3094</div>
      <div class="drill-meta-row">
        <span class="sev-pill critical">■ Critical</span>
        <span class="kev-badge">★ CISA KEV</span>
        <span class="exploit-badge">⚡ exploit available</span>
      </div>
      <button class="close">×</button>
    </div>
    <div class="drill-section">
      <h4>Description</h4>
      <p>…</p>
    </div>
    <div class="drill-section">
      <h4>CVSS 3.1</h4>
      <!-- score + vector card -->
    </div>
    <!-- Affected hosts / Linked vulns / Remediation / Actions -->
  </aside>
</div>
```

Key rules:
- **No persistent left filter drawer.** Filters live in a horizontal chip bar above the table. Frees the entire table width for data.
- **Click a row → side panel slides in from the right** (420px). The table area dims to ~60% width during drill. Same pattern across all list routes — analyst learns once, applies everywhere.
- Drill panel sections: title + meta-row pills · description · CVSS/score · affected items · remediation · action buttons (gradient CTA + secondaries).
- Panel close: × button top-right, or click another row to swap content.
- On mobile, panel becomes a full-screen overlay (`position: fixed; inset: 56px 0 0 0;`).
- Tables collapse to **card view** on mobile (severity pill + ID on row 1, title on row 2, asset + SLA pill on row 3).
- Bulk-action bar (when rows are checkable): floating rounded-pill at the bottom, glass background, slide-up animation. Count in pink, action buttons in row, close × on the right.

### Severity glyphs in tables

```
Critical  ■  red
High      ▲  orange
Medium    ◆  yellow
Low       ○  lavender
Info      □  blue
```

Always paired with the sev-pill chrome. The glyph is `font-family: var(--font-mono)`. Three-axis encoding: color + glyph + size.

## 4. Detail page (two-column with sticky metadata rail)

Used for `/assets/[id]`, `/tickets/[id]`, and any other "show me everything about one thing" route.

```html
<div class="breadcrumb">
  <a href="#">Assets</a> / <span class="current">prod-db-01</span>
</div>

<div class="meta-header">
  <h1>prod-db-01</h1>
  <span class="host-pill normal"><span class="dot"></span> normal</span>
  <span class="tag">prod</span>
  <span class="tag">postgres</span>
  <div class="actions">
    <button class="btn-secondary">Rescan</button>
    <button class="btn-cta">Create ticket</button>
  </div>
</div>

<div class="body-grid">  <!-- 1fr 340px -->
  <div>  <!-- main column: workflow content -->
    <div class="card">
      Vulnerabilities on this host (severity ribbon + rows)
    </div>
    <div class="card">
      Remediation timeline
    </div>
  </div>

  <aside class="right-rail">  <!-- 340px, sticky -->
    <div class="risk-card">
      <div class="risk-ring">  <!-- SVG with gradient stroke + center number -->
      </div>
      <div class="breakdown">
        <div class="row">Critical exposures · 2</div>
        <div class="row">SLA breaches · 1</div>
        <div class="row">CISA KEV count · 3</div>
        <div class="row">7-day change · ▲ +12</div>
      </div>
    </div>

    <div class="card">Owner (avatar + name + role + IdP pill + email + Reassign link)</div>

    <div class="card">Identity & host (8-row meta-grid stacked)</div>
  </aside>
</div>
```

Key rules:
- **Right rail is 340px and sticky.** Identity stays visible while you scroll work content.
- Page-head uses the host name + status pill + tags inline. Actions on the right (Rescan + Create ticket).
- **Risk score as a circular gradient ring** with the score in the center and a 4-row breakdown next to it. Gradient stroke uses the sunset gradient.
- Owner card: 40×40 sunset-gradient avatar (initials) + name + role + IdP pill (`Okta` / `Google` / `Azure` in monospace, small chrome) + email mono below. "Reassign" link in the card header.
- Metadata grid: 1-col stacked rows (label uppercase tracking-wide above value). Use mono for IPs, kernels, instance IDs, dates, durations.
- Activity timeline at the bottom (or in a tab): 28px dots in a column, sunset-tinted variants (pink/amber/violet/success).

## Anti-patterns

- **No tabs as the primary navigation for detail pages.** Tabs hide content. Use the two-column with rail instead. (Tested as variant C in sketch 005, not the winner.)
- **No left filter drawer on list pages.** Steals horizontal real estate. Use chip bar. (Tested as A in sketch 003, not the winner.)
- **No drill-down as full-page navigation** on list routes. Side panel keeps context. (Tested as variant B in sketch 006, not the winner.)
- **No glassmorphic cards on data-heavy pages.** Tested in sketch 001 variant B, not the winner. Glass effect is reserved for the login hero only and even there is the secondary option.
- **No symmetric two-column on detail pages** (50/50). Always asymmetric — main wider than rail.

## Origin

Synthesized from sketches 001 (hero split-screen), 002 (action-first hero), 003 + 006 (list+side-panel), 005 + 006 detail (two-column+rail).
