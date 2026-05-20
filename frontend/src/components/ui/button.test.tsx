import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { Button } from './button';

describe('<Button>', () => {
  it('renders default state with accessible name', () => {
    render(<Button>Sign in</Button>);
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('applies cta variant classes (gradient + glow per visual-language.md)', () => {
    render(<Button variant="cta">Start triage</Button>);
    const btn = screen.getByRole('button', { name: 'Start triage' });
    expect(btn.className).toMatch(/bg-gradient-sunset/);
    expect(btn.className).toMatch(/shadow-glow-cta/);
  });

  it('shows loading state with aria-busy, disabled, and loadingText (D-24, UX-01-03)', () => {
    render(
      <Button loading loadingText="Signing in…">
        Sign in
      </Button>
    );
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toBeDisabled();
    expect(btn).toHaveTextContent('Signing in…');
    expect(btn).not.toHaveTextContent('Sign in'); // children swapped
  });

  it('honors disabled prop', () => {
    render(<Button disabled>Click</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('reaches focus-visible via keyboard tab', async () => {
    render(<Button>Sign in</Button>);
    await userEvent.tab();
    const btn = screen.getByRole('button');
    expect(btn).toHaveFocus();
    expect(btn.className).toMatch(/focus-visible:ring-violet/);
  });

  it('renders as polymorphic anchor with asChild (D-23)', () => {
    render(
      <Button asChild>
        <a href="/dashboard">Go</a>
      </Button>
    );
    const link = screen.getByRole('link', { name: 'Go' });
    expect(link).toHaveAttribute('href', '/dashboard');
    expect(link.className).toMatch(/inline-flex/); // base button classes applied to anchor
  });

  it('renders leftIcon and rightIcon when provided (D-25)', () => {
    render(
      <Button
        leftIcon={<span data-testid="left">L</span>}
        rightIcon={<span data-testid="right">R</span>}
      >
        Label
      </Button>
    );
    expect(screen.getByTestId('left')).toBeInTheDocument();
    expect(screen.getByTestId('right')).toBeInTheDocument();
  });

  it('has no axe violations across variants and states (UX-F-04)', async () => {
    const { container } = render(
      <>
        <Button variant="cta">Start triage</Button>
        <Button variant="secondary">Snooze 1h</Button>
        <Button variant="ghost">View trace</Button>
        <Button variant="icon" aria-label="Notifications">
          N
        </Button>
        <Button loading loadingText="Signing in…">
          Sign in
        </Button>
        <Button disabled>Disabled</Button>
      </>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
