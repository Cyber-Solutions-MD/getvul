import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@/hooks/use-url-state', () => ({
  useUrlState: vi.fn(),
}));
vi.mock('@/lib/queries/use-trends', () => ({
  useTrends: vi.fn(),
}));
// Mock the dynamic-imported chart so the test asserts on the data it receives.
vi.mock('@/components/ui/trend-chart', () => ({
  TrendChart: ({ data }: { data: unknown }) => (
    <div data-testid="chart-data">{JSON.stringify(data)}</div>
  ),
}));

import { TrendSection } from './trend-section';
import { useUrlState } from '@/hooks/use-url-state';
import { useTrends } from '@/lib/queries/use-trends';

describe('<TrendSection>', () => {
  beforeEach(() => {
    (useUrlState as unknown as ReturnType<typeof vi.fn>).mockReturnValue([
      '30d',
      vi.fn(),
    ]);
    (useTrends as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: {
        severity_trends: {
          // Intentionally unsorted to exercise the date-asc reshape.
          '2026-04-02': { critical: 2, high: 1, medium: 4, low: 3 },
          '2026-04-01': { critical: 1, high: 2, medium: 3, low: 4 },
        },
      },
    });
  });

  it('reshapes severity_trends into ordered TrendDatum[] ascending by date', async () => {
    render(<TrendSection />);
    // next/dynamic renders the loading fallback synchronously, then awaits the
    // module. With the mock for `@/components/ui/trend-chart` in place, the
    // resolved component is the mock, but next/dynamic still wraps it in a
    // suspense-like dance. Find the testid after a microtask.
    const node = await screen.findByTestId('chart-data');
    const passed = JSON.parse(node.textContent ?? '[]');
    expect(passed).toEqual([
      { date: '2026-04-01', critical: 1, high: 2, medium: 3, low: 4 },
      { date: '2026-04-02', critical: 2, high: 1, medium: 4, low: 3 },
    ]);
  });

  it('section has aria-labelledby="trend-h" and h2 reads "30-day vulnerability trend"', () => {
    render(<TrendSection />);
    const section = document.querySelector('section[aria-labelledby="trend-h"]');
    expect(section).not.toBeNull();
    expect(screen.getByText('30-day vulnerability trend')).toBeInTheDocument();
  });
});
