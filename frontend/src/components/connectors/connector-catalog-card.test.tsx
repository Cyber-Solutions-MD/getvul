/**
 * connector-catalog-card.test.tsx — marketplace card for an available connector.
 *
 * Test 1: renders name + short description.
 * Test 2: Configure carries data-add-connector={type} and calls onConfigure(type).
 * Test 3: "Setup guide" link renders with the setup_url href when present.
 * Test 4: setup_url absent → no setup-guide link.
 * Test 5: missing description → fallback copy (never a blank card).
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConnectorCatalogCard } from './connector-catalog-card';
import { CATALOG_COPY } from './microcopy';

describe('ConnectorCatalogCard', () => {
  it('Test 1: renders name and description', () => {
    render(
      <ConnectorCatalogCard
        type="CROWDSTRIKE"
        name="CrowdStrike Falcon"
        description="Vulnerability management via Spotlight + CSPM"
        onConfigure={vi.fn()}
      />,
    );
    expect(screen.getByText('CrowdStrike Falcon')).toBeInTheDocument();
    expect(
      screen.getByText('Vulnerability management via Spotlight + CSPM'),
    ).toBeInTheDocument();
  });

  it('Test 2: Configure carries data-add-connector and calls onConfigure with the type', () => {
    const onConfigure = vi.fn();
    render(
      <ConnectorCatalogCard type="NESSUS" name="Nessus" description="On-prem scanner" onConfigure={onConfigure} />,
    );
    const btn = document.querySelector('[data-add-connector="NESSUS"]');
    expect(btn).not.toBeNull();
    fireEvent.click(btn as Element);
    expect(onConfigure).toHaveBeenCalledWith('NESSUS');
  });

  it('Test 3: setup guide link renders with the setup_url href', () => {
    render(
      <ConnectorCatalogCard
        type="WIZ"
        name="Wiz"
        description="Cloud security"
        setupUrl="https://docs.wiz.io/setup"
        onConfigure={vi.fn()}
      />,
    );
    const link = screen.getByRole('link', { name: new RegExp(CATALOG_COPY.setupGuideLabel, 'i') });
    expect(link).toHaveAttribute('href', 'https://docs.wiz.io/setup');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('Test 4: no setup_url → no setup guide link', () => {
    render(
      <ConnectorCatalogCard type="QUALYS" name="Qualys" description="VMDR" onConfigure={vi.fn()} />,
    );
    expect(screen.queryByRole('link', { name: new RegExp(CATALOG_COPY.setupGuideLabel, 'i') })).toBeNull();
  });

  it('Test 5: missing description falls back to placeholder copy', () => {
    render(<ConnectorCatalogCard type="RAPID7" name="Rapid7" onConfigure={vi.fn()} />);
    expect(screen.getByText(CATALOG_COPY.noDescription)).toBeInTheDocument();
  });
});
