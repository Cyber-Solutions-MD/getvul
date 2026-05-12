# Interaction Patterns — Drill-down, Filters, Bulk Actions, Timeline, Drag

## Drill-down side panel

The canonical "click a row to see details without leaving the list" pattern. Validated for `/vulnerabilities` and `/tickets` — apply to any future list route.

### Behavior

- Click any table row → 420px panel slides in from the right
- Table area transitions from `grid-template-columns: 1fr` to `1fr 420px`
- Animation: `transition: grid-template-columns 220ms cubic-bezier(0.2, 0, 0, 1)` on the parent grid
- Close via × button (top-right of panel) OR click another row to swap content
- The newly active row gets a pink `inset 3px 0 0 0` border + `surface-2` background

### Mobile

Below 1000px, the panel becomes a full-screen overlay: `position: fixed; inset: 56px 0 0 0; z-index: 9000;`. Close button is more prominent.

### Panel structure

```html
<aside class="drill-panel">
  <div class="drill-head">
    <div>
      <div class="drill-title">CVE-2024-3094</div>  <!-- mono, lg, weight 600 -->
      <div class="drill-meta-row">
        <span class="sev-pill critical">■ Critical</span>
        <span class="kev-badge">★ CISA KEV</span>
        <span class="exploit-badge">⚡ exploit available</span>
      </div>
    </div>
    <button class="close" onclick="toggleDrill(false)">
      <svg><use href="#i-x"/></svg>
    </button>
  </div>

  <div class="drill-section">
    <h4>Description</h4>
    <p>…</p>
  </div>

  <!-- Other sections: CVSS, Affected hosts, Linked vulnerabilities, Activity, Actions -->

  <div class="drill-section">
    <h4>Actions</h4>
    <div style="display: flex; flex-direction: column; gap: 8px;">
      <button class="btn-cta">Create ticket</button>
      <button class="btn-secondary">Snooze 24h</button>
      <button class="btn-secondary">Copy NVD link</button>
    </div>
  </div>
</aside>
```

Section heading style: `<h4>` is small uppercase tracking-wide muted label (NOT a typographic h4). Body is regular text-sm.

## Chip-bar filters

**No persistent left filter drawer.** All filters live in a horizontal chip bar above the table.

```html
<div class="filter-bar">
  <input class="filter-search" placeholder="Search CVE, product…" />
  <span class="sep"></span>
  <div class="chip active"><span class="sev-glyph critical">■</span> Critical</div>
  <div class="chip active"><span class="sev-glyph high">▲</span> High</div>
  <span class="sep"></span>
  <div class="chip active">Qualys</div>
  <div class="chip active">CISA KEV</div>
  <span class="sep"></span>
  <span class="saved-pill">★ Today's triage</span>
  <a class="clear-link" onclick="event.preventDefault();">Clear all</a>
</div>
```

### Rules

- Search input on the left (~220px wide)
- Separator `<span class="sep">` between groups (1px vertical line, subtle border color)
- Groups in order: search · severity · sources · saved-filter pill · clear-all
- Filter state is URL-synced (production: every change updates the query string for shareability)
- "Clear all" link uses muted color, pink on hover

### Saved-filter pill

Special chip in violet, to distinguish from regular filters:

```css
.saved-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px;
  background: var(--color-violet-soft);
  border: 1px solid rgba(167, 139, 250, 0.3);
  color: var(--color-violet);
  font-size: 11px; font-weight: 500;
}
```

Prefix with ★ for visual distinction.

## Bulk action floating bar

Appears when the user selects rows via checkboxes (variant A of sketch 003).

```html
<div class="bulk-bar">
  <span class="count"><span class="num">3</span> selected</span>
  <span class="sep"></span>
  <button class="bulk-action">Create tickets</button>
  <button class="bulk-action">Snooze</button>
  <button class="bulk-action">Tag</button>
  <button class="bulk-action">Resolve</button>
  <span class="sep"></span>
  <button class="bulk-action" onclick="clearSelection()">×</button>
</div>
```

### Rules

- Position: `fixed; bottom: 24px; left: 50%; transform: translateX(-50%);` — centered horizontally
- Chrome: glass surface (`rgba(36, 27, 64, 0.95)` + backdrop-blur), rounded-full pill, shadow-elevated
- Slide-up animation on appear: `animation: bulk-rise 220ms cubic-bezier(0, 0, 0, 1);`
- Count number in pink, mono
- Actions left-aligned, close × on the right
- Hides automatically when selection count returns to 0

## Activity timeline

Used in: vulnerability drill panel, asset detail, ticket detail.

```html
<div class="timeline">
  <div class="timeline-item">
    <div class="timeline-dot pink"><svg><use href="#i-flame"/></svg></div>
    <div class="timeline-body">
      <span class="who">Qualys</span>
      <span class="what">detected</span>
      <span class="ref">CVE-2024-3094</span>
      <div class="time">12m ago</div>
    </div>
  </div>
  <!-- More items -->
</div>
```

### Dot variants

