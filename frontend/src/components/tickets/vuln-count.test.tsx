import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { VulnCount } from './vuln-count';

describe('VulnCount', () => {
  it('total=3 crit=2 high=1 → renders T with text-text, C with text-[var(--color-severity-critical-on-soft)], H with text-[var(--color-severity-high-on-soft)]', () => {
    const { container } = render(<VulnCount total={3} critical={2} high={1} />);
    const spans = container.querySelectorAll('span');
    // Expect three colored spans (total, critical, high)
    const totalSpan = Array.from(spans).find(s => s.textContent === '3');
    const critSpan = Array.from(spans).find(s => s.textContent === '·2');
    const highSpan = Array.from(spans).find(s => s.textContent === '·1');
    expect(totalSpan).toBeDefined();
    expect(totalSpan?.className).toContain('text-text');
    expect(critSpan).toBeDefined();
    expect(critSpan?.className).toContain('text-[var(--color-severity-critical-on-soft)]');
    expect(highSpan).toBeDefined();
    expect(highSpan?.className).toContain('text-[var(--color-severity-high-on-soft)]');
  });

  it('total=3 crit=0 high=0 → zeros are explicit (not hidden)', () => {
    const { container } = render(<VulnCount total={3} critical={0} high={0} />);
    const text = container.textContent ?? '';
    expect(text).toContain('·0');
  });

  it('total=0 → renders em dash "—" and no breakdown', () => {
    const { container } = render(<VulnCount total={0} critical={0} high={0} />);
    const text = container.textContent ?? '';
    expect(text).toBe('—');
    // No breakdown spans when total is 0
    expect(container.querySelectorAll('span').length).toBe(1);
  });

  it('total=150 → renders "99+" for total', () => {
    const { container } = render(<VulnCount total={150} critical={10} high={5} />);
    const text = container.textContent ?? '';
    expect(text).toContain('99+');
  });

  it('total=99 → renders "99" (not capped)', () => {
    const { container } = render(<VulnCount total={99} critical={1} high={1} />);
    const text = container.textContent ?? '';
    expect(text).toContain('99');
    expect(text).not.toContain('99+');
  });

  it('total=100 → renders "99+"', () => {
    const { container } = render(<VulnCount total={100} critical={0} high={0} />);
    const text = container.textContent ?? '';
    expect(text).toContain('99+');
  });
});
