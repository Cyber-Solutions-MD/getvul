import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ExportBoardReportDialog } from './export-board-report-dialog';

// Isolates this dialog's own gating/state logic from the real `api()`
// wrapper (network/token/refresh mechanics are covered by lib/api.test.ts).
// API_URL is kept from the real module (empty string in tests).
const apiMock = vi.fn();
vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    api: (...args: unknown[]) => apiMock(...args),
  };
});

type MockReport = {
  id: string;
  schedule: string;
  recipients: string[] | null;
  sections: string[] | null;
};

const BOARD_SECTIONS = [
  'vulns',
  'assets',
  'risk',
  'top_hosts',
  'top_remediations',
  'tickets',
  'risk_trend',
  'mttr_by_tier',
  'sla_compliance',
];

function defaultApiImpl(path: string, options?: RequestInit) {
  if (path === '/api/v1/reports' && (!options || !options.method)) {
    return Promise.resolve([]); // GET — no existing board report by default
  }
  if (path === '/api/v1/reports' && options?.method === 'POST') {
    const body = JSON.parse(String(options.body));
    return Promise.resolve({ id: 'new-report-1', ...body });
  }
  if (/^\/api\/v1\/reports\/.+/.test(path) && options?.method === 'DELETE') {
    return Promise.resolve({ message: 'Deleted' });
  }
  return Promise.reject(new Error(`Unhandled api() call in test: ${path} ${options?.method ?? 'GET'}`));
}

/** Seeds GET /api/v1/reports with one pre-existing "board" ScheduledReport
 * (identified by the dialog via `sections` containing 'risk_trend'). */
function seedExistingBoardReport(overrides: Partial<MockReport> = {}): MockReport {
  const report: MockReport = {
    id: 'r1',
    schedule: 'weekly',
    recipients: ['ciso@co.com'],
    sections: BOARD_SECTIONS,
    ...overrides,
  };
  apiMock.mockImplementation((path: string, options?: RequestInit) => {
    if (path === '/api/v1/reports' && (!options || !options.method)) {
      return Promise.resolve([report]);
    }
    return defaultApiImpl(path, options);
  });
  return report;
}

function mockPdfFetchOnce(ok = true, status = 200) {
  fetchMock.mockResolvedValueOnce({
    ok,
    status,
    headers: { get: () => null },
    blob: async () => new Blob(['pdf-bytes'], { type: 'application/pdf' }),
  } as unknown as Response);
}

async function openAndSettle() {
  render(<ExportBoardReportDialog open onOpenChange={vi.fn()} />);
  // Flush the mount-time GET /api/v1/reports effect.
  await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/v1/reports'));
}

let fetchMock: ReturnType<typeof vi.fn>;
const originalFetch = globalThis.fetch;

