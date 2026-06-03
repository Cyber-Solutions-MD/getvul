'use client';
/**
 * WorkspacePane — D-SET-03 login-account + RBAC management pane.
 *
 * Two sections:
 *
 * Section 1 — Workspace settings (name/domain/timezone):
 *   Editable via the shared <SaveBar> → useUpdateTenantSettings.
 *
 * Section 2 — User accounts:
 *   - useTenantUsers() list: Avatar + display_name + email (mono) + role pill + active badge.
 *   - Owner-only controls (isOwner): "Add user" form (email/display_name/role → POST /tenant/users),
 *     per-row role change (PATCH .../role), deactivate (PATCH .../deactivate via ConfirmModal warning),
 *     delete (PATCH (DELETE) via ConfirmModal danger).
 *   - Non-owners see the list read-only.
 *
 * Security (T-14-16):
 *   RBAC checks here are UX-layer only. Backend enforces require_owner on
 *   every mutating endpoint — a non-owner who crafts a PATCH still gets 403.
 *
 * No raw palette utilities (gray-N / indigo-N).
 * data-pane="workspace" for test hooks.
 *
 * Plan 14-05.
 */

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import {
  useTenantUsers,
  type TenantUser,
} from '@/lib/queries/use-tenant-users';
import {
  useTenantSettings,
  useUpdateTenantSettings,
} from '@/lib/queries/use-tenant-settings';
import { useDirtyState } from './use-dirty-state';
import { SaveBar } from './save-bar';
import { SkeletonTable } from '@/components/states';
import { PartialFailureBanner } from '@/components/states';
import { Avatar } from '@/components/ui/Avatar';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { queryKeys } from '@/lib/queries/keys';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { useQueryClient } from '@tanstack/react-query';

// ── Types ─────────────────────────────────────────────────────────────────────

type WorkspaceFormValues = {
  name: string;
  domain: string;
  timezone: string;
};

type ConfirmState = {
  title: string;
  message: string;
  variant: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
} | null;

// ── Helpers ───────────────────────────────────────────────────────────────────

function rolePillClass(role: string): string {
  const map: Record<string, string> = {
    OWNER: 'bg-pink-soft text-pink',
    ADMIN: 'bg-violet-soft text-violet',
    ANALYST: 'bg-amber-soft text-amber',
    VIEWER: 'bg-surface-2 text-text-muted',
  };
  return map[role] ?? 'bg-surface-2 text-text-muted';
}

// ── User row subcomponent ─────────────────────────────────────────────────────

