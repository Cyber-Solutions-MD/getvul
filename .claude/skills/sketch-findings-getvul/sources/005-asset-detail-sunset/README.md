---
sketch: 005
name: asset-detail-sunset
question: "How should the asset detail page lay out — and which risk-score visualization works best with the sunset palette?"
winner: "B"
tags: [asset-detail, layout, risk-score, detail-page-pattern, metadata-sidebar]
---

# Sketch 005: Asset Detail — Sunset Palette

## Design Question

The v1 asset detail (`/assets/[id]`) shows: hostname + host status + OS + risk score + IP + owner (IdP pull) + nested vulnerability list + remediation list. Per the redesign direction, "less complex than Wiz" + "informative + actionable."

Three different layout patterns + three different risk-score visualizations to test together:

1. **Layout** — single-page stack / two-column with rail / tabbed
2. **Risk score viz** — big gradient number / circular ring with gradient stroke / horizontal bar with gradient fill

## How to View

```
open .planning/sketches/005-asset-detail-sunset/index.html
```

Three variants. Same asset: `prod-db-01` (Ubuntu 22.04, 10.0.3.42, owner Diego Salgado via Okta, risk 86, 7 vulns, 2 critical, 3 high, 1 medium, 1 low).

## Variants

- **A — Hero strip + single-page stack** — Big hero card across the top: asset name + status + tags + OS info + owner card + **risk score as a giant gradient-text number** (86 in red→amber gradient with `▲ +12 in 7d` delta below) + action buttons. Below: 7 vulnerabilities as embedded rows. Then a 2-col row with Remediation steps + Activity timeline. Then full-width Metadata grid (8 fields, 2 cols). Single scroll. Everything visible.

- **B — Two-column workspace with metadata rail** — Left main column has the Vulnerabilities card (with severity-breakdown ribbon — 2 critical / 3 high / 1 medium / 1 low) and the Remediation timeline. Right 340px rail (sticky on scroll) has: **risk score as a circular ring** (gradient stroke, 86 in the center, with breakdown rows: 2 critical exposures, 1 SLA breach, 3 KEV, ▲ +12 7d), owner card, identity/host metadata block (8 fields stacked), tags. Most "Linear-like."

- **C — Tabbed** — Compact hero with name + status + tags + OS one-liner + owner mention + **risk score as a horizontal bar with gradient fill** (86 with 0/50/100 scale) + actions. Below: tabs (Vulnerabilities 7 · Remediation · Activity · Identity & host) with the active-tab indicated by a pink bottom border. Each tab fills the main area. Vulnerabilities tab opens by default — shows the same severity-breakdown ribbon + 7 rows. Most "WIz-like" pattern.

All three use the same chrome (sidebar + topbar + breadcrumb), same severity treatment, same gradient CTA ("Create ticket"), same secondary "Rescan" button.

## What to Look For

**Layout comparison:**
- **A** — Everything visible at once. Long scroll. Pro: nothing hidden. Con: feels overwhelming.
- **B** — Two-column with persistent metadata rail. Pro: identity is always there as you scroll vulns. Con: less horizontal space for the main content.
- **C** — Tabbed. Pro: focused, less overwhelming per-screen. Con: tabbed UIs hide content; user has to click to discover.

**Risk score visualization comparison:**
- **A's big gradient number (86)** — most impactful. Reads instantly. But: takes a lot of room.
- **B's gradient ring with breakdown** — informative + visual. Shows why the score is what it is (2 critical, 1 SLA breach, etc.). Most "premium SaaS" feel.
- **C's gradient bar with 0–50–100 scale** — most grounded. Shows where on the scale this asset sits. Compact.

**Hero density:**
- A's hero is the loudest — big name, owner card embedded, big number, vertical action stack
- B's name strip is the calmest — just name + status + tags + actions on a single row, with all detail in the rail
- C's hero is balanced — name + one-liner + risk bar + actions

**Owner card:**
- A and B show the full owner card (avatar + name + role + email + IdP source pill)
- C shows owner as inline text only ("owner Diego Salgado"), full card lives in the Identity tab

**Vulnerability list embedding:**
- A: flat list of compact rows, no severity breakdown ribbon
- B and C: severity-breakdown ribbon at the top of the vuln list (■2 · ▲3 · ◆1 · ○1), then rows

**Activity timeline:**
- A: 4 items in a 2-col side-by-side with Remediation
- B: 5 items as a full-width timeline below the vulnerabilities
- C: lives behind the Activity tab

**Mobile (toggle 375):**
- All three collapse the sidebar.
- A: hero stacks (name → risk → actions); content stacks vertically
- B: metadata rail moves below the main column
- C: hero stacks; tabs scroll horizontally if needed

## Open variables

- The risk-score "delta" indicator (▲ +12 in 7d) shows the score is getting worse — is the up-arrow + red color the right signal language? (Up = bad in security context, can be counterintuitive.)
- Owner reassignment: B and C have a "Reassign" link near the owner card. A doesn't. Add it?
- The metadata grid in A is dense (8 fields, 2 cols, no card chrome). Could become its own card per category. Currently it's flat for compactness.
- Tags location: all three show tags inline with the hostname (`prod`, `postgres`, etc.). Could move to metadata block.
- Tab order in C: Vulnerabilities first feels right (it's the reason you're here). Identity last because it's reference info.
- The big gradient-text "86" in A is striking but might feel too marketing-y. Watch how it reads next to the rest of the page chrome.
