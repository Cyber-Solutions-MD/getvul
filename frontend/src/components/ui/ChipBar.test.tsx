// @vitest-environment jsdom
//
// Generic <ChipBar> — Plan 12-04. Descriptor-driven sibling of Phase 11's
// vuln-specific chip-bar. The vuln-specific chip-bar.tsx is a thin wrapper
// over this primitive; its locked Phase-11 test contract is the authoritative
// behavior, so this suite asserts the GENERIC API shape on top of that.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';

// Mock next/navigation in the same shape used by Phase 11's chip-bar.test.tsx
// — useSearchParams returns an object with `get`, `getAll`, `toString` (not a
// real URLSearchParams). The generic ChipBar must tolerate this shape because
// the existing vuln-specific tests will exercise it via the wrapper.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/test',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    getAll: (k: string) => mockParams.getAll(k),
    toString: () => mockParams.toString(),
  }),
}));

import { ChipBar, type ChipAxis } from './ChipBar';

const SEVERITY_AXIS: ChipAxis = {
  key: 'severity',
  label: 'Severity',
  allowList: ['critical', 'high', 'medium', 'low', 'info'] as const,
  counts: { critical: 12, high: 5 },
  chips: [
    { value: 'critical', label: 'Critical', glyph: '■', glyphClassName: 'text-[var(--color-severity-critical-on-soft)]' },
    { value: 'high', label: 'High', glyph: '▲', glyphClassName: 'text-[var(--color-severity-high-on-soft)]' },
  ],
};

const CATEGORY_AXIS: ChipAxis = {
  key: 'category',
  label: 'Category',
  allowList: ['WORKSTATION', 'SERVER', 'NETWORK', 'MOBILE', 'OTHER'] as const,
  chips: [
    { value: 'WORKSTATION', label: 'Workstation' },
    { value: 'SERVER', label: 'Server' },
  ],
};

const SOURCE_AXIS_DERIVED: ChipAxis = {
  key: 'source',
  label: 'Source',
  allowList: ['QUALYS', 'TENABLE', 'RAPID7'] as const,
  counts: { QUALYS: 8, TENABLE: 3 }, // RAPID7 absent — not rendered
  derivedFromCounts: true,
};

describe('<ChipBar> (UX-04-01 — generic descriptor-driven primitive)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders one chip group per axis with axis.label as visible chrome', () => {
    render(<ChipBar axes={[SEVERITY_AXIS, CATEGORY_AXIS]} />);
    expect(screen.getByText('Severity')).toBeInTheDocument();
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText(/Critical/)).toBeInTheDocument();
    expect(screen.getByText(/Workstation/)).toBeInTheDocument();
  });

  it('renders chip label + count merged as a single text node (Phase 11 contract)', () => {
    render(<ChipBar axes={[SEVERITY_AXIS]} />);
    // Phase 11 contract — the deepest matching element's textContent contains both label and count.
    const critical = screen.getByText(/Critical/);
    expect(critical.textContent).toContain('12');
  });

  it('hides count when axis.counts is missing', () => {
    render(<ChipBar axes={[CATEGORY_AXIS]} />);
    // 'Workstation' chip text should NOT contain a digit when no counts provided.
    const workstation = screen.getByText(/Workstation/);
    expect(workstation.textContent).toBe('Workstation');
  });

  it('renders chips derived from counts keys when derivedFromCounts=true (D-F-03)', () => {
    render(<ChipBar axes={[SOURCE_AXIS_DERIVED]} />);
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
    expect(screen.getByText(/TENABLE/)).toBeInTheDocument();
    // RAPID7 has no count in facets — not rendered even though it's in allowList.
    expect(screen.queryByText(/RAPID7/)).toBeNull();
  });

  it('chip click is synchronous — calls router.replace immediately with axis key flipped', () => {
    render(<ChipBar axes={[SEVERITY_AXIS]} />);
    const critical = screen.getByRole('button', { name: /critical/i });
    act(() => {
      fireEvent.click(critical);
    });
    // useUrlStateList toggle calls router.replace synchronously — no timer advance needed.
    expect(mockReplace).toHaveBeenCalled();
    const [target] = mockReplace.mock.calls[0];
    expect(target).toContain('severity=critical');
  });

  it('search input is rendered by default and debounces 250ms before flushing to URL', () => {
    render(<ChipBar axes={[SEVERITY_AXIS]} />);
    const search = screen.getByRole('searchbox') as HTMLInputElement;
    fireEvent.change(search, { target: { value: 'log4j' } });
    act(() => { vi.advanceTimersByTime(240); });
    expect(mockReplace).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(20); });
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).toContain('search=log4j');
  });

  it('search input can be hidden via showSearch=false', () => {
    render(<ChipBar axes={[SEVERITY_AXIS]} showSearch={false} />);
    expect(screen.queryByRole('searchbox')).toBeNull();
  });

  it('clear-all calls router.replace deleting every axis key + search', () => {
    mockParams = new URLSearchParams('severity=critical&category=SERVER&search=foo');
    render(<ChipBar axes={[SEVERITY_AXIS, CATEGORY_AXIS]} />);
    const clearAll = screen.getByRole('button', { name: /clear all/i });
    act(() => { fireEvent.click(clearAll); });
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).not.toContain('severity=');
    expect(target).not.toContain('category=');
    expect(target).not.toContain('search=');
  });

  it('renders saved-filter pill only when savedFilter prop is supplied', () => {
    const { rerender } = render(<ChipBar axes={[SEVERITY_AXIS]} />);
    expect(screen.queryByText(/Today's triage/)).toBeNull();
    rerender(
      <ChipBar
        axes={[SEVERITY_AXIS]}
        savedFilter={{ label: "Today's triage", query: 'severity=critical' }}
      />,
    );
    expect(screen.getByText(/Today's triage/)).toBeInTheDocument();
  });

  it('exposes data-axis attribute per chip group for selector targeting', () => {
    const { container } = render(<ChipBar axes={[SEVERITY_AXIS, CATEGORY_AXIS]} />);
    expect(container.querySelector('[data-axis="severity"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="category"]')).toBeTruthy();
  });
});
