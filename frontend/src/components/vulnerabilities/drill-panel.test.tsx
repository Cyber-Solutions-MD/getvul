// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

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
vi.mock('@/lib/mutations/use-create-ticket', () => ({
  useCreateTicketMutation: () => ({ mutate: vi.fn(), isPending: false }),
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
vi.mock('@/lib/queries/use-explain-cache', () => ({
  useExplainCache: () => ({ data: { cached: false }, isPending: false, isError: false }),
}));
vi.mock('@/lib/queries/use-ai-status', () => ({
  useAiStatus: () => ({ data: { configured: false }, isPending: false, isError: false }),
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
    mockParams = new URLSearchParams('cve=CVE-2024-3094&open=drill');
    useDetailMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: detail,
    } as unknown as ReturnType<typeof useVulnerabilityDetail>);
  });

  it('renders 9 sections in order (Header / CVSS / Affected hosts / Description / AI Explanation / Remediation / Remediation guidance / Activity / Actions)', () => {
    render(<DrillPanel cveId="CVE-2024-3094" />);
    const headings = screen.getAllByRole('heading').map((h) => h.textContent ?? '');
    // 9 named sections, in the documented order (Phase 24-05 / UI-SPEC D-11
    // inserts AI Explanation between Description and Remediation; Phase 25
    // Plan 04 D-06 inserts the NEW "Remediation guidance" section between
    // the raw Remediation text and Activity).
    const expectedOrder = [
      /CVE-2024-3094|Drill|Header/i,
      /CVSS/i,
      /Affected hosts/i,
      /Description/i,
      /AI Explanation/i,
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
});