```css
.timeline-dot { width: 28px; height: 28px; border-radius: 50%; border: 2px solid var(--color-border-subtle); display: grid; place-items: center; color: var(--color-text-muted); z-index: 1; }
.timeline-dot.pink    { background: var(--color-pink-soft);    border-color: rgba(236, 72, 153, 0.4); color: var(--color-pink); }
.timeline-dot.amber   { background: var(--color-amber-soft);   border-color: rgba(245, 158, 11, 0.4); color: var(--color-amber); }
.timeline-dot.violet  { background: var(--color-violet-soft);  border-color: rgba(167, 139, 250, 0.4); color: var(--color-violet); }
.timeline-dot.success { background: var(--color-success-soft); border-color: rgba(74, 222, 128, 0.4); color: var(--color-success); }
```

### Vertical line

Drawn via a `::before` on the `.timeline` container:

```css
.timeline { position: relative; }
.timeline::before {
  content: ''; position: absolute;
  left: 13px; top: 14px; bottom: 14px; width: 1px;
  background: var(--color-border-subtle);
}
```

### Color mapping (events → dot variant)

- **Pink** — new detections (flame icon), tickets created (ticket-plus icon), SLA-related events
- **Amber** — warnings, comments, "in progress" status changes
- **Violet** — assignment changes, comments
- **Success (green)** — completions, resolutions, sync successes
- **Default (no class)** — system events (scans completed, sync triggered)

### Body content

- `.who` — the actor (system or user, weight 500)
- `.what` — verb phrase, muted color
- `.ref` — referenced ID (CVE-XXXX-YYYY, JIRA-2841, hostnames), mono, weight 500
- `.time` — relative timestamp, faint, mono, below the message

## Comment input (ticket detail)

```html
<div style="display: flex; gap: 8px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--color-border-subtle);">
  <input class="filter-search" style="flex: 1; width: auto;" placeholder="Add a comment…" />
  <button class="btn-cta sm"><svg><use href="#i-comment"/></svg>Comment</button>
</div>
```

Lives at the bottom of the activity timeline card. Input grows to fill, gradient CTA on the right.

## Watcher / contributor stack

```html
<div class="val" style="display: flex; gap: -6px;">
  <div class="assignee-chip"><div class="avatar amber">JK</div></div>
  <div class="assignee-chip"><div class="avatar violet">MR</div></div>
  <span style="font-size: var(--text-xs); color: var(--color-text-muted); margin-left: 4px;">+3</span>
</div>
```

Avatars overlap slightly (`gap: -6px` via negative). Overflow count as text suffix. Hover (production) reveals the full list in a popover.

## View toggles

For switching between equivalent views of the same data (e.g., By CVE / By host on `/vulnerabilities`, List / Board on `/tickets`):

```html
<div class="view-toggle">
  <button class="active">List</button>
  <button>Board</button>
</div>
```

Pill segmented control. Compact. Position: in the page-head-actions zone, left of the export/CTA buttons.

## Drag-to-update status (deferred — Kanban future)

Sketched in 006 variant C, deferred as a future "Board view" toggle on the list route. When implemented:

- HTML5 drag-and-drop or library (probably `@dnd-kit` per modern React tooling)
- Drag handle: full card (cursor: grab → grabbing)
- Drop zones: each column body
- Drop animation: card slides into position with a brief fade
- Status update fires immediately on drop; revertible via toast undo
- Column lockouts: cannot drop "Completed" cards back to "Open" (one-way transitions where appropriate)

Visual feedback during drag:
- Source card: 50% opacity, slight rotation (`transform: rotate(2deg)`)
- Hovered column: dashed accent border, `surface-2` background
- Other columns: no change

## Pagination

```html
<div class="pager">
  <button disabled>‹</button>
  <button class="active">1</button>
  <button>2</button>
  <button>3</button>
  <button>…</button>
  <button>9</button>
  <button>›</button>
</div>
```

Mono numbers. Active page in pink with pink-soft background + pink border. Disabled prev at page 1 (opacity 0.3, cursor not-allowed).

## Hover and focus interactions

| Element | Hover behavior |
|---|---|
| Buttons (CTA, secondary, ghost) | 1px translate-Y up (fast), CTA also intensifies its glow |
| Table rows | Background lifts to `surface-2` |
| Nav items | Background lifts to `surface`, color brightens to `text` |
| Chips | Color brightens to `text`, border to `border` |
| Filter inputs | Border to `border`, no movement |
| Severity pills | (No hover — they're informational) |

Focus rings: violet 3px halo via box-shadow. Never the brown/yellow default browser ring.

## Anti-patterns

- **Don't put drill-down inside row expansion** (table rows expanding inline). Use the side panel.
- **Don't make filter chips draggable** to reorder. Keep them static.
- **Don't auto-dismiss the bulk action bar** if rows are selected — only when count → 0.
- **Don't animate the timeline dots** (no pulses or spins).
- **Don't use drag-and-drop on the main list view** — that's the Board variant only.
- **Don't open modals for content that fits in a side panel.** Modals are for confirmations only (delete, destructive actions).

## Origin

- Drill-down: sketch 003 winner, reused in 006 winner
- Chip bar: sketch 003 winner
- Bulk bar: sketch 003 variant A
- Timeline: sketches 005 + 006 detail
- Comment input: sketch 006 variant B (detail page)
- Watcher stack: sketch 006 variant B
- Drag/kanban (deferred): sketch 006 variant C
