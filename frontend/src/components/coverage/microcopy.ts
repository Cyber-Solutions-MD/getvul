/**
 * Microcopy for the /dashboard/coverage surface (Phase 41 Plan 01 — COV-01
 * tracer slice: the blind-spot list only). Co-located so copy reviews live
 * next to the components they ship with; mirrors
 * `frontend/src/components/assets/microcopy.ts`'s pattern. Tone follows
 * `copy-voice.md` — "peer, not butler."
 *
 * Strings are sourced verbatim from 41-UI-SPEC.md's Copywriting Contract
 * (page title/subtitle, the two D-11 empty-state variants, the blind-spot
 * row badge, and the "Never scanned" column header). Plan 02/03 extend
 * this module additively — coverage-strip and route-to-owner copy — rather
 * than inventing a second copy module for the same page.
 *
 * `scannerAbsent` (Plan 03, COV-02, UI-SPEC E4 backstop): the third empty
 * variant — >=1 authoritative (MDM/HR) connector configured but zero
 * scanner connectors exist. Distinct from `noInventory` above, which is
 * about the authoritative side being empty; this is the inverse ("we know
 * about your devices, but nothing scans them").
 */
export const microcopy = {
  page: {
    h1: 'Coverage',
    // "{N} devices in inventory have never been touched by a scanner"
    // (41-UI-SPEC.md) — singularized when n === 1 so the sentence stays
    // grammatical (mirrors assets/page.tsx's inline total===1 handling).
    subtitle: (n: number) =>
      `${n} device${n === 1 ? '' : 's'} in inventory ${n === 1 ? 'has' : 'have'} never been touched by a scanner`,
  },
  empty: {
    // D-11 — zero authoritative (MDM/HR) inventory connected. Distinct from
    // allCovered below: this is "we don't know," not "we checked and it's
    // fine" — never a misleading 0%/100% or a total-assets fallback.
    noInventory: {
      title: 'No inventory source connected',
      body: 'Connect an inventory source (Jamf / Intune / Humaans) to detect coverage gaps.',
      action: 'Connect an inventory source',
    },
    // Quiet-win — inventory exists, zero blind spots. No CTA: genuinely
    // quiet, not an error (state-patterns.md "quiet/win empty" variant).
    allCovered: {
      title: 'Every device is covered',
      body: (n: number) =>
        `All ${n} device${n === 1 ? '' : 's'} in your inventory ${n === 1 ? 'has' : 'have'} been touched by at least one scanner. Nothing to route right now.`,
    },
    // Plan 03 (COV-02, UI-SPEC E4 backstop) — inventory exists, but zero
    // scanner connectors configured. Never the noInventory copy above (that
    // is about the authoritative/MDM+HR side, not the scanner side).
    scannerAbsent: {
      title: 'No scanner connected',
      body: 'You have inventory sources connected, but no vulnerability scanner. Connect one to measure coverage.',
      action: 'Connect a scanner',
    },
  },
  columns: {
    hostname: 'Hostname',
    category: 'Category',
    os: 'OS',
    lastSeen: 'Last seen',
    neverScanned: 'Never scanned',
  },
  badge: {
    noScannerCoverage: 'No scanner coverage',
  },
} as const;
