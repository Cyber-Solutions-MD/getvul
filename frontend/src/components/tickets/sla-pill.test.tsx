import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { SlaPill } from './sla-pill';

// Fixed reference point for all time calculations
const NOW = new Date('2026-06-01T12:00:00Z').getTime();

function msFromNow(ms: number) {
  return new Date(NOW + ms).toISOString();
}

describe('SlaPill', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('due in the past → Overdue, severity-critical classes', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const pastDate = new Date(NOW - 2 * 60 * 60 * 1000).toISOString(); // 2h ago
    const { container } = render(<SlaPill dueAt={pastDate} />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-[var(--color-severity-critical-on-soft)]');
  });

  it('due in 3 days → Soon (within 7d), amber/severity-high classes', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const soonDate = msFromNow(3 * 24 * 60 * 60 * 1000); // 3 days from now
    const { container } = render(<SlaPill dueAt={soonDate} />);
    const pill = container.firstChild as HTMLElement;
    // Soon tier maps to severity-high (amber in the design system), on-soft token for AA contrast
    expect(pill.className).toContain('text-[var(--color-severity-high-on-soft)]');
  });

  it('due in 30 days → OK, severity-low (green) classes', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const okDate = msFromNow(30 * 24 * 60 * 60 * 1000); // 30 days from now
    const { container } = render(<SlaPill dueAt={okDate} />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-severity-low');
  });

  it('dueAt=null → Unknown, text-text-faint class', () => {
    const { container } = render(<SlaPill dueAt={null} />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-text-faint');
  });

  it('renders font-mono for SLA values', () => {
    const { container } = render(<SlaPill dueAt={null} />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('font-mono');
  });
});

// Phase 36 / D-11: server-truth `state` prop path (findings). The server is
// authoritative — these tests prove the pill renders the passed state
// directly and never re-derives via computeTier() (T-36-01, Anti-Pattern).
describe('SlaPill — server state prop (Phase 36 / D-11)', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('state="on_track" renders the ok tier tone (severity-low green) + "Nd left" copy', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const dueAt = msFromNow(30 * 24 * 60 * 60 * 1000); // 30 days from now
    const { container } = render(<SlaPill dueAt={dueAt} state="on_track" />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-severity-low');
    expect(pill.textContent).toBe('30d left');
  });

  it('state="approaching" renders the soon tier tone (severity-high amber)', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const dueAt = msFromNow(2 * 24 * 60 * 60 * 1000); // 2 days from now
    const { container } = render(<SlaPill dueAt={dueAt} state="approaching" />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-[var(--color-severity-high-on-soft)]');
    expect(pill.textContent).toBe('2d left');
  });

  it('state="breached" renders the overdue tier tone (severity-critical red)', () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const dueAt = msFromNow(-2 * 60 * 60 * 1000); // 2h ago
    const { container } = render(<SlaPill dueAt={dueAt} state="breached" />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-[var(--color-severity-critical-on-soft)]');
    expect(pill.textContent).toBe('−2h');
  });

  it('state="not_tracked" renders "No SLA" (never "Unknown") with the faint tone', () => {
    const { container } = render(<SlaPill dueAt={null} state="not_tracked" />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('text-text-faint');
    expect(pill.textContent).toBe('No SLA');
  });

  it('a contradictory dueAt is ignored when state is present — server truth wins, computeTier() is never consulted', () => {
    // dueAt says "overdue" (in the past) but the server state says on_track.
    // If computeTier() were consulted, this would render the critical/red
    // overdue tone instead — proving D-01/D-02/T-36-01 (server authoritative).
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const pastDate = msFromNow(-2 * 60 * 60 * 1000);
    const { container } = render(<SlaPill dueAt={pastDate} state="on_track" />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).not.toContain('text-[var(--color-severity-critical-on-soft)]');
    expect(pill.className).toContain('text-severity-low');
  });

  it('renders font-mono for the state-prop path too', () => {
    const { container } = render(<SlaPill dueAt={null} state="not_tracked" />);
    const pill = container.firstChild as HTMLElement;
    expect(pill.className).toContain('font-mono');
  });
});
