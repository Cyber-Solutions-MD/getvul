/**
 * page.test.tsx — tests for the /dashboard/exceptions list page (Phase 39
 * Plan 06). Mirrors campaigns/page.test.tsx's co-located page.test.tsx
 * convention (not literally named in 39-06-PLAN.md's `files_modified`, but
 * required to prove the plan's own must_haves — WR-13 state-branch order,
 * exact empty copy for BOTH the never-granted and filtered-to-zero cases,
 * no navigation on row interaction). See 39-06-SUMMARY.md.
 *
 * Test 1: renders exception rows via ExceptionsTable with a live query.
 * Test 2: state branches — error / loading / never-granted-empty are
 *         mutually exclusive (WR-13).
 * Test 3: never-granted empty state renders exact UI-SPEC copy + CTA.
 * Test 4: filtered-to-zero empty state renders distinct copy + a working
 *         "Clear all filters" action.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

const pushMock = vi.fn();
const replaceMock = vi.fn();
let searchParamsMock = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => '/dashboard/exceptions',
  useSearchParams: () => searchParamsMock,
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

import * as useExceptionsModule from '@/lib/queries/use-exceptions';
import type { ExceptionResponse } from '@/lib/queries/use-exceptions';
import ExceptionsPage from './page';

const mockException: ExceptionResponse = {
  id: 'e1',
  type: 'ACCEPTED_RISK',
  scope_type: 'FINDING',
  cve_id: 'CVE-2024-1234',
  vulnerability_id: 'v1',
  asset_id: 'a1',
  asset_group_id: null,
  justification: 'Compensating control via WAF rule.',
  approver_user_id: 'u1',
  approver_display_name: 'Ana Sokolova',
  granted_by_user_id: 'u2',
  expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  revoked_at: null,
  revoked_by_user_id: null,
  resurfaced_audited_at: null,
  created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
};

function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('/dashboard/exceptions page', () => {
  beforeEach(() => {
    pushMock.mockClear();
    replaceMock.mockClear();
    searchParamsMock = new URLSearchParams();
    vi.spyOn(useExceptionsModule, 'useExceptions').mockReturnValue({
      data: [mockException],
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useExceptionsModule.useExceptions>);
  });

  it('Test 1: renders exception rows via ExceptionsTable', () => {
    renderWithClient(<ExceptionsPage />);
    expect(screen.getByText(mockException.cve_id)).toBeInTheDocument();
  });

  it('Test 2: error / loading / never-granted-empty branches are mutually exclusive (WR-13)', () => {
    // Error state
    vi.spyOn(useExceptionsModule, 'useExceptions').mockReturnValueOnce({
      data: undefined,
      isPending: false,
      isLoading: false,
      error: new Error('Connection refused: cannot reach backend'),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useExceptionsModule.useExceptions>);
    const { unmount } = renderWithClient(<ExceptionsPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('status')).toBeNull();
    unmount();

    // Loading state
    vi.spyOn(useExceptionsModule, 'useExceptions').mockReturnValueOnce({
      data: undefined,
      isPending: true,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useExceptionsModule.useExceptions>);
    const { unmount: unmount2 } = renderWithClient(<ExceptionsPage />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
    unmount2();

    // Never-granted empty state
    vi.spyOn(useExceptionsModule, 'useExceptions').mockReturnValueOnce({
      data: [],
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useExceptionsModule.useExceptions>);
    renderWithClient(<ExceptionsPage />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('Test 3: never-granted empty state renders exact UI-SPEC copy + CTA', () => {
    vi.spyOn(useExceptionsModule, 'useExceptions').mockReturnValueOnce({
      data: [],
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useExceptionsModule.useExceptions>);
    const { container } = renderWithClient(<ExceptionsPage />);
    expect(screen.getByText('No exceptions granted yet')).toBeInTheDocument();
    const cta = screen.getByRole('link', { name: 'View vulnerabilities' });
    expect(cta).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/vulnerabilities"]')).not.toBeNull();
  });

  it('Test 4: filtered-to-zero empty state renders distinct copy + Clear all filters', () => {
    // One exception exists (FALSE_POSITIVE), but the active URL filter asks
    // for ACCEPTED_RISK only -> filtered.length === 0 while totalUnfiltered > 0.
    searchParamsMock = new URLSearchParams('type=ACCEPTED_RISK');
    vi.spyOn(useExceptionsModule, 'useExceptions').mockReturnValueOnce({
      data: [{ ...mockException, type: 'FALSE_POSITIVE' }],
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useExceptionsModule.useExceptions>);
    renderWithClient(<ExceptionsPage />);

    expect(screen.getByText('Nothing matches this filter')).toBeInTheDocument();
    expect(screen.queryByText('No exceptions granted yet')).toBeNull();

    const clearBtn = screen.getByRole('button', { name: 'Clear all filters' });
    fireEvent.click(clearBtn);
    expect(replaceMock).toHaveBeenCalledWith('/dashboard/exceptions', { scroll: false });
  });
});
