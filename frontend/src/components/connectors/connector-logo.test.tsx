/**
 * connector-logo.test.tsx — vendor logo tiles for the connectors marketplace.
 *
 * Resolution order: local brand image → inline Microsoft mark → brand monogram.
 *
 * Test 1: a monogram vendor renders its letter + an accessible name label.
 * Test 2: a Microsoft-family vendor renders the inline four-square SVG mark.
 * Test 3: an image vendor renders <img> pointing at its local brand SVG.
 * Test 4: image lookup accepts the UPPER backend type too.
 * Test 5: an unknown type falls back to the name's first letter (no crash).
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

  it('Test 2: Microsoft-family vendor renders the inline SVG mark, not a monogram', () => {
    render(<ConnectorLogo type="DEFENDER" name="Microsoft Defender for Endpoint" />);
    const tile = screen.getByRole('img', { name: 'Microsoft Defender for Endpoint' });
    expect(tile.querySelector('svg')).not.toBeNull();
    expect(tile.querySelector('img')).toBeNull();
    expect(tile.textContent).toBe('');
  });

  it('Test 3: image vendor renders <img> pointing at its local brand SVG', () => {
    render(<ConnectorLogo type="GITHUB" name="GitHub" />);
    const tile = screen.getByRole('img', { name: 'GitHub' });
    const img = tile.querySelector('img');
    expect(img).not.toBeNull();
    expect(img).toHaveAttribute('src', '/connector-logos/github.svg');
    // decorative inner image — the tile owns the accessible name
    expect(img).toHaveAttribute('alt', '');
  });

  it('Test 4: image lookup accepts the lowercased provider too', () => {
    render(<ConnectorLogo type="asana" name="Asana" />);
    const img = screen.getByRole('img', { name: 'Asana' }).querySelector('img');
    expect(img).toHaveAttribute('src', '/connector-logos/asana.svg');
  });

  it('Test 5: unknown type falls back to the name initial', () => {
    render(<ConnectorLogo type="TOTALLY_UNKNOWN" name="Zed Scanner" />);
    const tile = screen.getByRole('img', { name: 'Zed Scanner' });
    expect(tile.textContent).toBe('Z');
  });
});
