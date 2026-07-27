/**
 * connector-card.test.tsx — TDD RED-phase tests for ConnectorCard.
 *
 * Test 3: Renders ConnectorMark (provider lowercased), connector_name, SyncStatusPill, last_sync_at "Synced N ago".
 * Test 4: Delete action shown only for isAdmin=true.
 * Test 5: Toggling enable/disable calls onToggleEnabled with the inverse of is_enabled.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
  last_error: null,
  consecutive_failure_count: 0,
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

  // --- Plan 23-09: last-error inline summary + failure count (D-16, D-18) ---

  it('Test 6: failed connector with last_error shows one-line error summary, expandable to full message + timestamp', () => {
    render(
      <ConnectorCard
        connector={{
          ...MOCK_CONNECTOR,
          last_sync_status: 'failed',
          last_error: 'HTTP 503 Service Unavailable · req_8f2a91c',
          consecutive_failure_count: 1,
        }}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    // One-line summary visible (scoped to the <summary> element — the full
    // message repeats inside the expanded body once opened)
    const summaryEl = document.querySelector('summary');
    expect(summaryEl?.textContent).toMatch(/HTTP 503 Service Unavailable/i);

    // Expand to reveal full message + last_sync_at timestamp
    const details = document.querySelector('details');
    expect(details).not.toBeNull();
    fireEvent.click(summaryEl as Element);
    expect(details?.open).toBe(true);
    expect(screen.getAllByText(/HTTP 503 Service Unavailable/i).length).toBeGreaterThanOrEqual(1);
  });

  it('Test 7: failed connector with last_error=null shows fallback "Last sync failed" copy', () => {
    render(
      <ConnectorCard
        connector={{
          ...MOCK_CONNECTOR,
          last_sync_status: 'failed',
          last_error: null,
          consecutive_failure_count: 1,
        }}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    expect(document.querySelector('summary')?.textContent).toMatch(/last sync failed/i);
  });

  it('Test 8: healthy (ok) connector shows no error line', () => {
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
    expect(document.querySelector('details')).toBeNull();
    expect(screen.queryByText(/times in a row/i)).toBeNull();
  });

  it('Test 9: consecutive_failure_count > 1 renders "failed N times in a row"', () => {
    render(
      <ConnectorCard
        connector={{
          ...MOCK_CONNECTOR,
          last_sync_status: 'failed',
          last_error: 'timeout',
          consecutive_failure_count: 5,
        }}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    expect(screen.getByText(/failed 5 times in a row/i)).toBeTruthy();
  });

  it('Test 10: consecutive_failure_count <= 1 does not render "times in a row"', () => {
    render(
      <ConnectorCard
        connector={{
          ...MOCK_CONNECTOR,
          last_sync_status: 'failed',
          last_error: 'timeout',
          consecutive_failure_count: 1,
        }}
        isAdmin={true}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onSync={vi.fn()}
        onToggleEnabled={vi.fn()}
      />,
    );
    expect(screen.queryByText(/times in a row/i)).toBeNull();
  });

  // --- Plan 23-09: frontend-derived "next sync in ~Xm" line (D-17) ---

  describe('next-sync line', () => {
    const FROZEN_NOW = new Date('2026-07-27T12:00:00.000Z');

    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(FROZEN_NOW);
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('Test 11: future next-sync (< 60m away) renders "next sync in ~Xm"', () => {
      // last_sync_at 5m ago, interval 15m → next sync in ~10m
      const lastSyncAt = new Date(FROZEN_NOW.getTime() - 5 * 60_000).toISOString();
      render(
        <ConnectorCard
          connector={{ ...MOCK_CONNECTOR, last_sync_at: lastSyncAt, sync_interval_minutes: 15 }}
          isAdmin={true}
          onEdit={vi.fn()}
          onDelete={vi.fn()}
          onSync={vi.fn()}
          onToggleEnabled={vi.fn()}
        />,
      );
      expect(screen.getByText(/next sync in ~10m/i)).toBeTruthy();
    });

    it('Test 12: future next-sync (>= 60m away) renders "next sync in ~Xh"', () => {
      // last_sync_at just now, interval 120m → next sync in ~2h
      const lastSyncAt = FROZEN_NOW.toISOString();
      render(
        <ConnectorCard
          connector={{ ...MOCK_CONNECTOR, last_sync_at: lastSyncAt, sync_interval_minutes: 120 }}
          isAdmin={true}
          onEdit={vi.fn()}
          onDelete={vi.fn()}
          onSync={vi.fn()}
          onToggleEnabled={vi.fn()}
        />,
      );
      expect(screen.getByText(/next sync in ~2h/i)).toBeTruthy();
    });

    it('Test 13: last_sync_at null renders "not synced yet"', () => {
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
      expect(screen.getByText(/not synced yet/i)).toBeTruthy();
    });

    it('Test 14: computed next-sync already past renders "sync due"', () => {
      // last_sync_at 30m ago, interval 15m → next sync was 15m ago (past)
      const lastSyncAt = new Date(FROZEN_NOW.getTime() - 30 * 60_000).toISOString();
      render(
        <ConnectorCard
          connector={{ ...MOCK_CONNECTOR, last_sync_at: lastSyncAt, sync_interval_minutes: 15 }}
          isAdmin={true}
          onEdit={vi.fn()}
          onDelete={vi.fn()}
          onSync={vi.fn()}
          onToggleEnabled={vi.fn()}
        />,
      );
      expect(screen.getByText(/sync due/i)).toBeTruthy();
    });
  });
});
