// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

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
vi.mock('@/lib/mutations/use-create-ticket', () => ({
  useCreateTicketMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

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
});