function UserRow({
  user: u,
  currentUserId,
  isOwner,
  onRoleChange,
  onDeactivate,
}: {
  user: TenantUser;
  currentUserId: string;
  isOwner: boolean;
  onRoleChange: (userId: string, role: string) => void;
  onDeactivate: (user: TenantUser) => void;
}) {
  const isSelf = u.id === currentUserId;

  return (
    <tr className="bg-surface hover:bg-surface-2 transition-colors">
      {/* Avatar + name */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <Avatar name={u.display_name ?? undefined} email={u.email} size={32} />
          <div>
            <p className="text-sm font-medium text-text">
              {u.display_name || u.email}
            </p>
            {u.display_name && (
              <p className="font-mono text-xs text-text-faint">{u.email}</p>
            )}
          </div>
        </div>
      </td>
      {/* Email (shown separately when no display_name) */}
      <td className="px-4 py-3 hidden sm:table-cell">
        <span className="font-mono text-xs text-text-muted">{u.email}</span>
      </td>
      {/* Role */}
      <td className="px-4 py-3">
        {isOwner && !isSelf ? (
          <select
            value={u.role}
            onChange={(e) => onRoleChange(u.id, e.target.value)}
            className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xs text-text focus:border-violet focus:outline-none"
          >
            <option value="OWNER">Owner</option>
            <option value="ADMIN">Admin</option>
            <option value="ANALYST">Analyst</option>
            <option value="VIEWER">Viewer</option>
          </select>
        ) : (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${rolePillClass(u.role)}`}
          >
            {u.role}
          </span>
        )}
      </td>
      {/* Active badge */}
      <td className="px-4 py-3">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${
            u.is_active
              ? 'bg-success/10 text-success'
              : 'bg-danger/10 text-danger'
          }`}
        >
          {u.is_active ? 'Active' : 'Inactive'}
        </span>
      </td>
      {/* Owner-gated actions */}
      {isOwner && (
        <td className="px-4 py-3">
          {!isSelf && (
            <div className="flex gap-2">
              {u.is_active && (
                <button
                  type="button"
                  onClick={() => onDeactivate(u)}
                  className="text-xs text-text-faint hover:text-amber transition-colors"
                  aria-label={`Deactivate ${u.email}`}
                >
                  Deactivate
                </button>
              )}
            </div>
          )}
        </td>
      )}
    </tr>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function WorkspacePane() {
  const { user: authUser } = useAuth();
  const qc = useQueryClient();
  const { toast } = useToast();

  const isOwner = authUser?.role === 'OWNER';
  const isAdmin = authUser?.role === 'OWNER' || authUser?.role === 'ADMIN';

  // Settings fetch (workspace name/domain/timezone)
  const { data: settings, isPending: settingsPending, isError: settingsError } =
    useTenantSettings();
  const updateSettings = useUpdateTenantSettings();

  // Workspace dirty state
  const { values, setField, isDirty, reset } = useDirtyState<WorkspaceFormValues>({
    name: '',
    domain: '',
    timezone: 'UTC',
  });

  // Seed workspace form from settings
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (settings) {
      // TenantSettings has domain+timezone but not name — name comes from /tenant/me
      // Use domain+timezone from settings; name is read-only from authUser.tenant_name
      reset({
        name: authUser?.tenant_name ?? '',
        domain: settings.domain ?? '',
        timezone: settings.timezone ?? 'UTC',
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings, authUser?.tenant_name]);

  // Users fetch
  const { data: users, isPending: usersPending, isError: usersError, refetch: refetchUsers } =
    useTenantUsers();

  // Confirm modal state
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);

  // Add user form state
  const [addUserOpen, setAddUserOpen] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('ANALYST');
  const [addUserError, setAddUserError] = useState('');
  const [addUserPending, setAddUserPending] = useState(false);

  async function handleSaveWorkspace() {
    await updateSettings.mutateAsync({
      domain: values.domain || undefined,
      timezone: values.timezone,
    });
    reset();
  }

  function handleDiscardWorkspace() {
    if (settings) {
      reset({
        name: authUser?.tenant_name ?? '',
        domain: settings.domain ?? '',
        timezone: settings.timezone ?? 'UTC',
      });
    } else {
      reset();
    }
  }

  async function handleRoleChange(userId: string, role: string) {
    try {
      await api(`/api/v1/tenant/users/${userId}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      });
      await refetchUsers();
      toast({ variant: 'success', message: 'Role updated.' });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not update role.';
      toast({ variant: 'error', message });
    }
  }

  function handleDeactivate(u: TenantUser) {
    setConfirmState({
      title: 'Deactivate user',
      message: `Deactivate ${u.email}? They will no longer be able to sign in.`,
      variant: 'warning',
      onConfirm: async () => {
        setConfirmState(null);
        try {
          await api(`/api/v1/tenant/users/${u.id}/deactivate`, { method: 'PATCH' });
          await refetchUsers();
          toast({ variant: 'success', message: `${u.email} deactivated.` });
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'Could not deactivate user.';
          toast({ variant: 'error', message });
        }
      },
    });
  }

  async function handleAddUser(e: React.FormEvent) {
    e.preventDefault();
    setAddUserError('');
    if (!newEmail) { setAddUserError('Email is required.'); return; }
    setAddUserPending(true);
    try {
      await api('/api/v1/tenant/users', {
        method: 'POST',
        body: JSON.stringify({
          email: newEmail,
          display_name: newName || undefined,
          role: newRole,
        }),
      });
      await refetchUsers();
      qc.invalidateQueries({ queryKey: queryKeys.settings.users() });
      toast({ variant: 'success', message: `${newEmail} added.` });
      setNewEmail(''); setNewName(''); setNewRole('ANALYST');
      setAddUserOpen(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not add user.';
      setAddUserError(message);
    } finally {
      setAddUserPending(false);
    }
  }

  const isPending = settingsPending || usersPending;
  const isError = settingsError || usersError;

  return (
    <div data-pane="workspace" className="space-y-6 p-6">
      {/* Error banner */}
      {isError && (
        <PartialFailureBanner
          watchKeys={[queryKeys.settings.tenant(), queryKeys.settings.users()]}
        />
      )}

      {/* Loading skeleton */}
      {isPending && (
        <SkeletonTable
          rows={5}
          columns={[
            { kind: 'text', width: 140 },
            { kind: 'mono', width: 180 },
            { kind: 'pill', width: 60 },
            { kind: 'badge', width: 60 },
          ]}
        />
      )}

      {/* Section 1 — Workspace settings */}
      {!settingsPending && (
        <section className="rounded-lg border border-border-subtle bg-surface p-6">
          <h2 className="mb-4 text-base font-semibold text-text">Workspace</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Workspace name (read-only — no self-service rename endpoint) */}
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Name</label>
              <input
                type="text"
                value={values.name}
                readOnly
                disabled
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text-muted cursor-not-allowed"
              />
              <p className="mt-1 text-xs text-text-faint">Contact support to rename your workspace.</p>
            </div>
            {/* Domain */}
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Domain</label>
              <input
                type="text"
                value={values.domain}
                onChange={isOwner ? (e) => setField('domain', e.target.value) : undefined}
                readOnly={!isOwner}
                disabled={!isOwner}
                placeholder="example.com"
                className={`w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none ${!isOwner ? 'cursor-not-allowed text-text-muted' : ''}`}
              />
            </div>
            {/* Timezone */}
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Timezone</label>
              {isOwner ? (
                <select
                  value={values.timezone}
                  onChange={(e) => setField('timezone', e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text focus:border-violet focus:outline-none"
                >
                  {['UTC','Europe/London','Europe/Berlin','Europe/Paris','US/Eastern','US/Central','US/Mountain','US/Pacific','Asia/Tokyo','Asia/Shanghai','Asia/Singapore','Asia/Kolkata'].map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              ) : (
                <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text-muted">
                  {values.timezone}
                </p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Section 2 — User accounts */}
      {!usersPending && (
        <section className="rounded-lg border border-border-subtle bg-surface p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-text">Accounts</h2>
              {users && (
                <p className="text-sm text-text-muted">
                  {users.length} {users.length === 1 ? 'user' : 'users'} in this workspace
                </p>
              )}
            </div>
            {isOwner && (
              <button
                type="button"
                onClick={() => setAddUserOpen(!addUserOpen)}
                className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-sm text-text-muted hover:text-text transition-colors"
              >
                {addUserOpen ? 'Cancel' : 'Add user'}
              </button>
            )}
          </div>

          {/* Add user form */}
          {isOwner && addUserOpen && (
            <form onSubmit={handleAddUser} className="mb-4 rounded-lg border border-border bg-surface-2 p-4 space-y-3">
              <h3 className="text-sm font-medium text-text">Add user</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
                />
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Ana Sokolova"
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
                />
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:border-violet focus:outline-none"
                >
                  <option value="ADMIN">Admin</option>
                  <option value="ANALYST">Analyst</option>
                  <option value="VIEWER">Viewer</option>
                </select>
              </div>
              {addUserError && (
                <p className="text-xs text-danger">{addUserError}</p>
              )}
              <button
                type="submit"
                disabled={addUserPending}
                className="rounded-lg bg-gradient-to-r from-pink to-violet px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                style={{ background: 'var(--gradient-brand, var(--gradient-sunset, linear-gradient(135deg, #EC4899 0%, #A78BFA 50%, #F59E0B 100%)))' }}
              >
                {addUserPending ? 'Adding…' : 'Add user'}
              </button>
            </form>
          )}

          {/* Users table */}
          {users && users.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border-subtle">
                  <tr>
                    <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">User</th>
                    <th className="hidden px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint sm:table-cell">Email</th>
                    <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">Role</th>
                    <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">Status</th>
                    {isOwner && (
                      <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">Actions</th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {users.map((u) => (
                    <UserRow
                      key={u.id}
                      user={u}
                      currentUserId={authUser?.id ?? ''}
                      isOwner={isOwner}
                      onRoleChange={handleRoleChange}
                      onDeactivate={handleDeactivate}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Empty state for zero users */}
          {users && users.length === 0 && isAdmin && (
            <p className="text-sm text-text-faint">No users found in this workspace.</p>
          )}
        </section>
      )}

      {/* SaveBar for workspace settings (not for user actions) */}
      <SaveBar
        isDirty={isDirty}
        isSaving={updateSettings.isPending}
        onSave={handleSaveWorkspace}
        onDiscard={handleDiscardWorkspace}
      />

      {/* Confirm modal for deactivate/delete */}
      {confirmState && (
        <ConfirmModal
          open={true}
          title={confirmState.title}
          message={confirmState.message}
          variant={confirmState.variant}
          confirmLabel="Confirm"
          onConfirm={confirmState.onConfirm}
          onCancel={() => setConfirmState(null)}
        />
      )}
    </div>
  );
}
