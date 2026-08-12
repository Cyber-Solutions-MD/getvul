import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AssetsChipBar } from './assets-chip-bar';

// Phase 35 — mutable mockParams (mirrors vulnerabilities/chip-bar.test.tsx)
// so the OR/AND toggle tests can assert disabled/enabled state + the
// ?source_mode=and URL write.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  usePathname: () => '/assets',
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    getAll: (k: string) => mockParams.getAll(k),
    toString: () => mockParams.toString(),
  }),
}));

describe('AssetsChipBar', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
  });

  it('renders all 5 axes labels', () => {
    render(<AssetsChipBar facets={{ scanner: { QUALYS: 4 }, enrichment_source: { JAMF: 1 } }} />);
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText('Risk band')).toBeInTheDocument();
    expect(screen.getByText('Scanner')).toBeInTheDocument();
    expect(screen.getByText('Enrichment')).toBeInTheDocument();
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

  it('renders scanner chips derived from facets (D-F-03)', () => {
    const { container } = render(<AssetsChipBar facets={{ scanner: { QUALYS: 4 } }} />);
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
    // RAPID7 not in facets → not rendered
    expect(container.textContent).not.toContain('RAPID7');
  });

  // Phase 35 SRC-06 — the stale single `source` axis is partitioned into a
  // scanner axis and an independent enrichment_source facet.
  it('never renders the stale TENABLE/AWS_INSPECTOR/MOCK fakes on the scanner axis', () => {
    const { container } = render(
      <AssetsChipBar
        facets={{ scanner: { TENABLE: 5, AWS_INSPECTOR: 3, MOCK: 1, QUALYS: 10 } }}
      />,
    );
    expect(container.textContent).not.toContain('TENABLE');
    expect(container.textContent).not.toContain('AWS_INSPECTOR');
    expect(container.textContent).not.toContain('MOCK');
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
  });

  it('renders the real NESSUS/DEFENDER scanners when present in facets', () => {
    render(<AssetsChipBar facets={{ scanner: { NESSUS: 4, DEFENDER: 2 } }} />);
    expect(screen.getByText(/NESSUS/)).toBeInTheDocument();
    expect(screen.getByText(/DEFENDER/)).toBeInTheDocument();
  });

  it('renders enrichment_source chips independently of the scanner facet', () => {
    const { container } = render(
      <AssetsChipBar facets={{ enrichment_source: { JAMF: 3 }, scanner: { QUALYS: 1 } }} />,
    );
    expect(screen.getByText(/JAMF/)).toBeInTheDocument();
    // HUMAANS/INTUNE not in facets → not rendered
    expect(container.textContent).not.toContain('HUMAANS');
    expect(container.textContent).not.toContain('INTUNE');
  });

  it('renders OS family chips with proper casing', () => {
    render(<AssetsChipBar />);
    expect(screen.getByText('Linux')).toBeInTheDocument();
    expect(screen.getByText('Windows')).toBeInTheDocument();
    expect(screen.getByText('macOS')).toBeInTheDocument();
  });

  it('exposes data-axis selector per group', () => {
    // Scanner/enrichment axes are derivedFromCounts — need facets to render at all.
    const { container } = render(
      <AssetsChipBar facets={{ scanner: { QUALYS: 1 }, enrichment_source: { JAMF: 1 } }} />,
    );
    expect(container.querySelector('[data-axis="category"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="risk_band"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="scanner"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="enrichment_source"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="os_family"]')).toBeTruthy();
  });

  // Phase 35 SRC-02/03/04 — OR/AND source_mode toggle on the scanner axis.
  describe('OR/AND source_mode toggle', () => {
    it('is disabled when fewer than 2 scanners are selected', () => {
      mockParams = new URLSearchParams('scanner=QUALYS');
      render(<AssetsChipBar facets={{ scanner: { QUALYS: 1 } }} />);
      const toggle = screen.getByRole('button', { name: /any selected/i });
      expect(toggle).toBeDisabled();
    });

    it('is enabled once 2+ scanners are selected and flips ?source_mode=and on click', () => {
      mockParams = new URLSearchParams('scanner=QUALYS&scanner=RAPID7');
      render(<AssetsChipBar facets={{ scanner: { QUALYS: 1, RAPID7: 1 } }} />);
      const toggle = screen.getByRole('button', { name: /any selected/i });
      expect(toggle).not.toBeDisabled();
      act(() => {
        fireEvent.click(toggle);
      });
      expect(mockReplace).toHaveBeenCalledTimes(1);
      const [target] = mockReplace.mock.calls[0];
      expect(target).toContain('source_mode=and');
    });

    it('copy avoids AND/OR jargon — shows "Any selected" / "All selected"', () => {
      mockParams = new URLSearchParams('scanner=QUALYS&scanner=RAPID7');
      render(<AssetsChipBar facets={{ scanner: { QUALYS: 1, RAPID7: 1 } }} />);
      expect(screen.getByRole('button', { name: /any selected/i })).toBeInTheDocument();
      expect(screen.queryByText(/\bAND\b|\bOR\b/)).toBeNull();
    });
  });
});
