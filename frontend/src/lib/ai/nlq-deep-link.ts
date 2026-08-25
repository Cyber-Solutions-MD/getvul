// D-17 — the loop-closing read-only "Open in {list}" deep-link. This is the
// SINGLE source of truth for the D-17 param contract: it maps each
// *FilterInput field (backend/app/ai/schemas.py — VulnFilterInput /
// AssetFilterInput / TicketFilterInput) to the EXACT URL param name the
// target list page's useUrlState / useUrlStateList / useUrlStateBool /
// useUrlStateNumber readers consume (wired in the vulnerabilities/assets/
// tickets page.tsx files, Task 2). Applying the SAME translated filter to a
// real list view is therefore pure URL construction — zero new mutation
// surface (D-17 read-only; the T-44-11 XSS clamp lives on the READ side, in
// the list pages' own hooks — this function only ever WRITES a URL).

export type NlqEntity = 'vulnerabilities' | 'assets' | 'tickets';

export type NlqDeepLinkFilterValue =
  | string
  | number
  | boolean
  | readonly (string | number)[]
  | null
  | undefined;

export type NlqDeepLinkFilter = Record<string, NlqDeepLinkFilterValue>;

const ENTITY_ROUTES: Record<NlqEntity, string> = {
  vulnerabilities: '/dashboard/vulnerabilities',
  assets: '/dashboard/assets',
  tickets: '/dashboard/tickets',
};

// Any interpreted-filter key NOT present in the entity's map below is
// intentionally OMITTED from the deep-link — it names no URL param the
// target page reads, so surfacing it would silently violate "every param
// the page reads and filters on." Two notable omissions:
//   - vulnerabilities: VulnFilterInput deliberately has no hostname field
//     (W3) — nothing to omit there, the vuln entity is never host-scoped.
//   - tickets: `asset_hostname` is superseded by `resolved_asset_id` (added
//     server-side by query_assistant.py after `_resolve_hostname` runs) —
//     the raw hostname string is never a URL param the tickets list page
//     reads; only the resolved UUID (`asset_id`) is.
const FIELD_MAP: Record<NlqEntity, Record<string, string>> = {
  vulnerabilities: {
    severity: 'severity',
    status: 'status',
    cisa_kev: 'cisa_kev',
    exploit_available: 'exploit_available',
    age_days_min: 'age_days_min',
    asset_internet_facing: 'asset_internet_facing',
    sla_breached: 'sla_breached',
  },
  assets: {
    // AssetFilterInput.device_category maps onto the assets list page's
    // `category` axis (useUrlStateList('category', CATEGORIES, [])) — same
    // param the AssetsChipBar already writes.
    device_category: 'category',
    internet_facing: 'internet_facing',
  },
  tickets: {
    status: 'status',
    resolved_asset_id: 'asset_id',
  },
};

/**
 * Build a D-17 deep-link URL: the SAME translated filter that produced the
 * NLQ answer, expressed as the target list page's own URL param contract.
 * Omits null/undefined fields and any field the target page doesn't read.
 */
export function buildNlqDeepLink(entity: NlqEntity, filter: NlqDeepLinkFilter): string {
  const sp = new URLSearchParams();
  const map = FIELD_MAP[entity];

  for (const [key, value] of Object.entries(filter)) {
    const param = map[key];
    if (!param) continue; // unmapped field — not a URL param the target page reads
    if (value === null || value === undefined) continue;

    if (Array.isArray(value)) {
      value.forEach((v) => {
        if (v !== null && v !== undefined && v !== '') sp.append(param, String(v));
      });
      continue;
    }
    sp.set(param, String(value));
  }

  const qs = sp.toString();
  const base = ENTITY_ROUTES[entity];
  return qs ? `${base}?${qs}` : base;
}
