/**
 * Tests for SourcePill component (Plan 14-04 Task 1 RED).
 * Behavior:
 *   Test 2: SourcePill renders idp_source 'google'→blue, 'okta'→indigo,
 *           'humaans'→cyan, 'local'→gray with the source label.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SourcePill } from './source-pill';

describe('SourcePill', () => {
  it('renders the source label', () => {
    render(<SourcePill source="google" />);
    expect(screen.getByText('google')).toBeTruthy();
  });

  it('sets data-source-pill attribute', () => {
    const { container } = render(<SourcePill source="okta" />);
    const pill = container.querySelector('[data-source-pill="okta"]');
    expect(pill).toBeTruthy();
  });

  it('applies info token classes for google', () => {
    const { container } = render(<SourcePill source="google" />);
    const pill = container.querySelector('[data-source-pill="google"]');
    expect(pill?.className).toContain('text-info');
  });

  it('applies violet token classes for okta', () => {
    const { container } = render(<SourcePill source="okta" />);
    const pill = container.querySelector('[data-source-pill="okta"]');
    expect(pill?.className).toContain('text-violet');
  });

  it('applies info token classes for azure (same as google)', () => {
    const { container } = render(<SourcePill source="azure" />);
    const pill = container.querySelector('[data-source-pill="azure"]');
    expect(pill?.className).toContain('text-info');
  });

  it('applies info token classes for humaans (cyan analog via --color-info)', () => {
    const { container } = render(<SourcePill source="humaans" />);
    const pill = container.querySelector('[data-source-pill="humaans"]');
    expect(pill?.className).toContain('text-info');
  });

  it('applies faint token classes for local', () => {
    const { container } = render(<SourcePill source="local" />);
    const pill = container.querySelector('[data-source-pill="local"]');
    expect(pill?.className).toContain('text-text-faint');
  });

  it('uses mono font class', () => {
    const { container } = render(<SourcePill source="google" />);
    const pill = container.querySelector('[data-source-pill="google"]');
    expect(pill?.className).toContain('font-mono');
  });

  it('does not use raw freehand hex or indigo-[0-9] utility classes', () => {
    const { container } = render(<SourcePill source="okta" />);
    const pill = container.querySelector('[data-source-pill="okta"]');
    // Must not contain raw Tailwind palette like indigo-500 or blue-400
    expect(pill?.className).not.toMatch(/indigo-\d/);
    expect(pill?.className).not.toMatch(/blue-\d/);
    expect(pill?.className).not.toMatch(/cyan-\d/);
    expect(pill?.className).not.toMatch(/gray-\d/);
  });
});
