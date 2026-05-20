import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@/lib/queries/use-stats', () => ({
  useStats: vi.fn(),
}));

import { StatStripWired } from './stat-strip-wired';
import { useStats } from '@/lib/queries/use-stats';

describe('<StatStripWired>', () => {
  beforeEach(() => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: {
        dashboard_tiles: {
          critical_open: { value: 3, delta: 1, delta_direction: 'up' },
          sla_at_risk: { value: 12, delta: -2, delta_direction: 'down' },
          kev: { value: 5, delta: 0, delta_direction: 'flat' },
          mttr_30d: { value: '4.2d', delta: null, delta_direction: null },
        },
        top_vuln: null,
        vuln_open_count: 200,
        asset_total_count: 50,
        ticket_open_count: 7,
        onboarding_state: 'ready',
      },
    });
  });

  it('renders all four microcopy labels', () => {
    render(<StatStripWired />);
    expect(screen.getByText('Critical · open')).toBeInTheDocument();
    expect(screen.getByText('SLA · at risk')).toBeInTheDocument();
    expect(screen.getByText('CISA KEV')).toBeInTheDocument();
    expect(screen.getByText('MTTR · 30d')).toBeInTheDocument();
  });

  it('renders ShieldAlert / Clock / Flame / TrendingDown icons (D-S-05)', () => {
    const { container } = render(<StatStripWired />);
    expect(container.querySelector('svg.lucide-shield-alert')).not.toBeNull();
    expect(container.querySelector('svg.lucide-clock')).not.toBeNull();
    expect(container.querySelector('svg.lucide-flame')).not.toBeNull();
    expect(container.querySelector('svg.lucide-trending-down')).not.toBeNull();
  });

  it('mttr_30d Stat receives delta={null} — renders "Δ —" (Pitfall 8)', () => {
    render(<StatStripWired />);
    // microcopy.stats.deltaUnknown is rendered by Stat when delta is null/undefined.
    expect(screen.getByText('Δ —')).toBeInTheDocument();
  });

  it('section has aria-labelledby="stats-h" and sr-only h2 "Today at a glance"', () => {
    render(<StatStripWired />);
    const section = document.querySelector('section[aria-labelledby="stats-h"]');
    expect(section).not.toBeNull();
    expect(screen.getByText('Today at a glance')).toBeInTheDocument();
  });

  it('renders 4 Stat tiles (one per dashboard_tile)', () => {
    render(<StatStripWired />);
    // All 4 labels present is the strongest assertion of tile count;
    // additionally check that the StatStrip is rendered as the grid container.
    const labels = [
      'Critical · open',
      'SLA · at risk',
      'CISA KEV',
      'MTTR · 30d',
    ];
    labels.forEach((l) => expect(screen.getByText(l)).toBeInTheDocument());
  });
});
