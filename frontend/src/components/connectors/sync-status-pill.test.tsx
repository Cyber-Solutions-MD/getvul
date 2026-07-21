/**
 * sync-status-pill.test.tsx — TDD RED-phase tests for SyncStatusPill.
 *
 * Tests 1-4: 4-state mapping (ok / failed / syncing / null) verifying
 *   label text, CSS color class, and pulse animation for running state.
 * Test 5: queryKeys.cspm / .settings / .directoryUsers namespaces are in
 *   keys.ts (tested separately in keys.test.ts — see that file for full assertions).
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SyncStatusPill } from './sync-status-pill';

describe('SyncStatusPill', () => {
  it('Test 1: status="ok" renders label "Synced" with text-severity-low class', () => {
    const { container } = render(<SyncStatusPill status="ok" />);
    expect(screen.getByText('Synced')).toBeInTheDocument();
    // The pill container should include the severity-low color token
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-severity-low');
  });

  it('Test 2: status="failed" renders label "Failed" with severity-critical-on-soft class', () => {
    const { container } = render(<SyncStatusPill status="failed" />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-[var(--color-severity-critical-on-soft)]');
  });

  it('Test 3: status="syncing" renders label "Syncing" with amber-on-soft text and animated dot', () => {
    const { container } = render(<SyncStatusPill status="syncing" />);
    expect(screen.getByText('Syncing')).toBeInTheDocument();
    const pill = container.firstChild as HTMLElement;
    // Phase-16 (WR-04): amber text lifted to the on-soft token for AA on cream.
    expect(pill.className).toContain('text-[var(--color-amber-on-soft)]');
    // The leading dot should have motion-safe:animate-pulse
    const dot = pill.querySelector('span');
    expect(dot, 'leading dot span should exist').not.toBeNull();
    expect(dot!.className).toContain('motion-safe:animate-pulse');
  });

  it('Test 4: status=null renders "Never synced" with text-text-faint class', () => {
    const { container } = render(<SyncStatusPill status={null} />);
    expect(screen.getByText('Never synced')).toBeInTheDocument();
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-text-faint');
  });

  it('Test 4b: data-sync-status attribute reflects the status value', () => {
    const { container: c1 } = render(<SyncStatusPill status="ok" />);
    expect((c1.firstChild as HTMLElement).dataset.syncStatus).toBe('ok');

    const { container: c2 } = render(<SyncStatusPill status={null} />);
    expect((c2.firstChild as HTMLElement).dataset.syncStatus).toBe('never');
  });
});
