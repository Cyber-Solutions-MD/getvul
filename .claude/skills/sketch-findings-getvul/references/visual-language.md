# Visual Language — Severity, Status, SLA, Providers, CTAs

The shared vocabulary of small visual elements that recur on every screen.

## Severity (three-axis encoding)

**Color + Unicode glyph + size.** Survives 8% color-blind users, grayscale screenshots, and dense tabular data.

| Level | Color | Glyph | Token |
|---|---|---|---|
| Critical | `#F87171` red | `■` | `--color-severity-critical` |
| High | `#FB923C` orange | `▲` | `--color-severity-high` |
| Medium | `#FBBF24` yellow | `◆` | `--color-severity-medium` |
| Low | `#A78BFA` lavender | `○` | `--color-severity-low` |
| Info | `#60A5FA` blue | `□` | `--color-severity-info` |

### Severity pill (default chrome for any severity reference)

```html
<span class="sev-pill critical">
  <span class="sev-glyph critical">■</span> Critical
</span>
```

```css
.sev-pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; }
.sev-pill.critical { background: rgba(248, 113, 113, 0.12); color: var(--color-severity-critical); border: 1px solid rgba(248, 113, 113, 0.3); }
.sev-pill.high     { background: rgba(251, 146, 60, 0.12); color: var(--color-severity-high);     border: 1px solid rgba(251, 146, 60, 0.3); }
.sev-pill.medium   { background: rgba(251, 191, 36, 0.10); color: var(--color-severity-medium);   border: 1px solid rgba(251, 191, 36, 0.3); }
.sev-pill.low      { background: rgba(167, 139, 250, 0.12); color: var(--color-severity-low);      border: 1px solid rgba(167, 139, 250, 0.3); }
```

### Severity glyph alone (in dense table cells)

When a severity pill is too verbose, use just the glyph in the color:

```html
<span class="sev-glyph critical">■</span>
```

### Severity-breakdown ribbon

When showing distribution of vulns by severity (asset detail, dashboard):

```html
<div class="sev-breakdown" style="padding: 10px 14px; background: var(--color-surface-2); border-radius: var(--radius-md);">
  <div class="item"><span class="sev-glyph critical">■</span><span class="num" style="color: var(--color-severity-critical);">2</span> Critical</div>
  <div class="item"><span class="sev-glyph high">▲</span><span class="num" style="color: var(--color-severity-high);">3</span> High</div>
  <div class="item"><span class="sev-glyph medium">◆</span><span class="num" style="color: var(--color-severity-medium);">1</span> Medium</div>
  <div class="item"><span class="sev-glyph low">○</span><span class="num" style="color: var(--color-severity-low);">1</span> Low</div>
</div>
```

### Severity score numbers

CVSS scores (0.0–10.0) get colored by their severity band:

```css
.cell-score { font-family: var(--font-mono); font-weight: 600; }
/* >= 9.0 → critical color */
/* >= 7.0 → high color */
/* >= 4.0 → medium color */
/* < 4.0  → low color */
```

## Status workflow (separate color family from severity)

Used on tickets, deliberately distinct from severity colors so the eye separates them.

| Status | Color | Token |
|---|---|---|
| Open | Violet | `--color-violet` |
| In progress | Amber | `--color-amber` |
| Completed | Green | `--color-success` |
| Blocked | Red | `--color-danger` |

```html
<span class="status-pill open"><span class="dot"></span> Open</span>
<span class="status-pill inprogress"><span class="dot"></span> In progress</span>
<span class="status-pill completed"><span class="dot"></span> Completed</span>
<span class="status-pill blocked"><span class="dot"></span> Blocked</span>
```

The `<span class="dot">` is a 6×6 solid-current-color circle. Each pill has its own tinted background + bordered chrome (same shape as severity pills).

### Text on -soft fills (AA — locked)

When a badge, pill, or chip sets **text** on an accent's `-soft` fill (18% alpha), the base accent as the text color fails WCAG AA (4.5:1) at small sizes — measured `text-violet` on `violet-soft` = 4.35:1, `text-pink` on `pink-soft` = 4.0:1. Use the **`-on-soft`** shade for the text instead (same hue, brighter):

