import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Wave 0 RED scaffold for Phase 6 (PROD-06-03): the forced first-login
// password-change gate + the /change-password rotation page. Neither the gate
// branch in lib/auth.tsx nor the ./page module exist yet, so:
//   - the redirect-gate case fails because AuthProvider does not yet call
//     router.replace('/change-password') for a flagged user;
//   - the form/error/success cases fail because `import Page from './page'`
//     resolves to a not-yet-created module (import error = RED).
// No suite modifiers or placeholders — every case runs and fails for real
// until Wave 3 lands.

// ----- next/navigation mock -------------------------------------------------
const replace = vi.fn();
let mockPathname = '/dashboard';
let mockSearchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => mockPathname,
  useSearchParams: () => ({
    get: (k: string) => mockSearchParams.get(k),
    toString: () => mockSearchParams.toString(),
  }),
}));

// The rotation page (Wave 3). Importing it now is a RED trigger until the file
// exists; the form/error/success cases exercise it directly.
import Page from './page';
// AuthProvider owns the redirect gate under test (Wave 3 adds the
// must_change_password branch to its route-guard useEffect).
import { AuthProvider, useAuth } from '@/lib/auth';

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('change-password', () => {
  beforeEach(() => {
    replace.mockReset();
    mockPathname = '/dashboard';
    mockSearchParams = new URLSearchParams();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('redirect gate fires when must_change_password is true', async () => {
    // A stored token makes AuthProvider hydrate the session via /auth/me;
    // the flagged user must be pushed to /change-password by the guard.
    localStorage.setItem('getvul_token', 'flagged-token');
    global.fetch = vi.fn((url: string) => {
      if (String(url).includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 'u1',
              email: 'admin@getvul.local',
              display_name: 'Admin',
              avatar_url: null,
              role: 'OWNER',
              tenant_id: 't1',
              tenant_name: 'GetVul',
              must_change_password: true,
            }),
        } as Response);
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
    }) as unknown as typeof fetch;

    renderWithClient(
      <AuthProvider>
        <div>protected content</div>
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith('/change-password'),
    );
  });

  it('redirect gate fires after a fresh SPA login (no reload)', async () => {
    // SC#4 regression (code review WR-01): the flagged user comes in through the
    // primary login path — no stored token, so no mount /auth/me. The gate must
    // arm from the /auth/login response's UserInfo, which now carries
    // must_change_password. Before the fix, UserInfo lacked the field and the
    // user landed on /dashboard into a wall of 403s.
    global.fetch = vi.fn((url: string) => {
      if (String(url).includes('/auth/login')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              access_token: 'flagged-access',
              refresh_token: 'flagged-refresh',
              user: {
                id: 'u1',
                email: 'admin@getvul.local',
                display_name: 'Admin',
                avatar_url: null,
                role: 'OWNER',
                tenant_id: 't1',
                tenant_name: 'GetVul',
                must_change_password: true,
              },
            }),
        } as Response);
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
    }) as unknown as typeof fetch;

    function LoginTrigger() {
      const { login } = useAuth();
      return (
        <button onClick={() => login('admin@getvul.local', 'Admin123!')}>
          sign in
        </button>
      );
    }

    renderWithClient(
      <AuthProvider>
        <LoginTrigger />
      </AuthProvider>,
    );

    await userEvent.click(await screen.findByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith('/change-password'),
    );
  });

  it('renders the rotation form', async () => {
    renderWithClient(<Page />);
    expect(await screen.findByLabelText(/current password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^new password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm/i)).toBeInTheDocument();
  });

  it('shows an error on wrong current password', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 400,
        json: () =>
          Promise.resolve({ detail: 'Current password is incorrect' }),
      } as Response),
    ) as unknown as typeof fetch;

    renderWithClient(<Page />);
    await userEvent.type(
      await screen.findByLabelText(/current password/i),
      'WrongPass1!',
    );
    await userEvent.type(screen.getByLabelText(/^new password/i), 'NewPassw0rd!x');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewPassw0rd!x');
    await userEvent.click(screen.getByRole('button', { name: /change|update|save/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/current password is incorrect/i);
  });

  it('redirects to /dashboard on success', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            access_token: 'fresh-access',
            refresh_token: 'fresh-refresh',
          }),
      } as Response),
    ) as unknown as typeof fetch;

    renderWithClient(<Page />);
    await userEvent.type(
      await screen.findByLabelText(/current password/i),
      'Admin123!',
    );
    await userEvent.type(screen.getByLabelText(/^new password/i), 'NewPassw0rd!x');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewPassw0rd!x');
    await userEvent.click(screen.getByRole('button', { name: /change|update|save/i }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/dashboard'));
  });
});
