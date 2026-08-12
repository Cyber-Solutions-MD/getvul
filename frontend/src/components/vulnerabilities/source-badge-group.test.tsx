import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { SourceBadgeGroup } from './source-badge-group';

describe('SourceBadgeGroup (SRC-01 non-overclaiming provenance)', () => {
  it('renders_single_source_neutral: one source renders ONE mark, no "confirmed"/"verified" copy, no corroboration tint', () => {
    const { container } = render(<SourceBadgeGroup sources={['QUALYS']} count={1} />);
    expect(container.querySelectorAll('[role="img"]')).toHaveLength(1);
    expect(container.textContent ?? '').not.toMatch(/confirmed|verified/i);
    // No corroboration wrapper and no --color-success tint anywhere.
    expect(container.querySelector('[data-source-badge-group="multi"]')).toBeNull();
    expect(container.innerHTML).not.toContain('--color-success');
    expect(container.querySelector('[data-source-badge-group="single"]')).not.toBeNull();
  });

  it('renders_multi_source_corroborated: 2 sources render 2 marks + "2 sources" label + the corroboration tint', () => {
    const { container, getByText } = render(
      <SourceBadgeGroup sources={['QUALYS', 'RAPID7']} count={2} />,
    );
    expect(container.querySelectorAll('[role="img"]')).toHaveLength(2);
    expect(getByText('2 sources')).toBeInTheDocument();
    const wrapper = container.querySelector('[data-source-badge-group="multi"]') as HTMLElement;
    expect(wrapper).not.toBeNull();
    expect(wrapper.style.background).toContain('rgba(74, 222, 128');
    const label = getByText('2 sources') as HTMLElement;
    expect(label.style.color).toContain('--color-success');
  });

  it('marks_use_css_var_not_hex: every mark background references --gradient-provider- (never raw hex), no <img>', () => {
    const { container } = render(<SourceBadgeGroup sources={['QUALYS', 'RAPID7']} count={2} />);
    const marks = Array.from(container.querySelectorAll<HTMLElement>('[role="img"]'));
    expect(marks.length).toBeGreaterThan(0);
    for (const mark of marks) {
      expect(mark.style.background).toContain('--gradient-provider-');
      expect(mark.style.background).not.toMatch(/#[0-9a-fA-F]{3,6}/);
    }
    expect(container.querySelectorAll('img')).toHaveLength(0);
    expect(container.innerHTML).not.toMatch(/\.svg|\.png|logo/i);
  });

  it('unknown_source_neutral_fallback: an unrecognized code renders a neutral fallback mark, not a crash', () => {
    const { container } = render(<SourceBadgeGroup sources={['JAMF']} count={1} />);
    const marks = container.querySelectorAll('[role="img"]');
    expect(marks).toHaveLength(1);
    const mark = marks[0] as HTMLElement;
    expect(mark.getAttribute('aria-label')).toBe('JAMF');
    // Neutral fallback — no gradient var, no wrong-provider color leak.
    expect(mark.style.background).not.toContain('--gradient-provider-');
    expect(mark.textContent).toBe('J');
  });

  it('zero_sources_no_crash: sources=[] renders a neutral empty state, never throws', () => {
    expect(() => render(<SourceBadgeGroup sources={[]} count={0} />)).not.toThrow();
    const { container } = render(<SourceBadgeGroup sources={[]} count={0} />);
    expect(container.querySelectorAll('[role="img"]')).toHaveLength(0);
    expect(container.querySelector('[data-source-badge-group="empty"]')).not.toBeNull();
    expect(container.textContent).toContain('—');
  });

  it('count falls back to sources.length when omitted', () => {
    const { container, getByText } = render(<SourceBadgeGroup sources={['QUALYS', 'NESSUS']} />);
    expect(getByText('2 sources')).toBeInTheDocument();
    expect(container.querySelectorAll('[role="img"]')).toHaveLength(2);
  });
});
