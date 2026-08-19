// Single source-of-truth for all navigation items.
// Consumed by: sidebar.tsx, bottom-nav.tsx, nav-drawer.tsx, nav-more-sheet.tsx
// This is a plain .ts file (no JSX) — all types + arrays + helpers in one place.
import {
  Home, Bug, Server, Cloud, Ticket, Plug, Users, Settings, Zap, FolderKanban, Target, ShieldOff,
} from 'lucide-react';
import type { ComponentType } from 'react';

// D-N-01 (Phase 10) — chip key identifies which live count drives each nav item.
// Only Vulnerabilities (vuln_open_count), Assets (asset_total_count), and Tickets
// (ticket_open_count) carry chips. CSPM / Connectors / Users / Settings / Dashboard
// render WITHOUT chips per D-N-01.
export type ChipKey = 'vuln_open' | 'asset_total' | 'ticket_open';

export type NavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
  exact?: boolean;  // /dashboard root uses exact match (D-35) to avoid lighting up for nested routes
  chip?: ChipKey;   // when set, render a live count chip; otherwise no chip (D-N-01)
};

// D-36 verbatim — order/grouping/labels preserved. Phase 10 D-N-01 removes the chip
// from Dashboard and CSPM; only Vulnerabilities + Assets keep chips in this group.
export const TRIAGE_ITEMS: NavItem[] = [
  { label: 'Dashboard',       href: '/dashboard',                 icon: Home,   exact: true },
  { label: 'Vulnerabilities', href: '/dashboard/vulnerabilities', icon: Bug,    chip: 'vuln_open' },
  { label: 'Assets',          href: '/dashboard/assets',          icon: Server, chip: 'asset_total' },
  { label: 'CSPM',            href: '/dashboard/cspm',            icon: Cloud },
];

// D-36 grouping preserved. Phase 10 D-N-01 removes the chip from Connectors; only
// Tickets keeps a chip in this group.
export const WORKFLOW_ITEMS: NavItem[] = [
  // Phase 9's D-36 spec had "/dashboard/integrations" but the v1 route directory
  // is actually `connectors/` (verified during Phase 10 HUMAN-UAT). Correcting
  // the href here; the label stays `Connectors` per D-36 wording.
  { label: 'Tickets',    href: '/dashboard/tickets',       icon: Ticket, chip: 'ticket_open' },
  // Phase 13 Plan 09 (D-S-01) — standalone /tickets/rules route (sunset rewrite, D-S-01).
  // No chip per D-N-01 (rules surface does not carry a live count badge).
  { label: 'Rules',      href: '/dashboard/tickets/rules', icon: Zap },
  { label: 'Connectors', href: '/dashboard/connectors',    icon: Plug },
  // Phase 32 (32-05) — AssetGroup management surface. No chip per D-N-01
  // (this destination does not carry a live count badge).
  { label: 'Asset groups', href: '/dashboard/asset-groups', icon: FolderKanban },
  // Phase 38 (38-04, CAMP-01) — dedicated campaign list view. No chip per
  // D-N-01 (campaigns aren't one of the three chip-carrying destinations:
  // vuln_open / asset_total / ticket_open).
  { label: 'Campaigns', href: '/dashboard/campaigns', icon: Target },
  // Phase 39 (39-06, EXC-02/EXC-03) — manage-only exceptions list view. No
  // chip per D-N-01 (not one of the three chip-carrying destinations).
  { label: 'Exceptions', href: '/dashboard/exceptions', icon: ShieldOff },
];

export const UNLABELED_ITEMS: NavItem[] = [
  { label: 'Users',    href: '/dashboard/users',    icon: Users },
  { label: 'Settings', href: '/dashboard/settings', icon: Settings },
];

// Full 9-item list — used by the tablet drawer that shows all destinations.
export const ALL_ITEMS: NavItem[] = [
  ...TRIAGE_ITEMS,
  ...WORKFLOW_ITEMS,
  ...UNLABELED_ITEMS,
];

// The 3 primary phone slots (slots 1–3 in the 4-column bottom-nav).
// Slot 4 is the "More" button — not a NavItem.
export const BOTTOM_NAV_PRIMARY: NavItem[] = [
  TRIAGE_ITEMS[0], // Dashboard
  TRIAGE_ITEMS[1], // Vulnerabilities
  WORKFLOW_ITEMS[0], // Tickets
];

// The 6 secondary destinations behind the "More" bottom sheet.
// Everything in ALL_ITEMS that is NOT in BOTTOM_NAV_PRIMARY.
const primaryHrefs = new Set(BOTTOM_NAV_PRIMARY.map((i) => i.href));
export const MORE_ITEMS: NavItem[] = ALL_ITEMS.filter(
  (item) => !primaryHrefs.has(item.href),
);
// MORE_ITEMS = Assets, CSPM, Rules, Connectors, Users, Settings
// (/dashboard/assets, /dashboard/cspm, /dashboard/tickets/rules,
//  /dashboard/connectors, /dashboard/users, /dashboard/settings)

// Em-dash fallback rendered during loading AND on error per D-N-03.
export const CHIP_FALLBACK = '—';

/**
 * Returns true when `item` matches `pathname` per D-35:
 * - Items with `exact: true` require an exact pathname match.
 * - All other items match on prefix (the item's href OR any sub-route starting with href+'/').
 */
export function isActive(pathname: string | null, item: NavItem): boolean {
  if (!pathname) return false;
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(item.href + '/');
}
