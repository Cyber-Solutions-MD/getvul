// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';

// Mock next/navigation — extends canonical use-url-state.test.ts shape with
// getAll for multi-value chip params.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard/vulnerabilities',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    getAll: (k: string) => mockParams.getAll(k),
    toString: () => mockParams.toString(),
  }),
}));

// Mock saved-filters query — read-only in Phase 11 per D-F-04.
vi.mock('@/lib/queries/use-saved-filters', () => ({
  useSavedFilters: vi.fn(),
}));
import { useSavedFilters } from '@/lib/queries/use-saved-filters';

// Wave 2 (Plan 11-05) will create this file. Import is the RED signal.
import { ChipBar } from './chip-bar';

const useSavedFiltersMock = vi.mocked(useSavedFilters);

const baseFacets = {
  severity: { CRITICAL: 12, HIGH: 47, MEDIUM: 80, LOW: 3 },
  source: { QUALYS: 287, TENABLE: 192 },
  status: { OPEN: 322, SNOOZED: 14 },
};

describe('<ChipBar> (UX-03-01 + D-F-01/02/03/05 — chip-bar filter row)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
    useSavedFiltersMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [],
    } as unknown as ReturnType<typeof useSavedFilters>);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders search input, severity chips, source chips, Clear all', () => {
    render(<ChipBar facets={baseFacets} />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
    // Severity chips
    expect(screen.getByText(/Critical/)).toBeInTheDocument();
    expect(screen.getByText(/High/)).toBeInTheDocument();
    // Source chips from facets
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
    expect(screen.getByText(/TENABLE/)).toBeInTheDocument();
    // Clear all link
    expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
  });

  it('chip click is synchronous — clicking Critical immediately calls the URL setter (no debounce)', () => {
    render(<ChipBar facets={baseFacets} />);
    const critical = screen.getByRole('button', { name: /critical/i });
    act(() => {
      fireEvent.click(critical);
    });
    // No timers advanced — must already have fired
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).toContain('severity=critical');
  });

  it('search input debounces 250ms — typing log4j flushes once after the idle window', () => {
    render(<ChipBar facets={baseFacets} />);
    const search = screen.getByRole('searchbox') as HTMLInputElement;

    // Type without waiting → no URL update yet
    fireEvent.change(search, { target: { value: 'log' } });
    fireEvent.change(search, { target: { value: 'log4' } });
    fireEvent.change(search, { target: { value: 'log4j' } });
    act(() => {
      vi.advanceTimersByTime(240);
    });
    expect(mockReplace).not.toHaveBeenCalled();

    // After the 250ms idle window flushes once
    act(() => {
      vi.advanceTimersByTime(20);
    });
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).toContain('search=log4j');
  });

  it('chip counts surface from facets — Critical · 12 rendered', () => {
    render(<ChipBar facets={baseFacets} />);
    // Count "12" appears next to Critical chip
    expect(screen.getByText(/Critical/).textContent).toContain('12');
  });

  it('source chips are rendered from facets.source (not hardcoded)', () => {
    render(<ChipBar facets={{ ...baseFacets, source: { QUALYS: 287 } }} />);
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
    expect(screen.queryByText(/TENABLE/)).toBeNull();
  });

  it('Clear all wipes both chips AND search (planner default — UX-03-01 sibling)', () => {
    mockParams = new URLSearchParams(
      'severity=critical&severity=high&source=QUALYS&search=log4j'
    );
    render(<ChipBar facets={baseFacets} />);
    const clearAll = screen.getByRole('button', { name: /clear all/i });
    act(() => {
      fireEvent.click(clearAll);
    });
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).not.toContain('severity=');
    expect(target).not.toContain('source=');
    expect(target).not.toContain('search=');
  });

  it("saved-filter pill renders ONLY when savedFilters.length > 0 (D-F-04 read-only)", () => {
    // No saved filters — pill hidden
    const { rerender } = render(<ChipBar facets={baseFacets} />);
    expect(screen.queryByText(/Today's triage/)).toBeNull();

    // Inject one saved filter — pill visible
    useSavedFiltersMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: [
        {
          id: 'sf-1',
          name: "Today's triage",
          query: 'severity=critical&severity=high',
        },
      ],
    } as unknown as ReturnType<typeof useSavedFilters>);
    rerender(<ChipBar facets={baseFacets} />);
    expect(screen.getByText(/Today's triage/)).toBeInTheDocument();
  });
});
