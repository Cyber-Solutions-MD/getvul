// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

// Wave 2 (Plan 12-03 Task 1) creates this file. Import is the RED signal.
import { RiskRing } from './RiskRing';

const CIRC = 2 * Math.PI * 40;

function offsetFor(score: number) {
  return CIRC * (1 - score / 100);
}

describe('<RiskRing> (UX-04-03 — risk-score visualization)', () => {
  it('renders foreground arc for score 80 with correct stroke-dashoffset', () => {
    const { container } = render(<RiskRing score={80} />);
    const fg = container.querySelector('.ring-fg');
    expect(fg).toBeTruthy();
    expect(parseFloat(fg!.getAttribute('stroke-dashoffset')!)).toBeCloseTo(
      offsetFor(80),
      1,
    );
    expect(screen.getByTestId('risk-ring-score').textContent).toBe('80');
    expect(container.querySelector('[data-band="critical"]')).toBeTruthy();
  });

  it('renders score 20 with medium band tint (pink per D-R-01)', () => {
    const { container } = render(<RiskRing score={20} />);
    expect(container.querySelector('[data-band="medium"]')).toBeTruthy();
    expect(screen.getByTestId('risk-ring-score').className).toContain(
      'text-severity-medium',
    );
  });

  it('renders score 0 as empty ring + em-dash + "No exposures" caption', () => {
    const { container } = render(<RiskRing score={0} />);
    expect(container.querySelector('.ring-fg')).toBeNull();
    expect(screen.getByTestId('risk-ring-score').textContent).toBe('—');
    expect(screen.getByText('No exposures')).toBeInTheDocument();
  });

  it('renders score 100 as full ring with danger-tinted center', () => {
    const { container } = render(<RiskRing score={100} />);
    const fg = container.querySelector('.ring-fg');
    expect(fg).toBeTruthy();
    expect(parseFloat(fg!.getAttribute('stroke-dashoffset')!)).toBeCloseTo(
      0,
      1,
    );
    expect(screen.getByTestId('risk-ring-score').className).toContain(
      'text-severity-critical',
    );
    expect(screen.getByTestId('risk-ring-score').textContent).toBe('100');
  });

  it('renders score null as "Risk unavailable" + no arc + em-dash', () => {
    const { container } = render(<RiskRing score={null} />);
    expect(container.querySelector('.ring-fg')).toBeNull();
    expect(screen.getByText('Risk unavailable')).toBeInTheDocument();
    expect(screen.getByTestId('risk-ring-score').textContent).toBe('—');
  });

  it('always uses sunset gradient stroke regardless of band (locked_decisions item 5)', () => {
    const { container: c50 } = render(<RiskRing score={50} />);
    const { container: c80 } = render(<RiskRing score={80} />);
    expect(c50.querySelector('.ring-fg')!.getAttribute('stroke')).toBe(
      'url(#sunset-grad)',
    );
    expect(c80.querySelector('.ring-fg')!.getAttribute('stroke')).toBe(
      'url(#sunset-grad)',
    );
  });

  it('exposes aria-label for screen readers (score + band)', () => {
    render(<RiskRing score={80} />);
    expect(
      screen.getByRole('img', { name: /Risk score 80 — Critical/ }),
    ).toBeInTheDocument();
  });
});
