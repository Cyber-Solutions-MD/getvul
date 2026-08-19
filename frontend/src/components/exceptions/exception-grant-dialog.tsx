'use client';
/**
 * ExceptionGrantDialog — Phase 39 Plan 07 (EXC-01) the 4-field grant form
 * opened from the vuln drill panel's "Accept risk" / "Mark false positive"
 * buttons (drill-content.tsx). Wraps ResponsiveDialog directly (not
 * ConfirmModal — this is a real form with field-level validation, not a
 * confirm/cancel prompt).
 *
 * Field order is fixed (39-UI-SPEC.md Layout §2): Scope → Approver →
 * Justification → Expires. Expires is the visual focal point — it anchors
 * the form directly above the primary action with an always-visible helper
 * sentence, so the most consequence-bearing field is never submitted past
 * without being seen (EXC-02/EXC-04 "never permanently silenced").
 *
 * Scope semantics: this dialog always opens FROM a specific finding (CVE ×
 * asset). Broadening scope to "This asset" / "Asset group" keeps the SAME
 * CVE (`finding.cveId`) but widens the blast radius to all current AND
 * future detections of that CVE on the asset / asset group (D-11 forward-
 * looking) — there is no separate CVE input field; the mockup only shows
 * Scope/Approver/Justification/Expires (4 fields total).
 *
 * D-06: "Grant exception" (gradient CTA) stays disabled until scope target +
 * approver + justification + expiry are ALL filled — no partial submit.
 *
 * Error handling (39-UI-SPEC.md Copywriting Contract): the backend already
 * returns specific, well-worded HTTPException messages per failure branch.
 * classifyGrantError maps them to exactly the three response-time UI-SPEC
 * error surfaces this dialog owns (approver-fetch errors are a SEPARATE,
 * fourth surface owned entirely inside approver-combobox.tsx):
 *   - D-14 expiry-cap messages (server text always starts with "Pick a
 *     date...") -> field-level, under Expires.
 *   - The exact D-03 precondition string -> dialog-level banner, verbatim.
 *   - Anything else (404 target-not-found, inactive-approver 400, network
 *     failure, ...) -> the generic "Exception wasn't saved. HTTP {code} ·
 *     Retry." banner — never a bare "Something went wrong" (copy-voice.md).
 */
import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { ResponsiveDialog } from '@/components/ui/responsive-dialog';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ApproverCombobox, type SelectedApprover } from './approver-combobox';
import { useGrantException, type GrantExceptionBody } from '@/lib/queries/use-exception-mutations';
import { useAssetGroupsList } from '@/lib/queries/use-asset-groups';
import type { ExceptionType, ExceptionScopeType } from '@/lib/queries/use-exceptions';

// Mirrors backend/app/exceptions/service.py's DEFAULT_EXPIRY_DAYS /
// MAX_EXPIRY_DAYS exactly (client UX pre-fill only — the server never needs
// these to match byte-for-byte; validate_expiry is the sole authority,
// T-39-25).
const DEFAULT_EXPIRY_DAYS: Record<ExceptionType, number> = { FALSE_POSITIVE: 180, ACCEPTED_RISK: 90 };
const MAX_EXPIRY_DAYS = 365;

const JUSTIFICATION_MAX_LENGTH = 1000;
const JUSTIFICATION_WARN_THRESHOLD = 950;

// Mirrors sla-escalation-pane.tsx:267-268's FIELD_CLASS — the codebase's
// established native <select>/<input type=date> styling convention this
// phase follows instead of shadcn's Radix select/popover (39-UI-SPEC.md
// Design System).
const FIELD_CLASS =
  'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

const FIELD_LABEL_CLASS = 'mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted';

const TYPE_CHIP_CONFIG: Record<ExceptionType, { classes: string; label: string }> = {
  FALSE_POSITIVE: {
    classes: 'border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]',
    label: 'False positive',
  },
  ACCEPTED_RISK: {
    classes: 'border-amber/40 bg-amber/10 text-[var(--color-amber-on-soft)]',
    label: 'Accept risk',
  },
};

