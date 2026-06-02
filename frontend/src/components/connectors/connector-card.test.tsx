/**
 * connector-card.test.tsx — TDD RED-phase tests for ConnectorCard.
 *
 * Test 3: Renders ConnectorMark (provider lowercased), connector_name, SyncStatusPill, last_sync_at "Synced N ago".
 * Test 4: Delete action shown only for isAdmin=true.
 * Test 5: Toggling enable/disable calls onToggleEnabled with the inverse of is_enabled.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConnectorCard } from './connector-card';

const MOCK_CONNECTOR = {
  id: 'conn-1',
  connector_type: 'CROWDSTRIKE',
  connector_name: 'CrowdStrike Spotlight',
  is_enabled: true,
  config: {},
  has_credentials: true,
  last_sync_at: new Date(Date.now() - 2 * 60 * 60 * 1000 - 14 * 60 * 1000).toISOString(), // ~2h 14m ago
  last_sync_status: 'ok' as const,
  last_sync_record_count: 512,
  sync_interval_minutes: 15,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-02T10:00:00Z',
};

describe('ConnectorCard', () => {
  it('Test 3: renders ConnectorMark with lowercased provider, connector_name, SyncStatusPill, and last_sync_at relative time', () => {
    render(
      <ConnectorCard
        connector={MOCK_CONNECTOR}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );

    // connector_name is displayed
    expect(screen.getByText('CrowdStrike Spotlight')).toBeTruthy();

    // ConnectorMark renders with aria-label = lowercased connector_type
    const mark = document.querySelector('[aria-label="crowdstrike"]');
    expect(mark).not.toBeNull();

    // SyncStatusPill renders (data-sync-status attribute from sync-status-pill.tsx)
    const pill = document.querySelector('[data-sync-status]');
    expect(pill).not.toBeNull();

    // last_sync_at renders as relative time containing "ago"
    expect(screen.getByText(/ago/i)).toBeTruthy();
  });

  it('Test 3b: renders "Never synced" when last_sync_at is null', () => {
    render(
      <ConnectorCard
        connector={{ ...MOCK_CONNECTOR, last_sync_at: null, last_sync_status: null }}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    // Both the metadata text and the SyncStatusPill may render "Never synced" —
    // assert at least one exists (the behavior is: null sync shows "Never synced" in UI).
    expect(screen.getAllByText(/never synced/i).length).toBeGreaterThanOrEqual(1);
  });

  it('Test 3c: renders record count when last_sync_record_count is set', () => {
    render(
      <ConnectorCard
        connector={MOCK_CONNECTOR}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    expect(screen.getByText(/512 records/i)).toBeTruthy();
  });

  it('Test 4: Delete button shown only when isAdmin=true', () => {
    const { rerender } = render(
      <ConnectorCard
        connector={MOCK_CONNECTOR}
        isAdmin={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    // VIEWER: no delete button
    expect(screen.queryByRole('button', { name: /delete/i })).toBeNull();

    // Re-render as admin: delete button appears
    rerender(
      <ConnectorCard
        connector={MOCK_CONNECTOR}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /delete/i })).toBeTruthy();
  });

  it('Test 5: onToggleEnabled called with inverse of is_enabled when toggle clicked', () => {
    const onToggle = vi.fn();
    render(
      <ConnectorCard
        connector={MOCK_CONNECTOR}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={onToggle}
      />,
    );
    const toggleBtn = screen.getByRole('button', { name: /disable|enable/i });
    fireEvent.click(toggleBtn);
    // MOCK_CONNECTOR.is_enabled = true, so inverse = false
    expect(onToggle).toHaveBeenCalledWith(false);
  });
});
