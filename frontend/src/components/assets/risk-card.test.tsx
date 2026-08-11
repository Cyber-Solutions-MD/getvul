import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RiskCard } from './risk-card';
import type { AssetDetail } from '@/lib/queries/use-asset-detail';

// Locked behavior (12-07-PLAN Task 1 + locked_decisions item 2):
//   - RiskRing rendered with `asset.risk_score`
//   - 4 breakdown rows IN ORDER: Critical / SLA breach / KEV / Trend unavailable
//   - 7-day delta row renders "—" + "Trend unavailable" (history table deferred)

const baseAsset: AssetDetail = {
  id: 'a1',
  hostname: 'prod-db-01',
  os_name: 'Ubuntu',
  os_version: '22.04',
  device_category: 'SERVER',
  risk_score: 85,
  seen_by_sources: ['QUALYS'],
  assigned_user: 'alice@example.com',
  tags: [],
  sla_breach: 3,
  vuln_counts: {
    total: 12, critical: 2, high: 5, medium: 3, low: 1,
    exploitable: 1, kev: 4, sla_breach: 3,
  },
  directory_user: null,
  ip_addresses: [],
  mac_addresses: [],
  serial_number: null,
  model: null,
  managed_by: null,
  last_checkin_at: null,
  building: null,
  department: null,
  business_criticality: null,
  business_criticality_source: null,
  business_criticality_group_name: null,
  data_sensitivity: null,
  data_sensitivity_source: null,
  data_sensitivity_group_name: null,
  internet_facing: null,
  internet_facing_source: null,
  internet_facing_group_name: null,
};

describe('RiskCard', () => {
  it('renders the RiskRing with the asset score (a11y label includes 85)', () => {
    render(<RiskCard asset={baseAsset} />);
    // RiskRing exposes role=img with aria-label containing the score (see RiskRing.tsx).
    expect(screen.getByRole('img', { name: /Risk score 85/ })).toBeInTheDocument();
  });

  it('renders the 4 breakdown rows in the locked order: Critical / SLA / KEV / Trend', () => {
    render(<RiskCard asset={baseAsset} />);
    expect(screen.getByTestId('risk-row-critical').textContent).toContain('2');
    expect(screen.getByTestId('risk-row-critical').textContent).toContain('Critical');
    expect(screen.getByTestId('risk-row-sla').textContent).toContain('3');
    expect(screen.getByTestId('risk-row-sla').textContent).toContain('SLA breach');
    expect(screen.getByTestId('risk-row-kev').textContent).toContain('4');
    expect(screen.getByTestId('risk-row-kev').textContent).toContain('KEV');
    const delta = screen.getByTestId('risk-row-delta');
    expect(delta.textContent).toContain('—');
    expect(delta.textContent).toContain('Trend unavailable');
  });

  it('handles missing vuln_counts gracefully (defaults to 0)', () => {
    // Pitfall: backend may return null counts on edge-case assets.
    const stripped = {
      ...baseAsset,
      vuln_counts: undefined as unknown as AssetDetail['vuln_counts'],
      sla_breach: 0,
    };
    render(<RiskCard asset={stripped} />);
    expect(screen.getByTestId('risk-row-critical').textContent).toContain('0');
    expect(screen.getByTestId('risk-row-kev').textContent).toContain('0');
    expect(screen.getByTestId('risk-row-sla').textContent).toContain('0');
  });

  it('renders with null score — RiskRing shows "Risk unavailable"', () => {
    render(<RiskCard asset={{ ...baseAsset, risk_score: null }} />);
    expect(screen.getByText('Risk unavailable')).toBeInTheDocument();
  });

  it('exposes an aria-label on the card section', () => {
    render(<RiskCard asset={baseAsset} />);
    // Right-rail card needs a region label for screen-reader nav.
    expect(screen.getByRole('region', { name: /Risk score/i })).toBeInTheDocument();
  });
});
