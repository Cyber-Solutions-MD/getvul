/**
 * connector-logo.test.tsx — vendor logo tiles for the connectors marketplace.
 *
 * Test 1: a monogram vendor renders its letter + an accessible name label.
 * Test 2: a mark vendor (Microsoft family) renders an inline SVG, not a letter.
 * Test 3: accepts either the backend UPPER type or a lowercased provider.
 * Test 4: an unknown type falls back to the name's first letter (no crash).
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ConnectorLogo } from './connector-logo';

describe('ConnectorLogo', () => {
  it('Test 1: monogram vendor renders its letter and an accessible label', () => {
    render(<ConnectorLogo type="CROWDSTRIKE" name="CrowdStrike Falcon" />);
    const tile = screen.getByRole('img', { name: 'CrowdStrike Falcon' });
    expect(tile).toBeInTheDocument();
    expect(tile.textContent).toBe('C');
  });

  it('Test 2: mark vendor renders an inline SVG, not a monogram letter', () => {
    render(<ConnectorLogo type="DEFENDER" name="Microsoft Defender for Endpoint" />);
    const tile = screen.getByRole('img', { name: 'Microsoft Defender for Endpoint' });
    expect(tile.querySelector('svg')).not.toBeNull();
    expect(tile.textContent).toBe(''); // no letter when a mark is present
  });

  it('Test 3: accepts a lowercased provider string too', () => {
    render(<ConnectorLogo type="asana" name="Asana" />);
    const tile = screen.getByRole('img', { name: 'Asana' });
    expect(tile.querySelector('svg')).not.toBeNull();
  });

  it('Test 4: unknown type falls back to the name initial', () => {
    render(<ConnectorLogo type="TOTALLY_UNKNOWN" name="Zed Scanner" />);
    const tile = screen.getByRole('img', { name: 'Zed Scanner' });
    expect(tile.textContent).toBe('Z');
  });
});
