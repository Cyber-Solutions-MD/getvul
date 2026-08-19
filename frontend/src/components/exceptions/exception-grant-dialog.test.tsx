import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError } from '@/lib/api';
import { ExceptionGrantDialog, type ExceptionFinding } from './exception-grant-dialog';

// Isolates this dialog's own gating/error-mapping/payload-shape logic from
// ApproverCombobox's own internals (separately covered by
// approver-combobox.test.tsx) — a simple stand-in button fires onSelect
// with a fixed user.
vi.mock('./approver-combobox', () => ({
  ApproverCombobox: ({ onSelect }: { onSelect: (u: { id: string; email: string; display_name: string | null }) => void }) => (
    <button type="button" onClick={() => onSelect({ id: 'u1', email: 'ana@co.com', display_name: 'Ana Sokolova' })}>
      Pick approver
    </button>
  ),
}));

vi.mock('@/lib/queries/use-asset-groups', () => ({
  useAssetGroupsList: vi.fn(() => ({
    data: [{ id: 'g1', name: 'Prod DB fleet', tenant_id: 't1', description: null, member_count: 3, created_at: null, updated_at: null }],
    isLoading: false,
    isError: false,
  })),
}));

const mutateFn = vi.fn();
const resetFn = vi.fn();
let mutationPending = false;
let mutationError: unknown = null;

vi.mock('@/lib/queries/use-exception-mutations', () => ({
  useGrantException: vi.fn(() => ({
    mutate: (body: unknown, opts?: { onSuccess?: () => void }) => {
      mutateFn(body);
      if (!mutationError) opts?.onSuccess?.();
    },
    isPending: mutationPending,
    error: mutationError,
    reset: resetFn,
  })),
}));

const FULL_FINDING: ExceptionFinding = {
  vulnerabilityId: 'v1',
  cveId: 'CVE-2024-3094',
  assetId: 'a1',
  hostname: 'prod-db-01',
};

function fillApproverAndJustification(text = 'Compensating control in place.') {
  fireEvent.click(screen.getByText('Pick approver'));
  fireEvent.change(screen.getByLabelText('Justification'), { target: { value: text } });
}

