/**
 * Microcopy for the /assets surfaces (list + detail).
 *
 * Co-located so copy reviews live next to the components they ship with;
 * mirrors `frontend/src/components/vulnerabilities/microcopy.ts` pattern
 * from Phase 11. Tone follows `copy-voice.md` — "peer, not butler".
 */
export const microcopy = {
  page: {
    h1: 'Assets',
    eyebrow: 'Inventory',
  },
  chips: {
    category: 'Category',
    risk_band: 'Risk band',
    // Phase 35 SRC-06: the stale single `source` axis is partitioned into a
    // `scanner` axis (corroboration-eligible) and an `enrichment_source`
    // facet (JAMF/HUMAANS/Intune — presence only, no AND semantics).
    scanner: 'Scanner',
    enrichment_source: 'Enrichment',
    os_family: 'OS',
    // Phase 35 SRC-02/03/04 — OR/AND source-mode toggle, copy reused
    // verbatim from vulnerabilities/microcopy.ts (Plan 02) so the label is
    // identical across every surface. Avoids AND/OR jargon (copy-voice.md).
    sourceModeLabel: 'Match',
    sourceModeAny: 'Any selected',
    sourceModeAll: 'All selected',
    sourceModeDisabledHint: 'Select 2 or more scanners to match all of them',
  },
  empty: {
    noResults: {
      title: 'No assets match these filters',
      body: 'Adjust the chip-bar or clear filters to see the full inventory.',
    },
    noAssets: {
      title: 'No assets yet',
      body: 'Connect a scanner or MDM source to start collecting devices.',
    },
  },
  columns: {
    hostname: 'Hostname',
    os: 'OS',
    owner: 'Owner',
    risk: 'Risk',
    tags: 'Tags',
    sources: 'Sources',
  },
} as const;
