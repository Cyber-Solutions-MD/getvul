'use client';
/**
 * /dashboard/asset-groups — AssetGroup management page (32-05-PLAN Task 2).
 *
 * Mirrors connectors/page.tsx's composition (useAuth -> isAdmin, list hook,
 * SkeletonTable/PartialFailureBanner/EmptyState states, ConfirmModal +
 * ResponsiveDialog reuse) but scoped to a much smaller entity: a real
 * AssetGroup (name/description/membership/exposure override), not a
 * credentialed connector.
 *
 * D-X-01 state patterns (mandatory):
 *   - isPending -> SkeletonTable
 *   - error     -> PartialFailureBanner
 *   - zero groups -> explained empty state (not a bare "No data")
 *   - mutations -> toasts (handled in the hooks)
 *
 * Admin gating is UI-layer defense-in-depth ONLY (T-32-13) — every mutating
 * endpoint is `require_admin`-gated server-side; a non-admin sees the same
 * list read-only with no create/edit/delete/membership/override affordances.
 */
import { useState } from 'react';
import { Pencil, Trash2, Plus, Users, X } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  useAssetGroupsList,
  useDeleteAssetGroup,
  useGroupMembers,
  useAddGroupMember,
  useRemoveGroupMember,
  useGroupExposureOverrides,
  useSetGroupExposureOverride,
  type AssetGroupResponse,
} from '@/lib/queries/use-asset-groups';
import { useAssets } from '@/lib/queries/use-assets';
import { SkeletonTable, EmptyState, PartialFailureBanner } from '@/components/states';
import { useDocumentTitle } from '@/hooks/use-document-title';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { ResponsiveDialog } from '@/components/ui/responsive-dialog';
import { AssetGroupForm } from '@/components/assets/asset-group-form';

const SKELETON_COLUMNS = [
  { kind: 'text' as const, width: 200 },
  { kind: 'text' as const, width: 280 },
  { kind: 'pill' as const, width: 60 },
];

const CRITICALITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;
const SENSITIVITY_OPTIONS = ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED'] as const;

function titleCase(v: string): string {
  return v.charAt(0) + v.slice(1).toLowerCase();
}

type FormState = { open: boolean; mode: 'add' | 'edit'; existing?: AssetGroupResponse };
type DeleteState = { open: boolean; groupId: string; groupName: string };

/** Add-member search — debounced hostname search against /api/v1/assets, mirroring
 * ReassignCombobox's 250ms debounce (reassign-combobox.tsx) without the full
 * combobox keyboard-nav surface (a simple type-and-click list is enough here). */
