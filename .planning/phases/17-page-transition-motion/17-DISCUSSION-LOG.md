# Phase 17: Page-transition motion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 17-page-transition-motion
**Areas discussed:** When it fires, Transition feel, Transition scope, Firefox fallback, First paint, Skeleton, Scroll, App entry, Drill+nav

---

## When it fires

| Option | Description | Selected |
|--------|-------------|----------|
| Pathname changes only | Fade only on route path change; drill/tab/toggle (searchParams) do not fade | ✓ |
| Every navigation | Fade on any URL change incl. searchParams | |

**User's choice:** Pathname changes only
**Notes:** Highest-risk decision; safest for UX-D-06-04 (no DrillPanel race). Must key off `usePathname()`.

---

## Transition feel — style

| Option | Description | Selected |
|--------|-------------|----------|
| Pure opacity fade | Opacity only, no movement; matches contract "no transforms" | ✓ |
| Fade + subtle drift | Cross-fade + ~8px vertical slide (a transform) | |

**User's choice:** Pure opacity fade

## Transition feel — duration

| Option | Description | Selected |
|--------|-------------|----------|
| 220–320ms (snappy) | --motion-base/--motion-slow | ✓ |
| 520ms (reserved token) | --motion-xslow as reserved in foundation.md | |

**User's choice:** 220–320ms (snappy)
**Notes:** Claude discretion within band, leaning 320ms for a full-content cross-fade.

---

## Transition scope

| Option | Description | Selected |
|--------|-------------|----------|
| Content-only fades | Sidebar+topbar stay still; needs view-transition-name isolation | ✓ |
| Full-viewport fade | Whole screen incl. chrome fades (VT default) | |

**User's choice:** Content-only fades

---

## Firefox fallback

| Option | Description | Selected |
|--------|-------------|----------|
| CSS-keyframe cross-fade | Parity fade on template mount; reused by reduced-motion blanket | ✓ |
| Clean instant swap | No animation in Firefox | |

**User's choice:** CSS-keyframe cross-fade

---

## First paint / hard reload

| Option | Description | Selected |
|--------|-------------|----------|
| Nav only, not first load | No fade on hard reload/first paint; fades on later navs | ✓ |
| Fade on every entry | Also fade in content on first paint | |

**User's choice:** Nav only, not first load

---

## Skeleton (fade target)

| Option | Description | Selected |
|--------|-------------|----------|
| Fade into skeleton | Fade on pathname change → new route skeleton; skeleton→data no second fade | ✓ |
| Wait for data | Delay fade until data loaded | |

**User's choice:** Fade into skeleton
**Notes:** Motion decoupled from network latency.

---

## Scroll behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Next.js default | Scroll-to-top forward, restore on back/forward | ✓ |
| Custom scroll handling | Explicit scroll management coordinated with transition | |

**User's choice:** Keep Next.js default

---

## App entry (login → dashboard)

| Option | Description | Selected |
|--------|-------------|----------|
| Instant (no fade) | First mount of authed template appears instantly | ✓ |
| Fade on entry | Cross-fade dashboard in from login | |

**User's choice:** Instant (no fade)

---

## DrillPanel open during route change

| Option | Description | Selected |
|--------|-------------|----------|
| Fades out with content | Panel captured in outgoing snapshot, fades with content | ✓ |
| Close first, then fade | Animate panel closed before route fade | |

**User's choice:** Fades out with content

---

## Claude's Discretion

- Exact duration within 220–320ms (leaning 320ms).
- `view-transition-name` value and content-wrapper location.
- Transition CSS location (recommend globals.css single-source).
- Validation depth: recommended a lightweight e2e assertion that the fade fires on a real
  pathname change (raised; user proceeded to create context without an explicit pick).

## Deferred Ideas

- Navigation pending indicator (top loading bar / pending cue) — new capability outside
  UX-D-06; noted for future backlog.