const SCOPE_OPTIONS: { value: ExceptionScopeType; label: string }[] = [
  { value: 'FINDING', label: 'This finding' },
  { value: 'ASSET', label: 'This asset' },
  { value: 'ASSET_GROUP', label: 'Asset group' },
];

export type ExceptionFinding = {
  /** Vulnerability row id — required for FINDING scope (server derives
   * cve_id/asset_id from it, Pitfall 9; the dialog never sends an
   * independent free cve_id for FINDING, T-39-26). */
  vulnerabilityId: string;
  cveId: string | null;
  assetId: string | null;
  hostname: string | null;
};

export type ExceptionGrantDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pre-set by the triggering drill-panel button — never chosen inside the dialog. */
  type: ExceptionType;
  finding: ExceptionFinding;
};

function isoDateOnly(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function addDaysUtc(base: Date, days: number): Date {
  const d = new Date(base);
  d.setUTCDate(d.getUTCDate() + days);
  return d;
}

/** Maps a grant-mutation error to the UI-SPEC's field-level vs. dialog-level
 * surfaces. Returns both as null when there is no error. */
function classifyGrantError(error: unknown): { banner: string | null; expiryField: string | null } {
  if (!(error instanceof ApiError)) return { banner: null, expiryField: null };
  if (error.message.startsWith('Pick a date')) {
    return { banner: null, expiryField: error.message };
  }
  if (error.message === 'This finding is already remediated — nothing to except.') {
    return { banner: error.message, expiryField: null };
  }
  return { banner: `Exception wasn't saved. HTTP ${error.code} · Retry.`, expiryField: null };
}

function buildPayload(
  type: ExceptionType,
  scope: ExceptionScopeType,
  finding: ExceptionFinding,
  selectedGroupId: string,
  approverId: string,
  justification: string,
  expiresAtIso: string,
): GrantExceptionBody {
  const base = { type, justification, approver_user_id: approverId, expires_at: expiresAtIso };
  if (scope === 'FINDING') {
    return { ...base, scope_type: 'FINDING', vulnerability_id: finding.vulnerabilityId };
  }
  if (scope === 'ASSET') {
    return { ...base, scope_type: 'ASSET', asset_id: finding.assetId ?? '', cve_id: finding.cveId ?? '' };
  }
  return { ...base, scope_type: 'ASSET_GROUP', asset_group_id: selectedGroupId, cve_id: finding.cveId ?? '' };
}

export function ExceptionGrantDialog({ open, onOpenChange, type, finding }: ExceptionGrantDialogProps) {
  const [scope, setScope] = useState<ExceptionScopeType>('FINDING');
  const [approver, setApprover] = useState<SelectedApprover | null>(null);
  const [justification, setJustification] = useState('');
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [expiresAt, setExpiresAt] = useState('');

  const mutation = useGrantException();
  const groupsQuery = useAssetGroupsList();

  // Reset to the fresh, type-defaulted state every time the dialog opens —
  // it stays mounted across open/close cycles (drill-content.tsx renders it
  // once, unconditionally), so state from a PREVIOUS finding/type must never
  // leak into the next open. mutation.reset() clears a stale error banner
  // from a previous failed attempt.
  useEffect(() => {
    if (!open) return;
    setScope('FINDING');
    setApprover(null);
    setJustification('');
    setSelectedGroupId('');
    setExpiresAt(isoDateOnly(addDaysUtc(new Date(), DEFAULT_EXPIRY_DAYS[type])));
    mutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, type]);

  const minDate = isoDateOnly(addDaysUtc(new Date(), 1));
  const maxDate = isoDateOnly(addDaysUtc(new Date(), MAX_EXPIRY_DAYS));

  const scopeTargetFilled =
    scope === 'FINDING' ? true : scope === 'ASSET' ? !!finding.assetId : !!selectedGroupId;
  const canSubmit =
    scopeTargetFilled && !!approver && justification.trim().length > 0 && !!expiresAt && !mutation.isPending;

  const { banner: dialogBannerError, expiryField: expiryFieldError } = classifyGrantError(mutation.error);

  const handleSubmit = () => {
    if (!scopeTargetFilled || !approver || justification.trim().length === 0 || !expiresAt) return;
    const payload = buildPayload(
      type,
      scope,
      finding,
      selectedGroupId,
      approver.id,
      justification.trim(),
      `${expiresAt}T00:00:00.000Z`,
    );
    mutation.mutate(payload, { onSuccess: () => onOpenChange(false) });
  };

  const typeChip = TYPE_CHIP_CONFIG[type];
  const titleId = 'grant-exception-title';

  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange} ariaLabelledBy={titleId}>
      <div className="p-6">
        <div className="mb-1 flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs',
                typeChip.classes,
              )}
            >
              <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
              {typeChip.label}
            </span>
            <h2 id={titleId} className="text-lg font-semibold text-text">
              Grant exception
            </h2>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Close"
            className="rounded-md p-1 text-text-faint transition-colors hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
          >
            <X size={18} />
          </button>
        </div>
        <p className="mb-4 font-mono text-xs text-text-muted">
          {finding.cveId ?? '—'} on {finding.hostname ?? '—'}
        </p>

        {dialogBannerError && (
          <div role="alert" className="mb-4 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-xs text-danger">
            {dialogBannerError}
          </div>
        )}

        <div className="space-y-4">
          {/* Scope */}
          <div>
            <span className={FIELD_LABEL_CLASS}>Scope</span>
            <div role="group" aria-label="Scope" className="inline-flex rounded-full border border-border-subtle bg-surface p-0.5">
              {SCOPE_OPTIONS.map((opt) => {
                const disabled =
                  (opt.value === 'ASSET' && !finding.assetId) ||
                  ((opt.value === 'ASSET' || opt.value === 'ASSET_GROUP') && !finding.cveId);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setScope(opt.value)}
                    disabled={disabled}
                    aria-pressed={scope === opt.value}
                    className={cn(
                      'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                      'disabled:cursor-not-allowed disabled:opacity-40',
                      scope === opt.value
                        ? 'border border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]'
                        : 'text-text-muted hover:text-text',
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
            {scope === 'ASSET_GROUP' && (
              <select
                aria-label="Asset group"
                value={selectedGroupId}
                onChange={(e) => setSelectedGroupId(e.target.value)}
                disabled={groupsQuery.isLoading}
                className={cn(FIELD_CLASS, 'mt-2')}
              >
                <option value="">
                  {groupsQuery.isLoading ? 'Loading asset groups…' : 'Select a group…'}
                </option>
                {(groupsQuery.data ?? []).map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Approver */}
          <div>
            <span className={FIELD_LABEL_CLASS}>Approver</span>
            <ApproverCombobox value={approver} onSelect={setApprover} />
          </div>

          {/* Justification */}
          <div>
            <label htmlFor="exception-justification" className={FIELD_LABEL_CLASS}>
              Justification
            </label>
            <textarea
              id="exception-justification"
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              maxLength={JUSTIFICATION_MAX_LENGTH}
              rows={4}
              placeholder="Why is this a false positive, or why is the risk acceptable?"
              className={FIELD_CLASS}
            />
            <div className="mt-1 flex justify-end">
              {justification.length >= JUSTIFICATION_WARN_THRESHOLD && (
                <span className="font-mono text-xs text-text-muted">
                  {JUSTIFICATION_MAX_LENGTH - justification.length} characters left
                </span>
              )}
            </div>
          </div>

          {/* Expires — the visual focal point (39-UI-SPEC.md Layout §2). */}
          <div>
            <label htmlFor="exception-expires" className={FIELD_LABEL_CLASS}>
              Expires
            </label>
            <input
              id="exception-expires"
              type="date"
              min={minDate}
              max={maxDate}
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className={FIELD_CLASS}
            />
            {expiryFieldError ? (
              <p role="alert" className="mt-1 text-xs text-danger">
                {expiryFieldError}
              </p>
            ) : (
              <p className="mt-1 text-xs text-text-muted">
                Mandatory — this decision resurfaces for review on this date.
              </p>
            )}
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-text-muted hover:text-text hover:bg-surface transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="btn-cta inline-flex items-center justify-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:pointer-events-none disabled:opacity-50"
          >
            {mutation.isPending ? 'Granting…' : 'Grant exception'}
          </button>
        </div>
      </div>
    </ResponsiveDialog>
  );
}