| Fill | Text token | Hex |
|---|---|---|
| `--color-violet-soft` | `--color-violet-on-soft` | `#C4B5FD` (violet-300) |
| `--color-pink-soft` | `--color-pink-on-soft` | `#F472B6` (pink-400) |
| `--color-amber-soft` | `--color-amber-on-soft` | `#F59E0B` (amber already clears AA) |

The tinted-fill *border* and *dot* still use the base accent — only the text lifts. Applies to the "Open" status pill, OWNER/ADMIN role badges, and any future accent-on-soft badge. The `-soft` tokens on their own (backgrounds, focus rings, glows) are unaffected.

## SLA (3-tier time deltas)

Always right-aligned. Mono font. Color-coded.

| Tier | Color | Examples |
|---|---|---|
| Overdue | Red (matches `critical`) | `−2h SLA`, `−8h overdue` |
| Soon (<24h) | Amber (matches `high`) | `4h left`, `18h left` |
| OK | Green | `3d left`, `done 2d ago` |

```html
<span class="sla-pill overdue">−2h SLA</span>
<span class="sla-pill soon">4h left</span>
<span class="sla-pill ok">3d left</span>
```

```css
.sla-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px; border-radius: 999px;
  font-family: var(--font-mono); font-size: 11px; font-weight: 500;
}
.sla-pill.overdue { background: rgba(248, 113, 113, 0.15); color: var(--color-severity-critical); border: 1px solid rgba(248, 113, 113, 0.3); }
.sla-pill.soon    { background: rgba(251, 146, 60, 0.15); color: var(--color-severity-high); border: 1px solid rgba(251, 146, 60, 0.3); }
.sla-pill.ok      { background: rgba(74, 222, 128, 0.12); color: var(--color-success); border: 1px solid rgba(74, 222, 128, 0.3); }
```

## Special badges

### CISA KEV badge

Red, mono, uppercase. Always inline alongside the severity pill or the CVE ID. Tells the analyst "this is exploited in the wild, prioritize it."

```html
<span class="kev-badge">★ CISA KEV</span>
```

```css
.kev-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 7px; border-radius: 4px;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: var(--color-severity-critical);
  font-size: 10px; font-family: var(--font-mono); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}
```

### Exploit-available badge

Amber, mono. Tells the analyst "an exploit exists but it's not necessarily being used yet."

```html
<span class="exploit-badge">⚡ exploit available</span>
```

### Stale-data pill

Amber. Used on table cells when data is from a connector that's currently down.

```html
<span class="stale-pill">stale</span>
```

## Provider identity (Jira / Asana / GitHub)

Small gradient marks + tinted chips. **No real provider logos** — recognizable enough via color + glyph and avoids licensing.

| Provider | Color family | Glyph |
|---|---|---|
| Jira | Cool blue (`#5C9CFF`) | 4-square grid `■` |
| Asana | Coral (`#FF8AA0`) | 3 dots |
| GitHub | Violet (matches sunset accent) | Issue circle |

```html
<span class="provider jira">
  <div class="provider-mark jira"><svg><use href="#i-jira-stack"/></svg></div>
  Jira
</span>
```

```css
.provider {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 2px 8px; border-radius: 6px;
  font-size: 11px; font-weight: 500; font-family: var(--font-mono);
}
.provider.jira    { background: rgba(38, 132, 255, 0.12); color: #5C9CFF; border: 1px solid rgba(38, 132, 255, 0.3); }
.provider.asana   { background: rgba(241, 80, 110, 0.12); color: #FF8AA0; border: 1px solid rgba(241, 80, 110, 0.3); }
.provider.github  { background: rgba(167, 139, 250, 0.12); color: var(--color-violet); border: 1px solid rgba(167, 139, 250, 0.3); }

.provider-mark { width: 14px; height: 14px; border-radius: 3px; display: grid; place-items: center; }
.provider-mark.jira   { background: linear-gradient(135deg, #5C9CFF, #2684FF); }
.provider-mark.asana  { background: linear-gradient(135deg, #FF8AA0, #F1506E); }
.provider-mark.github { background: linear-gradient(135deg, #C7BAFF, #A78BFA); }
```

## Avatars

40px (owner card, primary), 26px (topbar user chip), 20px (assignee chip in tables/kanban).

