// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SeverityRibbon } from './severity-ribbon';

describe('SeverityRibbon', () => {
  it('renders all 5 severity entries with glyph + count merged in one text node', () => {
    render(<SeverityRibbon counts={{ critical: 2, high: 3, medium: 1, low: 1, info: 0 }} />);
    expect(screen.getByTestId('ribbon-critical').textContent).toBe('■2');
    expect(screen.getByTestId('ribbon-high').textContent).toBe('▲3');
    expect(screen.getByTestId('ribbon-medium').textContent).toBe('◆1');
    expect(screen.getByTestId('ribbon-low').textContent).toBe('○1');
    expect(screen.getByTestId('ribbon-info').textContent).toBe('□0');
  });

  it('dims zero-count entries with text-text-faint', () => {
    render(<SeverityRibbon counts={{ critical: 0, high: 1, medium: 0, low: 0 }} />);
    expect(screen.getByTestId('ribbon-critical').className).toContain('text-text-faint');
    expect(screen.getByTestId('ribbon-high').className).toContain('text-severity-high');
  });

  it('exposes aria-label per entry for screen readers', () => {
    render(<SeverityRibbon counts={{ critical: 2, high: 3, medium: 0, low: 0 }} />);
    expect(screen.getByLabelText('2 Critical')).toBeInTheDocument();
    expect(screen.getByLabelText('3 High')).toBeInTheDocument();
  });

  it('defaults missing info to 0 and dims it', () => {
    render(<SeverityRibbon counts={{ critical: 1, high: 0, medium: 0, low: 0 }} />);
    expect(screen.getByTestId('ribbon-info').textContent).toBe('□0');
    expect(screen.getByTestId('ribbon-info').className).toContain('text-text-faint');
  });
});
