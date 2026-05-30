'use client';
/**
 * OwnerCard — UX-04-04 right-rail card.
 *
 * Flip-edit pattern (D-A-01):
 *   - Default mode: avatar + name + role + IdP pill + email + "Reassign" button.
 *   - Edit mode: <ReassignCombobox /> inline (no modal, no sheet — analyst stays
 *     on the asset detail page).
 *
 * Fallback hierarchy when directory_user is absent (Pitfall 4):
 *   - display_name → assigned_user email → "Unassigned"
 *   - role         → "Unassigned in directory" (when email exists) | "No owner set"
 *   - IdP pill is HIDDEN when directory_user is null (no orphan source label).
 *
 * Threat anchors (T-12-04): Avatar + name + email + idp_source labels render
 * as React text children. IdpPill maps `source.toLowerCase()` through a
 * hardcoded label table; unknown sources render as raw text (no innerHTML).
 */
import { useState } from 'react';
import { Avatar } from '@/components/ui/Avatar';
import { ReassignCombobox } from './reassign-combobox';
import type { AssetDetail } from '@/lib/queries/use-asset-detail';

const IDP_LABEL: Record<string, string> = {
  google: 'Google',
  azure: 'Azure',
  okta: 'Okta',
  humaans: 'Humaans',
  microsoft: 'Microsoft',
  local: 'Local',
};

function IdpPill({ source }: { source: string }) {
  // T-12-04: unknown values fall through as raw text — never innerHTML.
  const label = IDP_LABEL[source.toLowerCase()] ?? source;
  return (
    <span
      className="rounded-full border border-border-subtle bg-surface px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide text-text-muted"
      data-testid="idp-pill"
    >
      {label}
    </span>
  );
}

export function OwnerCard({ asset }: { asset: AssetDetail }) {
  const [isEditing, setIsEditing] = useState(false);
  const du = asset.directory_user;

  // Fallback hierarchy.
  const displayName = du?.display_name ?? asset.assigned_user ?? 'Unassigned';
  const role =
    du?.role ?? (asset.assigned_user ? 'Unassigned in directory' : 'No owner set');

  if (isEditing) {
    return (
      <section
        className="rounded-lg border border-border-subtle bg-surface-2 p-4"
        aria-label="Owner — edit mode"
      >
        <ReassignCombobox
          assetId={asset.id}
          initialEmail={asset.assigned_user}
          onDone={() => setIsEditing(false)}
        />
      </section>
    );
  }

  return (
    <section
      className="rounded-lg border border-border-subtle bg-surface-2 p-4"
      aria-label="Owner"
      data-testid="owner-card"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Avatar
            name={du?.display_name ?? undefined}
            email={asset.assigned_user ?? undefined}
            size={40}
          />
          <div className="space-y-0.5">
            <div className="text-sm font-medium text-text" data-testid="owner-name">
              {displayName}
            </div>
            <div className="text-xs text-text-muted">{role}</div>
            {asset.assigned_user && displayName !== asset.assigned_user && (
              <div className="text-xs font-mono text-text-muted">{asset.assigned_user}</div>
            )}
            {/* When displayName falls back to the email, render the email
                exactly once (rendered via displayName). The line above is
                suppressed in that case to avoid duplication. */}
            {du?.idp_source && (
              <div className="pt-1">
                <IdpPill source={du.idp_source} />
              </div>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setIsEditing(true)}
          className="text-xs text-violet hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
          data-testid="owner-reassign-btn"
        >
          Reassign
        </button>
      </div>
    </section>
  );
}
