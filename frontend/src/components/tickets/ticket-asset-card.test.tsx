/**
 * TicketAssetCard tests — UX-05-04 (rail Asset card + cross-link)
 * TDD RED: Tests written before implementation.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TicketAssetCard } from './ticket-asset-card';

describe('TicketAssetCard', () => {
  it('Test 1: renders asset hostname and a link to /assets/{assetId}', () => {
    render(
      <TicketAssetCard
        assetId="asset-uuid-123"
        hostname="prod-db-01.internal"
        osName="Ubuntu 22.04"
        riskScore={72}
      />,
    );
    // hostname is visible
    expect(screen.getByText('prod-db-01.internal')).toBeInTheDocument();
    // Link points to /assets/{assetId}
    const link = screen.getByRole('link', { name: /view asset/i });
    expect(link).toHaveAttribute('href', '/dashboard/assets/asset-uuid-123');
  });

  it('Test 2: when assetId is null renders "Multiple hosts" and no single link', () => {
    render(
      <TicketAssetCard
        assetId={null}
        hostname={null}
        osName={null}
        riskScore={null}
      />,
    );
    expect(screen.getByText(/multiple hosts/i)).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
