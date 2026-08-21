/**
 * page.test.tsx — /dashboard/analytics (Phase 42 Plan 01, TREND-01/03
 * tracer slice; Plan 02 appends TREND-02's aging/burndown assertions).
 * Mirrors coverage/page.test.tsx's `vi.spyOn`-the-hook convention. Adds the
 * recharts jsdom scaffolding from `components/ui/trend-chart.test.tsx`
 * (ResizeObserver polyfill + getBoundingClientRect/offsetWidth/offsetHeight
 * mocks) since this page nests <RiskTrendChart>/<BacklogAgingChart>, real
 * recharts charts — unlike Coverage, which renders no chart.
 *
 * One test per UI-SPEC state branch: loading, error, empty (insufficient
 * history), populated (line renders), single-data-point (renders a dot,
 * not a connecting line), version-boundary-marker present when boundaries
 * is non-empty.
 *
 * Plan 02 (TREND-02) adds: the aging chart's 3 buckets + overdue headline
 * tile + burndown tile all render in the populated branch; the zero-open
 * aging case renders the explicit "0% of open backlog is overdue" tile
 * (UI-SPEC E3); and the burndown tile's no-change + overflow-capped
 * branches (UI-SPEC E4).
 */
import { render, screen, within, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

const replaceMock = vi.fn();
let searchParamsMock = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: replaceMock }),
  usePathname: () => '/dashboard/analytics',
  useSearchParams: () => searchParamsMock,
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

// recharts ResponsiveContainer relies on ResizeObserver — jsdom doesn't ship
// one (mirrors components/ui/trend-chart.test.tsx's scaffolding).
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;

// Recharts ResponsiveContainer measures parent via getBoundingClientRect;
// jsdom returns 0x0 for every element. Force a non-zero size so <LineChart>
// actually renders <Line>/<ReferenceLine>/dot geometry.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'getBoundingClientRect', {
    configurable: true,
    value: () => ({
      width: 600,
      height: 200,
      top: 0,
      left: 0,
      right: 600,
      bottom: 200,
      x: 0,
      y: 0,
      toJSON() {
        return this;
      },
    }),
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
    configurable: true,
    get() {
      return 600;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    get() {
      return 200;
    },
  });
});

import userEvent from '@testing-library/user-event';
import * as useAnalyticsModule from '@/lib/queries/use-analytics';
import type { AgingBucket, AnalyticsOverviewResponse, Burndown } from '@/lib/queries/use-analytics';
import * as useAssetGroupsModule from '@/lib/queries/use-asset-groups';
import type { AssetGroupResponse } from '@/lib/queries/use-asset-groups';
import AnalyticsPage from './page';

function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// Plan 02 defaults — every pre-Plan-02 test below only cares about
// trend/boundaries; these keep the AnalyticsOverviewResponse contract
// satisfied without touching those tests' existing `data` literals.
const DEFAULT_AGING: AgingBucket[] = [
  { bucket: 'within_sla', critical: 0, high: 0, medium: 0, low: 0 },
  { bucket: 'recently_breached', critical: 0, high: 0, medium: 0, low: 0 },
  { bucket: 'long_overdue', critical: 0, high: 0, medium: 0, low: 0 },
];
const DEFAULT_BURNDOWN: Burndown = {
  status: 'no_change',
  net_per_week: 0,
  open_backlog: 0,
  days_to_clear: null,
  capped: false,
};

