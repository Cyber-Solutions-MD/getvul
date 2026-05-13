import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { SsoButton } from './sso-button';

describe('<SsoButton>', () => {
  it('renders Google provider with verbatim D-46 label', () => {
    render(<SsoButton provider="google" />);
    expect(
      screen.getByRole('button', { name: 'Continue with Google' })
    ).toBeInTheDocument();
  });

  it('renders Microsoft provider with verbatim D-46 label', () => {
    render(<SsoButton provider="microsoft" />);
    expect(
      screen.getByRole('button', { name: 'Continue with Microsoft' })
    ).toBeInTheDocument();
  });

  it('forwards onClick prop', async () => {
    const handler = vi.fn();
    render(<SsoButton provider="google" onClick={handler} />);
    await userEvent.click(screen.getByRole('button'));
    expect(handler).toHaveBeenCalledOnce();
  });

  it('has no axe violations', async () => {
    const { container } = render(
      <>
        <SsoButton provider="google" />
        <SsoButton provider="microsoft" />
      </>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
