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
    expect(pill.className).toContain('text-severity-critical');
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
