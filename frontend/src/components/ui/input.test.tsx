import * as React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { useForm } from 'react-hook-form';
import { Input } from './input';
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
} from './form';

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

  // WR-01 regression: when a password <Input> is composed through <FormControl>,
  // the Radix <Slot>-forwarded id / aria-invalid / aria-describedby must land on
  // the real <input>, NOT the eye-toggle wrapper <div>. The password branch
  // spreads {...props} (which carries the Slot-injected attributes) onto the
  // inner <input>, and forwardRef sends the ref there too, so the <label htmlFor>
  // association and the aria-[invalid=true]:border-danger styling both target the
  // input. This test locks that behavior.
  it('forwards FormControl a11y attributes onto the inner password <input> (WR-01)', () => {
    function Harness() {
      const form = useForm({ defaultValues: { password: '' } });
      React.useEffect(() => {
        form.setError('password', { type: 'manual', message: 'Required' });
      }, [form]);
      return (
        <Form {...form}>
          <form>
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
                  <FormControl>
                    <Input type="password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </form>
        </Form>
      );
    }

    render(<Harness />);
    const labelled = screen.getByLabelText('Password');
    // The label must resolve to the <input>, not the wrapper <div>.
    expect(labelled.tagName).toBe('INPUT');
    // A forced Zod/RHF error must set aria-invalid on that same <input> so the
    // aria-[invalid=true]:border-danger selector matches.
    expect(labelled).toHaveAttribute('aria-invalid', 'true');
    // id + aria-describedby must also be on the input (label association + SR).
    expect(labelled.getAttribute('id')).toMatch(/-form-item$/);
    expect(labelled.getAttribute('aria-describedby')).toContain('-form-item-message');
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
