'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Home, Bug, Server, Cloud, Ticket, Plug, Users, Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { GradientText } from '@/components/ui/gradient-text';

type NavItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
  exact?: boolean;  // /dashboard root uses exact match (D-35) to avoid lighting up for nested routes
  count?: string;   // D-35 — render as '—' placeholder; real data wired in Phase 10
};

// D-36 verbatim:
const TRIAGE_ITEMS: NavItem[] = [
  { label: 'Dashboard',       href: '/dashboard',                 icon: Home,   exact: true, count: '—' },
  { label: 'Vulnerabilities', href: '/dashboard/vulnerabilities', icon: Bug,    count: '—' },
  { label: 'Assets',          href: '/dashboard/assets',          icon: Server, count: '—' },
  { label: 'CSPM',            href: '/dashboard/cspm',            icon: Cloud,  count: '—' },
];

const WORKFLOW_ITEMS: NavItem[] = [
  // D-36: "Connectors (Plug, route /dashboard/integrations — keep that path; the v1 directory is
  // named `integrations` even though the nav label is `Connectors`)"
  { label: 'Tickets',    href: '/dashboard/tickets',      icon: Ticket, count: '—' },
  { label: 'Connectors', href: '/dashboard/integrations', icon: Plug,   count: '—' },
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

export function Sidebar() {
  const pathname = usePathname();

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
        <NavSection label="Triage" items={TRIAGE_ITEMS} pathname={pathname} />
        <NavSection label="Workflow" items={WORKFLOW_ITEMS} pathname={pathname} />
      </div>
      {/* Unlabeled bottom group per D-36 — mt-auto anchors to the bottom because the wrapper above takes flex-1 */}
      <div className="mt-auto">
        <NavSection items={UNLABELED_ITEMS} pathname={pathname} />
      </div>
    </nav>
  );
}

function NavSection({ label, items, pathname }: { label?: string; items: NavItem[]; pathname: string | null }) {
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
                {item.count !== undefined && (
                  <span className="text-[11px] tabular-nums text-text-faint">{item.count}</span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
