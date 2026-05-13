import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { GradientText } from './gradient-text';

describe('<GradientText>', () => {
  it('renders children inside a span by default', () => {
    render(<GradientText>without opening another tool.</GradientText>);
    const el = screen.getByText('without opening another tool.');
    expect(el.tagName).toBe('SPAN');
  });

  it('applies sunset gradient inline style (D-22)', () => {
    render(<GradientText data-testid="gt">x</GradientText>);
    const el = screen.getByTestId('gt');
    expect(el.style.background).toContain('var(--gradient-sunset)');
    expect(
      el.style.webkitBackgroundClip || el.style.backgroundClip
    ).toContain('text');
    expect(el.style.webkitTextFillColor || el.style.color).toBe('transparent');
  });

  it('polymorphs via asChild (D-22)', () => {
    render(
      <GradientText asChild>
        <h1>Big headline</h1>
      </GradientText>
    );
    const el = screen.getByText('Big headline');
    expect(el.tagName).toBe('H1');
    expect(el.style.background).toContain('var(--gradient-sunset)');
  });

  it('has no axe violations', async () => {
    const { container } = render(<GradientText>accent</GradientText>);
    expect(await axe(container)).toHaveNoViolations();
  });
});
