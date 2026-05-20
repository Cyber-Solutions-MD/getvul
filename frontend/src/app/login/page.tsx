'use client';
import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { useAuth } from '@/lib/auth';
import { loginSchema, forgotSchema, resetSchema } from '@/lib/validation/auth';
import { sanitizeNext } from './sanitize-next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
} from '@/components/ui/form';
import { SsoButton } from '@/components/ui/sso-button';
import { GradientText } from '@/components/ui/gradient-text';
import { ErrorAlert } from '@/components/auth/error-alert';

type Mode = 'login' | 'forgot' | 'reset';

// Hard-coded sample CVE rows for the left-panel product peek (D-44).
// Real public KEV references; mono lowercase fake hostnames.
const SAMPLE_VULNS = [
  { cve: 'CVE-2024-3094',  title: 'xz-utils backdoor',     host: 'prod-db-01',   cvss: 10.0, severity: 'critical' as const },
  { cve: 'CVE-2021-44228', title: 'Log4Shell RCE',         host: 'auth-api-02',  cvss: 10.0, severity: 'critical' as const },
  { cve: 'CVE-2022-22965', title: 'Spring4Shell',          host: 'web-edge-04',  cvss:  9.8, severity: 'critical' as const },
  { cve: 'CVE-2023-23397', title: 'Outlook NTLM leak',     host: 'mail-relay-1', cvss:  9.8, severity: 'high'     as const },
];

export default function LoginPage() {
  // Pitfall 8: useSearchParams() requires a Suspense boundary to stream-render
  // safely under Next 15 + React 19. Without it the build emits a warning and
  // the route falls back to fully client-rendered.
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginPanels />
    </Suspense>
  );
}

function LoginFallback() {
  return (
    <main className="min-h-screen bg-bg grid place-items-center text-text-faint text-sm">
      Loading…
    </main>
  );
}

function LoginPanels() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, login, loginSSO } = useAuth();

  // Mode state machine per D-43. Enter 'reset' if URL has ?reset=TOKEN.
  const resetToken = searchParams.get('reset');
  const [mode, setMode] = useState<Mode>(resetToken ? 'reset' : 'login');
  const [authError, setAuthError] = useState<string | null>(null);
  const [forgotSent, setForgotSent] = useState(false);

  // Bounce already-authed users to ?next= (validated), otherwise /dashboard.
  // D-50 + Pitfall 10 — open-redirect mitigation via sanitizeNext.
  useEffect(() => {
    if (user) {
      router.replace(sanitizeNext(searchParams.get('next')));
    }
  }, [user, router, searchParams]);

  return (
    <main className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-bg text-text">
      <LeftPanel />
      <RightPanel
        mode={mode}
        setMode={(m) => {
          setMode(m);
          setAuthError(null);
          setForgotSent(false);
        }}
        authError={authError}
        setAuthError={setAuthError}
        forgotSent={forgotSent}
        setForgotSent={setForgotSent}
        login={login}
        loginSSO={loginSSO}
        router={router}
        searchParams={searchParams}
        resetToken={resetToken}
      />
    </main>
  );
}

