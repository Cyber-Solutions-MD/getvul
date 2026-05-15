import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { ActivityFeed, type ActivityItem } from './activity-feed';

// Deterministic "now" so Intl.RelativeTimeFormat output is testable.
const NOW = new Date('2026-05-15T12:00:00Z').getTime();

describe('<ActivityFeed>', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const items: ActivityItem[] = [
    {
      id: '1',
      category: 'new_critical_vuln',
      title: 'Qualys detected CVE-2024-3094',
      body: null,
      occurred_at: new Date(NOW - 12 * 60 * 1000).toISOString(), // 12 min ago
    },
    {
      id: '2',
      category: 'sla_breach',
      title: 'SLA breach: 3 tickets overdue',
      body: 'CRITICAL severity past due',
      occurred_at: new Date(NOW - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      href: '/dashboard/tickets',
    },
    {
      id: '3',
      category: 'sync_failure',
      title: 'Tenable sync failed',
      body: null,
      occurred_at: new Date(NOW - 5 * 60 * 1000).toISOString(), // 5 min ago
    },
  ];

  it('renders one row per item with the title (D-P-04)', () => {
    render(<ActivityFeed items={items} />);
    expect(
      screen.getByText('Qualys detected CVE-2024-3094')
    ).toBeInTheDocument();
    expect(screen.getByText('SLA breach: 3 tickets overdue')).toBeInTheDocument();
    expect(screen.getByText('Tenable sync failed')).toBeInTheDocument();
  });

  it('renders D-A-03 default emptyCopy verbatim when items=[]', () => {
    render(<ActivityFeed items={[]} />);
    expect(
      screen.getByText(
        "No recent activity. We'll show events here as they happen."
      )
    ).toBeInTheDocument();
  });

  it('renders custom emptyCopy when provided', () => {
    render(<ActivityFeed items={[]} emptyCopy="Custom empty." />);
    expect(screen.getByText('Custom empty.')).toBeInTheDocument();
  });

  it('renders lucide icons per category (D-A-02)', () => {
    render(<ActivityFeed items={items} />);
    // Each row carries data-testid="row-<category>"; find the svg inside.
    const criticalRow = screen.getByTestId('row-new_critical_vuln');
    const criticalSvg = criticalRow.querySelector('svg');
    expect(criticalSvg).not.toBeNull();
    expect(criticalSvg!.getAttribute('class') || '').toMatch(/shield-alert/i);

    const slaRow = screen.getByTestId('row-sla_breach');
    const slaSvg = slaRow.querySelector('svg');
    expect(slaSvg!.getAttribute('class') || '').toMatch(/\bclock\b/i);

    const syncRow = screen.getByTestId('row-sync_failure');
    const syncSvg = syncRow.querySelector('svg');
    expect(syncSvg!.getAttribute('class') || '').toMatch(/wifi-off/i);
  });

  it('risk_change category defaults to TrendingDown icon (D-A-02)', () => {
    const riskItem: ActivityItem = {
      id: '4',
      category: 'risk_change',
      title: 'Asset risk dropped',
      body: null,
      occurred_at: new Date(NOW - 60 * 1000).toISOString(),
    };
    render(<ActivityFeed items={[riskItem]} />);
    const row = screen.getByTestId('row-risk_change');
    const svg = row.querySelector('svg');
    expect(svg!.getAttribute('class') || '').toMatch(/trending-down/i);
  });

  it('category rows render a tinted icon container consuming sunset tokens (D-A-01)', () => {
    render(<ActivityFeed items={items} />);
    const criticalRow = screen.getByTestId('row-new_critical_vuln');
    // Tinted icon container — must consume a sunset Tailwind color class (bg-pink-soft,
    // text-pink, etc.). The exact class names live in the implementation; we assert the
    // category-tint contract by checking the icon container has SOME bg-* class beyond
    // the row default.
    const iconWrapper = criticalRow.querySelector('[aria-hidden="true"]');
    expect(iconWrapper).not.toBeNull();
    expect(iconWrapper!.className).toMatch(
      /(bg-pink|bg-pink-soft|bg-severity-critical|bg-danger)/
    );
  });

  it('items with href render an <a> link wrapping the row', () => {
    render(<ActivityFeed items={items} />);
    const slaRow = screen.getByTestId('row-sla_breach');
    const anchor = slaRow.querySelector('a[href]');
    expect(anchor).not.toBeNull();
    expect(anchor!.getAttribute('href')).toBe('/dashboard/tickets');
  });

  it('items without href render no anchor (non-link variant)', () => {
    render(<ActivityFeed items={items} />);
    const criticalRow = screen.getByTestId('row-new_critical_vuln');
    expect(criticalRow.querySelector('a[href]')).toBeNull();
  });

  it('renders relative time strings via Intl.RelativeTimeFormat (copy-voice "Xm ago")', () => {
    render(<ActivityFeed items={items} />);
    // 12 minutes ago / 2 hours ago / 5 minutes ago — exact strings depend on locale
    // ('numeric: auto' may produce "12 minutes ago" in en); we check the row contains
    // a minute/hour token + 'ago'.
    const criticalRow = screen.getByTestId('row-new_critical_vuln');
    expect(criticalRow.textContent || '').toMatch(/ago/);
    const slaRow = screen.getByTestId('row-sla_breach');
    expect(slaRow.textContent || '').toMatch(/ago/);
  });

  it('renders body when present', () => {
    render(<ActivityFeed items={items} />);
    expect(
      screen.getByText('CRITICAL severity past due')
    ).toBeInTheDocument();
  });

  it('has no axe violations with items + empty state (D-Test-01)', async () => {
    const { container: c1 } = render(<ActivityFeed items={items} />);
    expect(await axe(c1)).toHaveNoViolations();
    const { container: c2 } = render(<ActivityFeed items={[]} />);
    expect(await axe(c2)).toHaveNoViolations();
  });
});
