/**
 * tickets-chip-bar.test.tsx — Phase 35 SRC-02/03: real server-filtering
 * source axis (distinct from the display-only SourceBadgeGroup on rows).
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TicketsChipBar } from './tickets-chip-bar';

vi.mock('next/navigation', () => ({
  usePathname: () => '/dashboard/tickets',
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe('TicketsChipBar', () => {
  it('renders all 5 axes labels', () => {
    render(<TicketsChipBar />);
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Provider')).toBeInTheDocument();
    expect(screen.getByText('Severity')).toBeInTheDocument();
    expect(screen.getByText('SLA')).toBeInTheDocument();
    expect(screen.getByText('Source')).toBeInTheDocument();
  });

  it('renders all 6 real scanner values statically when no source facet is given', () => {
    render(<TicketsChipBar />);
    ['CROWDSTRIKE', 'NESSUS', 'DEFENDER', 'WIZ', 'QUALYS', 'RAPID7'].forEach((s) => {
      expect(screen.getByText(s)).toBeInTheDocument();
    });
  });

  it('renders only facet-present source chips when a source facet is supplied', () => {
    const { container } = render(<TicketsChipBar facets={{ source: { QUALYS: 4 } }} />);
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
    expect(container.textContent).not.toContain('RAPID7');
  });

  it('exposes data-axis="source" for the chip-bar filter axis', () => {
    const { container } = render(<TicketsChipBar />);
    expect(container.querySelector('[data-axis="source"]')).toBeTruthy();
  });

  it('has no AND toggle for the source axis (SRC-04 is scoped to Vulns/Assets/CSPM)', () => {
    const { container } = render(<TicketsChipBar />);
    expect(container.querySelector('[data-source-mode-toggle]')).toBeNull();
  });
});
