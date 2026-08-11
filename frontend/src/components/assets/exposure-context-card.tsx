'use client';
/**
 * ExposureContextCard — Phase 32 (32-05-PLAN) right-rail card.
 *
 * Three exposure-context fields (business_criticality, data_sensitivity,
 * internet_facing), each with a source badge (auto / manually set /
 * group: {name}) sourced from the matching `*_source` (+ `*_group_name`)
 * fields on `AssetDetail`. Admins get an inline flip-edit override control
 * per row (select for the two enum fields, a Yes/No toggle for
 * internet_facing); non-admins see the same rows read-only, matching
 * OwnerCard's flip-edit interaction (owner-card.tsx) and
 * IdentityMetadataRail's stacked-row shape (identity-metadata-rail.tsx).
 *
 * Admin gating in the UI is defense-in-depth ONLY (32-CONTEXT.md's UI
 * section) — the backend's `require_role("admin")` on
 * `PATCH /assets/{id}/exposure-context` is the real boundary (T-32-13).
 */
import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { useSetExposureOverride } from '@/lib/queries/use-exposure-override';
import type { ExposureField } from '@/lib/queries/use-exposure-override';
import type { AssetDetail } from '@/lib/queries/use-asset-detail';
import { cn } from '@/lib/utils';

const CRITICALITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;
const SENSITIVITY_OPTIONS = ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED'] as const;

type ExposureSource = 'AUTO' | 'ASSET_OVERRIDE' | 'GROUP_OVERRIDE' | null;

// Title-cases a SCREAMING_SNAKE enum value for display ("CRITICAL" -> "Critical").
function titleCase(v: string): string {
  return v.charAt(0) + v.slice(1).toLowerCase();
}

/**
 * Source badge — reuses the sunset pill idiom already established by
 * OwnerCard's IdpPill (owner-card.tsx:33-44): subtle bordered pill, mono
 * uppercase text. Not a severity/status signal, so it stays neutral rather
 * than tinted.
 */
function SourceBadge({ source, groupName }: { source: ExposureSource; groupName: string | null }) {
  let label: string;
  if (source === 'ASSET_OVERRIDE') {
    label = 'manually set';
  } else if (source === 'GROUP_OVERRIDE') {
    label = groupName ? `group: ${groupName}` : 'group';
  } else {
    label = 'auto';
  }
  return (
    <span
      className="rounded-full border border-border-subtle bg-surface px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide text-text-muted"
      data-testid="exposure-source-badge"
    >
      {label}
    </span>
  );
}

type ExposureRowProps = {
  field: ExposureField;
  label: string;
  displayValue: string;
  source: ExposureSource;
  groupName: string | null;
  isAdmin: boolean;
  mutation: ReturnType<typeof useSetExposureOverride>;
} & (
  | { kind: 'select'; options: readonly string[]; currentValue: string }
  | { kind: 'toggle'; currentValue: boolean | null }
);

