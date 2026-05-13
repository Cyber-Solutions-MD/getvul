import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';

// sanitizeNext lives in a sibling file because Next.js 15 rejects non-default
// exports from page files. Same semantics, just a different import path.
import LoginPage from './page';
import { sanitizeNext } from './sanitize-next';

// ----- next/navigation mock -------------------------------------------------
const replace = vi.fn();
let mockSearchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => ({
    get: (k: string) => mockSearchParams.get(k),
    toString: () => mockSearchParams.toString(),
  }),
}));

// ----- useAuth mock ---------------------------------------------------------
const login = vi.fn();
const loginSSO = vi.fn();
vi.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    login,
    loginSSO,
    logout: vi.fn(),
    token: null,
    register: vi.fn(),
  }),
}));

describe('sanitizeNext (open-redirect mitigation — Pitfall 10, T-09-05-01)', () => {
  it('null/empty returns /dashboard', () => {
    expect(sanitizeNext(null)).toBe('/dashboard');
    expect(sanitizeNext('')).toBe('/dashboard');
  });

  it('same-origin path passes through', () => {
    expect(sanitizeNext('/dashboard/vulnerabilities')).toBe('/dashboard/vulnerabilities');
    expect(sanitizeNext(encodeURIComponent('/dashboard/tickets/T-1'))).toBe('/dashboard/tickets/T-1');
  });

  it('blocks protocol-relative URL //evil.com', () => {
    expect(sanitizeNext('//evil.com')).toBe('/dashboard');
    expect(sanitizeNext(encodeURIComponent('//evil.com/path'))).toBe('/dashboard');
  });

  it('blocks absolute URL https://evil.com', () => {
    expect(sanitizeNext('https://evil.com')).toBe('/dashboard');
    expect(sanitizeNext(encodeURIComponent('https://evil.com'))).toBe('/dashboard');
  });

  it('blocks backslash trickery /\\evil', () => {
    expect(sanitizeNext('/\\evil.com')).toBe('/dashboard');
  });

  it('returns /dashboard on decode failure', () => {
    // Malformed percent-encoding triggers decodeURIComponent to throw.
    expect(sanitizeNext('%E0%A4%A')).toBe('/dashboard');
  });
});

describe('<LoginPage> — mode switching + SSO visibility (UX-01-02, UX-01-04)', () => {
  beforeEach(() => {
    replace.mockReset();
    login.mockReset();
    loginSSO.mockReset();
    mockSearchParams = new URLSearchParams();
  });

  it('login mode (default) shows SSO row + divider + email/password form', async () => {
    render(<LoginPage />);
    expect(
      await screen.findByRole('button', { name: 'Continue with Google' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Continue with Microsoft' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/or with email/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('clicking "Forgot password?" enters forgot mode and HIDES SSO row + divider (UX-01-04)', async () => {
    render(<LoginPage />);
    await userEvent.click(
      await screen.findByRole('button', { name: 'Forgot password?' }),
    );

    expect(
      screen.queryByRole('button', { name: 'Continue with Google' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Continue with Microsoft' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/or with email/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Reset your password' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Send reset link' }),
    ).toBeInTheDocument();
  });

  it('?reset=TOKEN enters reset mode and pre-fills the token (D-43)', async () => {
    mockSearchParams = new URLSearchParams('reset=abc123');
    render(<LoginPage />);
    expect(
      await screen.findByRole('heading', { name: 'Set a new password' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Continue with Google' }),
    ).not.toBeInTheDocument();
    const token = screen.getByLabelText('Reset token') as HTMLInputElement;
    expect(token.value).toBe('abc123');
  });
});

describe('<LoginPage> — autoComplete attrs per D-48', () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams();
  });

  it('login email field uses autoComplete=email + autoFocus', async () => {
    render(<LoginPage />);
    const email = await screen.findByLabelText('Email');
    expect(email).toHaveAttribute('autocomplete', 'email');
    expect(email).toHaveFocus();
  });

  it('login password field uses autoComplete=current-password', async () => {
    render(<LoginPage />);
    const password = await screen.findByLabelText('Password');
    expect(password).toHaveAttribute('autocomplete', 'current-password');
  });

  it('reset mode new-password field uses autoComplete=new-password and token uses autoComplete=off', async () => {
    mockSearchParams = new URLSearchParams('reset=tok');
    render(<LoginPage />);
    const np = await screen.findByLabelText('New password');
    expect(np).toHaveAttribute('autocomplete', 'new-password');
    const token = screen.getByLabelText('Reset token');
    expect(token).toHaveAttribute('autocomplete', 'off');
  });
});

describe('<LoginPage> — UX-01-05 ErrorAlert classes on 401', () => {
  beforeEach(() => {
    replace.mockReset();
    login.mockReset();
    mockSearchParams = new URLSearchParams();
  });

  it('shows ErrorAlert with bg-danger-soft + border-danger when login throws 401 (D-49)', async () => {
    login.mockRejectedValueOnce({ status: 401, message: 'unused-by-D49-generic' });
    render(<LoginPage />);

    await userEvent.type(await screen.findByLabelText('Email'), 'a@b.co');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Email or password is incorrect.');
    expect(alert.className).toMatch(/bg-danger-soft/);
    expect(alert.className).toMatch(/border-danger/);
  });
});

describe('<LoginPage> — Pitfall 9 anti-enumeration forgot-password copy', () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams();
    // Stub fetch so the forgot-password POST resolves cleanly.
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response),
    ) as unknown as typeof fetch;
  });

  it('shows generic confirmation regardless of backend response', async () => {
    render(<LoginPage />);
    await userEvent.click(
      await screen.findByRole('button', { name: 'Forgot password?' }),
    );
    await userEvent.type(screen.getByLabelText('Email'), 'whoever@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }));

    expect(
      await screen.findByText(
        'If that email is registered, a reset token is on its way.',
      ),
    ).toBeInTheDocument();
  });
});

describe('<LoginPage> — D-51 SSO 5xx surfaces ErrorAlert (T-09-05-07 mitigation)', () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams();
    loginSSO.mockReset();
  });

  it('SSO failure (loginSSO throws D-51 copy) renders ErrorAlert with D-51 copy', async () => {
    // The actual HEAD-equivalent pre-flight lives inside loginSSO (lib/auth.tsx —
    // the JSON GET catches non-2xx before navigation). At the /login level we
    // mock loginSSO to throw the D-51 Error — proving the surfacing path works
    // end-to-end into <ErrorAlert>.
    loginSSO.mockRejectedValueOnce(
      new Error('Sign-in with Google is temporarily unavailable. Try email instead.'),
    );

    render(<LoginPage />);
    await userEvent.click(
      await screen.findByRole('button', { name: 'Continue with Google' }),
    );

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(
      'Sign-in with Google is temporarily unavailable. Try email instead.',
    );
    expect(alert.className).toMatch(/bg-danger-soft/);
    expect(alert.className).toMatch(/border-danger/);
  });

  it('keeps the H1 tagline reachable to assistive tech (LeftPanel a11y fix; WCAG 2 SC 1.3.1)', async () => {
    render(<LoginPage />);
    await screen.findByLabelText('Email');
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1).toHaveTextContent(/See your security posture/);
  });
});

describe('<LoginPage> — axe', () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams();
  });

  it('login mode has no accessibility violations', async () => {
    const { container } = render(<LoginPage />);
    await screen.findByLabelText('Email');
    expect(await axe(container)).toHaveNoViolations();
  });
});
