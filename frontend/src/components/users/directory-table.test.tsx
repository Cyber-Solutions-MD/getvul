/**
 * Tests for DirectoryTable (Plan 14-04 Task 1 RED).
 * Behaviors:
 *   Test 3: renders row per person with Avatar + display_name + email + SourcePill + title/dept chip
 *   Test 4: does NOT render RBAC role as a chip (Pitfall 7)
 *   Test 5: Toggling a row's selection checkbox calls onSelect with the row id
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DirectoryTable } from './directory-table';
import type { DirectoryUser } from './directory-table';

const SAMPLE_USER: DirectoryUser = {
  id: 'user-001',
  email: 'alice@example.com',
  display_name: 'Alice Smith',
  role: 'ADMIN',          // RBAC role — should NOT appear as a chip
  department: 'Engineering',
  job_title: 'Senior Engineer',
  idp_source: 'google',
  is_active: true,
  groups: ['eng-team'],
  avatar_url: null,
  last_login_at: null,
  device_count: 2,
  devices: [],
  max_risk_score: 45,
  total_vulns: 3,
  critical_vulns: 1,
  high_vulns: 2,
  exploitable_vulns: 0,
};

describe('DirectoryTable', () => {
  it('renders a row per user with data-user-row', () => {
    const { container } = render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    const rows = container.querySelectorAll('[data-user-row]');
    expect(rows.length).toBe(1);
  });

  it('renders display_name in the row', () => {
    render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText('Alice Smith')).toBeTruthy();
  });

  it('renders email in the row', () => {
    render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText('alice@example.com')).toBeTruthy();
  });

  it('renders a SourcePill with idp_source', () => {
    const { container } = render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    const pill = container.querySelector('[data-source-pill="google"]');
    expect(pill).toBeTruthy();
  });

  it('renders job_title in the row', () => {
    render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText('Senior Engineer')).toBeTruthy();
  });

  it('renders department in the row', () => {
    render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText('Engineering')).toBeTruthy();
  });

  // Test 4 — Pitfall 7: RBAC role must NOT appear
  it('does NOT render RBAC role (ADMIN) as a chip or text node', () => {
    const { container } = render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    // The RBAC role value should not appear anywhere in the rendered output
    // Search in data-directory-table wrapper
    const table = container.querySelector('[data-directory-table]');
    expect(table?.textContent).not.toContain('ADMIN');
  });

  // Test 5 — row selection checkbox calls onSelect with the row id
  it('calls onSelect with row id when selection checkbox is toggled', () => {
    const onSelect = vi.fn();
    render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={onSelect}
      />
    );
    const checkbox = screen.getByRole('checkbox', { name: /select alice/i });
    fireEvent.click(checkbox);
    expect(onSelect).toHaveBeenCalledWith('user-001');
  });

  it('renders the table with data-directory-table attribute', () => {
    const { container } = render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={[]}
        onSelect={vi.fn()}
      />
    );
    expect(container.querySelector('[data-directory-table]')).toBeTruthy();
  });

  it('marks selected rows visually when selectedIds includes the row id', () => {
    render(
      <DirectoryTable
        users={[SAMPLE_USER]}
        selectedIds={['user-001']}
        onSelect={vi.fn()}
      />
    );
    const checkbox = screen.getByRole('checkbox', { name: /select alice/i });
    expect((checkbox as HTMLInputElement).checked).toBe(true);
  });
});
