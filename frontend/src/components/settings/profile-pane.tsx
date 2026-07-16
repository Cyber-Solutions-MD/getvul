'use client';
/**
 * ProfilePane — D-SET-06 identity view + change-password form.
 *
 * Identity card (read-only):
 *   - display_name / email (mono) / role / tenant_name from useAuth().user
 *   - idp_source + last_login_at from useTenantUsers() filtered by user.email
 *     (finding #4 / Pitfall 6 — /auth/me lacks these fields)
 *
 * Change Password form:
 *   - HIDDEN when allow_password_login===false (SSO-only account)
 *   - Two fields: current_password + new_password → useChangePassword()
 *   - Has its own submit; no SaveBar needed here
 *
 * RBAC: no gating on this pane (always visible per D-SET-05).
 * Threat: T-14-16 — backend gating is authoritative; this pane is UX-only.
 *
 * No raw palette utilities (gray-N / indigo-N). No useEffect-fetch.
 * data-pane="profile" for test hooks.
 */

import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { useTenantUsers, useChangePassword } from '@/lib/queries/use-tenant-users';
import { SkeletonTable } from '@/components/states';
import { PartialFailureBanner } from '@/components/states';
import { Avatar } from '@/components/ui/Avatar';
import { queryKeys } from '@/lib/queries/keys';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatRelativeDate(iso: string | null): string {
  if (!iso) return 'Never';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  // Simple relative format: matches copy-voice.md "12m ago" / "2h 14m ago"
  const diffMs = Date.now() - d.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) {
    const mins = diffMins % 60;
    return mins > 0 ? `${diffHrs}h ${mins}m ago` : `${diffHrs}h ago`;
  }
  const diffDays = Math.floor(diffHrs / 24);
  return `${diffDays}d ago`;
}

