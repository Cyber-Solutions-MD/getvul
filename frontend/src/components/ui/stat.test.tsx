import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { ShieldAlert } from 'lucide-react';
import { Stat } from './stat';

describe('<Stat>', () => {
  it('renders label, value, and hint (D-P-02)', () => {
    render(<Stat label="Critical · open" value={3} hint="vs goal 0" />);
    expect(screen.getByText('Critical · open')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('vs goal 0')).toBeInTheDocument();
  });

  it("delta > 0 with deltaIsGood='down' renders danger color + TrendingUp icon (D-S-03)", () => {
    render(
      <Stat
        label="Critical · open"
        value={3}
        delta={1}
        deltaIsGood="down"
        data-testid="stat"
      />
    );
    // The delta block contains the signed number and 'from yesterday' default
    const deltaBlock = screen.getByText(/\+1/);
    expect(deltaBlock.className).toMatch(/text-danger/);
    // TrendingUp icon — lucide renders as svg with class .lucide-trending-up
    const svg = deltaBlock.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('class') || '').toMatch(/trending-up/i);
  });

  it("default deltaSuffix is 'from yesterday' (Warning 13)", () => {
    render(<Stat label="x" value={5} delta={2} deltaIsGood="down" />);
    expect(screen.getByText(/from yesterday/)).toBeInTheDocument();
  });

  it("custom deltaSuffix appears in delta block (Warning 13)", () => {
    render(
      <Stat
        label="x"
        value={5}
        delta={2}
        deltaIsGood="down"
        deltaSuffix="from last hour"
      />
    );
    expect(screen.getByText(/from last hour/)).toBeInTheDocument();
  });

  it("delta < 0 with deltaIsGood='down' renders success color + TrendingDown icon (D-S-03)", () => {
    render(<Stat label="x" value={3} delta={-2} deltaIsGood="down" />);
    const deltaBlock = screen.getByText(/-2/);
    expect(deltaBlock.className).toMatch(/text-success/);
    const svg = deltaBlock.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('class') || '').toMatch(/trending-down/i);
  });

  it("delta=null renders 'Δ —' — Pitfall 8 / D-S-04 (not spinner, not empty)", () => {
    const { container } = render(
      <Stat label="MTTR · 30d" value="4.2d" delta={null} />
    );
    expect(container.textContent).toContain('Δ —');
  });

  it("delta=0 renders no arrow (direction='flat')", () => {
    const { container } = render(
      <Stat label="CISA KEV" value={5} delta={0} deltaIsGood="down" />
    );
    // No TrendingUp / TrendingDown SVGs in the rendered tree
    const svgs = container.querySelectorAll('svg');
    const hasArrow = Array.from(svgs).some((s) => {
      const cls = s.getAttribute('class') || '';
      return /trending-up|trending-down/i.test(cls);
    });
    expect(hasArrow).toBe(false);
  });

  it('icon prop renders top-right when provided (D-S-05)', () => {
    render(
      <Stat
        label="x"
        value={1}
        icon={<ShieldAlert data-testid="icon" />}
      />
    );
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('value rendered with font-mono and tabular-nums (D-S)', () => {
    render(<Stat label="x" value={42} data-testid="stat" />);
    const valueEl = screen.getByText('42');
    expect(valueEl.className).toMatch(/font-mono/);
    expect(valueEl.className).toMatch(/tabular-nums/);
  });

  it('has no axe violations (D-Test-01)', async () => {
    const { container } = render(
      <Stat
        label="Critical · open"
        value={3}
        delta={1}
        deltaIsGood="down"
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