function AddMemberSearch({
  groupId,
  existingMemberIds,
}: {
  groupId: string;
  existingMemberIds: Set<string>;
}) {
  const [input, setInput] = useState('');
  const addMutation = useAddGroupMember(groupId);
  const assets = useAssets({
    filters: { search: input.trim().length >= 2 ? input.trim() : undefined },
    page: 1,
    sort: 'hostname',
    order: 'asc',
  });

  const showResults = input.trim().length >= 2;
  const candidates = (assets.data?.items ?? []).filter((a) => !existingMemberIds.has(a.id));

  return (
    <div className="space-y-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Search hosts by name..."
        aria-label="Search assets to add as a member"
        className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
      />
      {showResults && (
        <ul className="max-h-40 overflow-y-auto rounded-md border border-border-subtle" data-testid="add-member-results">
          {assets.isLoading && (
            <li className="px-3 py-2 text-xs text-text-muted">Loading...</li>
          )}
          {!assets.isLoading && candidates.length === 0 && (
            <li className="px-3 py-2 text-xs text-text-muted">
              No matching hosts (or all matches are already members).
            </li>
          )}
          {candidates.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between gap-2 px-3 py-1.5 text-sm text-text hover:bg-surface"
            >
              <span className="font-mono">{a.hostname ?? a.id}</span>
              <button
                type="button"
                onClick={() => addMutation.mutate(a.id)}
                disabled={addMutation.isPending}
                className="text-xs text-[var(--color-violet-on-soft)] hover:underline disabled:opacity-50"
              >
                Add
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Per-group membership + exposure-override management panel — rendered
 * inside a ResponsiveDialog. Read-only for non-admins (no add/remove/edit
 * affordances rendered at all — matches the card's defense-in-depth gate). */
function ManageGroupPanel({ group, isAdmin }: { group: AssetGroupResponse; isAdmin: boolean }) {
  const members = useGroupMembers(group.id);
  const removeMutation = useRemoveGroupMember(group.id);
  const overrides = useGroupExposureOverrides(group.id);
  const setOverrideMutation = useSetGroupExposureOverride(group.id);

  const memberIds = new Set((members.data ?? []).map((m) => m.id));

  return (
    <div className="space-y-6">
      <section aria-label="Members" data-testid="group-members-section">
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-text">
          <Users size={14} aria-hidden />
          Members
        </h3>
        {members.isLoading && <SkeletonTable rows={3} columns={[{ kind: 'text', width: 220 }]} />}
        {members.error && (
          <PartialFailureBanner
            errors={[{ code: 'http_error', requestId: (members.error as Error).message || 'unknown' }]}
            onRetry={() => members.refetch()}
          />
        )}
        {!members.isLoading && !members.error && (members.data ?? []).length === 0 && (
          <p className="text-sm text-text-muted">No hosts in this group yet.</p>
        )}
        {!members.isLoading && (members.data?.length ?? 0) > 0 && (
          <ul className="space-y-1" data-testid="group-members-list">
            {members.data!.map((m) => (
              <li
                key={m.id}
                className="flex items-center justify-between gap-2 rounded-md border border-border-subtle bg-surface px-3 py-1.5 text-sm"
              >
                <span className="font-mono text-text">{m.hostname ?? m.id}</span>
                {isAdmin && (
                  <button
                    type="button"
                    onClick={() => removeMutation.mutate(m.id)}
                    disabled={removeMutation.isPending}
                    className="text-xs text-text-muted hover:text-severity-critical disabled:opacity-50"
                    aria-label={`Remove ${m.hostname ?? m.id}`}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {isAdmin && (
          <div className="mt-3">
            <AddMemberSearch groupId={group.id} existingMemberIds={memberIds} />
          </div>
        )}
      </section>

      <section aria-label="Group exposure override" data-testid="group-override-section">
        <h3 className="mb-2 text-sm font-semibold text-text">Exposure override</h3>
        <p className="mb-2 text-xs text-text-muted">
          Applies to every current and future member — a per-asset override still wins.
        </p>
        {overrides.isLoading && <SkeletonTable rows={3} columns={[{ kind: 'text', width: 220 }]} />}
        {overrides.error && (
          <PartialFailureBanner
            errors={[{ code: 'http_error', requestId: (overrides.error as Error).message || 'unknown' }]}
            onRetry={() => overrides.refetch()}
          />
        )}
        {!overrides.isLoading && !overrides.error && (
          <div className="space-y-2">
            <GroupOverrideRow
              label="Business criticality"
              field="business_criticality"
              value={overrides.data?.business_criticality ?? null}
              options={CRITICALITY_OPTIONS}
              isAdmin={isAdmin}
              mutation={setOverrideMutation}
            />
            <GroupOverrideRow
              label="Data sensitivity"
              field="data_sensitivity"
              value={overrides.data?.data_sensitivity ?? null}
              options={SENSITIVITY_OPTIONS}
              isAdmin={isAdmin}
              mutation={setOverrideMutation}
            />
            <GroupOverrideRow
              label="Internet-facing"
              field="internet_facing"
              value={overrides.data?.internet_facing ?? null}
              options={['true', 'false']}
              isAdmin={isAdmin}
              mutation={setOverrideMutation}
            />
          </div>
        )}
      </section>
    </div>
  );
}

function GroupOverrideRow({
  label,
  field,
  value,
  options,
  isAdmin,
  mutation,
}: {
  label: string;
  field: 'business_criticality' | 'data_sensitivity' | 'internet_facing';
  value: string | null;
  options: readonly string[];
  isAdmin: boolean;
  mutation: ReturnType<typeof useSetGroupExposureOverride>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? options[0]);

  const displayValue = value === null ? 'Not set (falls through to auto/asset)' : titleCase(value);

  if (isEditing) {
    return (
      <div className="flex items-center gap-2 border-t border-border-subtle py-2 text-xs" data-testid={`group-override-edit-${field}`}>
        <span className="w-40 shrink-0 uppercase tracking-wide text-text-faint">{label}</span>
        <select
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label={`${label} value`}
          className="flex-1 rounded-md border border-border-subtle bg-surface px-2 py-1.5 text-sm text-text"
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {titleCase(opt)}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setIsEditing(false)}
          className="text-xs text-text-muted hover:text-text"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() =>
            mutation.mutate({ field, value: draft }, { onSuccess: () => setIsEditing(false) })
          }
          disabled={mutation.isPending}
          className="text-xs font-medium text-[var(--color-violet-on-soft)] hover:underline disabled:opacity-50"
          data-testid={`group-override-save-${field}`}
        >
          Save
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between gap-2 border-t border-border-subtle py-2 text-xs" data-testid={`group-override-row-${field}`}>
      <span className="uppercase tracking-wide text-text-faint">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-text">{displayValue}</span>
        {isAdmin && (
          <button
            type="button"
            onClick={() => {
              setDraft(value ?? options[0]);
              setIsEditing(true);
            }}
            className="text-xs text-[var(--color-violet-on-soft)] hover:underline"
            data-testid={`group-override-edit-btn-${field}`}
            aria-label={`Edit ${label} override`}
          >
            Edit
          </button>
        )}
      </div>
    </div>
  );
}

function AssetGroupsPageInner() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';

  const groupsQuery = useAssetGroupsList();
  const deleteMutation = useDeleteAssetGroup();

  const [formState, setFormState] = useState<FormState>({ open: false, mode: 'add' });
  const [deleteState, setDeleteState] = useState<DeleteState>({ open: false, groupId: '', groupName: '' });
  const [manageGroup, setManageGroup] = useState<AssetGroupResponse | null>(null);

  function openAddForm() {
    setFormState({ open: true, mode: 'add' });
  }
  function openEditForm(group: AssetGroupResponse) {
    setFormState({ open: true, mode: 'edit', existing: group });
  }
  function closeForm() {
    setFormState({ open: false, mode: 'add' });
  }

  function handleDelete(group: AssetGroupResponse) {
    setDeleteState({ open: true, groupId: group.id, groupName: group.name });
  }
  function handleConfirmDelete() {
    deleteMutation.mutate(deleteState.groupId, {
      onSettled: () => setDeleteState({ open: false, groupId: '', groupName: '' }),
    });
  }

  const formTitleId = 'asset-group-form-title';
  const manageTitleId = 'asset-group-manage-title';

  const header = (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-text">Asset groups</h1>
        <p className="mt-1 text-sm text-text-muted">
          Group hosts by environment, team, or compliance scope to set exposure context in bulk.
        </p>
      </div>
      {isAdmin && (
        <button
          type="button"
          onClick={openAddForm}
          style={{ background: 'var(--gradient-sunset)' }}
          className="inline-flex shrink-0 items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-[var(--glow-cta)] hover:-translate-y-px transition-all"
          data-testid="new-asset-group-btn"
        >
          <Plus size={16} aria-hidden />
          New group
        </button>
      )}
    </div>
  );

  if (groupsQuery.isPending) {
    return (
      <div className="space-y-8">
        {header}
        <SkeletonTable rows={4} columns={SKELETON_COLUMNS} />
      </div>
    );
  }

  if (groupsQuery.error) {
    return (
      <div className="space-y-8">
        {header}
        <PartialFailureBanner
          errors={[
            {
              code: 'unknown',
              requestId: 'unknown',
              message: (groupsQuery.error as Error).message,
            },
          ]}
          onRetry={() => groupsQuery.refetch()}
        />
      </div>
    );
  }

  const groups = groupsQuery.data ?? [];

  return (
    <div className="space-y-8">
      {header}

      {groups.length === 0 ? (
        <EmptyState>
          <EmptyState.Title>No asset groups yet</EmptyState.Title>
          <EmptyState.Body>
            Groups let you set business criticality, data sensitivity, or internet-facing status
            for many hosts at once — a per-asset override still wins over any group.
          </EmptyState.Body>
          {isAdmin ? (
            <EmptyState.Actions>
              <button
                type="button"
                onClick={openAddForm}
                style={{ background: 'var(--gradient-sunset)' }}
                className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-[var(--glow-cta)] hover:-translate-y-px transition-all"
              >
                <Plus size={16} aria-hidden />
                New group
              </button>
            </EmptyState.Actions>
          ) : (
            <EmptyState.Suggestion>
              Ask an admin to create the first asset group.
            </EmptyState.Suggestion>
          )}
        </EmptyState>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="asset-groups-grid">
          {groups.map((g) => (
            <div
              key={g.id}
              className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface-2 p-4"
              data-testid={`asset-group-card-${g.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <h2 className="text-sm font-semibold text-text">{g.name}</h2>
                <span
                  className="flex shrink-0 items-center gap-1 rounded-full border border-border-subtle bg-surface px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide text-text-muted"
                  data-testid={`asset-group-member-count-${g.id}`}
                >
                  <Users size={10} aria-hidden />
                  {g.member_count}
                </span>
              </div>
              {g.description && <p className="text-xs text-text-muted">{g.description}</p>}
              <div className="mt-2 flex items-center gap-3 border-t border-border-subtle pt-2 text-xs">
                <button
                  type="button"
                  onClick={() => setManageGroup(g)}
                  className="text-[var(--color-violet-on-soft)] hover:underline"
                  data-testid={`manage-group-${g.id}`}
                >
                  Manage
                </button>
                {isAdmin && (
                  <>
                    <button
                      type="button"
                      onClick={() => openEditForm(g)}
                      aria-label={`Edit ${g.name}`}
                      className="inline-flex items-center gap-1 text-text-muted hover:text-text"
                    >
                      <Pencil size={12} aria-hidden />
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(g)}
                      aria-label={`Delete ${g.name}`}
                      className="inline-flex items-center gap-1 text-text-muted hover:text-severity-critical"
                    >
                      <Trash2 size={12} aria-hidden />
                      Delete
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit form dialog */}
      <ResponsiveDialog
        open={formState.open}
        onOpenChange={(o) => { if (!o) closeForm(); }}
        ariaLabelledBy={formTitleId}
        dismissOnBackdropClick={false}
      >
        <div className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 id={formTitleId} className="text-lg font-semibold text-text">
              {formState.mode === 'add' ? 'New asset group' : 'Edit asset group'}
            </h2>
            <button
              type="button"
              onClick={closeForm}
              aria-label="Close"
              className="rounded-md p-1 text-text-faint transition-colors hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
            >
              <X size={18} />
            </button>
          </div>
          <AssetGroupForm mode={formState.mode} existing={formState.existing} onClose={closeForm} />
        </div>
      </ResponsiveDialog>

      {/* Manage (members + override) dialog */}
      <ResponsiveDialog
        open={!!manageGroup}
        onOpenChange={(o) => { if (!o) setManageGroup(null); }}
        ariaLabelledBy={manageTitleId}
      >
        <div className="p-6">
          {manageGroup && (
            <>
              <div className="mb-4 flex items-center justify-between">
                <h2 id={manageTitleId} className="text-lg font-semibold text-text">
                  {manageGroup.name}
                </h2>
                <button
                  type="button"
                  onClick={() => setManageGroup(null)}
                  aria-label="Close"
                  className="rounded-md p-1 text-text-faint transition-colors hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
                >
                  <X size={18} />
                </button>
              </div>
              <ManageGroupPanel group={manageGroup} isAdmin={isAdmin} />
            </>
          )}
        </div>
      </ResponsiveDialog>

      {/* Delete confirm modal */}
      <ConfirmModal
        open={deleteState.open}
        title="Delete asset group"
        message={`Delete "${deleteState.groupName}"? Its member hosts revert to group-less exposure resolution (per-asset override or auto). This can't be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteState({ open: false, groupId: '', groupName: '' })}
      />
    </div>
  );
}

export default function AssetGroupsPage() {
  useDocumentTitle('Asset groups');
  return <AssetGroupsPageInner />;
}