function ExposureRow(props: ExposureRowProps) {
  const { field, label, displayValue, source, groupName, isAdmin, mutation } = props;
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(() =>
    props.kind === 'select' ? props.currentValue : String(props.currentValue ?? false),
  );

  function startEdit() {
    setDraft(props.kind === 'select' ? props.currentValue : String(props.currentValue ?? false));
    setIsEditing(true);
  }

  function save() {
    mutation.mutate(
      { field, value: draft },
      { onSuccess: () => setIsEditing(false) },
    );
  }

  if (isEditing) {
    return (
      <div
        className="space-y-2 border-t border-border-subtle py-2 text-xs"
        aria-label={`${label} — edit mode`}
        data-testid={`exposure-edit-row-${field}`}
      >
        <span className="uppercase tracking-wide text-text-faint">{label}</span>
        {props.kind === 'select' ? (
          <select
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={mutation.isPending}
            aria-label={`${label} value`}
            className="w-full rounded-md border border-border-subtle bg-surface px-2 py-1.5 text-sm text-text focus:border-violet focus:outline-none focus:ring-2 focus:ring-violet/30"
          >
            {props.options.map((opt) => (
              <option key={opt} value={opt}>
                {titleCase(opt)}
              </option>
            ))}
          </select>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setDraft('true')}
              disabled={mutation.isPending}
              className={cn(
                'flex-1 rounded-md border px-2 py-1.5 text-sm transition-colors',
                draft === 'true'
                  ? 'border-violet/60 bg-violet/10 text-[var(--color-violet-on-soft)]'
                  : 'border-border-subtle text-text-muted hover:border-border',
              )}
            >
              Yes
            </button>
            <button
              type="button"
              onClick={() => setDraft('false')}
              disabled={mutation.isPending}
              className={cn(
                'flex-1 rounded-md border px-2 py-1.5 text-sm transition-colors',
                draft === 'false'
                  ? 'border-violet/60 bg-violet/10 text-[var(--color-violet-on-soft)]'
                  : 'border-border-subtle text-text-muted hover:border-border',
              )}
            >
              No
            </button>
          </div>
        )}
        <div className="flex justify-end gap-3 pt-1">
          <button
            type="button"
            onClick={() => setIsEditing(false)}
            disabled={mutation.isPending}
            className="text-xs text-text-muted hover:text-text"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={mutation.isPending}
            className="text-xs font-medium text-[var(--color-violet-on-soft)] hover:underline disabled:opacity-50"
            data-testid={`exposure-save-${field}`}
          >
            {mutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex items-center justify-between gap-3 border-t border-border-subtle py-2 text-xs"
      data-testid={`exposure-row-${field}`}
    >
      <span className="uppercase tracking-wide text-text-faint">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-text">{displayValue}</span>
        <SourceBadge source={source} groupName={groupName} />
        {isAdmin && (
          <button
            type="button"
            onClick={startEdit}
            aria-label={`Edit ${label}`}
            data-testid={`exposure-edit-btn-${field}`}
            className="text-xs text-[var(--color-violet-on-soft)] hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
          >
            Edit
          </button>
        )}
      </div>
    </div>
  );
}

export function ExposureContextCard({ asset }: { asset: AssetDetail }) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';
  const mutation = useSetExposureOverride(asset.id);

  return (
    <section
      className="rounded-lg border border-border-subtle bg-surface-2 p-4"
      aria-label="Exposure context"
      data-testid="exposure-context-card"
    >
      <h3 className="mb-2 text-xs uppercase tracking-wide text-text-faint">
        Exposure context
      </h3>
      <ExposureRow
        field="business_criticality"
        label="Business criticality"
        displayValue={asset.business_criticality ? titleCase(asset.business_criticality) : '—'}
        source={asset.business_criticality_source}
        groupName={asset.business_criticality_group_name}
        isAdmin={isAdmin}
        mutation={mutation}
        kind="select"
        options={CRITICALITY_OPTIONS}
        currentValue={asset.business_criticality ?? CRITICALITY_OPTIONS[1]}
      />
      <ExposureRow
        field="data_sensitivity"
        label="Data sensitivity"
        displayValue={asset.data_sensitivity ? titleCase(asset.data_sensitivity) : '—'}
        source={asset.data_sensitivity_source}
        groupName={asset.data_sensitivity_group_name}
        isAdmin={isAdmin}
        mutation={mutation}
        kind="select"
        options={SENSITIVITY_OPTIONS}
        currentValue={asset.data_sensitivity ?? SENSITIVITY_OPTIONS[1]}
      />
      <ExposureRow
        field="internet_facing"
        label="Internet-facing"
        displayValue={asset.internet_facing === null ? '—' : asset.internet_facing ? 'Yes' : 'No'}
        source={asset.internet_facing_source}
        groupName={asset.internet_facing_group_name}
        isAdmin={isAdmin}
        mutation={mutation}
        kind="toggle"
        currentValue={asset.internet_facing}
      />
    </section>
  );
}
