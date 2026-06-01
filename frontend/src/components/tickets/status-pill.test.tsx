import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusPill } from './status-pill';

describe('StatusPill', () => {
  it('open: has violet classes and leading dot span', () => {
    const { container } = render(<StatusPill externalStatus="open" />);
    const pill = container.querySelector('[data-status]') as HTMLElement;
    expect(pill).toBeDefined();
    expect(pill.className).toContain('border-violet/40');
    expect(pill.className).toContain('bg-violet-soft');
    expect(pill.className).toContain('text-violet');
    // Leading dot span
    const dot = pill.querySelector('span.size-1\\.5');
    expect(dot).toBeDefined();
    expect(dot?.className).toContain('rounded-full');
    expect(dot?.className).toContain('bg-current');
  });

  it('completed (lowercase from backend) maps to severity-low classes', () => {
    const { container } = render(<StatusPill externalStatus="completed" />);
    const pill = container.querySelector('[data-status]') as HTMLElement;
    expect(pill.className).toContain('border-severity-low/40');
    expect(pill.className).toContain('bg-severity-low/10');
    expect(pill.className).toContain('text-severity-low');
  });

  it('in_progress maps to amber classes', () => {
    const { container } = render(<StatusPill externalStatus="in_progress" />);
    const pill = container.querySelector('[data-status]') as HTMLElement;
    expect(pill.className).toContain('border-amber/40');
    expect(pill.className).toContain('bg-amber/10');
    expect(pill.className).toContain('text-amber');
  });

  it('case-insensitive mapping: COMPLETED resolves to completed pill', () => {
    const { container } = render(<StatusPill externalStatus="COMPLETED" />);
    const pill = container.querySelector('[data-status]') as HTMLElement;
    expect(pill.className).toContain('text-severity-low');
  });

  it('blocked=true renders BOTH a provider-status pill AND a Blocked pill', () => {
    const { container } = render(<StatusPill externalStatus="open" blocked={true} />);
    const pills = container.querySelectorAll('[data-status]');
    expect(pills.length).toBe(2);
    // First pill: provider status (open = violet)
    expect(pills[0].className).toContain('text-violet');
    // Second pill: blocked (severity-critical)
    expect(pills[1].className).toContain('text-severity-critical');
    expect(pills[1].textContent).toContain('Blocked');
  });

  it('blocked pill has severity-critical classes', () => {
    const { container } = render(<StatusPill externalStatus="open" blocked={true} />);
    const pills = container.querySelectorAll('[data-status]');
    const blockedPill = pills[1] as HTMLElement;
    expect(blockedPill.className).toContain('border-severity-critical/40');
    expect(blockedPill.className).toContain('bg-severity-critical/10');
    expect(blockedPill.className).toContain('text-severity-critical');
  });

  it('label text is plain ("Open", "In progress", "Completed") — no status: prefix', () => {
    const { getByText } = render(<StatusPill externalStatus="open" />);
    expect(getByText('Open')).toBeDefined();
  });
});
