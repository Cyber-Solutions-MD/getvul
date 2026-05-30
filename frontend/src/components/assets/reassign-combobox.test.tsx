import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { ReassignCombobox } from './reassign-combobox';

// D-A-01 contract:
//   Esc → onDone() (no mutation)
//   Enter → mutate(highlighted.email), then onDone() on success
//   Click outside → onDone() (no mutation)
// ArrowDown/Up cycle the highlight; clicking an option commits the same way Enter does.

const mutateFn = vi.fn();
let mutationPending = false;
let mutationError: Error | null = null;

vi.mock('@/lib/queries/use-assignable-users', () => ({
  useAssignableUsers: vi.fn((q: string) => ({
    data: {
      users: q
        ? [
            {
              email: 'bob@example.com',
              display_name: 'Bob Builder',
              idp_source: 'okta',
              role: 'USER',
              department: null,
              job_title: null,
              avatar_url: null,
              groups: [],
              is_active: true,
            },
            {
              email: 'cathy@example.com',
              display_name: 'Cathy Coder',
              idp_source: 'google',
              role: 'USER',
              department: null,
              job_title: null,
              avatar_url: null,
              groups: [],
              is_active: true,
            },
          ]
        : [],
      total: q ? 2 : 0,
      page: 1,
      page_size: 25,
    },
    isLoading: false,
  })),
}));

vi.mock('@/lib/queries/use-reassign-asset', () => ({
  useReassignAsset: vi.fn(() => ({
    mutate: (email: string, opts?: { onSuccess?: () => void }) => {
      mutateFn(email);
      opts?.onSuccess?.();
    },
    isPending: mutationPending,
    error: mutationError,
  })),
}));

function renderCombobox(props: { initialEmail?: string | null; onDone?: () => void } = {}) {
  const onDone = props.onDone ?? vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  return {
    onDone,
    ...render(
      <ReassignCombobox
        assetId="a1"
        initialEmail={props.initialEmail ?? null}
        onDone={onDone}
      />,
      { wrapper: Wrapper },
    ),
  };
}

describe('ReassignCombobox', () => {
  beforeEach(() => {
    mutateFn.mockReset();
    mutationPending = false;
    mutationError = null;
  });

  it('auto-focuses the search input on mount', () => {
    renderCombobox();
    const input = screen.getByLabelText('Search assignable users') as HTMLInputElement;
    expect(document.activeElement).toBe(input);
  });

  it('Escape cancels without mutating', () => {
    const onDone = vi.fn();
    renderCombobox({ onDone });
    const combobox = screen.getByTestId('reassign-combobox');
    fireEvent.keyDown(combobox, { key: 'Escape' });
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(mutateFn).not.toHaveBeenCalled();
  });

  it('Enter on highlighted option commits via mutation and calls onDone', async () => {
    const onDone = vi.fn();
    renderCombobox({ onDone });
    const input = screen.getByLabelText('Search assignable users');
    fireEvent.change(input, { target: { value: 'bob' } });

    // Wait for the 250ms debounce + the rendered options to materialize.
    await waitFor(
      () => expect(screen.getByTestId('reassign-option-0')).toBeInTheDocument(),
      { timeout: 1000 },
    );

    const combobox = screen.getByTestId('reassign-combobox');
    fireEvent.keyDown(combobox, { key: 'Enter' });

    expect(mutateFn).toHaveBeenCalledWith('bob@example.com');
    expect(onDone).toHaveBeenCalled();
  });

  it('clicking outside the combobox cancels (mousedown on body)', () => {
    const onDone = vi.fn();
    renderCombobox({ onDone });
    fireEvent.mouseDown(document.body);
    expect(onDone).toHaveBeenCalled();
    expect(mutateFn).not.toHaveBeenCalled();
  });

  it('ArrowDown moves the highlight; clicking an option commits', async () => {
    const onDone = vi.fn();
    renderCombobox({ onDone });
    const input = screen.getByLabelText('Search assignable users');
    fireEvent.change(input, { target: { value: 'b' } });
    await waitFor(
      () => expect(screen.getByTestId('reassign-option-0')).toBeInTheDocument(),
      { timeout: 1000 },
    );

    const combobox = screen.getByTestId('reassign-combobox');
    fireEvent.keyDown(combobox, { key: 'ArrowDown' });
    fireEvent.keyDown(combobox, { key: 'Enter' });
    expect(mutateFn).toHaveBeenCalledWith('cathy@example.com');
    expect(onDone).toHaveBeenCalled();
  });

  it('clicking an option commits + calls onDone', async () => {
    const onDone = vi.fn();
    renderCombobox({ onDone });
    const input = screen.getByLabelText('Search assignable users');
    fireEvent.change(input, { target: { value: 'b' } });
    await waitFor(
      () => expect(screen.getByTestId('reassign-option-0')).toBeInTheDocument(),
      { timeout: 1000 },
    );

    fireEvent.click(screen.getByTestId('reassign-option-0'));
    expect(mutateFn).toHaveBeenCalledWith('bob@example.com');
    expect(onDone).toHaveBeenCalled();
  });

  it('shows an empty-input hint before the user types (W9 — avoids full directory dump)', () => {
    renderCombobox();
    expect(
      screen.getByText(/Start typing a name or email/i),
    ).toBeInTheDocument();
  });

  it('exposes ARIA roles: combobox + listbox + option', async () => {
    renderCombobox();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    const input = screen.getByLabelText('Search assignable users');
    fireEvent.change(input, { target: { value: 'b' } });
    await waitFor(
      () => expect(screen.getAllByRole('option').length).toBeGreaterThan(0),
      { timeout: 1000 },
    );
  });

  it('Enter with no directory match is a no-op (WR-02 — no free-text commit)', () => {
    // Initial state: items haven't loaded yet, so there is no highlighted
    // option. Pressing Enter must NOT commit the raw input string — that's
    // the front-line defense against BL-01 / non-email Asset.assigned_user.
    const onDone = vi.fn();
    renderCombobox({ onDone });
    const combobox = screen.getByTestId('reassign-combobox');
    fireEvent.keyDown(combobox, { key: 'Enter' });
    expect(mutateFn).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it('ARIA wiring lives on the input per WAI-ARIA combobox pattern (WR-03)', () => {
    renderCombobox();
    const input = screen.getByLabelText('Search assignable users');
    expect(input).toHaveAttribute('role', 'combobox');
    expect(input).toHaveAttribute('aria-controls', 'reassign-listbox');
    expect(input).toHaveAttribute('aria-autocomplete', 'list');
  });
});