function LeftPanel() {
  // Left panel — bg-gradient-mesh drifting (Wave 0 keyframes) + D-45 verbatim
  // marketing + D-44 hard-coded vuln-peek rows. The <section> itself is NOT
  // aria-hidden — that would swallow the H1 tagline (the product's elevator
  // pitch) from assistive tech and violate WCAG 2 SC 1.3.1. Only the truly
  // decorative children (gradient mesh, severity color glyphs, peek rows) are
  // aria-hidden.
  return (
    <section className="hidden lg:flex relative overflow-hidden bg-bg-darker">
      {/* Drifting mesh — decorative; aria-hidden so SR doesn't announce it */}
      <div
        aria-hidden
        className="absolute inset-0 bg-gradient-mesh opacity-80 animate-gradient-drift"
      />
      <div className="relative z-10 flex flex-col justify-between px-12 py-16 w-full">
        <div>
          {/* D-45 verbatim — tagline with GradientText accent on the second clause.
              Reachable by SR via H1 landmark. */}
          <h1 className="text-5xl font-extrabold leading-tight tracking-tighter text-text">
            See your security posture{' '}
            <GradientText>without opening another tool.</GradientText>
          </h1>
          <p className="mt-4 max-w-md text-base text-text-muted">
            One dashboard. Every scanner. Real ownership. Tickets out, fewer meetings.
          </p>
        </div>

        {/* Decorative product peek — vuln-peek rows are illustrative content,
            not part of the page's primary information. Hide from assistive tech
            so the form is the focus and the H1 is the landmark. */}
        <div aria-hidden className="mt-12 space-y-2 max-w-md">
          {SAMPLE_VULNS.map((v) => (
            <div
              key={v.cve}
              className="flex items-center gap-3 rounded-lg border border-border-subtle bg-surface-glass backdrop-blur-sm px-3 py-2.5 text-sm"
            >
              <span
                aria-hidden
                className={
                  v.severity === 'critical'
                    ? 'inline-block h-2.5 w-2.5 rounded-sm bg-severity-critical'
                    : 'inline-block h-2.5 w-2.5 rounded-sm bg-severity-high'
                }
              />
              <span className="font-mono text-text">{v.cve}</span>
              <span className="flex-1 truncate text-text-muted">{v.title}</span>
              <span className="font-mono text-text-faint text-xs">{v.host}</span>
              <span className="font-mono tabular-nums text-text text-xs">
                {v.cvss.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

interface RightPanelProps {
  mode: Mode;
  setMode: (m: Mode) => void;
  authError: string | null;
  setAuthError: (e: string | null) => void;
  forgotSent: boolean;
  setForgotSent: (v: boolean) => void;
  login: ReturnType<typeof useAuth>['login'];
  loginSSO: ReturnType<typeof useAuth>['loginSSO'];
  router: ReturnType<typeof useRouter>;
  searchParams: ReturnType<typeof useSearchParams>;
  resetToken: string | null;
}

function RightPanel(props: RightPanelProps) {
  const { mode } = props;

  return (
    <section className="flex items-center justify-center px-6 py-12 lg:px-12">
      <div className="w-full max-w-sm space-y-6">
        {/* Per-mode heading per D-43 */}
        <div>
          <h2 className="text-2xl font-bold text-text">
            {mode === 'login' && 'Sign in'}
            {mode === 'forgot' && 'Reset your password'}
            {mode === 'reset' && 'Set a new password'}
          </h2>
          {mode === 'login' && (
            <p className="mt-1 text-sm text-text-muted">
              Welcome back. Use your work account.
            </p>
          )}
          {mode === 'forgot' && (
            <p className="mt-1 text-sm text-text-muted">
              Enter the email tied to your account.
            </p>
          )}
          {mode === 'reset' && (
            <p className="mt-1 text-sm text-text-muted">
              Pick a strong one. Min 8 characters.
            </p>
          )}
        </div>

        {/* Form-level error per D-28, UX-01-05 */}
        {props.authError && <ErrorAlert>{props.authError}</ErrorAlert>}

        {/* SSO row — login mode only per D-43, UX-01-04 */}
        {mode === 'login' && <SsoRow {...props} />}

        {/* Mode-specific form */}
        {mode === 'login' && <LoginForm {...props} />}
        {mode === 'forgot' && <ForgotForm {...props} />}
        {mode === 'reset' && <ResetForm {...props} />}

        {/* Mode-switch links per D-47 — forgot has an explicit "back" link;
            reset is token-gated so has no in-app entry path. */}
        {mode === 'forgot' && (
          <button
            type="button"
            className="block text-sm text-text-muted hover:text-text underline-offset-4 hover:underline"
            onClick={() => props.setMode('login')}
          >
            Back to sign in
          </button>
        )}
      </div>
    </section>
  );
}

// D-46 UI label "Microsoft" maps to backend OIDC route name 'azure' — backend
// route is /auth/login/azure (existing v1 contract). Promoted to a helper so
// reviewers have one obvious place to look for the indirection.
const toBackendProvider = (
  uiProvider: 'google' | 'microsoft',
): 'google' | 'azure' => (uiProvider === 'microsoft' ? 'azure' : 'google');

function SsoRow({ loginSSO, setAuthError }: RightPanelProps) {
  async function handleSso(uiProvider: 'google' | 'microsoft') {
    setAuthError(null);
    // D-46 UI label "Microsoft" maps to backend OIDC route name 'azure' — never
    // pass 'microsoft' to loginSSO().
    const backendProvider = toBackendProvider(uiProvider);
    try {
      await loginSSO(backendProvider);
    } catch (e: unknown) {
      // D-51: loginSSO now throws with the verbatim user-facing message
      const msg =
        e instanceof Error
          ? e.message
          : `Sign-in with ${uiProvider === 'google' ? 'Google' : 'Microsoft'} is temporarily unavailable. Try email instead.`;
      setAuthError(msg);
    }
  }

  return (
    <>
      <div className="space-y-2.5">
        <SsoButton provider="google" onClick={() => handleSso('google')} />
        <SsoButton provider="microsoft" onClick={() => handleSso('microsoft')} />
      </div>
      {/* `or with email` divider per D-32, UX-01-02. One-off, not a primitive. */}
      <div className="flex items-center gap-3 text-xs uppercase tracking-wider text-text-faint">
        <span className="h-px flex-1 bg-border-subtle" />
        <span>or with email</span>
        <span className="h-px flex-1 bg-border-subtle" />
      </div>
    </>
  );
}

function LoginForm({
  login,
  setAuthError,
  router,
  searchParams,
  setMode,
}: RightPanelProps) {
  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    mode: 'onSubmit', // D-53
    defaultValues: { email: '', password: '' },
  });

  async function onSubmit(values: z.infer<typeof loginSchema>) {
    setAuthError(null);
    try {
      await login(values.email, values.password);
      // Honor ?next= with open-redirect mitigation per D-50 + Pitfall 10.
      const dest = sanitizeNext(searchParams.get('next'));
      router.replace(dest);
    } catch (e: unknown) {
      // D-49: 401 → generic; other 4xx → pass-through backend message.
      const err = e as { status?: number; message?: string } | undefined;
      const status = err?.status;
      if (status === 401) {
        setAuthError('Email or password is incorrect.');
      } else {
        setAuthError(err?.message ?? 'Sign-in failed. Try again in a moment.');
      }
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  placeholder="you@company.com"
                  autoFocus
                  autoComplete="email"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Password</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  autoComplete="current-password"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* D-47: right-aligned "Forgot password?" link below password */}
        <div className="flex justify-end">
          <button
            type="button"
            className="text-sm text-text-muted hover:text-text underline-offset-4 hover:underline"
            onClick={() => setMode('forgot')}
          >
            Forgot password?
          </button>
        </div>

        {/* D-52: per-mode CTA copy */}
        <Button
          type="submit"
          variant="cta"
          size="lg"
          className="w-full"
          loading={form.formState.isSubmitting}
          loadingText="Signing in…"
        >
          Sign in
        </Button>
      </form>
    </Form>
  );
}

function ForgotForm({
  setAuthError,
  forgotSent,
  setForgotSent,
}: RightPanelProps) {
  const form = useForm<z.infer<typeof forgotSchema>>({
    resolver: zodResolver(forgotSchema),
    mode: 'onSubmit',
    defaultValues: { email: '' },
  });

  async function onSubmit(values: z.infer<typeof forgotSchema>) {
    setAuthError(null);
    try {
      // Direct backend call — forgot-password does not go through useAuth().
      // Pitfall 9: regardless of backend response shape (including network
      // failure), we show the same generic copy to defeat user enumeration.
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? '';
      await fetch(`${apiUrl}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: values.email }),
      });
    } catch {
      // Swallow — still show generic confirmation below.
    } finally {
      setForgotSent(true);
    }
  }

  if (forgotSent) {
    // Pitfall 9: anti-enumeration — generic confirmation regardless of outcome.
    return (
      <div className="rounded-md border border-border bg-surface p-4 text-sm text-text-muted">
        If that email is registered, a reset token is on its way.
      </div>
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  placeholder="you@company.com"
                  autoFocus
                  autoComplete="email"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button
          type="submit"
          variant="cta"
          size="lg"
          className="w-full"
          loading={form.formState.isSubmitting}
          loadingText="Sending…"
        >
          Send reset link
        </Button>
      </form>
    </Form>
  );
}

function ResetForm({
  resetToken,
  setAuthError,
  setMode,
}: RightPanelProps) {
  const form = useForm<z.infer<typeof resetSchema>>({
    resolver: zodResolver(resetSchema),
    mode: 'onSubmit',
    defaultValues: { token: resetToken ?? '', newPassword: '' },
  });

  const [done, setDone] = useState(false);

  async function onSubmit(values: z.infer<typeof resetSchema>) {
    setAuthError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? '';
      const res = await fetch(`${apiUrl}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: values.token,
          new_password: values.newPassword,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setAuthError(body?.detail ?? 'Reset failed. Request a new link.');
        return;
      }
      setDone(true);
    } catch {
      setAuthError('Network error. Try again in a moment.');
    }
  }

  if (done) {
    return (
      <div className="space-y-4">
        <div className="rounded-md border border-success bg-success-soft p-4 text-sm text-success">
          Password updated. Sign in to continue.
        </div>
        <Button
          variant="secondary"
          size="lg"
          className="w-full"
          onClick={() => setMode('login')}
        >
          Back to sign in
        </Button>
      </div>
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="token"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Reset token</FormLabel>
              <FormControl>
                <Input
                  type="text"
                  // D-48: token paste field uses autoComplete='off'
                  autoComplete="off"
                  spellCheck={false}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="newPassword"
          render={({ field }) => (
            <FormItem>
              <FormLabel>New password</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  // D-48 spec says 'first field' — for reset mode the first
                  // fillable field is newPassword (token is pre-filled from
                  // the ?reset= deep link, so autoFocus belongs here).
                  autoFocus
                  autoComplete="new-password"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button
          type="submit"
          variant="cta"
          size="lg"
          className="w-full"
          loading={form.formState.isSubmitting}
          loadingText="Updating…"
        >
          Set new password
        </Button>
      </form>
    </Form>
  );
}
