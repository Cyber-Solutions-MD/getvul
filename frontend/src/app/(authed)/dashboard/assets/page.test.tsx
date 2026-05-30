import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AssetsPage from './page';

const push = vi.fn();
const replace = vi.fn();
const refetch = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => '/assets',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

vi.mock('@/lib/queries/use-assets', async () => {
  const actual = await vi.importActual<typeof import('@/lib/queries/use-assets')>(
    '@/lib/queries/use-assets',
  );
  return {
    ...actual,
    useAssets: vi.fn(() => ({
      data: {
        items: [
          {
            id: 'a1',
            hostname: 'prod-db-01',
            os_name: 'Ubuntu 22.04',
            device_category: 'SERVER',
            risk_score: 85,
            seen_by_sources: ['QUALYS'],
            assigned_user: 'alice@example.com',
            tags: ['pci'],
            total_vulns: 4,
            critical: 1,
            high: 2,
            exploitable: 0,
            kev: 0,
            sla_breach_count: 0,
          },
        ],
        total: 1,
        page: 1,
        page_size: 25,
        pages: 1,
      },
      isPending: false,
      isLoading: false,
      error: null,
      refetch,
    })),
  };
});

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('/assets page', () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    refetch.mockReset();
  });

  it('renders H1 and total count eyebrow', () => {
    renderWithClient(<AssetsPage />);
    expect(
      screen.getByRole('heading', { name: 'Assets' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Inventory · 1 assets/)).toBeInTheDocument();
  });

  it('renders the AssetsChipBar with static axes', () => {
    // Source axis is derivedFromCounts (D-F-03) — until the backend emits
    // asset facets it renders nothing. The page surface still wires it via
    // <AssetsChipBar facets=> so when facets arrive it lights up automatically.
    // Direct-from-allow-list axes always render — assert via the chip-bar's
    // data-axis-label data attribute (added by ChipGroup) so we don't collide
    // with table column header text (e.g. 'OS' appears in both surfaces).
    const { container } = renderWithClient(<AssetsPage />);
    expect(screen.getByText('Category')).toBeInTheDocument();
    expect(screen.getByText('Risk band')).toBeInTheDocument();
    expect(
      container.querySelector('[data-axis-label="os_family"]'),
    ).toBeTruthy();
    expect(container.querySelector('[data-axis="category"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="risk_band"]')).toBeTruthy();
    expect(container.querySelector('[data-axis="os_family"]')).toBeTruthy();
  });

  it('renders the AssetsTable with the loaded row', () => {
    renderWithClient(<AssetsPage />);
    expect(screen.getByText('prod-db-01')).toBeInTheDocument();
  });

  it('clicking a row pushes to /assets/{id}', () => {
    renderWithClient(<AssetsPage />);
    fireEvent.click(screen.getByText('prod-db-01'));
    expect(push).toHaveBeenCalledWith('/assets/a1');
  });
});