function roleBadgeClass(role: string): string {
  // Phase-15 a11y (UX-07-03): OWNER/ADMIN role-badge text fails WCAG AA on the
  // accent-soft fill in dark mode (pink 4.0:1, violet 4.4:1). Lift to the
  // brighter same-hue shade (pink-400 / violet-300) to clear 4.5:1 while keeping
  // the colored-pill identity. These are the canonical --color-{pink,violet}-on-soft
  // shades documented in the design system (BL-04): visual-language.md "Text on -soft fills".
  // Phase-16 (UX-D-03-04): replaced JIT hex literals (#F472B6 / #C4B5FD) with
  // CSS variable references so the light-mode overrides in globals.css take effect
  // (dark: pink-400/violet-300 via BL-04; light: pink-800/violet-800 via Phase-16).
  // Phase-16 (WR-02): ANALYST also migrated from base text-amber (#F59E0B, ~1.9:1 on
  // amber-soft fill in light) to --color-amber-on-soft so the #92400E light override
  // resolves. Dark mode is byte-identical (dark --color-amber-on-soft = #F59E0B).
  // Completes the on-soft migration alongside OWNER/ADMIN.
  const map: Record<string, string> = {
    OWNER: 'bg-pink-soft text-[var(--color-pink-on-soft)]',
    ADMIN: 'bg-violet-soft text-[var(--color-violet-on-soft)]',
    ANALYST: 'bg-amber-soft text-[var(--color-amber-on-soft)]',
    VIEWER: 'bg-surface-2 text-text-muted',
  };
  return map[role] ?? 'bg-surface-2 text-text-muted';
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ProfilePane() {
  const { user } = useAuth();
  const { data: users, isPending, isError } = useTenantUsers();
  const changePasswordMutation = useChangePassword();

  // Change password form state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [pwError, setPwError] = useState('');

  // Find the current user's full record in the tenant users list (finding #4)
  const tenantUser = users?.find((u) => u.email === user?.email);

  // SSO-only: hide Change Password form when allow_password_login===false
  const showPasswordForm = tenantUser ? tenantUser.allow_password_login === true : false;

  // idp_source and last_login_at come from tenantUser (not /auth/me)
  const idp_source = tenantUser?.idp_source ?? null;
  const last_login_at = tenantUser?.last_login_at ?? null;

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError('');
    if (!currentPassword || !newPassword) {
      setPwError('Both fields are required.');
      return;
    }
    try {
      await changePasswordMutation.mutateAsync({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
    } catch {
      // error is handled by the mutation's onError toast
    }
  }

  return (
    <div
      data-pane="profile"
      className="space-y-6 p-6"
    >
      {/* Error banner */}
      {isError && (
        <PartialFailureBanner
          watchKeys={[queryKeys.settings.users()]}
        />
      )}

      {/* Loading skeleton */}
      {isPending && (
        <SkeletonTable
          rows={4}
          columns={[
            { kind: 'text', width: 120 },
            { kind: 'mono', width: 200 },
          ]}
        />
      )}

      {/* Identity card */}
      <section className="rounded-lg border border-border-subtle bg-surface p-6">
        <h2 className="mb-4 text-base font-semibold text-text">Identity</h2>
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <Avatar
            name={user?.display_name}
            email={user?.email}
            size={48}
          />
          <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2">
            {/* Display name */}
            <div>
              <span className="block text-xs font-medium uppercase tracking-wide text-text-faint">
                Name
              </span>
              <span className="mt-0.5 block text-sm text-text">
                {user?.display_name || '—'}
              </span>
            </div>

            {/* Email (mono — copy-paste value) */}
            <div>
              <span className="block text-xs font-medium uppercase tracking-wide text-text-faint">
                Email
              </span>
              <span className="mt-0.5 block font-mono text-sm text-text">
                {user?.email}
              </span>
            </div>

            {/* Role */}
            <div>
              <span className="block text-xs font-medium uppercase tracking-wide text-text-faint">
                Role
              </span>
              <span
                className={`mt-0.5 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${roleBadgeClass(user?.role ?? '')}`}
              >
                {user?.role}
              </span>
            </div>

            {/* Tenant */}
            <div>
              <span className="block text-xs font-medium uppercase tracking-wide text-text-faint">
                Workspace
              </span>
              <span className="mt-0.5 block text-sm text-text">
                {user?.tenant_name || '—'}
              </span>
            </div>

            {/* IdP source — from /tenant/users (finding #4) */}
            <div>
              <span className="block text-xs font-medium uppercase tracking-wide text-text-faint">
                Identity provider
              </span>
              <span className="mt-0.5 block text-sm text-text">
                {idp_source ? idp_source : (isPending ? '—' : '—')}
              </span>
            </div>

            {/* Last login — from /tenant/users */}
            <div>
              <span className="block text-xs font-medium uppercase tracking-wide text-text-faint">
                Last sign-in
              </span>
              <span className="mt-0.5 block font-mono text-sm text-text-muted">
                {formatRelativeDate(last_login_at)}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Change password form — hidden for SSO-only accounts (allow_password_login===false) */}
      {showPasswordForm && (
        <section className="rounded-lg border border-border-subtle bg-surface p-6">
          <h2 className="mb-1 text-base font-semibold text-text">Change password</h2>
          <p className="mb-4 text-sm text-text-muted">
            Update your account password. You&apos;ll stay signed in after changing it.
          </p>
          <form onSubmit={handleChangePassword} className="space-y-4" noValidate>
            <div>
              <label
                htmlFor="profile-current-password"
                className="mb-1 block text-sm font-medium text-text"
              >
                Current password
              </label>
              <input
                id="profile-current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none focus:ring-1 focus:ring-violet"
                placeholder="••••••••"
              />
            </div>
            <div>
              <label
                htmlFor="profile-new-password"
                className="mb-1 block text-sm font-medium text-text"
              >
                New password
              </label>
              <input
                id="profile-new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none focus:ring-1 focus:ring-violet"
                placeholder="Min 8 characters"
              />
            </div>
            {pwError && (
              <p className="text-xs text-danger">{pwError}</p>
            )}
            <button
              type="submit"
              disabled={changePasswordMutation.isPending}
              className="rounded-lg bg-gradient-to-r from-pink to-violet px-4 py-2 text-sm font-medium text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
              style={{ background: 'var(--gradient-brand, var(--gradient-sunset, linear-gradient(135deg, #EC4899 0%, #A78BFA 50%, #F59E0B 100%)))' }}
            >
              {changePasswordMutation.isPending ? 'Updating…' : 'Update password'}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
