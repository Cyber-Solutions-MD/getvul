import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { Input } from './input';

describe('<Input>', () => {
  it('renders text input by default', () => {
    render(<Input aria-label="Email" type="email" placeholder="you@company.com" />);
    const input = screen.getByLabelText('Email');
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('type', 'email');
  });

  it('exposes password eye-toggle button with aria-pressed when type=password (D-27)', () => {
    render(<Input aria-label="Password" type="password" />);
    const toggle = screen.getByRole('button', { name: 'Show password' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
  });

  it('toggles password visibility on click; updates aria-label and aria-pressed (D-27)', async () => {
    render(<Input aria-label="Password" type="password" defaultValue="secret" />);
    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('type', 'password');

    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');
    const toggle = screen.getByRole('button', { name: 'Hide password' });
    expect(toggle).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(toggle);
    expect(input).toHaveAttribute('type', 'password');
  });

  it('flips to border-danger when aria-invalid is true (D-28)', () => {
    render(<Input aria-label="Email" type="email" aria-invalid="true" />);
    const input = screen.getByLabelText('Email');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input.className).toMatch(/aria-\[invalid=true\]:border-danger/);
  });

  it('honors disabled prop', () => {
    render(<Input aria-label="Email" disabled />);
    expect(screen.getByLabelText('Email')).toBeDisabled();
  });

  it('has no axe violations (UX-F-04)', async () => {
    const { container } = render(
      <>
        <label htmlFor="e">Email</label>
        <Input id="e" type="email" />
        <label htmlFor="p">Password</label>
        <Input id="p" type="password" />
        <label htmlFor="d">Disabled</label>
        <Input id="d" disabled />
      </>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
