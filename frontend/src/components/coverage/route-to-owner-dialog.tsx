'use client';
/**
 * RouteToOwnerDialog — Phase 41 Plan 05 (COV-03): the 2-branch, no-form-field
 * confirm dialog for the "Route to owner" row/drill action. Wraps
 * `ResponsiveDialog` directly (not `ConfirmModal` — its variant→color map is
 * danger/warning/info, none of which is the required violet-focus secondary
 * chrome; not `ExceptionGrantDialog` either — that dialog is a real 4-field
 * form, and this action has zero fields, D-09 explicitly rejects a manual
 * owner-entry field).
 *
 * Two copy branches (41-UI-SPEC.md Copywriting Contract, D-07/D-09):
 *   - `ownerResolved=true`  — "Notify {owner} about this device?" / "Notify owner"
 *   - `ownerResolved=false` — "No owner found for this device" / "Notify admins"
 * Presentational only — the caller supplies `ownerResolved`/`ownerName` and
 * owns the mutation (`onConfirm` + `isPending`); this component decides
 * nothing about WHICH branch applies (see microcopy.ts's doc comment on why
 * every current call site passes `ownerResolved={false}`).
 *
 * Confirm button uses secondary (`.btn-secondary`-equivalent) chrome with a
 * violet focus ring — NEVER `bg-gradient-sunset` (UI-SPEC Color: this page
 * has no page-level primary CTA).
 */
import { microcopy } from './microcopy';
import { ResponsiveDialog } from '@/components/ui/responsive-dialog';

export type RouteToOwnerDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The blind-spot asset's hostname — interpolated into the resolved-owner body copy. */
  hostname: string;
  /** True when a directory owner is already known for this row (see module doc — never true today). */
  ownerResolved: boolean;
  /** Owner display name, used for the resolved branch's title/body (first name only). */
  ownerName?: string | null;
  onConfirm: () => void;
  isPending: boolean;
};

const CONFIRM_BTN_CLASS =
  'inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:pointer-events-none disabled:opacity-50';

const CANCEL_BTN_CLASS =
  'rounded-lg border border-border-subtle px-4 py-2 text-sm text-text-muted hover:text-text hover:bg-surface transition';

export function RouteToOwnerDialog({
  open,
  onOpenChange,
  hostname,
  ownerResolved,
  ownerName,
  onConfirm,
  isPending,
}: RouteToOwnerDialogProps) {
  const firstName = (ownerName ?? '').trim().split(/\s+/)[0] || 'the owner';
  const copy = ownerResolved
    ? {
        title: microcopy.routeToOwner.dialog.resolved.title(firstName),
        body: microcopy.routeToOwner.dialog.resolved.body(hostname, firstName),
        confirmLabel: microcopy.routeToOwner.dialog.resolved.confirm,
      }
    : {
        title: microcopy.routeToOwner.dialog.unresolvable.title,
        body: microcopy.routeToOwner.dialog.unresolvable.body,
        confirmLabel: microcopy.routeToOwner.dialog.unresolvable.confirm,
      };

  const titleId = 'route-to-owner-title';

  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange} ariaLabelledBy={titleId}>
      <div className="p-6">
        <h2 id={titleId} className="text-lg font-semibold text-text">
          {copy.title}
        </h2>
        <p className="mt-2 text-sm text-text-muted whitespace-pre-wrap">{copy.body}</p>
        <div className="mt-6 flex justify-end gap-3 pb-[env(safe-area-inset-bottom)]">
          <button type="button" onClick={() => onOpenChange(false)} className={CANCEL_BTN_CLASS}>
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className={CONFIRM_BTN_CLASS}
          >
            {isPending ? microcopy.routeToOwner.pendingLabel : copy.confirmLabel}
          </button>
        </div>
      </div>
    </ResponsiveDialog>
  );
}
