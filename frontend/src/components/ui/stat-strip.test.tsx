import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { StatStrip } from './stat-strip';
import { Stat } from './stat';

describe('<StatStrip>', () => {
  it('wraps children in a grid with 4-tile desktop layout (D-P-03 + D-M-02)', () => {
    render(
      <StatStrip data-testid="strip">
        <Stat label="a" value={1} />
        <Stat label="b" value={2} />
        <Stat label="c" value={3} />
        <Stat label="d" value={4} />
      </StatStrip>
    );
    const strip = screen.getByTestId('strip');
    expect(strip.className).toMatch(/\bgrid\b/);
    expect(strip.className).toMatch(/xl:grid-cols-4/);
  });

  it('with 2 children, desktop ladder caps at 2 columns', () => {
    render(
      <StatStrip data-testid="strip">
        <Stat label="a" value={1} />
        <Stat label="b" value={2} />
      </StatStrip>
    );
    const strip = screen.getByTestId('strip');
    expect(strip.className).toMatch(/xl:grid-cols-2/);
  });

  it('with 1 child, desktop ladder is 1 column', () => {
    render(
      <StatStrip data-testid="strip">
        <Stat label="a" value={1} />
      </StatStrip>
    );
    const strip = screen.getByTestId('strip');
    expect(strip.className).toMatch(/xl:grid-cols-1/);
  });

  it('with 5 children, desktop ladder caps at 4 columns (D-M-02 cap)', () => {
    render(
      <StatStrip data-testid="strip">
        <Stat label="a" value={1} />
        <Stat label="b" value={2} />
        <Stat label="c" value={3} />
        <Stat label="d" value={4} />
        <Stat label="e" value={5} />
      </StatStrip>
    );
    const strip = screen.getByTestId('strip');
    expect(strip.className).toMatch(/xl:grid-cols-4/);
  });

  it('has responsive ladder grid-cols-1 → md:grid-cols-2 → xl:grid-cols-N (D-M-02)', () => {
    render(
      <StatStrip data-testid="strip">
        <Stat label="a" value={1} />
        <Stat label="b" value={2} />
        <Stat label="c" value={3} />
        <Stat label="d" value={4} />
      </StatStrip>
    );
    const strip = screen.getByTestId('strip');
    expect(strip.className).toMatch(/grid-cols-1/);
    expect(strip.className).toMatch(/md:grid-cols-2/);
  });

  it('merges consumer className', () => {
    render(
      <StatStrip className="my-custom" data-testid="strip">
        <Stat label="a" value={1} />
      </StatStrip>
    );
    expect(screen.getByTestId('strip').className).toMatch(/my-custom/);
  });

  it('has no axe violations (D-Test-01)', async () => {
    const { container } = render(
      <StatStrip>
        <Stat label="Critical · open" value={3} delta={1} deltaIsGood="down" />
        <Stat label="SLA · at risk" value={12} delta={-2} deltaIsGood="down" />
        <Stat label="MTTR · 30d" value="4.2d" delta={null} />
        <Stat label="CISA KEV" value={5} delta={0} deltaIsGood="down" />
      </StatStrip>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
