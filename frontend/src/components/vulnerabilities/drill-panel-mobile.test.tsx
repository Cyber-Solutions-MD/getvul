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
      // Phase 33 Plan 04 (RISK-05): shadow/preview risk-exposure fields —
      // shared DrillContent renders the same section on mobile.
      risk_exposure_score: 82,
      risk_exposure_breakdown: [
        { key: 'severity_cvss', label: 'Severity / CVSS', raw_value: '10.0', points: 35, max_points: 35 },
        { key: 'kev_floor', label: 'CISA KEV floor', raw_value: 'raised 78 -> 90', points: 12, max_points: 0 },
      ],
      risk_model_version: 'v1',
    },
  }),
}));
vi.mock('@/lib/mutations/use-snooze', () => ({
  useSnoozeMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

// Phase 36 (SLA-03, D-07): the new escalation-history section (shared
// DrillContent) uses a real useQuery-backed hook -- mock it so this
// pre-existing suite doesn't need a QueryClientProvider wrapper, mirroring
// the use-explain-cache/use-ai-status rationale above.
const mockUseVulnEscalations = vi.fn();
vi.mock('@/lib/queries/use-vuln-escalations', () => ({
  useVulnEscalations: (...args: unknown[]) => mockUseVulnEscalations(...args),
}));

// Phase 24-05: the new AI Explanation section (nested inside the shared
// DrillContent) uses real useQuery-backed hooks -- mock them so this
// pre-existing suite doesn't need a QueryClientProvider wrapper. See
// drill-panel.test.tsx for the identical rationale.
// (24-10) use-ai-status replaces use-connectors-admin as the section's key-
// configured signal (D-23 gap closure) -- mocked the same way.
// Phase 27 (AID-01, Plan 03): converted to forwarding vi.fn()s (mirroring
// drill-panel.test.tsx's own Plan 03 upgrade) so the new gap-fill tests can
// drive an Analyst+/key-configured/missing-section scenario per-test, while
// every pre-existing test keeps the SAME default return values as before.
const mockUseExplainCache = vi.fn();
vi.mock('@/lib/queries/use-explain-cache', () => ({
  useExplainCache: (...args: unknown[]) => mockUseExplainCache(...args),
}));
const mockUseAiStatus = vi.fn();
vi.mock('@/lib/queries/use-ai-status', () => ({
  useAiStatus: (...args: unknown[]) => mockUseAiStatus(...args),
}));
// Phase 27 (AID-01, Plan 03): no mock existed for @/lib/auth before this
// plan -- every pre-existing test ran against the REAL useAuth() context
// default (`user: null` -> role 'VIEWER'). Mocked here with the SAME
// default so every pre-existing assertion is unaffected.
const mockUseAuth = vi.fn();
vi.mock('@/lib/auth', () => ({ useAuth: () => mockUseAuth() }));
// Phase 27 (AID-01, Plan 03): the gap-fill row calls useExplainStream
// DIRECTLY (bypassing AiExplanationSection) -- forwarding call args so
// gap-fill tests can drive a specific state. Defaults to 'idle' for every
// resourceType, matching the REAL hook's initial state, so the 3
// pre-existing AiExplanationSection mounts are unaffected.
const mockStart = vi.fn();
const mockUseExplainStream = vi.fn();
vi.mock('@/lib/ai/use-explain-stream', () => ({
  useExplainStream: (...args: unknown[]) => mockUseExplainStream(...args),
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
    // Phase 27 (AID-01, Plan 03): SAME defaults the hardcoded mocks always
    // returned before this plan -- every pre-existing test is unaffected.
    mockUseExplainCache.mockReset();
    mockUseExplainCache.mockReturnValue({ data: { cached: false }, isPending: false, isError: false });
    mockUseAiStatus.mockReset();
    mockUseAiStatus.mockReturnValue({ data: { configured: false }, isPending: false, isError: false });
    mockUseAuth.mockReset();
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });
    mockStart.mockReset();
    mockUseExplainStream.mockReset();
    mockUseExplainStream.mockReturnValue({ state: { phase: 'idle' }, start: mockStart });
    mockUseVulnEscalations.mockReset();
    mockUseVulnEscalations.mockReturnValue({ isPending: false, isError: false, data: [] });
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

  // ───────────────────────────────────────────────────────────────────────
  // Phase 25 Plan 07 Task 3 (AIR-02, Pitfall 5): the mobile renderConfirm
  // path is a SEPARATE code path from desktop's ConfirmModal -- proving the
  // desktop textarea threads correctly (drill-panel.test.tsx) says nothing
  // about mobile. These tests mirror the desktop mutation-boundary proof
  // for this divergent path.
  // ───────────────────────────────────────────────────────────────────────

  // Phase 27 (AID-01, Plan 02): DrillContent's compose-on-open effect
  // (title/description state + the resourceId-keyed guard) lives INSIDE
  // the shared DrillContent component that drill-panel-mobile.tsx renders
  // directly (27-RESEARCH.md Pattern 4 -- "no separate state needed there
  // ... exactly as description already does today") -- so the field
  // auto-composes here too, even though the mobile UI's OWN Title Input +
  // updated caption/placeholder are Plan 03's explicit scope ("mobile
  // Title Input mirror"), not this plan's. The caption/placeholder text
  // below is intentionally still Phase 25's (drill-panel-mobile.tsx's own
  // JSX is untouched by this plan); only the "starting empty" assumption
  // is now false and is updated to match reality.
  it('renders the description Textarea between the gap-fill row and the Cancel/Confirm row, auto-composed on first open (Asset context always present, D-04)', () => {
    setMatchMedia(true);
    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

    const dialogs = screen.getAllByRole('dialog');
    const nestedConfirm = dialogs[dialogs.length - 1];

    // Phase 27 (AID-01, Plan 03): the OLD field-scoped caption is
    // superseded by the shared "AI-drafted" caption (mirrors the desktop
    // ConfirmModal's own Plan 02 change) -- sits once, above the Title
    // field, covering both Title and Description.
    expect(within(nestedConfirm).getByText('AI-drafted — review before creating.')).toBeInTheDocument();
    const textarea = within(nestedConfirm).getByPlaceholderText(
      'No AI draft available yet — add a description or leave blank.',
    ) as HTMLTextAreaElement;
    expect(textarea.value).toContain('Asset context:');

    // Document-order: picker < textarea < Cancel/Confirm row.
    const picker = within(nestedConfirm).getByRole('radiogroup', { name: 'Ticketing provider' });
    const cancelBtn = within(nestedConfirm).getByRole('button', { name: 'Cancel' });
    const positions = [picker, textarea, cancelBtn].map((el) =>
      Array.from(nestedConfirm.querySelectorAll('*')).indexOf(el),
    );
    expect(positions[0]).toBeLessThan(positions[1]);
    expect(positions[1]).toBeLessThan(positions[2]);
  });

  it('typing into the mobile textarea and confirming threads the description into createTicket.mutateAsync body', () => {
    setMatchMedia(true);
    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

    const dialogs = screen.getAllByRole('dialog');
    const nestedConfirm = dialogs[dialogs.length - 1];
    const textarea = within(nestedConfirm).getByPlaceholderText(
      'No AI draft available yet — add a description or leave blank.',
    );
    fireEvent.change(textarea, { target: { value: 'Patch xz to 5.4.x per vendor advisory.' } });

    const confirmBtn = within(nestedConfirm).getByRole('button', { name: /create ticket/i });
    fireEvent.click(confirmBtn);

    expect(mockMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Patch xz to 5.4.x per vendor advisory.' }),
    );
  });

  it('clearing the auto-composed description before confirming threads description: undefined (never an empty string) into the mutation body (mobile mirrors desktop, never a silent skip)', () => {
    setMatchMedia(true);
    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

    const dialogs = screen.getAllByRole('dialog');
    const nestedConfirm = dialogs[dialogs.length - 1];
    // Phase 27 (AID-01, Plan 02): the shared DrillContent effect auto-
    // composes on open -- "leaving it blank" no longer happens by default.
    // The analyst can still clear it explicitly (SC2); this proves that
    // path still threads `undefined` (never an empty string).
    const textarea = within(nestedConfirm).getByPlaceholderText(
      'No AI draft available yet — add a description or leave blank.',
    );
    fireEvent.change(textarea, { target: { value: '' } });

    const confirmBtn = within(nestedConfirm).getByRole('button', { name: /create ticket/i });
    fireEvent.click(confirmBtn);

    expect(mockMutateAsync).toHaveBeenCalledWith(expect.objectContaining({ description: undefined }));
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 27 Plan 03 (AID-01): mirrors drill-panel.test.tsx's Title Input
  // tests for the divergent mobile Drawer.NestedRoot renderConfirm path
  // (Pitfall 5 -- never imports ConfirmModal, builds its own markup).
  // ───────────────────────────────────────────────────────────────────────

  describe('mobile Title Input (AID-01, Plan 03)', () => {
    it('renders the Title Input with the shared LOCKED caption, deterministically composed on first open', () => {
      setMatchMedia(true);
      render(<DrillPanelMobile cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialogs = screen.getAllByRole('dialog');
      const nestedConfirm = dialogs[dialogs.length - 1];

      expect(within(nestedConfirm).getByText('AI-drafted — review before creating.')).toBeInTheDocument();
      const titleInput = within(nestedConfirm).getByRole('textbox', { name: 'Title' }) as HTMLInputElement;
      expect(titleInput).toBeInTheDocument();
      // Deterministic D-01 format -- this file's mocked detail has no
      // affected_hosts/asset_hostname, so hostsLine falls back to '—'.
      expect(titleInput.value).toBe('[Critical] CVE-2024-3094 on —');
    });

    it('typing into the mobile Title Input and confirming threads the title into createTicket.mutateAsync body', () => {
      setMatchMedia(true);
      render(<DrillPanelMobile cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialogs = screen.getAllByRole('dialog');
      const nestedConfirm = dialogs[dialogs.length - 1];
      fireEvent.change(within(nestedConfirm).getByRole('textbox', { name: 'Title' }), {
        target: { value: 'Patch the xz backdoor now' },
      });

      const confirmBtn = within(nestedConfirm).getByRole('button', { name: /create ticket/i });
      fireEvent.click(confirmBtn);

      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Patch the xz backdoor now' }),
      );
    });

    it('clearing the auto-composed Title before confirming threads title: undefined (never an empty string) into the mutation body', () => {
      setMatchMedia(true);
      render(<DrillPanelMobile cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialogs = screen.getAllByRole('dialog');
      const nestedConfirm = dialogs[dialogs.length - 1];
      fireEvent.change(within(nestedConfirm).getByRole('textbox', { name: 'Title' }), {
        target: { value: '' },
      });

      const confirmBtn = within(nestedConfirm).getByRole('button', { name: /create ticket/i });
      fireEvent.click(confirmBtn);

      expect(mockMutateAsync).toHaveBeenCalledWith(expect.objectContaining({ title: undefined }));
    });
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 27 Plan 03 (AID-01): the mobile mirror of the "Draft with AI"
  // gap-fill row -- identical descriptor-driven rendering to desktop,
  // never a separate logic path (D-05 divergence lesson).
  // ───────────────────────────────────────────────────────────────────────

  describe('mobile gap-fill row (AID-01, Plan 03)', () => {
    it('gap-fill interactions (clicking a trigger) never call createTicket.mutateAsync -- SC3 holds on the mobile surface independently, not only by desktop inference', () => {
      setMatchMedia(true);
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      // mockUseExplainCache stays at the default {cached:false} -- both
      // Description and Remediation are "missing," so both buttons render.

      render(<DrillPanelMobile cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialogs = screen.getAllByRole('dialog');
      const nestedConfirm = dialogs[dialogs.length - 1];

      const draftDescriptionBtn = within(nestedConfirm).getByRole('button', {
        name: 'Draft description with AI',
      });
      const draftRemediationBtn = within(nestedConfirm).getByRole('button', {
        name: 'Draft remediation with AI',
      });
      fireEvent.click(draftDescriptionBtn);
      fireEvent.click(draftRemediationBtn);

      expect(mockStart).toHaveBeenCalledTimes(2);
      expect(mockMutateAsync).not.toHaveBeenCalled();
    });

    it('renders no gap-fill buttons for Viewer role / no key configured (default fixture state), even though the descriptor is threaded', () => {
      setMatchMedia(true);
      render(<DrillPanelMobile cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialogs = screen.getAllByRole('dialog');
      const nestedConfirm = dialogs[dialogs.length - 1];
      expect(
        within(nestedConfirm).queryByRole('button', { name: 'Draft description with AI' }),
      ).toBeNull();
      expect(
        within(nestedConfirm).queryByRole('button', { name: 'Draft remediation with AI' }),
      ).toBeNull();
    });
  });

  // Phase 33 Plan 04 (RISK-05): the shared DrillContent Risk Exposure
  // section renders via the mobile wrapper too — at minimum the heading +
  // overall score appear (full breakdown-row coverage lives in
  // drill-panel.test.tsx).
  it('renders the "Risk exposure" section (heading + score) via the mobile wrapper (RISK-05)', () => {
    setMatchMedia(true);
    render(<DrillPanelMobile cveId="CVE-2024-3094" />);
    expect(screen.getByText('Risk exposure')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.getByText('★ KEV floor applied')).toBeInTheDocument();
  });
});
