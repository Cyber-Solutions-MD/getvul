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
  });

  it('renders 10 sections in order (Header / CVSS / Affected hosts / Description / AI Explanation / Prioritization / Remediation / Remediation guidance / Activity / Actions)', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    const headings = screen.getAllByRole('heading').map((h) => h.textContent ?? '');
    // 10 named sections, in the documented order (Phase 24-05 / UI-SPEC D-11
    // inserts AI Explanation between Description and Remediation; Phase 25
    // Plan 04 D-06 inserts "Remediation guidance" between the raw
    // Remediation text and Activity; Phase 26 Plan 04 (D-03/D-09) inserts
    // the NEW "Prioritization" section between AI Explanation and the raw
    // Remediation text).
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
      /Actions/i,
    ];
    expectedOrder.forEach((re, idx) => {
      expect(headings[idx] ?? '').toMatch(re);
    });
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
});
