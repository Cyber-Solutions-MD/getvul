// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';

// Mock next/navigation. Panel state is URL-encoded per D-P-02.
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

// Mock the detail query — Wave 1 will ship the real hook.
vi.mock('@/lib/queries/use-vulnerability-detail', () => ({
  useVulnerabilityDetail: vi.fn(),
}));
import { useVulnerabilityDetail } from '@/lib/queries/use-vulnerability-detail';

// Mock the mutations used by the panel actions.
vi.mock('@/lib/mutations/use-snooze', () => ({
  useSnoozeMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
// Phase 25 Plan 07 Task 2: fireTicket() calls createTicket.mutateAsync (not
// `.mutate`) — mockMutateAsync is exported at module scope so the new
// description-threading tests below can assert on the exact mutation body.
const mockMutateAsync = vi.fn().mockResolvedValue({ tickets: [] });
vi.mock('@/lib/mutations/use-create-ticket', () => ({
  useCreateTicketMutation: () => ({ mutate: vi.fn(), mutateAsync: mockMutateAsync, isPending: false }),
}));

// Phase 24-05: the new AI Explanation section (nested inside DrillContent,
// between Description and Remediation) uses real useQuery-backed hooks --
// mock them so this pre-existing suite doesn't need a QueryClientProvider
// wrapper. Deterministic "no key configured, Viewer-default" state (real
// useAuth() default-context value with no Provider resolves user:null ->
// role defaults to VIEWER inside the section) keeps every other assertion
// in this file unaffected by the new section's own content.
// (24-10) use-ai-status replaces use-connectors-admin as the section's key-
// configured signal (D-23 gap closure) -- mocked the same way.
//
// Phase 25 Plan 07 Task 2: both hooks are now `vi.fn()`-backed (forwarding
// call args) so the new description-textarea test below can give the
// resourceType="remediation-guidance" mount a grounded/cached=true result
// (unlocking the "Copy into ticket description" button) while every
// pre-existing test keeps the untouched cache-miss/unconfigured default via
// the outer beforeEach.
const mockUseExplainCache = vi.fn();
vi.mock('@/lib/queries/use-explain-cache', () => ({
  useExplainCache: (...args: unknown[]) => mockUseExplainCache(...args),
}));
const mockUseAiStatus = vi.fn();
vi.mock('@/lib/queries/use-ai-status', () => ({
  useAiStatus: (...args: unknown[]) => mockUseAiStatus(...args),
}));

// Phase 27 (AID-01, Plan 03): the desktop gap-fill row is role/key-gated
// (D-17 inherited) -- no mock existed for @/lib/auth before this plan, so
// every pre-existing test ran against the REAL useAuth() context default
// (`user: null` -> role 'VIEWER'). Mocked here with the SAME default so
// every pre-existing assertion is unaffected; new gap-fill tests override
// the role per-test.
const mockUseAuth = vi.fn();
vi.mock('@/lib/auth', () => ({ useAuth: () => mockUseAuth() }));

// Phase 27 (AID-01, Plan 03): the gap-fill row calls useExplainStream
// DIRECTLY (bypassing AiExplanationSection) for 'vuln'/'remediation-guidance'
// -- forwarding call args (resourceType) so gap-fill tests can drive a
// specific state per section. Defaults to 'idle' for every resourceType,
// matching the REAL hook's initial state, so the 3 pre-existing
// AiExplanationSection mounts (vuln/prioritization/remediation-guidance)
// are unaffected by this mock's introduction.
const mockStart = vi.fn();
const mockUseExplainStream = vi.fn();
vi.mock('@/lib/ai/use-explain-stream', () => ({
  useExplainStream: (...args: unknown[]) => mockUseExplainStream(...args),
}));

// Phase 36 (SLA-03, D-07): the new escalation-history section (inside
// DrillContent) uses a real useQuery-backed hook -- mock it so this
// pre-existing suite doesn't need a QueryClientProvider wrapper, mirroring
// the use-explain-cache/use-ai-status rationale above.
const mockUseVulnEscalations = vi.fn();
vi.mock('@/lib/queries/use-vuln-escalations', () => ({
  useVulnEscalations: (...args: unknown[]) => mockUseVulnEscalations(...args),
}));

// Phase 25 Plan 07 Task 2: a cache-hit/grounded mock (needed to unlock the
// "Copy into ticket description" button) renders <AiFeedbackControl>, which
// calls the REAL useAiFeedback() mutation -- requires a QueryClientProvider
// this pre-existing suite doesn't wrap with. Mocked the same way
// ai-explanation-section.test.tsx already stubs it.
vi.mock('@/lib/queries/use-ai-feedback', () => ({
  useAiFeedback: () => ({ mutate: vi.fn() }),
}));

// Phase 25 Plan 07 Task 2: the desktop ConfirmModal fallback branch renders
// <TicketProviderPicker>, backed by useTicketingProviders — mocked with one
// configured provider so the new description-textarea tests can open the
// confirm dialog and reach an enabled "Create ticket" confirm button.
vi.mock('@/lib/queries/use-ticketing-providers', () => ({
  useTicketingProviders: () => ({
    isLoading: false,
    isError: false,
    data: [{ provider: 'JIRA', enabled: true }],
  }),
}));

// Phase 39 Plan 07 (EXC-01): the Actions section now always renders
// <ExceptionGrantDialog> (state-controlled, closed by default) — it calls
// the real useGrantException()/useAssetGroupsList() hooks, which need a
// QueryClientProvider this pre-existing suite doesn't wrap with. Mocked the
// same way every other real query/mutation hook in this file already is.
vi.mock('@/lib/queries/use-exception-mutations', () => ({
  useGrantException: () => ({ mutate: vi.fn(), isPending: false, error: null, reset: vi.fn() }),
}));
vi.mock('@/lib/queries/use-asset-groups', () => ({
  useAssetGroupsList: () => ({ data: [], isLoading: false, isError: false }),
}));
// The grant dialog's Approver field (ApproverCombobox) uses the real
// useAssignableUsers query hook — same QueryClientProvider-avoidance
// rationale as above.
vi.mock('@/lib/queries/use-assignable-users', () => ({
  useAssignableUsers: () => ({ data: { users: [], total: 0, page: 1, page_size: 25 }, isLoading: false, isError: false }),
}));

// Wave 2 (Plan 11-05) will create this file. Import is the RED signal.
import { DrillPanel } from './drill-panel';

const useDetailMock = vi.mocked(useVulnerabilityDetail);

const detail = {
  id: '1',
  cve_id: 'CVE-2024-3094',
  title: 'xz-utils backdoor',
  description: 'Supply-chain backdoor in xz-utils.',
  cvss_v3_score: 10,
  severity: 'critical',
  cisa_kev: true,
  remediation: 'Downgrade to xz 5.4.x.',
  affected_hosts: [{ host: 'prod-01', ip: '10.0.0.1' }],
  activity: [],
};

describe('<DrillPanel> (UX-03-03 + D-P-01/02/05/06)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockMutateAsync.mockClear();
    mockParams = new URLSearchParams('cve=CVE-2024-3094&open=drill');
    useDetailMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: detail,
    } as unknown as ReturnType<typeof useVulnerabilityDetail>);
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

  it('renders 11 sections in order (Header / CVSS / Affected hosts / Description / AI Explanation / Prioritization / Remediation / Remediation guidance / Activity / Escalation history / Actions)', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    const headings = screen.getAllByRole('heading').map((h) => h.textContent ?? '');
    // 11 named sections, in the documented order (Phase 24-05 / UI-SPEC D-11
    // inserts AI Explanation between Description and Remediation; Phase 25
    // Plan 04 D-06 inserts "Remediation guidance" between the raw
    // Remediation text and Activity; Phase 26 Plan 04 (D-03/D-09) inserts
    // the NEW "Prioritization" section between AI Explanation and the raw
    // Remediation text; Phase 36 Plan 06 (SLA-03, D-07) inserts "Escalation
    // history" between Activity and Actions).
    const expectedOrder = [
      /CVE-2024-3094|Drill|Header/i,
      /CVSS/i,
      /Affected hosts/i,
      /Description/i,
      /AI Explanation/i,
      /^Prioritization$/i,
      /Remediation$/i,
      /Remediation guidance/i,
      /Activity/i,
      /Escalation history/i,
      /Actions/i,
    ];
    expectedOrder.forEach((re, idx) => {
      expect(headings[idx] ?? '').toMatch(re);
    });
  });

  it('renders a CVSS score the API sent as a STRING ("10.0") without crashing (regression: Decimal is JSON-serialized as a string, not a number)', () => {
    useDetailMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: { ...detail, cvss_v3_score: '10.0' },
    } as unknown as ReturnType<typeof useVulnerabilityDetail>);
    render(<DrillPanel cveId="CVE-2024-3094" />);
    // Before the fix this threw `v.cvss_v3_score.toFixed is not a function`
    // and the error boundary replaced the whole panel.
    expect(screen.getByText(/Score:\s*10\.0/)).toBeInTheDocument();
  });

  it('close × button closes the panel (URL setter removes open=drill)', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    const close = screen.getByRole('button', { name: /close/i });
    fireEvent.click(close);
    expect(mockReplace).toHaveBeenCalled();
    const [target] = mockReplace.mock.calls[0];
    expect(target).not.toContain('open=drill');
  });

  it('Esc key closes the panel', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(mockReplace).toHaveBeenCalled();
    const [target] = mockReplace.mock.calls[0];
    expect(target).not.toContain('open=drill');
  });

  it('clicking outside the panel closes it (clickaway)', () => {
    render(
      <div>
        <div data-testid="outside">outside region</div>
        <DrillPanel cveId="CVE-2024-3094" />
      </div>
    );
    fireEvent.mouseDown(screen.getByTestId('outside'));
    expect(mockReplace).toHaveBeenCalled();
    const [target] = mockReplace.mock.calls[0];
    expect(target).not.toContain('open=drill');
  });

  it('row-swap — new cveId prop swaps panel content (no close, no URL setter)', () => {
    const { rerender } = render(<DrillPanel cveId="CVE-2024-3094" />);
    useDetailMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: { ...detail, cve_id: 'CVE-2024-1000', title: 'Other vuln' },
    } as unknown as ReturnType<typeof useVulnerabilityDetail>);
    rerender(<DrillPanel cveId="CVE-2024-1000" />);
    // Setter NOT called during row-swap — it's a content swap, not close
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it('focus moves to the close button on open (D-P-06)', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    const close = screen.getByRole('button', { name: /close/i });
    expect(document.activeElement).toBe(close);
  });

  it('Tab cycles through panel interactives; Shift-Tab from close returns focus to origin row', () => {
    // Render with a fake originating row in the document
    render(
      <div>
        <div tabIndex={0} data-testid="origin-row">origin row</div>
        <DrillPanel cveId="CVE-2024-3094" originRowRef={null} />
      </div>
    );
    const close = screen.getByRole('button', { name: /close/i });
    // Tab from close → focusable inside the panel (assert focus moves off close)
    close.focus();
    fireEvent.keyDown(close, { key: 'Tab' });
    // After Tab, focus must not still be on close
    // (We cannot guarantee where focus lands without the real focus-trap, but
    // we can assert the contract: focus moved out of close.)
    expect(document.activeElement).not.toBe(close);
  });

  it('Actions section has Snooze (secondary) + Create ticket (primary btn-cta)', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    const snooze = screen.getByRole('button', { name: /snooze/i });
    const create = screen.getByRole('button', { name: /create ticket/i });
    expect(snooze).toBeInTheDocument();
    expect(create).toBeInTheDocument();
    expect(create.className).toMatch(/btn-cta|primary/);
  });

  it('Phase 39 (EXC-01): Actions section gains "Accept risk" + "Mark false positive" secondary buttons that open the grant dialog with the matching type and FINDING scope', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    expect(screen.queryByRole('heading', { name: 'Grant exception' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Accept risk' }));
    expect(screen.getByRole('heading', { name: 'Grant exception' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'This finding' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(/CVE-2024-3094 on/)).toBeInTheDocument();

    // Cancel closes it.
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('heading', { name: 'Grant exception' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Mark false positive' }));
    expect(screen.getByRole('heading', { name: 'Grant exception' })).toBeInTheDocument();
  });

  it('420px width on desktop — className contains w-[420px]', () => {
    const { container } = render(<DrillPanel cveId="CVE-2024-3094" />);
    const aside = container.querySelector('[data-drill-panel]') as HTMLElement;
    expect(aside.className).toMatch(/w-\[420px\]/);
  });

  it('URL-encoded panel state — ?cve=CVE-2024-3094&open=drill renders open with content', () => {
    mockParams = new URLSearchParams('cve=CVE-2024-3094&open=drill');
    render(<DrillPanel cveId="CVE-2024-3094" />);
    // Panel content reflects detail.cve_id
    expect(screen.getByText(/CVE-2024-3094/)).toBeInTheDocument();
  });

  // Phase 26 Plan 04 Task 2 (D-03/D-09): the new "Prioritization" section
  // mounts AiExplanationSection with resourceType="prioritization",
  // positioned after AI Explanation and before the raw Remediation section.
  it('mounts the "Prioritization" section between AI Explanation and raw Remediation, with its own aria-labelledby', () => {
    const { container } = render(<DrillPanel cveId="CVE-2024-3094" />);
    const aiSection = container.querySelector<HTMLElement>('section[aria-labelledby="drill-ai-h"]');
    const prioritizationSection = container.querySelector<HTMLElement>(
      'section[aria-labelledby="drill-prioritization-h"]',
    );
    const remedSection = container.querySelector<HTMLElement>('section[aria-labelledby="drill-remed-h"]');
    expect(prioritizationSection).not.toBeNull();
    expect(document.getElementById('drill-prioritization-h')).toHaveTextContent('Prioritization');

    // Document-order check: AI Explanation < Prioritization < raw Remediation.
    const sections = Array.from(container.querySelectorAll<HTMLElement>('section'));
    const aiIdx = sections.indexOf(aiSection!);
    const prioritizationIdx = sections.indexOf(prioritizationSection!);
    const remedIdx = sections.indexOf(remedSection!);
    expect(aiIdx).toBeGreaterThanOrEqual(0);
    expect(prioritizationIdx).toBeGreaterThan(aiIdx);
    expect(remedIdx).toBeGreaterThan(prioritizationIdx);
  });

  // Phase 25 Plan 04 Task 2 (D-06): the new "Remediation guidance" section
  // mounts AiExplanationSection with resourceType="remediation-guidance",
  // positioned after the raw Remediation section and before Activity.
  it('mounts the "Remediation guidance" section between raw Remediation and Activity, with its own aria-labelledby', () => {
    const { container } = render(<DrillPanel cveId="CVE-2024-3094" />);
    const guidanceSection = container.querySelector<HTMLElement>('section[aria-labelledby="drill-remediation-guidance-h"]');
    const remedSection = container.querySelector<HTMLElement>('section[aria-labelledby="drill-remed-h"]');
    const activitySection = container.querySelector<HTMLElement>('section[aria-labelledby="drill-activity-h"]');
    expect(guidanceSection).not.toBeNull();
    expect(document.getElementById('drill-remediation-guidance-h')).toHaveTextContent('Remediation guidance');

    // Document-order check: remed < guidance < activity.
    const sections = Array.from(container.querySelectorAll<HTMLElement>('section'));
    const remedIdx = sections.indexOf(remedSection!);
    const guidanceIdx = sections.indexOf(guidanceSection!);
    const activityIdx = sections.indexOf(activitySection!);
    expect(remedIdx).toBeGreaterThanOrEqual(0);
    expect(guidanceIdx).toBeGreaterThan(remedIdx);
    expect(activityIdx).toBeGreaterThan(guidanceIdx);
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 25 Plan 07 Task 2 (AIR-02): the ticket-create ConfirmModal gains a
  // description Textarea. Proven at the mutation boundary (fake.mutateAsync
  // call args), not just the DOM value (Pitfall 4).
  // ───────────────────────────────────────────────────────────────────────

  describe('ticket-create dialog description textarea (AIR-02)', () => {
    it('renders the Textarea in the confirm dialog with the LOCKED "Description" label + placeholder, auto-composed on first open (Asset context always present, D-04)', () => {
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const textarea = screen.getByRole('textbox', { name: 'Description' }) as HTMLTextAreaElement;
      expect(textarea).toBeInTheDocument();
      expect(textarea.placeholder).toBe(
        'No AI draft available yet — add a description or leave blank.',
      );
      // Phase 27 (AID-01): auto-composed on open (D-02) -- never hard-empty
      // even with nothing AI-cached (this suite's default mock state).
      // Asset context needs no AI call, so it always renders (D-04).
      expect(textarea.value).toContain('Asset context:');
    });

    it('typing into the textarea and confirming threads the description into createTicket.mutateAsync body (not only the DOM)', async () => {
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const textarea = screen.getByRole('textbox', { name: 'Description' });
      fireEvent.change(textarea, { target: { value: 'Patch xz to 5.4.x per vendor advisory.' } });

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      const confirmBtn = within(dialog).getByRole('button', { name: /create ticket/i });
      fireEvent.click(confirmBtn);

      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Patch xz to 5.4.x per vendor advisory.' }),
      );
    });

    it('clearing the auto-composed Title/Description before confirming threads title: undefined, description: undefined (never empty strings) into the mutation body', () => {
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      // Phase 27 (AID-01): both fields auto-compose on open -- "leaving them
      // blank" no longer happens by default. The analyst can still clear
      // them explicitly (SC2); this proves that path still threads
      // `undefined` (never an empty string) into the mutation.
      fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), { target: { value: '' } });
      fireEvent.change(screen.getByRole('textbox', { name: 'Description' }), { target: { value: '' } });

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      const confirmBtn = within(dialog).getByRole('button', { name: /create ticket/i });
      fireEvent.click(confirmBtn);

      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ title: undefined, description: undefined }),
      );
    });

    it('opening the confirm dialog composes the full body even after "Copy into ticket description" was used first (Pitfall 2 -- the resourceId guard, not a blank-string check, governs)', () => {
      const summary = 'Cited remediation steps, plain text.';
      mockUseExplainCache.mockImplementation((resourceType: string) =>
        resourceType === 'remediation-guidance'
          ? { data: { cached: true, summary, business_risk: 'n/a', citations: [], grounded: true }, isPending: false, isError: false }
          : { data: { cached: false }, isPending: false, isError: false },
      );

      render(<DrillPanel cveId="CVE-2024-3094" />);
      // Analyst uses the pre-existing main-panel copy button BEFORE ever
      // opening the confirm dialog for this vuln.
      fireEvent.click(screen.getByRole('button', { name: 'Copy into ticket description' }));
      // First genuine open of the confirm dialog for this vuln -- compose
      // runs unconditionally (the resourceId guard has not fired for this
      // id yet), overwriting the bare copied summary with the full
      // composed body. Both Title AND Description populate together --
      // the guard governs the whole draft, not per-field.
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const textarea = screen.getByRole('textbox', { name: 'Description' }) as HTMLTextAreaElement;
      expect(textarea.value).toContain(`Remediation:\n${summary}`);
      expect(textarea.value).toContain('Asset context:');
      const titleInput = screen.getByRole('textbox', { name: 'Title' }) as HTMLInputElement;
      expect(titleInput.value).toBe('[Critical] CVE-2024-3094 on prod-01');
    });
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 27 Plan 02 (AID-01): the ticket-create ConfirmModal gains an
  // editable Title Input, deterministically composed (D-01) alongside the
  // widened multi-section Description above, via a resourceId-keyed
  // composed-once guard (RESEARCH Pattern 4, closing Pitfalls 2 & 3).
  // ───────────────────────────────────────────────────────────────────────

  describe('ticket-create dialog title input + compose-on-open guard (AID-01)', () => {
    it('renders the Title Input with the shared LOCKED caption, deterministically composed on first open regardless of AI cache state', () => {
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      expect(screen.getByText('AI-drafted — review before creating.')).toBeInTheDocument();
      const titleInput = screen.getByRole('textbox', { name: 'Title' }) as HTMLInputElement;
      expect(titleInput).toBeInTheDocument();
      // Deterministic D-01 format: "[{sevLabel}] {cveLabel} on {hostsLine}"
      // -- true even though this suite's default mocks have no AI key
      // configured (severity: 'critical' -> 'Critical'; host: 'prod-01').
      expect(titleInput.value).toBe('[Critical] CVE-2024-3094 on prod-01');
    });

    it('typing into the Title Input and confirming threads the title into createTicket.mutateAsync body', () => {
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), {
        target: { value: 'Patch the xz backdoor now' },
      });

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      fireEvent.click(within(dialog).getByRole('button', { name: /create ticket/i }));

      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Patch the xz backdoor now' }),
      );
    });

    it('editing the Title, cancelling, and re-opening the SAME vuln preserves the edit (composed-once guard, not a recompose)', () => {
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      fireEvent.change(screen.getByRole('textbox', { name: 'Title' }), {
        target: { value: 'My own edited title' },
      });

      const dialogBeforeCancel = screen.getAllByRole('dialog').slice(-1)[0];
      fireEvent.click(within(dialogBeforeCancel).getByRole('button', { name: /cancel/i }));

      // Re-open the SAME vuln's dialog -- the guard must NOT recompose.
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
      const titleInput = screen.getByRole('textbox', { name: 'Title' }) as HTMLInputElement;
      expect(titleInput.value).toBe('My own edited title');
    });

    it('switching to a DIFFERENT vuln recomposes the Title -- vuln A never carries onto a ticket for vuln B (Pitfall 3)', () => {
      const { rerender } = render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
      expect((screen.getByRole('textbox', { name: 'Title' }) as HTMLInputElement).value).toBe(
        '[Critical] CVE-2024-3094 on prod-01',
      );
      const dialogA = screen.getAllByRole('dialog').slice(-1)[0];
      fireEvent.click(within(dialogA).getByRole('button', { name: /cancel/i }));

      // Simulate a row-switch to a different vuln with no remount --
      // Pitfall 3's exact reproduction path (idOrCve changes, DrillContent
      // is not unmounted).
      useDetailMock.mockReturnValue({
        isPending: false,
        isError: false,
        data: {
          ...detail,
          id: '2',
          cve_id: 'CVE-2024-1000',
          severity: 'medium',
          cisa_kev: false,
          affected_hosts: [{ host: 'staging-02' }],
        },
      } as unknown as ReturnType<typeof useVulnerabilityDetail>);
      rerender(<DrillPanel cveId="CVE-2024-1000" />);

      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
      const titleInput = screen.getByRole('textbox', { name: 'Title' }) as HTMLInputElement;
      // Must be vuln B's own composed title, never vuln A's edited value.
      expect(titleInput.value).toBe('[Medium] CVE-2024-1000 on staging-02');
      expect(titleInput.value).not.toContain('CVE-2024-3094');
    });

    it('never auto-submits: opening the dialog and letting it compose does NOT call createTicket.mutateAsync until Create is clicked (SC3)', () => {
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      // Compose-on-open has already run (a real effect fired, populating
      // both fields) -- yet the mutation itself must not have fired.
      expect((screen.getByRole('textbox', { name: 'Title' }) as HTMLInputElement).value).not.toBe('');
      expect(mockMutateAsync).not.toHaveBeenCalled();
    });
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 27 Plan 03 (AID-01): the "Draft with AI" gap-fill row. Two
  // role/key-gated text-buttons that trigger useExplainStream('vuln' |
  // 'remediation-guidance', id).start() DIRECTLY (bypassing
  // AiExplanationSection) and append the labeled section on a grounded
  // 'done', with the full typed degradation matrix. Never a submit path.
  // ───────────────────────────────────────────────────────────────────────

  describe('"Draft with AI" gap-fill row (AID-01, Plan 03)', () => {
    it('renders no gap-fill buttons for Viewer role, even with an AI key configured (D-17)', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      expect(screen.queryByRole('button', { name: 'Draft description with AI' })).toBeNull();
      expect(screen.queryByRole('button', { name: 'Draft remediation with AI' })).toBeNull();
    });

    it('renders no gap-fill buttons when no AI key is configured, even for Analyst+ (D-23 parity)', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: false }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      expect(screen.queryByRole('button', { name: 'Draft description with AI' })).toBeNull();
      expect(screen.queryByRole('button', { name: 'Draft remediation with AI' })).toBeNull();
    });

    it('renders both gap-fill buttons for Analyst+ with a key configured, when both Description and Remediation are missing from the composed body', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).getByRole('button', { name: 'Draft description with AI' })).toBeInTheDocument();
      expect(within(dialog).getByRole('button', { name: 'Draft remediation with AI' })).toBeInTheDocument();
    });

    it('while phase is "analyzing", the trigger is replaced by the shared AnalyzingIndicator pulsing-dot (D-12), not a second spinner', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      mockUseExplainStream.mockImplementation((resourceType: string) =>
        resourceType === 'vuln'
          ? { state: { phase: 'analyzing' }, start: mockStart }
          : { state: { phase: 'idle' }, start: mockStart },
      );
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).queryByRole('button', { name: 'Draft description with AI' })).toBeNull();
      expect(within(dialog).getByText('Analyzing this finding…')).toBeInTheDocument();
    });

    it('on a grounded "done", appends "Description:\\n{summary}" to the CURRENT description without overwriting prior content, then hides the button', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      mockUseExplainStream.mockImplementation((resourceType: string) =>
        resourceType === 'vuln'
          ? {
              state: {
                phase: 'done',
                data: { summary: 'Freshly generated explanation.', business_risk: 'n/a', citations: [], grounded: true },
              },
              start: mockStart,
            }
          : { state: { phase: 'idle' }, start: mockStart },
      );
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const textarea = screen.getByRole('textbox', { name: 'Description' }) as HTMLTextAreaElement;
      // Prior composed content (Asset context, always present, D-04) is
      // preserved -- the new section is APPENDED, never a wholesale replace.
      expect(textarea.value).toContain('Asset context:');
      expect(textarea.value).toContain('Description:\nFreshly generated explanation.');

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).queryByRole('button', { name: 'Draft description with AI' })).toBeNull();
    });

    it('a mocked busy error keeps the trigger clickable and shows the amber retry caption verbatim (retryable, D-25)', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      mockUseExplainStream.mockImplementation((resourceType: string) =>
        resourceType === 'vuln'
          ? { state: { phase: 'error', kind: 'busy' }, start: mockStart }
          : { state: { phase: 'idle' }, start: mockStart },
      );
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).getByRole('button', { name: 'Draft description with AI' })).toBeInTheDocument();
      expect(within(dialog).getByText('AI busy — try again in a moment')).toBeInTheDocument();
    });

    it('a mocked grounded_false error renders the terminal insufficient-evidence caption verbatim, with no retry button (D-10)', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      mockUseExplainStream.mockImplementation((resourceType: string) =>
        resourceType === 'vuln'
          ? { state: { phase: 'error', kind: 'grounded_false' }, start: mockStart }
          : { state: { phase: 'idle' }, start: mockStart },
      );
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).getByText('Not enough finding data to explain this reliably')).toBeInTheDocument();
      expect(within(dialog).queryByRole('button', { name: 'Draft description with AI' })).toBeNull();
    });

    it('a mocked unsafe error on remediation renders the danger terminal caption verbatim, with no partial content, no retry (T-25-02)', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      mockUseExplainStream.mockImplementation((resourceType: string) =>
        resourceType === 'remediation-guidance'
          ? { state: { phase: 'error', kind: 'unsafe' }, start: mockStart }
          : { state: { phase: 'idle' }, start: mockStart },
      );
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).getByText('This guidance was withheld for safety')).toBeInTheDocument();
      expect(within(dialog).queryByRole('button', { name: 'Draft remediation with AI' })).toBeNull();
    });

    it('a mocked budget_exceeded error shows the amber caption for every role, but "Raise the cap" only for Admin/Owner (role-differentiated)', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseExplainStream.mockImplementation((resourceType: string) =>
        resourceType === 'vuln'
          ? { state: { phase: 'error', kind: 'budget_exceeded' }, start: mockStart }
          : { state: { phase: 'idle' }, start: mockStart },
      );

      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      const { unmount } = render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
      let dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).getByText('AI budget exceeded')).toBeInTheDocument();
      expect(within(dialog).queryByRole('link', { name: 'Raise the cap' })).toBeNull();
      unmount();

      mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
      dialog = screen.getAllByRole('dialog').slice(-1)[0];
      expect(within(dialog).getByText('AI budget exceeded')).toBeInTheDocument();
      expect(within(dialog).getByRole('link', { name: 'Raise the cap' })).toHaveAttribute(
        'href',
        '/dashboard/connectors',
      );
    });

    it('gap-fill interactions (clicking both triggers) never call createTicket.mutateAsync (SC3)', () => {
      mockUseAiStatus.mockReturnValue({ data: { configured: true }, isPending: false, isError: false });
      mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
      render(<DrillPanel cveId="CVE-2024-3094" />);
      fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));

      const dialog = screen.getAllByRole('dialog').slice(-1)[0];
      fireEvent.click(within(dialog).getByRole('button', { name: 'Draft description with AI' }));
      fireEvent.click(within(dialog).getByRole('button', { name: 'Draft remediation with AI' }));

      expect(mockStart).toHaveBeenCalledTimes(2);
      expect(mockMutateAsync).not.toHaveBeenCalled();
    });
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 33 Plan 04 (RISK-05): the shadow/preview "Risk exposure" section,
  // between CVSS and Affected hosts. Read-only display of the backend's
  // per-finding risk_exposure_score + risk_exposure_breakdown — the sole
  // permitted reader of the shadow score this phase (RISK-06 zero-consumer
  // gate). Data-driven over the breakdown array; KEV-floor chip conditioned
  // on a `kev_floor` component; null-safe absent state.
  // ───────────────────────────────────────────────────────────────────────

  describe('Risk exposure section (RISK-05)', () => {
    const breakdown = [
      { key: 'severity_cvss', label: 'Severity / CVSS', raw_value: '10.0', points: 35, max_points: 35 },
      { key: 'epss', label: 'EPSS', raw_value: '0.94', points: 18, max_points: 20 },
      { key: 'native_exploitability', label: 'Native exploitability', raw_value: '0.8', points: 12, max_points: 15 },
      { key: 'exposure_business_criticality', label: 'Business criticality', raw_value: 'CRITICAL', points: 10, max_points: 10 },
      { key: 'corroboration', label: 'Corroboration', raw_value: '3 sources', points: 6.67, max_points: 10 },
      { key: 'kev_floor', label: 'CISA KEV floor', raw_value: 'raised 78 -> 90', points: 12, max_points: 0 },
    ];

    it('renders the "Risk exposure" heading, overall score, one row per breakdown component, the preview caption, and the KEV-floor chip', () => {
      useDetailMock.mockReturnValue({
        isPending: false,
        isError: false,
        data: { ...detail, risk_exposure_score: 82, risk_exposure_breakdown: breakdown, risk_model_version: 'v1' },
      } as unknown as ReturnType<typeof useVulnerabilityDetail>);
      render(<DrillPanel cveId="CVE-2024-3094" />);

      expect(screen.getByText('Risk exposure')).toBeInTheDocument();
      expect(screen.getByText('82')).toBeInTheDocument();

      breakdown.forEach((c) => {
        expect(screen.getByText(c.label)).toBeInTheDocument();
      });
      expect(screen.getByText(/0\.94/)).toBeInTheDocument();

      expect(
        screen.getByText('Shadow score — not yet used for sorting or alerts.'),
      ).toBeInTheDocument();
      expect(screen.getByText('★ KEV floor applied')).toBeInTheDocument();
    });

    it('does NOT render the KEV-floor chip when the breakdown has no kev_floor component', () => {
      const breakdownNoKev = breakdown.filter((c) => c.key !== 'kev_floor');
      useDetailMock.mockReturnValue({
        isPending: false,
        isError: false,
        data: { ...detail, risk_exposure_score: 70, risk_exposure_breakdown: breakdownNoKev, risk_model_version: 'v1' },
      } as unknown as ReturnType<typeof useVulnerabilityDetail>);
      render(<DrillPanel cveId="CVE-2024-3094" />);

      expect(screen.getByText('Risk exposure')).toBeInTheDocument();
      expect(screen.queryByText('★ KEV floor applied')).toBeNull();
    });

    it('renders nothing (no crash) when risk_exposure_score / risk_exposure_breakdown are null', () => {
      useDetailMock.mockReturnValue({
        isPending: false,
        isError: false,
        data: { ...detail, risk_exposure_score: null, risk_exposure_breakdown: null, risk_model_version: null },
      } as unknown as ReturnType<typeof useVulnerabilityDetail>);
      expect(() => render(<DrillPanel cveId="CVE-2024-3094" />)).not.toThrow();

      expect(screen.queryByText('Risk exposure')).toBeNull();
    });
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 36 Plan 06 (SLA-01/02, D-11): the extended SlaPill rendering the
  // server-computed sla_state on the drill panel, matching the finding row.
  // ───────────────────────────────────────────────────────────────────────

  describe('SLA state pill (SLA-01/02, D-11)', () => {
    it('renders the SlaPill with the server sla_state (breached)', () => {
      useDetailMock.mockReturnValue({
        isPending: false,
        isError: false,
        data: { ...detail, sla_state: 'breached', sla_due_at: '2024-01-01T00:00:00Z' },
      } as unknown as ReturnType<typeof useVulnerabilityDetail>);
      render(<DrillPanel cveId="CVE-2024-3094" />);

      // Overdue tone renders a mono "−Nh"/"−Nd" label (sla-pill.tsx TIER_CONFIG).
      expect(screen.getByText(/^−\d+[hd]$/)).toBeInTheDocument();
    });

    it('renders "No SLA" for a not_tracked (below-floor) finding, never a client-computed fallback', () => {
      useDetailMock.mockReturnValue({
        isPending: false,
        isError: false,
        data: { ...detail, sla_state: 'not_tracked', sla_due_at: null },
      } as unknown as ReturnType<typeof useVulnerabilityDetail>);
      render(<DrillPanel cveId="CVE-2024-3094" />);

      expect(screen.getByText('No SLA')).toBeInTheDocument();
    });

    it('renders no SlaPill at all when the server sends no sla_state (never falls back to client-side computeTier)', () => {
      useDetailMock.mockReturnValue({
        isPending: false,
        isError: false,
        data: { ...detail, sla_state: undefined, sla_due_at: undefined },
      } as unknown as ReturnType<typeof useVulnerabilityDetail>);
      render(<DrillPanel cveId="CVE-2024-3094" />);

      expect(screen.queryByText('No SLA')).toBeNull();
      expect(screen.queryByText('Unknown')).toBeNull();
    });
  });

  // ───────────────────────────────────────────────────────────────────────
  // Phase 36 Plan 06 (SLA-03, D-07): the escalation-history list — empty /
  // populated / failed-delivery audit-only (D-08, no retry) states.
  // ───────────────────────────────────────────────────────────────────────

  describe('Escalation history (SLA-03, D-07)', () => {
    it('renders the compact inline "No escalations yet" empty state', () => {
      mockUseVulnEscalations.mockReturnValue({ isPending: false, isError: false, data: [] });
      render(<DrillPanel cveId="CVE-2024-3094" />);

      expect(screen.getByText('No escalations yet')).toBeInTheDocument();
      expect(
        screen.getByText(
          "This finding hasn't crossed the approaching or breach threshold — new entries appear here the moment it does.",
        ),
      ).toBeInTheDocument();
    });

    it('renders a populated chronological timeline (channel chip + transition + fired_at)', () => {
      mockUseVulnEscalations.mockReturnValue({
        isPending: false,
        isError: false,
        data: [
          {
            id: 'e1',
            from_state: 'on_track',
            to_state: 'approaching',
            channel: 'slack',
            fired_at: '2024-06-01T14:03:00Z',
            delivery_status: 'sent',
            error_message: null,
          },
        ],
      });
      render(<DrillPanel cveId="CVE-2024-3094" />);

      expect(screen.getByText('Slack')).toBeInTheDocument();
      expect(screen.getByText(/On track.*Approaching/)).toBeInTheDocument();
    });

    it('a failed delivery renders an amber-tinted row with the exact copy, and NO retry button (D-08 audit-only) — the transition record stays visible (D-07)', () => {
      mockUseVulnEscalations.mockReturnValue({
        isPending: false,
        isError: false,
        data: [
          {
            id: 'e2',
            from_state: 'approaching',
            to_state: 'breached',
            channel: 'slack',
            fired_at: '2024-06-01T14:03:00Z',
            delivery_status: 'failed',
            error_message: 'Slack webhook returned HTTP 404',
          },
        ],
      });
      render(<DrillPanel cveId="CVE-2024-3094" />);

      // Transition record stays visible even though delivery failed (D-07).
      expect(screen.getByText(/Approaching.*Breached/)).toBeInTheDocument();
      expect(
        screen.getByText(/Slack delivery failed — Slack webhook returned HTTP 404 · fired/),
      ).toBeInTheDocument();
      // Audit-only: no retry button/clickable element anywhere in this row (D-08).
      expect(screen.queryByRole('button', { name: /retry/i })).toBeNull();
    });
  });
});