describe('ExceptionGrantDialog', () => {
  beforeEach(() => {
    mutateFn.mockReset();
    resetFn.mockReset();
    mutationPending = false;
    mutationError = null;
  });

  it('renders the header type chip + fixed CVE/host context', () => {
    render(
      <ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />,
    );
    expect(screen.getByText('Accept risk')).toBeInTheDocument();
    expect(screen.getByText('CVE-2024-3094 on prod-db-01')).toBeInTheDocument();
  });

  it('renders the 4 fields in fixed order: Scope, Approver, Justification, Expires', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    const labels = screen.getAllByText(/Scope|Approver|Justification|Expires/, { selector: 'span, label' }).map((el) => el.textContent);
    expect(labels).toEqual(['Scope', 'Approver', 'Justification', 'Expires']);
  });

  it('defaults scope to "This finding" and pre-fills Expires to the type default window (90d for ACCEPTED_RISK)', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    expect(screen.getByRole('button', { name: 'This finding' })).toHaveAttribute('aria-pressed', 'true');
    const expected = new Date();
    expected.setUTCDate(expected.getUTCDate() + 90);
    const expectedStr = expected.toISOString().slice(0, 10);
    expect(screen.getByLabelText('Expires')).toHaveValue(expectedStr);
  });

  it('D-06: Grant exception stays disabled until all four fields are filled, then enables', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    const submit = screen.getByRole('button', { name: /Grant exception/ });
    expect(submit).toBeDisabled();

    fillApproverAndJustification();
    expect(submit).toBeEnabled();
  });

  it('D-06: switching to Asset group re-disables submit until a group is explicitly chosen', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    fillApproverAndJustification();
    const submit = screen.getByRole('button', { name: /Grant exception/ });
    expect(submit).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: 'Asset group' }));
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Asset group'), { target: { value: 'g1' } });
    expect(submit).toBeEnabled();
  });

  it('"This asset" scope option is disabled when the finding has no asset_id', () => {
    render(
      <ExceptionGrantDialog
        open
        onOpenChange={vi.fn()}
        type="ACCEPTED_RISK"
        finding={{ ...FULL_FINDING, assetId: null }}
      />,
    );
    expect(screen.getByRole('button', { name: 'This asset' })).toBeDisabled();
  });

  it('backstop: justification counter appears near the 1000-char cap and a full-length value is preserved (no silent truncation)', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    const textarea = screen.getByLabelText('Justification') as HTMLTextAreaElement;

    // A 1000-char value ending mid-word — asserts the cap is exactly 1000,
    // not truncated earlier, and the counter renders once >= the warn
    // threshold.
    const longValue = 'a'.repeat(994) + 'wordish';
    expect(longValue).toHaveLength(1001);
    fireEvent.change(textarea, { target: { value: longValue.slice(0, 1000) } });
    expect(textarea.value).toHaveLength(1000);
    expect(textarea.value.endsWith('wordis')).toBe(true);
    expect(screen.getByText('0 characters left')).toBeInTheDocument();
  });

  it('does NOT show the counter below the warn threshold', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    fireEvent.change(screen.getByLabelText('Justification'), { target: { value: 'short justification' } });
    expect(screen.queryByText(/characters left/)).toBeNull();
  });

  it('submits the FINDING-scope payload with vulnerability_id and no cve_id/asset_id', () => {
    const onOpenChange = vi.fn();
    render(<ExceptionGrantDialog open onOpenChange={onOpenChange} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    fillApproverAndJustification('Mitigated via WAF rule.');
    fireEvent.click(screen.getByRole('button', { name: /Grant exception/ }));

    expect(mutateFn).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'ACCEPTED_RISK',
        scope_type: 'FINDING',
        vulnerability_id: 'v1',
        approver_user_id: 'u1',
        justification: 'Mitigated via WAF rule.',
      }),
    );
    const sentBody = mutateFn.mock.calls[0][0];
    expect(sentBody).not.toHaveProperty('cve_id');
    expect(sentBody).not.toHaveProperty('asset_id');
    expect(sentBody.expires_at).toMatch(/^\d{4}-\d{2}-\d{2}T00:00:00\.000Z$/);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('submits the ASSET-scope payload with asset_id + the finding cve_id, no vulnerability_id', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="FALSE_POSITIVE" finding={FULL_FINDING} />);
    fillApproverAndJustification();
    fireEvent.click(screen.getByRole('button', { name: 'This asset' }));
    fireEvent.click(screen.getByRole('button', { name: /Grant exception/ }));

    expect(mutateFn).toHaveBeenCalledWith(
      expect.objectContaining({
        scope_type: 'ASSET',
        asset_id: 'a1',
        cve_id: 'CVE-2024-3094',
      }),
    );
    expect(mutateFn.mock.calls[0][0]).not.toHaveProperty('vulnerability_id');
  });

  it('submits the ASSET_GROUP-scope payload with the selected group id + the finding cve_id', () => {
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="FALSE_POSITIVE" finding={FULL_FINDING} />);
    fillApproverAndJustification();
    fireEvent.click(screen.getByRole('button', { name: 'Asset group' }));
    fireEvent.change(screen.getByLabelText('Asset group'), { target: { value: 'g1' } });
    fireEvent.click(screen.getByRole('button', { name: /Grant exception/ }));

    expect(mutateFn).toHaveBeenCalledWith(
      expect.objectContaining({ scope_type: 'ASSET_GROUP', asset_group_id: 'g1', cve_id: 'CVE-2024-3094' }),
    );
  });

  it('D-03: renders the exact precondition string as a dialog-level banner', () => {
    mutationError = new ApiError('This finding is already remediated — nothing to except.', 400, 'req-1');
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    expect(
      screen.getByText('This finding is already remediated — nothing to except.'),
    ).toBeInTheDocument();
    // Not rendered under Expires — this is a dialog-level, not field-level, error.
    expect(screen.getByLabelText('Expires').nextElementSibling?.textContent).not.toMatch(/remediated/);
  });

  it('D-14: renders the expiry-cap message under Expires, field-level', () => {
    mutationError = new ApiError('Pick a date between tomorrow and 2027-08-19.', 400, 'req-1');
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    expect(screen.getByLabelText('Expires').nextElementSibling?.textContent).toBe(
      'Pick a date between tomorrow and 2027-08-19.',
    );
  });

  it('generic failure renders the HTTP-coded fallback, never a bare "Something went wrong"', () => {
    mutationError = new ApiError('Approver must be an active user in your organization.', 400, 'req-1');
    render(<ExceptionGrantDialog open onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />);
    expect(screen.getByText("Exception wasn't saved. HTTP 400 · Retry.")).toBeInTheDocument();
  });

  it('resets to a fresh state (including clearing a prior error) every time it re-opens', () => {
    const { rerender } = render(
      <ExceptionGrantDialog open={false} onOpenChange={vi.fn()} type="ACCEPTED_RISK" finding={FULL_FINDING} />,
    );
    rerender(<ExceptionGrantDialog open type="FALSE_POSITIVE" onOpenChange={vi.fn()} finding={FULL_FINDING} />);
    expect(resetFn).toHaveBeenCalled();
    expect(screen.getByLabelText('Justification')).toHaveValue('');
  });
});
