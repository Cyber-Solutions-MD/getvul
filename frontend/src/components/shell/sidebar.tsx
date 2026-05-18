'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Home, Bug, Server, Cloud, Ticket, Plug, Users, Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { GradientText } from '@/components/ui/gradient-text';
import { useStats } from '@/lib/queries/use-stats';

// D-N-01 (Phase 10) — chip key identifies which live count drives each nav item.
// Only Vulnerabilities (vuln_open_count), Assets (asset_total_count), and Tickets
// (ticket_open_count) carry chips. CSPM / Connectors / Users / Settings / Dashboard
// render WITHOUT chips per D-N-01.
type ChipKey = 'vuln_open' | 'asset_total' | 'ticket_open';

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
  exact?: boolean;  // /dashboard root uses exact match (D-35) to avoid lighting up for nested routes
  chip?: ChipKey;   // when set, render a live count chip; otherwise no chip (D-N-01)
};

// D-36 verbatim — order/grouping/labels preserved. Phase 10 D-N-01 removes the chip
// from Dashboard and CSPM; only Vulnerabilities + Assets keep chips in this group.
const TRIAGE_ITEMS: NavItem[] = [
  { label: 'Dashboard',       href: '/dashboard',                 icon: Home,   exact: true },
  { label: 'Vulnerabilities', href: '/dashboard/vulnerabilities', icon: Bug,    chip: 'vuln_open' },
  { label: 'Assets',          href: '/dashboard/assets',          icon: Server, chip: 'asset_total' },
  { label: 'CSPM',            href: '/dashboard/cspm',            icon: Cloud },
];

// D-36 grouping preserved. Phase 10 D-N-01 removes the chip from Connectors; only
// Tickets keeps a chip in this group.
const WORKFLOW_ITEMS: NavItem[] = [
  // Phase 9's D-36 spec had "/dashboard/integrations" but the v1 route directory
  // is actually `connectors/` (verified during Phase 10 HUMAN-UAT). Correcting
  // the href here; the label stays `Connectors` per D-36 wording.
  { label: 'Tickets',    href: '/dashboard/tickets',    icon: Ticket, chip: 'ticket_open' },
  { label: 'Connectors', href: '/dashboard/connectors', icon: Plug },
];

const UNLABELED_ITEMS: NavItem[] = [
  { label: 'Users',    href: '/dashboard/users',    icon: Users },
  { label: 'Settings', href: '/dashboard/settings', icon: Settings },
];

function isActive(pathname: string | null, item: NavItem): boolean {
  if (!pathname) return false;
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(item.href + '/');
}

// Em-dash fallback rendered during loading AND on error per D-N-03 — no placeholder
// bar primitive; the dash preserves chip width across the loading→loaded transition,
// avoiding CLS. Width of three digits in tabular-nums mono is comparable to the
// em-dash glyph at the same 11px size, so a 3-digit count does not shift surrounding
// layout.
const CHIP_FALLBACK = '—';

export function Sidebar() {
  const pathname = usePathname();
  // D-N-02: single shared useStats() call. Because the (authed) route group is wrapped
  // in QueryClientProvider (Plan 02) and /dashboard's page also calls useStats(), this
  // hook hits the same TanStack cache — no double-fetch. Verified by sidebar-cache.test.tsx.
  const stats = useStats();
  // D-N-03: render '—' on loading AND on error. Backend (Plan 01) provides the three
  // count fields at the top level of the /stats response (D-N-02).
  const counts: Record<ChipKey, number | null> = {
    vuln_open:    stats.data?.vuln_open_count ?? null,
    asset_total:  stats.data?.asset_total_count ?? null,
    ticket_open:  stats.data?.ticket_open_count ?? null,
  };

  return (
    <nav
      // D-41: hide on viewports <=999px; visible on >=1000px (verbatim D-41 — uses Tailwind 3.4 arbitrary-variant max-[999px] to match exactly, NOT `lg` which is 1024px).
      // <nav> (not <aside>) — the sidebar's role IS navigation; aria-label disambiguates against the in-page <nav> chrome if any.
      className="max-[999px]:hidden flex w-[220px] shrink-0 flex-col border-r border-border bg-bg-darker min-h-screen"
      aria-label="Primary navigation"
    >
      {/* Brand mark — D-40: wraps Link to /dashboard */}
      <div className="px-5 py-5">
        <Link href="/dashboard" className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet rounded-md">
          <span className="text-xl font-bold tracking-tight">
            <GradientText>GetVul</GradientText>
          </span>
        </Link>
      </div>

      {/* Wrap top sections in flex-1 + overflow so they share remaining space and `mt-auto` anchors reliably */}
      <div className="flex-1 overflow-y-auto">
        <NavSection label="Triage" items={TRIAGE_ITEMS} pathname={pathname} counts={counts} />
        <NavSection label="Workflow" items={WORKFLOW_ITEMS} pathname={pathname} counts={counts} />
      </div>
      {/* Unlabeled bottom group per D-36 — mt-auto anchors to the bottom because the wrapper above takes flex-1 */}
      <div className="mt-auto">
        <NavSection items={UNLABELED_ITEMS} pathname={pathname} counts={counts} />
      </div>
    </nav>
  );
}

function NavSection({
  label,
  items,
  pathname,
  counts,
}: {
  label?: string;
  items: NavItem[];
  pathname: string | null;
  counts: Record<ChipKey, number | null>;
}) {
  // Wrapper is a plain <div> (not <nav>) because the outer <aside aria-label="Primary
  // navigation"> is already the single navigation landmark. Nesting <nav> elements
  // without unique aria-labels trips axe's landmark-unique rule (D-30 a11y bar).
  return (
    <div className="px-3 py-2">
      {label && (
        <div className="px-3 pt-3 pb-1 text-[11px] font-medium uppercase tracking-wider text-text-faint">
          {label}
        </div>
      )}
      <ul className="space-y-0.5">
        {items.map((item) => {
          const active = isActive(pathname, item);
          const Icon = item.icon;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet',
                  active
                    ? 'text-text bg-surface'
                    : 'text-text-muted hover:text-text hover:bg-surface/60',
                )}
              >
                {/* Gradient active strip — D-35 implies an active visual marker */}
                {active && (
                  <span
                    aria-hidden
                    className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r bg-gradient-sunset-vertical"
                  />
                )}
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className="flex-1">{item.label}</span>
                {item.chip !== undefined && renderChip(counts[item.chip])}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// D-N-03: pure presentation — em-dash on null (loading or error), number otherwise.
// No placeholder-bar primitive here on purpose; the em-dash fallback prevents layout
// shift during the loading-to-loaded transition (acceptance criterion).
function renderChip(value: number | null): React.ReactNode {
  return (
    <span className="text-[11px] tabular-nums text-text-faint">
      {value === null ? CHIP_FALLBACK : value}
    </span>
  );
}
