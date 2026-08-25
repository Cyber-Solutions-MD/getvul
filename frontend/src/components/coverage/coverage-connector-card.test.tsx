/**
 * coverage-connector-card.test.tsx — Phase 41 Plan 03 (COV-02).
 *
 * Asserts: the 3-tier color-class boundaries (>=90 / 50-89 / <50), the
 * null -> "—" rendering (D-11, never a misleading 0%), the normalized
 * last_sync_status flowing through to SyncStatusPill unchanged (Pitfall 3
 * regression guard — this component receives an already-normalized value),
 * and the stale pill's `stale · {N}d` text + non-red chrome (D-06).
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CoverageConnectorCard } from './coverage-connector-card';
import type { CoverageConnectorCard as CoverageConnectorCardData } from '@/lib/queries/use-coverage-summary';

const BASE_CARD: CoverageConnectorCardData = {
  connector_type: 'QUALYS',
  coverage_pct: 75,
  is_stale: false,
  stale_days: null,
  last_sync_status: 'ok',
  last_sync_at: '2026-08-19T00:00:00Z',
};

describe('CoverageConnectorCard', () => {
  it('renders text-success at >= 90% coverage', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, coverage_pct: 90 }} />);
    const pct = screen.getByText('90%');
    expect(pct.className).toMatch(/text-success/);
  });

  it('renders text-warning at 50-89% coverage', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, coverage_pct: 75 }} />);
    const pct = screen.getByText('75%');
    expect(pct.className).toMatch(/text-warning/);
  });

  it('renders text-danger at < 50% coverage', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, coverage_pct: 49 }} />);
    const pct = screen.getByText('49%');
    expect(pct.className).toMatch(/text-danger/);
  });

  it('renders an em-dash (not "0%") when coverage_pct is null', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, coverage_pct: null }} />);
    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.queryByText(/0%/)).toBeNull();
  });

  it('renders SyncStatusPill in its "ok" state for an already-normalized last_sync_status (Pitfall 3 regression guard)', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, last_sync_status: 'ok' }} />);
    const pill = document.querySelector('[data-sync-status="ok"]');
    expect(pill).not.toBeNull();
  });

  it('renders the stale pill as "stale · {N}d" with amber (non-danger) chrome when is_stale is true', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, is_stale: true, stale_days: 12 }} />);
    const stalePill = document.querySelector('[data-stale-pill]');
    expect(stalePill).not.toBeNull();
    expect(stalePill?.textContent).toMatch(/stale · 12d/);
    expect(stalePill?.className).toMatch(/amber/);
    expect(stalePill?.className).not.toMatch(/danger/);
    expect(stalePill?.className).not.toMatch(/severity-critical/);
  });

  it('renders no stale pill when is_stale is false', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, is_stale: false, stale_days: null }} />);
    expect(document.querySelector('[data-stale-pill]')).toBeNull();
  });

  it('renders the ConnectorMark lowercased and the display label', () => {
    render(<CoverageConnectorCard card={{ ...BASE_CARD, connector_type: 'CROWDSTRIKE' }} />);
    expect(document.querySelector('[aria-label="crowdstrike"]')).not.toBeNull();
    expect(screen.getByText('CrowdStrike')).toBeTruthy();
  });
});