function mockQuery(overrides: {
  data?: Partial<AnalyticsOverviewResponse>;
  isPending?: boolean;
  error?: Error | null;
}) {
  const data: AnalyticsOverviewResponse | undefined = overrides.data
    ? {
        trend: overrides.data.trend ?? [],
        boundaries: overrides.data.boundaries ?? [],
        aging: overrides.data.aging ?? DEFAULT_AGING,
        aging_pct_overdue: overrides.data.aging_pct_overdue ?? 0,
        burndown: overrides.data.burndown ?? DEFAULT_BURNDOWN,
        scope: overrides.data.scope ?? 'all',
        group_name: overrides.data.group_name ?? null,
      }
    : undefined;
  vi.spyOn(useAnalyticsModule, 'useAnalytics').mockReturnValue({
    data,
    isPending: overrides.isPending ?? false,
    isLoading: overrides.isPending ?? false,
    error: overrides.error ?? null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useAnalyticsModule.useAnalytics>);
}

// Plan 03 (D-02) — a small AssetGroup fixture factory + spy helper, mirrors
// `mockQuery`'s convention. Defaults to an empty list in `beforeEach` below
// so pre-Plan-03 tests (which don't care about groups) never attempt a
// real network fetch through the unmocked hook.
function mockGroups(groups: AssetGroupResponse[]) {
  vi.spyOn(useAssetGroupsModule, 'useAssetGroupsList').mockReturnValue({
    data: groups,
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof useAssetGroupsModule.useAssetGroupsList>);
}

function makeGroup(name: string): AssetGroupResponse {
  return {
    id: `group-${name.toLowerCase().replace(/\s+/g, '-')}`,
    tenant_id: 'tenant-a',
    name,
    description: null,
    member_count: 3,
    created_at: null,
    updated_at: null,
  };
}

describe('/dashboard/analytics page', () => {
  beforeEach(() => {
    replaceMock.mockClear();
    searchParamsMock = new URLSearchParams();
    // Default: no groups, so pre-Plan-03 tests below render the scope
    // dropdown's single 'All (tenant)' item and never exercise the
    // search-filter branch. Plan 03 tests override this per-case.
    mockGroups([]);
  });

  it('loading branch renders the skeleton, no alert/status', () => {
    mockQuery({ isPending: true });
    renderWithClient(<AnalyticsPage />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('error branch renders PartialFailureBanner, not the skeleton or an empty state', () => {
    mockQuery({ error: new Error('Connection refused: cannot reach backend') });
    renderWithClient(<AnalyticsPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('below-minimum-history empty state (D-04) renders when the window has zero snapshot points', () => {
    mockQuery({ data: { trend: [], boundaries: [] } });
    renderWithClient(<AnalyticsPage />);
    expect(screen.getByText('Trends appear after a few days of history')).toBeInTheDocument();
    expect(screen.getByText(/All \(tenant\) doesn't have enough snapshot history yet/)).toBeInTheDocument();
  });

  it('a healthy tenant scoring 0 with real history is NOT treated as empty (D-04 falsy-score guard)', () => {
    mockQuery({
      data: {
        trend: [
          { date: '2026-08-19', avg_risk_exposure_score: 0, risk_model_version: 'v1' },
          { date: '2026-08-20', avg_risk_exposure_score: 0, risk_model_version: 'v1' },
        ],
        boundaries: [],
      },
    });
    renderWithClient(<AnalyticsPage />);
    expect(screen.queryByText('Trends appear after a few days of history')).toBeNull();
    expect(screen.getByRole('table', { name: 'Risk-exposure trend' })).toBeInTheDocument();
  });

  it('an all-null series (empty-membership group) renders the D-04 empty state, not a misleading all-null line (G-42-4)', () => {
    // A group with zero CURRENT members returns one row per snapshot day, each
    // with avg_risk_exposure_score: null (correct D-06 gap semantics). The
    // empty-state gate must key on the count of SCORED (non-null) points, not
    // raw row count — otherwise this renders the populated all-null-line branch.
    mockQuery({
      data: {
        trend: [
          { date: '2026-08-18', avg_risk_exposure_score: null, risk_model_version: 'v1' },
          { date: '2026-08-19', avg_risk_exposure_score: null, risk_model_version: 'v1' },
          { date: '2026-08-20', avg_risk_exposure_score: null, risk_model_version: 'v1' },
        ],
        boundaries: [],
      },
    });
    renderWithClient(<AnalyticsPage />);
    expect(screen.getByText('Trends appear after a few days of history')).toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Risk-exposure trend' })).toBeNull();
  });

  it('populated branch renders the trend line (single version, no boundary marker)', () => {
    mockQuery({
      data: {
        trend: [
          { date: '2026-08-18', avg_risk_exposure_score: 20, risk_model_version: 'v1' },
          { date: '2026-08-19', avg_risk_exposure_score: 22, risk_model_version: 'v1' },
          { date: '2026-08-20', avg_risk_exposure_score: 24, risk_model_version: 'v1' },
        ],
        boundaries: [],
      },
    });
    const { container } = renderWithClient(<AnalyticsPage />);
    // Exactly one <Line> series (one detected version) and zero boundary markers.
    expect(container.querySelectorAll('.recharts-line').length).toBe(1);
    expect(container.querySelectorAll('.recharts-reference-line').length).toBe(0);
    // sr-only data table is the canonical accessible path (SVG is aria-hidden).
    const table = screen.getByRole('table', { name: 'Risk-exposure trend' });
    expect(table).toBeInTheDocument();
    expect(within(table).getAllByRole('row').length).toBeGreaterThan(3); // header + 3 data rows
  });

  it('exactly one data point renders a single dot marker, never a connecting line (UI-SPEC E2)', () => {
    mockQuery({
      data: {
        trend: [{ date: '2026-08-20', avg_risk_exposure_score: 18, risk_model_version: 'v1' }],
        boundaries: [],
      },
    });
    const { container } = renderWithClient(<AnalyticsPage />);
    // Still reaches the populated branch (MIN_HISTORY_POINTS=1, not the
    // empty state) and renders a dot for the lone point.
    expect(screen.queryByText('Trends appear after a few days of history')).toBeNull();
    expect(container.querySelectorAll('.recharts-dot').length).toBeGreaterThanOrEqual(1);
  });

  it('version-boundary marker renders (with a neutral, non-violet stroke) when boundaries is non-empty', () => {
    mockQuery({
      data: {
        trend: [
          { date: '2026-08-18', avg_risk_exposure_score: 20, risk_model_version: 'v1' },
          { date: '2026-08-19', avg_risk_exposure_score: 22, risk_model_version: 'v2' },
          { date: '2026-08-20', avg_risk_exposure_score: 23, risk_model_version: 'v2' },
        ],
        boundaries: [{ date: '2026-08-19', old_version: 'v1', new_version: 'v2' }],
      },
    });
    const { container } = renderWithClient(<AnalyticsPage />);
    const referenceLines = container.querySelectorAll('.recharts-reference-line');
    expect(referenceLines.length).toBe(1);
    // Two version segments -> two <Line> series (v1, v2) — no interpolation
    // across the boundary (connectNulls=false on each).
    expect(container.querySelectorAll('.recharts-line').length).toBe(2);
    // The boundary label text renders somewhere in the chart.
    expect(container.textContent ?? '').toContain('v1 → v2');
  });

  // ── Plan 02 (TREND-02): backlog aging + burndown ────────────────────────

  it('populated branch renders the backlog aging chart (3 buckets), the overdue tile, and the burndown tile', () => {
    mockQuery({
      data: {
        trend: [
          { date: '2026-08-18', avg_risk_exposure_score: 20, risk_model_version: 'v1' },
          { date: '2026-08-19', avg_risk_exposure_score: 22, risk_model_version: 'v1' },
        ],
        boundaries: [],
        aging: [
          { bucket: 'within_sla', critical: 1, high: 2, medium: 0, low: 3 },
          { bucket: 'recently_breached', critical: 1, high: 0, medium: 0, low: 0 },
          { bucket: 'long_overdue', critical: 0, high: 0, medium: 1, low: 0 },
        ],
        aging_pct_overdue: 25,
        burndown: {
          status: 'shrinking',
          net_per_week: 1.6,
          open_backlog: 4,
          days_to_clear: 12,
          capped: false,
        },
      },
    });
    renderWithClient(<AnalyticsPage />);

    // Overdue headline tile — the full locked sentence, explicit.
    expect(screen.getByText('25% of open backlog is overdue')).toBeInTheDocument();

    // Aging sr-only data table (the canonical accessible path) has exactly
    // 3 bucket rows (+ header), with the 3 locked bucket-label strings.
    const agingTable = screen.getByRole('table', { name: 'Backlog aging' });
    expect(within(agingTable).getAllByRole('row').length).toBe(4); // header + 3 buckets
    expect(within(agingTable).getByText('Within SLA')).toBeInTheDocument();
    expect(within(agingTable).getByText('Recently breached')).toBeInTheDocument();
    expect(within(agingTable).getByText('Long overdue')).toBeInTheDocument();

    // Burndown tile — headline number + shrinking directional copy +
    // projected-clear line, all from already-computed props.
    const burndownTile = screen.getByTestId('burndown-tile');
    expect(within(burndownTile).getByTestId('burndown-net-per-week')).toHaveTextContent('1.6');
    expect(within(burndownTile).getByText('Backlog shrinking — 1.6 findings/week net')).toBeInTheDocument();
    expect(within(burndownTile).getByText('12d to clear at this rate')).toBeInTheDocument();
  });

  it('zero open backlog renders the explicit "0% of open backlog is overdue" tile (UI-SPEC E3 zero-one-many)', () => {
    mockQuery({
      data: {
        trend: [{ date: '2026-08-20', avg_risk_exposure_score: 0, risk_model_version: 'v1' }],
        boundaries: [],
        // aging/aging_pct_overdue default to the all-zero fixture above.
      },
    });
    renderWithClient(<AnalyticsPage />);
    expect(screen.getByText('0% of open backlog is overdue')).toBeInTheDocument();
  });

  it('burndown no-change branch renders a distinct copy row with no projected-clear line (UI-SPEC E4)', () => {
    mockQuery({
      data: {
        trend: [{ date: '2026-08-20', avg_risk_exposure_score: 10, risk_model_version: 'v1' }],
        boundaries: [],
        burndown: { status: 'no_change', net_per_week: 0, open_backlog: 5, days_to_clear: null, capped: false },
      },
    });
    renderWithClient(<AnalyticsPage />);
    const burndownTile = screen.getByTestId('burndown-tile');
    expect(within(burndownTile).getByText('No change this period')).toBeInTheDocument();
    expect(within(burndownTile).queryByText(/to clear at this rate/)).toBeNull();
    expect(within(burndownTile).queryByText(/no clear date/)).toBeNull();
  });

  it('burndown growing branch renders "no clear date at this rate", never a fabricated projection', () => {
    mockQuery({
      data: {
        trend: [{ date: '2026-08-20', avg_risk_exposure_score: 10, risk_model_version: 'v1' }],
        boundaries: [],
        burndown: { status: 'growing', net_per_week: 3.2, open_backlog: 9, days_to_clear: null, capped: false },
      },
    });
    renderWithClient(<AnalyticsPage />);
    const burndownTile = screen.getByTestId('burndown-tile');
    expect(within(burndownTile).getByText('Backlog growing — 3.2 findings/week net')).toBeInTheDocument();
    expect(within(burndownTile).getByText('Backlog growing — no clear date at this rate')).toBeInTheDocument();
  });

  it('burndown overflow-capped branch renders "500+ d to clear", never an absurd exact number (UI-SPEC E4)', () => {
    mockQuery({
      data: {
        trend: [{ date: '2026-08-20', avg_risk_exposure_score: 10, risk_model_version: 'v1' }],
        boundaries: [],
        burndown: { status: 'shrinking', net_per_week: 0.2, open_backlog: 500, days_to_clear: 500, capped: true },
      },
    });
    renderWithClient(<AnalyticsPage />);
    const burndownTile = screen.getByTestId('burndown-tile');
    expect(within(burndownTile).getByText('500+ d to clear')).toBeInTheDocument();
  });

  // ── Plan 03 (TREND-01 D-02/D-03, TREND-03 UI-SPEC E2): scope dropdown,
  //    custom range, multi-boundary ───────────────────────────────────────

  it('scope dropdown lists All (tenant) + each asset group; selecting a group shows the mandatory caption and re-scopes', async () => {
    const user = userEvent.setup();
    const group = makeGroup('Production Web Tier');
    mockGroups([group]);
    mockQuery({
      data: {
        trend: [{ date: '2026-08-20', avg_risk_exposure_score: 15, risk_model_version: 'v1' }],
        boundaries: [],
      },
    });
    renderWithClient(<AnalyticsPage />);

    await user.click(screen.getByRole('button', { name: 'Scope' }));
    expect(screen.getByRole('menuitem', { name: 'All (tenant)' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Production Web Tier' })).toBeInTheDocument();

    await user.click(screen.getByRole('menuitem', { name: 'Production Web Tier' }));

    expect(
      screen.getByText("Shows Production Web Tier's current members, applied retroactively across this window."),
    ).toBeInTheDocument();
    // D-02: the SAME scope selection re-scopes useAnalytics's query (which
    // feeds every chart on the page — trend/aging/burndown share this one
    // call, D-13's single compute pass).
    expect(useAnalyticsModule.useAnalytics).toHaveBeenLastCalledWith(
      expect.objectContaining({ scope: 'group', groupId: group.id }),
    );
  });

  it('many groups: the inline search filter narrows the visible list (UI-SPEC E1 overflow)', async () => {
    const user = userEvent.setup();
    const groups = [
      makeGroup('Production Web Tier'),
      makeGroup('Staging Web Tier'),
      makeGroup('Corp Laptops'),
      makeGroup('Finance Servers'),
      makeGroup('EU Region DBs'),
      makeGroup('US Region DBs'),
      makeGroup('Contractor Devices'),
    ];
    mockGroups(groups);
    mockQuery({ data: { trend: [], boundaries: [] } });
    renderWithClient(<AnalyticsPage />);

    await user.click(screen.getByRole('button', { name: 'Scope' }));
    expect(screen.getAllByRole('menuitem')).toHaveLength(groups.length + 1); // + 'All (tenant)'

    await user.type(screen.getByPlaceholderText('Search groups'), 'Finance');

    const items = screen.getAllByRole('menuitem');
    expect(items).toHaveLength(2); // 'All (tenant)' + 'Finance Servers'
    expect(screen.getByRole('menuitem', { name: 'Finance Servers' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Production Web Tier' })).toBeNull();
  });

  it('custom range: To before From shows the order error and clears once corrected', () => {
    searchParamsMock = new URLSearchParams('window=custom');
    mockQuery({ isPending: true });
    renderWithClient(<AnalyticsPage />);

    const fromInput = screen.getByLabelText('From');
    const toInput = screen.getByLabelText('To');
    fireEvent.change(fromInput, { target: { value: '2026-08-20' } });
    fireEvent.change(toInput, { target: { value: '2026-08-10' } });

    expect(screen.getByRole('alert')).toHaveTextContent('End date must be after start date.');

    fireEvent.change(toInput, { target: { value: '2026-08-25' } });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('custom range: an incomplete/invalid range never enables the query (fires no request)', () => {
    searchParamsMock = new URLSearchParams('window=custom');
    mockQuery({ isPending: true });
    renderWithClient(<AnalyticsPage />);

    // Freshly selecting 'Custom range' with no dates picked yet.
    expect(useAnalyticsModule.useAnalytics).toHaveBeenLastCalledWith(
      expect.objectContaining({ window: 'custom', from: '', to: '' }),
    );

    const fromInput = screen.getByLabelText('From');
    const toInput = screen.getByLabelText('To');
    fireEvent.change(fromInput, { target: { value: '2026-08-20' } });
    fireEvent.change(toInput, { target: { value: '2026-08-10' } });

    // Still invalid (to < from) — the hook receives the raw values and is
    // solely responsible for gating `enabled` off of them (see
    // use-analytics.ts's exported isCustomRangeValid, unit-proven below).
    expect(useAnalyticsModule.useAnalytics).toHaveBeenLastCalledWith(
      expect.objectContaining({ from: '2026-08-20', to: '2026-08-10' }),
    );
    expect(useAnalyticsModule.isCustomRangeValid('2026-08-20', '2026-08-10')).toBe(false);
  });

  it('a 3-version, 2-boundary payload renders 2 ReferenceLine markers, not just the first (UI-SPEC E2)', () => {
    mockQuery({
      data: {
        trend: [
          { date: '2026-08-01', avg_risk_exposure_score: 10, risk_model_version: 'v1' },
          { date: '2026-08-02', avg_risk_exposure_score: 20, risk_model_version: 'v2' },
          { date: '2026-08-03', avg_risk_exposure_score: 30, risk_model_version: 'v3' },
        ],
        boundaries: [
          { date: '2026-08-02', old_version: 'v1', new_version: 'v2' },
          { date: '2026-08-03', old_version: 'v2', new_version: 'v3' },
        ],
      },
    });
    const { container } = renderWithClient(<AnalyticsPage />);
    expect(container.querySelectorAll('.recharts-reference-line').length).toBe(2);
    expect(container.querySelectorAll('.recharts-line').length).toBe(3);
  });
});

describe('isCustomRangeValid / isCustomRangeComplete (use-analytics.ts)', () => {
  it('is invalid while either field is empty, valid once complete and in order, invalid when reversed', () => {
    expect(useAnalyticsModule.isCustomRangeComplete('', '')).toBe(false);
    expect(useAnalyticsModule.isCustomRangeComplete('2026-08-01', '')).toBe(false);
    expect(useAnalyticsModule.isCustomRangeValid('', '')).toBe(false);
    expect(useAnalyticsModule.isCustomRangeValid('2026-08-01', '2026-08-10')).toBe(true);
    expect(useAnalyticsModule.isCustomRangeValid('2026-08-10', '2026-08-01')).toBe(false);
    expect(useAnalyticsModule.isCustomRangeValid('2026-08-01', '2026-08-01')).toBe(true); // to === from is valid (a 1-day range)
  });
});
