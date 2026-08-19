import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ApproverCombobox, type SelectedApprover } from './approver-combobox';

// Pitfall 6: this combobox is a controlled form field (value/onSelect), NOT
// an inline editor that mutates on selection — contrast reassign-combobox's
// D-A-01 (Enter -> mutate -> onDone). Escape here only closes the open
// suggestion list (there is no "cancel the whole field" concept for a
// single form field), it never accepts an onDone-style callback.

let usersData: { users: unknown[] } | undefined;
let usersLoading = false;
let usersError = false;

vi.mock('@/lib/queries/use-assignable-users', () => ({
  useAssignableUsers: vi.fn((q: string) => ({
    data: usersData ?? {
      users: q
        ? [
            { id: 'u-bob', email: 'bob@example.com', display_name: 'Bob Builder', idp_source: 'okta', role: 'USER', department: null, job_title: null, avatar_url: null, groups: [], is_active: true },
            { id: 'u-cathy', email: 'cathy@example.com', display_name: 'Cathy Coder', idp_source: 'google', role: 'USER', department: null, job_title: null, avatar_url: null, groups: [], is_active: true },
          ]
        : [],
      total: q ? 2 : 0,
      page: 1,
      page_size: 25,
    },
    isLoading: usersLoading,
    isError: usersError,
  })),
}));

function renderCombobox(value: SelectedApprover | null = null) {
  const onSelect = vi.fn();
  return { onSelect, ...render(<ApproverCombobox value={value} onSelect={onSelect} />) };
}

describe('ApproverCombobox', () => {
  beforeEach(() => {
    usersData = undefined;
    usersLoading = false;
    usersError = false;
  });

  it('never imports reassign-combobox or useReassignAsset (Pitfall 6)', () => {
    // Matches the plan's own literal verification gate exactly (grep -c
    // useReassignAsset == 0). A bare substring check on "reassign-combobox"
    // would also trip on this file's OWN descriptive header comments (which
    // legitimately name the analog file), reproducing the exact false-
    // positive 39-06-SUMMARY.md documented for its "useRouter" mention — so
    // this asserts no IMPORT statement pulls it in, not "never mentioned".
    const source = readFileSync(join(__dirname, 'approver-combobox.tsx'), 'utf-8');
    expect(source).not.toMatch(/from ['"].*reassign-combobox['"]/);
    expect(source).not.toMatch(/useReassignAsset/);
  });

  it('starts empty and shows the "start typing" hint before 2 chars', () => {
    renderCombobox();
    expect(screen.getByText(/Start typing a name or email/i)).toBeInTheDocument();
  });

  it('fires onSelect(user) on click WITHOUT triggering any mutation — no mutate/onDone call exists', async () => {
    const { onSelect } = renderCombobox();
    const input = screen.getByLabelText('Search approvers');
    fireEvent.change(input, { target: { value: 'bob' } });

    await waitFor(() => expect(screen.getByTestId('approver-option-0')).toBeInTheDocument(), { timeout: 1000 });
    fireEvent.click(screen.getByTestId('approver-option-0'));

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'u-bob', email: 'bob@example.com', display_name: 'Bob Builder' }),
    );
  });

  it('Enter on the highlighted option commits via onSelect', async () => {
    const { onSelect } = renderCombobox();
    const input = screen.getByLabelText('Search approvers');
    fireEvent.change(input, { target: { value: 'b' } });
    await waitFor(() => expect(screen.getByTestId('approver-option-0')).toBeInTheDocument(), { timeout: 1000 });

    const combobox = screen.getByTestId('approver-combobox');
    fireEvent.keyDown(combobox, { key: 'ArrowDown' });
    fireEvent.keyDown(combobox, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'u-cathy' }));
  });

  it('Escape closes the suggestion list without selecting (no onSelect call)', async () => {
    const { onSelect } = renderCombobox();
    const input = screen.getByLabelText('Search approvers');
    fireEvent.change(input, { target: { value: 'b' } });
    await waitFor(() => expect(screen.getByTestId('approver-option-0')).toBeInTheDocument(), { timeout: 1000 });

    const combobox = screen.getByTestId('approver-combobox');
    fireEvent.keyDown(combobox, { key: 'Escape' });
    expect(screen.queryByTestId('approver-list')).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('renders disabled with placeholder "Loading approvers…" while a 2+-char search is in flight', async () => {
    usersLoading = true;
    render(<ApproverCombobox value={null} onSelect={vi.fn()} />);
    const input = screen.getByLabelText('Search approvers') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'bo' } });
    // isLoadingResults only flips once `debounced` (250ms) has caught up
    // with the typed value — wait for the real timer rather than asserting
    // synchronously.
    await waitFor(() => expect(input).toBeDisabled(), { timeout: 1000 });
    expect(input.placeholder).toBe('Loading approvers…');
  });

  it('shows "Approvers failed to load. Retry." inline on fetch error', () => {
    usersError = true;
    render(<ApproverCombobox value={null} onSelect={vi.fn()} />);
    expect(screen.getByText('Approvers failed to load. Retry.')).toBeInTheDocument();
  });

  it('clears the displayed text when the external value prop resets to null', () => {
    const { rerender } = render(
      <ApproverCombobox value={{ id: 'u1', email: 'ana@co.com', display_name: 'Ana Sokolova' }} onSelect={vi.fn()} />,
    );
    expect(screen.getByLabelText('Search approvers')).toHaveValue('Ana Sokolova');

    rerender(<ApproverCombobox value={null} onSelect={vi.fn()} />);
    expect(screen.getByLabelText('Search approvers')).toHaveValue('');
  });

  it('exposes ARIA roles: combobox + listbox + option', async () => {
    renderCombobox();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    const input = screen.getByLabelText('Search approvers');
    fireEvent.change(input, { target: { value: 'b' } });
    await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(0), { timeout: 1000 });
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  it('ARIA wiring lives on the input per WAI-ARIA combobox pattern', () => {
    renderCombobox();
    const input = screen.getByLabelText('Search approvers');
    expect(input).toHaveAttribute('role', 'combobox');
    expect(input).toHaveAttribute('aria-controls', 'approver-listbox');
    expect(input).toHaveAttribute('aria-autocomplete', 'list');
  });
});
