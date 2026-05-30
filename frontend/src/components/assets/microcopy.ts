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
    source: 'Source',
    os_family: 'OS',
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
