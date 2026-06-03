/**
 * use-tenant-users.ts — TanStack hooks for /tenant/users surface.
 *
 * Hooks:
 *   useTenantUsers    — GET /api/v1/tenant/users (Admin-gated)
 *   useChangePassword — POST /auth/change-password (authenticated)
 *
 * Profile sourcing (finding #4 / Pitfall 6):
 *   /auth/me returns only {id, tenant_id, email, role} — NOT idp_source or
 *   last_login_at. This hook provides the full UserResponse list; the
 *   ProfilePane filters by user.email to get idp_source + last_login_at.
 *
 * Plan 14-05.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import { useToast } from '@/components/ui/ToastProvider';

// ── Types ─────────────────────────────────────────────────────────────────────

export type TenantUser = {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  role: string;
  is_active: boolean;
  /** When false, user is SSO-only — hide Change Password form (D-SET-06). */
  allow_password_login: boolean;
  groups: string[] | null;
  department: string | null;
  job_title: string | null;
  /** "google" | "azure" | "okta" | "humaans" | "local" | null */
  idp_source: string | null;
  /** ISO datetime string or null */
  last_login_at: string | null;
};

export type ChangePasswordBody = {
  current_password: string;
  new_password: string;
};

// ── Hooks ─────────────────────────────────────────────────────────────────────

/**
 * useTenantUsers — GET /api/v1/tenant/users.
 * Returns the full list of users with RBAC + identity details.
 * Used by ProfilePane (find self by email for idp_source/last_login_at) and
 * WorkspacePane (full user list management).
 */
export function useTenantUsers() {
  return useQuery({
    queryKey: queryKeys.settings.users(),
    queryFn: ({ signal }) =>
      api<TenantUser[]>('/api/v1/tenant/users', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}

/**
 * useChangePassword — POST /auth/change-password.
 * Hidden from the ProfilePane when allow_password_login===false (SSO-only).
 * Toasts on success/error.
 */
export function useChangePassword() {
  const { toast } = useToast();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (body: ChangePasswordBody) =>
      api<{ message: string }>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      toast({ variant: 'success', message: 'Password changed.' });
      // Invalidate settings.users to refresh any per-user state
      qc.invalidateQueries({ queryKey: queryKeys.settings.users() });
    },
    onError: (err: Error) => {
      toast({
        variant: 'error',
        message: err.message || 'Could not change password. Try again.',
      });
    },
    retry: 0,
  });
}