Sunset-gradient base. Variants: violet (`linear-gradient(135deg, var(--color-violet), var(--color-pink))`), amber (`linear-gradient(135deg, var(--color-amber), var(--color-pink))`) for visual variety in multi-avatar contexts.

```css
.avatar { border-radius: 50%; background: var(--gradient-sunset); color: white; display: grid; place-items: center; font-weight: 600; box-shadow: var(--glow-pink); }
```

Initials inside (2 chars). Real avatar images deferred until /users phase.

## CTAs (call-to-action buttons)

### Primary — the gradient CTA

**Used once or twice per screen, for the main action.** Never more.

```html
<button class="btn-cta"><svg><use href="#i-zap"/></svg>Start triage</button>
```

```css
.btn-cta {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 18px; border-radius: var(--radius-md);
  background: var(--gradient-sunset);
  color: white; font-size: var(--text-sm); font-weight: 600;
  box-shadow: var(--glow-cta);
  transition: all var(--motion-fast);
}
.btn-cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 36px rgba(236, 72, 153, 0.5);
}
```

The `--glow-cta` token combines an outer glow + a 1px inner highlight for premium feel.

### Secondary

Dark surface, bordered. For non-primary actions next to the CTA (Export, Snooze, Rescan, View trace).

```css
.btn-secondary {
  padding: 8px 14px; border-radius: var(--radius-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border-subtle);
  color: var(--color-text); font-size: var(--text-sm); font-weight: 500;
}
.btn-secondary:hover { background: var(--color-surface-2); border-color: var(--color-border); }
```

### Ghost

For toolbar / table-action affordances. No chrome until hover.

```css
.btn-ghost { padding: 6px 10px; color: var(--color-text-muted); font-size: var(--text-xs); }
.btn-ghost:hover { color: var(--color-text); }
.btn-ghost.active { color: var(--color-text); background: var(--color-surface-2); }
```

### Icon button

34×34 rounded square. Topbar bell/help, table header sort/menu.

```css
.icon-btn {
  width: 34px; height: 34px; border-radius: var(--radius-md);
  background: var(--color-surface); border: 1px solid var(--color-border-subtle);
  display: grid; place-items: center; color: var(--color-text-muted);
}
.icon-btn:hover { color: var(--color-text); border-color: var(--color-border); }
```

### Special: amber-tinted icon button (system alert)

```css
.icon-btn[data-alert] { border-color: rgba(251, 146, 60, 0.4); color: var(--color-amber); }
```

Used in the topbar when there's a partial-failure or other system-level warning.

## Form inputs

```css
.field-input {
  width: 100%; padding: 12px 14px;
  background: var(--color-surface-2);
  color: var(--color-text);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  transition: border-color var(--motion-fast), box-shadow var(--motion-fast);
}
.field-input::placeholder { color: var(--color-text-faint); }
.field-input:focus {
  outline: none;
  border-color: var(--color-violet);
  box-shadow: 0 0 0 3px var(--color-violet-soft);
}
```

Focus ring uses **violet** (not pink) to avoid competing with the CTA. 3px soft halo on focus.

## Toggles / switches

For boolean settings (KEV-only, Exploit-only, etc.):

```css
.switch {
  position: relative; width: 30px; height: 18px;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border-subtle);
  border-radius: 999px;
}
.switch::after {
  content: ''; position: absolute; top: 1px; left: 1px;
  width: 14px; height: 14px; border-radius: 50%;
  background: var(--color-text-muted);
  transition: all var(--motion-fast);
}
.switch.on { background: var(--gradient-sunset); border-color: transparent; }
.switch.on::after { left: 13px; background: white; }
```

When ON: full sunset gradient. When OFF: dim surface.

## Chips

Used for filter chips, tags, and minor controls.

```css
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border-subtle);
  color: var(--color-text-muted);
  font-size: 11px;
  cursor: pointer;
}
.chip.active {
  background: var(--color-pink-soft);
  border-color: var(--color-pink);
  color: var(--color-pink);
}
```

Active state: pink. (Severity-glyph chips override with their own color in `.sev-glyph.${level}`.)

## Origin

Cross-cutting — every sketch uses these. Especially codified in 003 (severity), 004 (state colors), 005 (avatar/risk visuals), 006 (provider/status).
