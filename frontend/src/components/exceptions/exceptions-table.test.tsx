/**
 * exceptions-table.test.tsx — tests for ExceptionsTable (Phase 39 Plans 06 + 07).
 *
 * Test 1: all UI-SPEC column headers rendered.
 * Test 2: default sort is ascending by expires_at (soonest-expiring first, D-19).
 * Test 3: clicking the Expires header toggles sort direction.
 * Test 4: row click toggles a LOCAL inline-accordion expand (justification +
 *         audit metadata) — not a callback, not navigation.
 * Test 5 (Plan 07, D-17): Revoke is enabled for an active row, disabled for
 *         historical (revoked/expired) rows.
 * Test 6: revoked/expired historical rows render a muted chip, never
 *         sla-pill.overdue.
 * Test 7: never imports next/navigation / calls useRouter.
 * Plan 07 additions: clicking Revoke opens a warning ConfirmModal with the
 *         exact D-17 copy; confirming calls useRevokeException(row.id).
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ExceptionsTable } from './exceptions-table';
import type { ExceptionResponse } from '@/lib/queries/use-exceptions';

// ExceptionsTable now calls the real useRevokeException(id) mutation hook
// (Plan 07) — mocked the same way reassign-combobox.test.tsx stubs
// useReassignAsset, so this suite doesn't need a QueryClientProvider wrapper.
const mutateFn = vi.fn();
let mutationPending = false;
vi.mock('@/lib/queries/use-exception-mutations', () => ({
  useRevokeException: vi.fn((id: string) => ({
    mutate: (_vars: unknown, opts?: { onSuccess?: () => void }) => {
      mutateFn(id);
      opts?.onSuccess?.();
    },
    isPending: mutationPending,
  })),
}));

const now = Date.now();
const iso = (offsetDays: number) => new Date(now + offsetDays * 24 * 60 * 60 * 1000).toISOString();

// Data rows carry tabIndex=0 (keyboard nav target); the accordion-expand row
// injected below an expanded row does not, so this selector always returns
// only the "real" data rows in DOM (i.e. current sort) order.
function dataRowCveIds(container: HTMLElement): (string | null)[] {
  return Array.from(container.querySelectorAll('tbody > tr[tabindex="0"]')).map(
    (row) => row.querySelector('td:nth-child(2) span')?.textContent ?? null,
  );
}

function makeRow(overrides: Partial<ExceptionResponse>): ExceptionResponse {
  return {
    id: 'e1',
    type: 'ACCEPTED_RISK',
    scope_type: 'FINDING',
    cve_id: 'CVE-2024-0001',
    vulnerability_id: 'v1',
    asset_id: 'a1',
    asset_group_id: null,
    justification: 'Compensating control in place; mitigated via WAF rule.',
    approver_user_id: 'u1',
    approver_display_name: 'Ana Sokolova',
    granted_by_user_id: 'u2',
    expires_at: iso(30),
    revoked_at: null,
    revoked_by_user_id: null,
    resurfaced_audited_at: null,
    created_at: iso(-2),
    ...overrides,
  };
}

const SOON_ROW = makeRow({ id: 'soon', cve_id: 'CVE-2024-0003', expires_at: iso(3) });
const OK_ROW = makeRow({ id: 'ok', cve_id: 'CVE-2024-0002', expires_at: iso(30) });
const FAR_ROW = makeRow({ id: 'far', cve_id: 'CVE-2024-0001', expires_at: iso(60) });

describe('ExceptionsTable', () => {
  beforeEach(() => {
    mutateFn.mockReset();
    mutationPending = false;
  });

  it('Test 1: renders all UI-SPEC column headers', () => {
    render(<ExceptionsTable rows={[]} />);
    ['Type', 'CVE / target', 'Scope', 'Approver', 'Granted'].forEach((h) => {
      expect(screen.getByText(h)).toBeInTheDocument();
    });
    expect(screen.getByText(/Expires/)).toBeInTheDocument();
    expect(screen.getByText('Revoke')).toBeInTheDocument();
  });

  it('Test 2: default sort is ascending by expires_at (soonest first)', () => {
    const { container } = render(<ExceptionsTable rows={[FAR_ROW, SOON_ROW, OK_ROW]} />);
    expect(dataRowCveIds(container)).toEqual([SOON_ROW.cve_id, OK_ROW.cve_id, FAR_ROW.cve_id]);
  });

  it('Test 3: clicking the Expires header toggles sort direction', () => {
    const { container } = render(<ExceptionsTable rows={[FAR_ROW, SOON_ROW, OK_ROW]} />);
    const header = container.querySelector('[data-col="expires"]')!;
    expect(header.textContent).toContain('↑');
    fireEvent.click(header);
    expect(header.textContent).toContain('↓');
    expect(dataRowCveIds(container)).toEqual([FAR_ROW.cve_id, OK_ROW.cve_id, SOON_ROW.cve_id]);
  });

  it('Test 4: row click toggles a local inline-accordion expand (not a callback)', () => {
    render(<ExceptionsTable rows={[SOON_ROW]} />);
    expect(screen.queryByText(SOON_ROW.justification)).toBeNull();

    const row = screen.getByText(SOON_ROW.cve_id).closest('tr')!;
    fireEvent.click(row);
    expect(screen.getByText(SOON_ROW.justification)).toBeInTheDocument();
    expect(row.getAttribute('aria-expanded')).toBe('true');

    fireEvent.click(row);
    expect(screen.queryByText(SOON_ROW.justification)).toBeNull();
  });

  it('Enter/Space on a focused row also toggles the expand', () => {
    render(<ExceptionsTable rows={[SOON_ROW]} />);
    const row = screen.getByText(SOON_ROW.cve_id).closest('tr')!;
    row.focus();
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(screen.getByText(SOON_ROW.justification)).toBeInTheDocument();
    fireEvent.keyDown(row, { key: ' ' });
    expect(screen.queryByText(SOON_ROW.justification)).toBeNull();
  });

  it('Test 5 (Plan 07, D-17): Revoke is enabled for an active row', () => {
    render(<ExceptionsTable rows={[SOON_ROW]} />);
    const revokeBtn = screen.getByRole('button', { name: /Revoke exception/ });
    expect(revokeBtn).toBeEnabled();
  });

  it('D-17: Revoke is disabled for already-historical (revoked/expired) rows', () => {
    const revoked = makeRow({ id: 'revoked', cve_id: 'CVE-2024-9001', revoked_at: iso(-1) });
    const expired = makeRow({ id: 'expired', cve_id: 'CVE-2024-9002', expires_at: iso(-5) });
    render(<ExceptionsTable rows={[revoked, expired]} />);
    expect(screen.getByRole('button', { name: /Revoke exception for CVE-2024-9001/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Revoke exception for CVE-2024-9002/ })).toBeDisabled();
  });

  it('D-17: clicking Revoke opens a warning ConfirmModal with the exact copy; confirming calls useRevokeException(row.id)', () => {
    render(<ExceptionsTable rows={[SOON_ROW]} />);
    fireEvent.click(screen.getByRole('button', { name: /Revoke exception/ }));

    expect(screen.getByText('Revoke this exception?')).toBeInTheDocument();
    expect(
      screen.getByText(/CVE-2024-0003 on this finding returns to the active queue immediately/),
    ).toBeInTheDocument();
    const confirmBtn = screen.getByRole('button', { name: 'Revoke exception' });
    expect(confirmBtn).toBeInTheDocument();

    fireEvent.click(confirmBtn);
    expect(mutateFn).toHaveBeenCalledWith(SOON_ROW.id);
    // The modal closes on successful confirm (onSuccess -> setRevokeTarget(null)).
    expect(screen.queryByText('Revoke this exception?')).toBeNull();
  });

  it('D-17: clicking Revoke on a row does not also toggle the row expand (stopPropagation)', () => {
    render(<ExceptionsTable rows={[SOON_ROW]} />);
    fireEvent.click(screen.getByRole('button', { name: /Revoke exception/ }));
    expect(screen.queryByText(SOON_ROW.justification)).toBeNull();
  });

  it('D-17: Cancel dismisses the ConfirmModal without calling the mutation', () => {
    render(<ExceptionsTable rows={[SOON_ROW]} />);
    fireEvent.click(screen.getByRole('button', { name: /Revoke exception/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(mutateFn).not.toHaveBeenCalled();
    expect(screen.queryByText('Revoke this exception?')).toBeNull();
  });

  it('Test 6: revoked/expired historical rows render a muted chip, never sla-pill.overdue', () => {
    const revoked = makeRow({ id: 'revoked', cve_id: 'CVE-2024-9001', revoked_at: iso(-1) });
    const expired = makeRow({ id: 'expired', cve_id: 'CVE-2024-9002', expires_at: iso(-5) });
    render(<ExceptionsTable rows={[revoked, expired]} />);
    expect(screen.getByText('Revoked')).toBeInTheDocument();
    expect(screen.getByText('Expired')).toBeInTheDocument();
    expect(screen.queryByText(/overdue/i)).toBeNull();
  });

  it('Test 7: never imports next/navigation / calls useRouter', () => {
    const source = readFileSync(join(__dirname, 'exceptions-table.tsx'), 'utf-8');
    expect(source).not.toMatch(/from ['"]next\/navigation['"]/);
    expect(source).not.toMatch(/useRouter\(/);
  });
});