beforeEach(() => {
  apiMock.mockReset();
  apiMock.mockImplementation(defaultApiImpl);

  fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  // jsdom has no real createObjectURL/anchor-navigation; both are no-ops we
  // don't need to observe (the acceptance surface is the fetch call shape).
  URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

  localStorage.clear();
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe('ExportBoardReportDialog', () => {
  it('defaults period to "Last quarter" and scheduling toggle unchecked', async () => {
    await openAndSettle();
    expect(screen.getByRole('button', { name: 'Last quarter' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('checkbox', { name: /Also send this report/i })).not.toBeChecked();
  });

  it('selecting "Custom range" reveals From/To date inputs; To < From blocks submit with a validation message', async () => {
    await openAndSettle();
    fireEvent.click(screen.getByRole('button', { name: 'Custom range' }));

    const from = screen.getByLabelText('From');
    const to = screen.getByLabelText('To');
    expect(from).toBeInTheDocument();
    expect(to).toBeInTheDocument();

    fireEvent.change(from, { target: { value: '2026-06-01' } });
    fireEvent.change(to, { target: { value: '2026-05-01' } });

    expect(screen.getByText("'To' must not be before 'From'.")).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Export board report/ })).toBeDisabled();
  });

  it('custom range with To >= From enables submit', async () => {
    await openAndSettle();
    fireEvent.click(screen.getByRole('button', { name: 'Custom range' }));
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-05-01' } });
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-06-01' } });
    expect(screen.getByRole('button', { name: /Export board report/ })).toBeEnabled();
  });

  it('on submit the CTA enters a disabled "Generating…" state and the dialog stays open until it resolves', async () => {
    await openAndSettle();

    let resolveFetch: (value: unknown) => void = () => {};
    fetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );

    fireEvent.click(screen.getByRole('button', { name: /Export board report/ }));

    const generating = await screen.findByRole('button', { name: /Generating…/ });
    expect(generating).toBeDisabled();
    // Dialog is still open — the title is still rendered.
    expect(screen.getByText('Export board report', { selector: 'h2' })).toBeInTheDocument();

    resolveFetch({
      ok: true,
      status: 200,
      headers: { get: () => null },
      blob: async () => new Blob(['pdf-bytes']),
    });

    await waitFor(() => expect(screen.queryByRole('button', { name: /Generating…/ })).not.toBeInTheDocument());
  });

  it('closes the dialog on a successful export', async () => {
    const onOpenChange = vi.fn();
    render(<ExportBoardReportDialog open onOpenChange={onOpenChange} />);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/v1/reports'));

    mockPdfFetchOnce(true);
    fireEvent.click(screen.getByRole('button', { name: /Export board report/ }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it('fetches /api/v1/export/summary with the default period param and no explicit section params', async () => {
    await openAndSettle();
    mockPdfFetchOnce(true);
    fireEvent.click(screen.getByRole('button', { name: /Export board report/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const calledUrl = String(fetchMock.mock.calls[0][0]);
    expect(calledUrl).toContain('/api/v1/export/summary');
    expect(calledUrl).toContain('format=pdf');
    expect(calledUrl).toContain('period=quarter');
    expect(calledUrl).not.toContain('section=');
  });

  it('submits a custom range as from/to params, not a period preset', async () => {
    await openAndSettle();
    fireEvent.click(screen.getByRole('button', { name: 'Custom range' }));
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-03-31' } });

    mockPdfFetchOnce(true);
    fireEvent.click(screen.getByRole('button', { name: /Export board report/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const calledUrl = String(fetchMock.mock.calls[0][0]);
    expect(calledUrl).toContain('from=2026-01-01');
    expect(calledUrl).toContain('to=2026-03-31');
    expect(calledUrl).not.toContain('period=');
  });

  it('checking "Also send this report {cadence} by email" reveals inline cadence/recipients fields in the SAME dialog', async () => {
    await openAndSettle();
    expect(screen.queryByLabelText('Cadence')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: /Also send this report/i }));

    expect(screen.getByLabelText('Cadence')).toBeInTheDocument();
    expect(screen.getByLabelText('Recipients')).toBeInTheDocument();
    // Single dialog — no second dialog surface was opened.
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
  });

  it('enabling scheduling and submitting POSTs /api/v1/reports with the board sections', async () => {
    await openAndSettle();
    fireEvent.click(screen.getByRole('checkbox', { name: /Also send this report/i }));
    fireEvent.change(screen.getByLabelText('Recipients'), { target: { value: 'ciso@co.com, board@co.com' } });
    fireEvent.change(screen.getByLabelText('Cadence'), { target: { value: 'monthly' } });

    mockPdfFetchOnce(true);
    fireEvent.click(screen.getByRole('button', { name: /Export board report/ }));

    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith(
        '/api/v1/reports',
        expect.objectContaining({ method: 'POST' }),
      ),
    );
    const postCall = apiMock.mock.calls.find(([path, opts]) => path === '/api/v1/reports' && opts?.method === 'POST');
    const body = JSON.parse(String(postCall?.[1]?.body));
    expect(body).toMatchObject({
      name: 'Board report',
      schedule: 'monthly',
      recipients: ['ciso@co.com', 'board@co.com'],
      sections: BOARD_SECTIONS,
    });
  });

  it('a generation error renders the name-the-failure copy + a "retry with charts off" affordance and keeps the dialog open', async () => {
    await openAndSettle();
    mockPdfFetchOnce(false, 500);

    fireEvent.click(screen.getByRole('button', { name: /Export board report/ }));

    expect(await screen.findByText('Board report generation failed.')).toBeInTheDocument();
    expect(
      screen.getByText('Try again — if chart rendering keeps failing, retry with charts off (tables only).'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry with charts off (tables only)' })).toBeInTheDocument();
    // Still open — the dialog's own title is still rendered.
    expect(screen.getByText('Export board report', { selector: 'h2' })).toBeInTheDocument();
  });

  it('"retry with charts off" re-submits without the 3 chart-bearing sections', async () => {
    await openAndSettle();
    mockPdfFetchOnce(false, 500);
    fireEvent.click(screen.getByRole('button', { name: /Export board report/ }));
    await screen.findByText('Board report generation failed.');

    mockPdfFetchOnce(true);
    fireEvent.click(screen.getByRole('button', { name: 'Retry with charts off (tables only)' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const retryUrl = String(fetchMock.mock.calls[1][0]);
    for (const s of ['vulns', 'assets', 'risk', 'top_hosts', 'top_remediations', 'tickets']) {
      expect(retryUrl).toContain(`section=${s}`);
    }
    for (const s of ['risk_trend', 'mttr_by_tier', 'sla_compliance']) {
      expect(retryUrl).not.toContain(`section=${s}`);
    }
  });

  it('seeds the scheduling toggle CHECKED when a board ScheduledReport already exists', async () => {
    seedExistingBoardReport({ schedule: 'weekly' });
    render(<ExportBoardReportDialog open onOpenChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByRole('checkbox', { name: /Also send this report/i })).toBeChecked());
    expect(screen.getByText('weekly', { selector: 'span' })).toBeInTheDocument();
  });

  it('unchecking an already-enabled toggle opens the E7 "Stop scheduled board report" confirm (no typed reason)', async () => {
    seedExistingBoardReport({ schedule: 'daily' });
    render(<ExportBoardReportDialog open onOpenChange={vi.fn()} />);
    const checkbox = await screen.findByRole('checkbox', { name: /Also send this report/i });
    await waitFor(() => expect(checkbox).toBeChecked());

    fireEvent.click(checkbox);

    expect(screen.getByText('Stop scheduled board report')).toBeInTheDocument();
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('daily', { selector: 'span' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Stop sending' })).toBeInTheDocument();
    // No typed-reason input anywhere in the confirm.
    expect(within(dialog).queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
  });

  it('"Cancel" on the stop-confirm leaves the toggle checked and issues no request', async () => {
    seedExistingBoardReport({ schedule: 'weekly' });
    render(<ExportBoardReportDialog open onOpenChange={vi.fn()} />);
    const checkbox = await screen.findByRole('checkbox', { name: /Also send this report/i });
    await waitFor(() => expect(checkbox).toBeChecked());

    fireEvent.click(checkbox);
    apiMock.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByText('Stop scheduled board report')).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Also send this report/i })).toBeChecked();
    expect(apiMock).not.toHaveBeenCalled();
  });

  it('"Stop sending" calls DELETE /api/v1/reports/{id} and unchecks the toggle', async () => {
    seedExistingBoardReport({ id: 'report-42', schedule: 'weekly' });
    render(<ExportBoardReportDialog open onOpenChange={vi.fn()} />);
    const checkbox = await screen.findByRole('checkbox', { name: /Also send this report/i });
    await waitFor(() => expect(checkbox).toBeChecked());

    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole('button', { name: 'Stop sending' }));

    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith('/api/v1/reports/report-42', expect.objectContaining({ method: 'DELETE' })),
    );
    await waitFor(() => expect(screen.queryByText('Stop scheduled board report')).not.toBeInTheDocument());
    expect(screen.getByRole('checkbox', { name: /Also send this report/i })).not.toBeChecked();
  });
});
