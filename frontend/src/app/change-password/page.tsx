'use client';
import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { changePasswordSchema } from '@/lib/validation/auth';
import { sanitizeNext } from '@/app/login/sanitize-next';
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
import { ErrorAlert } from '@/components/auth/error-alert';

// PROD-06-03 force-rotation surface. Lives OUTSIDE the (authed) group (peer of
// login/) so it renders without the AppShell, mirroring /login. The redirect
// gate in lib/auth.tsx lands the flagged user here; this page turns the Wave 2
// backend 403 into a usable rotation flow.
export default function ChangePasswordPage() {
  // Pitfall 8: useSearchParams() requires a Suspense boundary under Next 15 +
  // React 19, matching login/page.tsx.
  return (
    <Suspense fallback={<ChangePasswordFallback />}>
      <ChangePasswordForm />
    </Suspense>
  );
}

function ChangePasswordFallback() {
  return (
    <main className="min-h-screen bg-bg grid place-items-center text-text-faint text-sm">
      Loading…
    </main>
  );
}

function ChangePasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<z.infer<typeof changePasswordSchema>>({
    resolver: zodResolver(changePasswordSchema),
    mode: 'onSubmit',
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
  });

  async function onSubmit(values: z.infer<typeof changePasswordSchema>) {
    setFormError(null);
    // Raw fetch (not the toast-wrapped hook) — this flow needs the fresh
    // flag-free tokens straight from the response body (RESEARCH Finding 11).
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? '';
    const token =
      typeof window !== 'undefined'
        ? localStorage.getItem('getvul_token')
        : null;

    let resp: Response;
    try {
      resp = await fetch(`${apiUrl}/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          current_password: values.current_password,
          new_password: values.new_password,
        }),
      });
    } catch {
      setFormError('Network error. Try again in a moment.');
      return;
    }

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      // Backend detail is already specific (wrong current password, weak,
      // Admin123! reject) — surface it verbatim; do not navigate.
      setFormError(body?.detail ?? 'Password change failed. Try again.');
      return;
    }

    // T-06-token-replay: overwrite the old flagged tokens with the fresh
    // flag-free ones BEFORE navigating, so the guard doesn't bounce the user
    // back to /change-password (Pitfall 3).
    const data = await resp.json().catch(() => ({}));
    if (typeof window !== 'undefined') {
      if (data?.access_token) {
        localStorage.setItem('getvul_token', data.access_token);
      }
      if (data?.refresh_token) {
        localStorage.setItem('getvul_refresh', data.refresh_token);
      }
    }

    // T-06-open-redirect: sanitizeNext keeps ?next to same-origin relative
    // paths only; defaults to /dashboard.
    router.replace(sanitizeNext(searchParams.get('next')));
  }

  return (
    <main className="min-h-screen bg-bg text-text flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text">Set a new password</h1>
          <p className="mt-1 text-sm text-text-muted">
            This account still uses the default install credentials. Set a new
            password before continuing.
          </p>
        </div>

        {formError && <ErrorAlert>{formError}</ErrorAlert>}

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="current_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current password</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      autoFocus
                      autoComplete="current-password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="new_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New password</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="Min 8 characters"
                      autoComplete="new-password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="confirm_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm new password</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
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
              Update password
            </Button>
          </form>
        </Form>
      </div>
    </main>
  );
}
