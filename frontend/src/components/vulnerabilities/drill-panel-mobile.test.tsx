// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';

// Mock next/navigation
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

vi.mock('@/lib/queries/use-vulnerability-detail', () => ({
  useVulnerabilityDetail: () => ({
    isPending: false,
    isError: false,
    data: {
      id: '1',
      cve_id: 'CVE-2024-3094',
      title: 'xz backdoor',
      severity: 'critical',
      cisa_kev: true,
    },
  }),
}));
vi.mock('@/lib/mutations/use-snooze', () => ({
  useSnoozeMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

// The mobile nested confirm now renders TicketProviderPicker, which calls
// drill-content.tsx's createTicket.mutateAsync (not `.mutate`) — the mock
// must expose mutateAsync so fireTicket's `await createTicket.mutateAsync`
// resolves instead of throwing "mutateAsync is not a function".
const mockMutateAsync = vi.fn().mockResolvedValue({ tickets: [] });
vi.mock('@/lib/mutations/use-create-ticket', () => ({
  useCreateTicketMutation: () => ({ mutateAsync: mockMutateAsync, isPending: false }),
}));

// D-14/REL-04: the mobile nested confirm renders <TicketProviderPicker>,
// which is backed by useTicketingProviders. Mock it per-test so Case A/B
// can control the configured-provider list and loading state.
vi.mock('@/lib/queries/use-ticketing-providers', () => ({
  useTicketingProviders: vi.fn(),
}));
import { useTicketingProviders } from '@/lib/queries/use-ticketing-providers';
const useProvidersMock = vi.mocked(useTicketingProviders);

// Wave 2 (Plan 11-05) will create this file. Import is the RED signal.
import { DrillPanelMobile } from './drill-panel-mobile';

function setMatchMedia(matches: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((q: string) => ({
    matches,
    media: q,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }) as unknown as MediaQueryList);
}

describe('<DrillPanelMobile> (UX-03-06 + D-P-03 — vaul bottom-sheet)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams('cve=CVE-2024-3094&open=drill');
    mockMutateAsync.mockClear();
    // Default: a single configured provider, so pre-existing tests that
    // open the nested confirm (but don't assert on provider selection)
    // keep passing. Case A/B below override this per-test.
    useProvidersMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [{ provider: 'JIRA', enabled: true }],
    } as unknown as ReturnType<typeof useTicketingProviders>);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('at viewport <900px the component renders a vaul Drawer (role="dialog")', () => {
    setMatchMedia(true); // matches max-width: 899px
    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('at viewport ≥900px the component renders nothing (desktop branch covers it)', () => {
    setMatchMedia(false);
    const { container } = render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    // No dialog and no panel content
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it('open state driven by URL — removing open=drill closes the drawer', () => {
    setMatchMedia(true);
    mockParams = new URLSearchParams('cve=CVE-2024-3094&open=drill');
    const { rerender } = render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Remove open=drill from URL — drawer closes on rerender
    mockParams = new URLSearchParams('cve=CVE-2024-3094');
    rerender(<DrillPanelMobile cveId="CVE-2024-3094" />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('swipe-to-close + Esc both close (vaul native — fires close handler → URL setter)', () => {
    setMatchMedia(true);
    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(mockReplace).toHaveBeenCalled();
    const [target] = mockReplace.mock.calls[0];
    expect(target).not.toContain('open=drill');
  });

  it('nested ConfirmModal — Create ticket inside the drawer opens a Drawer.NestedRoot', () => {
    setMatchMedia(true);
    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    const createBtn = screen.getByRole('button', { name: /create ticket/i });
    fireEvent.click(createBtn);
    // Nested vaul drawer surfaces a second dialog (confirm modal)
    const dialogs = screen.getAllByRole('dialog');
    expect(dialogs.length).toBeGreaterThanOrEqual(2);
  });

  it('at <900px the same DrillContent shared with desktop renders inside vaul without crashing', () => {
    setMatchMedia(true);
    expect(() =>
      render(<DrillPanelMobile cveId="CVE-2024-3094" />)
    ).not.toThrow();
    expect(screen.getByText(/CVE-2024-3094/)).toBeInTheDocument();
  });

  // REL-04 / CR-01 gap closure (23-11): the mobile nested confirm must
  // honor the analyst-selected/default-selected provider — never fall
  // through to the hardcoded 'ASANA' — mirroring the desktop ConfirmModal
  // branch's confirmDisabled={!ticketProvider} gate.
  it('Case A — mobile confirm fires the SELECTED provider (JIRA), never a silent ASANA fallback', async () => {
    setMatchMedia(true);
    useProvidersMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { provider: 'JIRA', enabled: true },
        { provider: 'ASANA', enabled: true },
      ],
    } as unknown as ReturnType<typeof useTicketingProviders>);

    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

    const dialogs = screen.getAllByRole('dialog');
    const nestedConfirm = dialogs[dialogs.length - 1];
    const confirmBtn = within(nestedConfirm).getByRole('button', {
      name: /create ticket/i,
    });

    // TicketProviderPicker default-selects the first configured provider
    // (JIRA) — the confirm button must be enabled once that fires.
    expect(confirmBtn).not.toBeDisabled();
    fireEvent.click(confirmBtn);

    expect(mockMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ provider: 'JIRA' }),
    );
    expect(mockMutateAsync).not.toHaveBeenCalledWith(
      expect.objectContaining({ provider: 'ASANA' }),
    );
  });

  it('Case B — mobile confirm is BLOCKED (disabled), not defaulted to ASANA, while no provider is loaded/selected', () => {
    setMatchMedia(true);
    useProvidersMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useTicketingProviders>);

    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

    const dialogs = screen.getAllByRole('dialog');
    const nestedConfirm = dialogs[dialogs.length - 1];
    const confirmBtn = within(nestedConfirm).getByRole('button', {
      name: /create ticket/i,
    });

    expect(confirmBtn).toBeDisabled();
    fireEvent.click(confirmBtn);
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });
});
