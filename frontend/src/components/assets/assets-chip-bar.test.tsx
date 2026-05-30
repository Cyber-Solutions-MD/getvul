import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AssetsChipBar } from './assets-chip-bar';

vi.mock('next/navigation', () => ({
  usePathname: () => '/assets',
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe('AssetsChipBar', () => {
  it('renders all 4 axes labels', () => {
    render(<AssetsChipBar facets={{ source: { QUALYS: 4, TENABLE: 2 } }} />);
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText('Risk band')).toBeInTheDocument();
    expect(screen.getByText('Source')).toBeInTheDocument();
    expect(screen.getByText('OS')).toBeInTheDocument();
  });

  it('renders category chips with sentence-case labels', () => {
    render(<AssetsChipBar />);
    expect(screen.getByText('Workstation')).toBeInTheDocument();
    expect(screen.getByText('Server')).toBeInTheDocument();
  });

  it('renders risk-band chips with score ranges in copy', () => {
    render(<AssetsChipBar />);
    expect(screen.getByText(/Critical · 80–100/)).toBeInTheDocument();
    expect(screen.getByText(/Low · 0–19/)).toBeInTheDocument();
  });

  it('renders source chips derived from facets (D-F-03)', () => {
    const { container } = render(<AssetsChipBar facets={{ source: { QUALYS: 4 } }} />);
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
    // RAPID7 not in facets → not rendered
    expect(container.textContent).not.toContain('RAPID7');
  });

  it('renders OS family chips with proper casing', () => {
    render(<AssetsChipBar />);
    expect(screen.getByText('Linux')).toBeInTheDocument();
    expect(screen.getByText('Windows')).toBeInTheDocument();
    expect(screen.getByText('macOS')).toBeInTheDocument();
  });

  it('exposes data-axis selector per group', () => {
    // Source axis is derivedFromCounts — needs facets to render at all.
    const { container } = render(<AssetsChipBar facets={{ source: { QUALYS: 1 } }} />);
    expect(container.querySelector('[data-axis="category"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="risk_band"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="source"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="os_family"]')).toBeTruthy();
  });
});
