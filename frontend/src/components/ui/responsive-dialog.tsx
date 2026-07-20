'use client';
/**
 * ResponsiveDialog — desktop centered modal / mobile vaul bottom sheet.
 *
 * D-07 (Phase 15-03): All app modals/dialogs convert to vaul bottom sheets
 * on mobile (<768px), matching the existing DrillPanelMobile treatment.
 *
 * Desktop branch:  role="dialog" centered modal (preserves existing test contracts).
 * Mobile branch:   vaul Drawer.Root bottom sheet — vaul handles Esc + focus trap;
 *                  no custom focus-trap code needed in this branch.
 *
 * Guard pattern: when !open return null — prevents lingering portal chrome from
 * breaking the `queryByRole('dialog') === null` contract in jsdom tests.
 * (Mirrors drill-panel-mobile.tsx precedent, commit 7a789cd.)
 */

import React from 'react';
import { Drawer } from 'vaul';
import { useMediaQuery } from '@/hooks/use-media-query';

interface ResponsiveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Aria label for the dialog container — used directly when ariaLabelledBy is absent. */
  ariaLabel?: string;
  /** aria-labelledby id — points to a heading element inside children. */
  ariaLabelledBy?: string;
  /**
   * Desktop backdrop-click dismisses the dialog. Default true (ConfirmModal
   * parity). Pass false for a D-13 no-op backdrop — X and Esc still close.
   */
  dismissOnBackdropClick?: boolean;
  children: React.ReactNode;
}

export function ResponsiveDialog({
  open,
  onOpenChange,
  ariaLabel,
  ariaLabelledBy,
  dismissOnBackdropClick = true,
  children,
}: ResponsiveDialogProps) {
  // SSR-safe: returns false on server / first client render → desktop branch
  // renders on first hydration, avoiding hydration mismatch. After mount, the
  // effect in useMediaQuery updates to the real breakpoint value.
  const isMobile = useMediaQuery('(max-width: 767px)');

  // Guard — no lingering portal chrome when closed.
  // Matches the drill-panel-mobile.tsx `if (!open) return null` pattern.
  if (!open) return null;

  // ── Mobile branch: vaul bottom sheet ──────────────────────────────────────
  // vaul handles: Esc-to-close, focus trap, overlay dismissal, gesture drag.
  // Custom trapTabKey is NOT needed here. `dismissOnBackdropClick` is a
  // desktop-only concern (see the branch below) — vaul's own swipe/overlay
  // dismissal on mobile is out of this prop's scope.
  if (isMobile) {
    return (
      <Drawer.Root open={open} onOpenChange={onOpenChange} direction="bottom">
        <Drawer.Portal>
          <Drawer.Overlay className="fixed inset-0 z-[9000] bg-bg-darker/60" />
          <Drawer.Content
            className="fixed inset-x-0 bottom-0 z-[9001] max-h-[85dvh] overflow-y-auto rounded-t-lg border-t border-border-subtle bg-surface"
            aria-label={ariaLabel}
            aria-labelledby={ariaLabelledBy}
          >
            {/* sr-only title satisfies vaul's Drawer.Title requirement without
                duplicating the visible heading rendered by children. */}
            {ariaLabel && (
              <Drawer.Title className="sr-only">{ariaLabel}</Drawer.Title>
            )}
            {children}
          </Drawer.Content>
        </Drawer.Portal>
      </Drawer.Root>
    );
  }

  // ── Desktop branch: centered modal ────────────────────────────────────────
  // Preserves the existing shell that all 5 ConfirmModal call sites rely on.
  // role="dialog" is on the inner div so jsdom test assertions continue to
  // pass (useMediaQuery returns false on first render → desktop always in jsdom).
  // Backdrop-click dismisses by default (ConfirmModal parity — those 5 call
  // sites never pass `dismissOnBackdropClick`, so nothing changes for them).
  // When the caller passes `dismissOnBackdropClick={false}` (the connectors
  // add/edit dialog, D-13), a backdrop click is a true no-op — only the X
  // button and Esc close it. Esc always closes regardless of this prop.
  // The caller (ConfirmModal) retains its own Esc + trapTabKey effects so the
  // desktop focus-trap contract is not regressed.
  return (
    // Backdrop: click-on-backdrop (when enabled) or Esc dismisses the dialog.
    // role="presentation" removes landmark semantics from the overlay layer so
    // assistive technology only announces the inner role="dialog".
    // onClick guard (e.target === e.currentTarget) prevents close when the user
    // clicks inside the dialog panel — no stopPropagation needed on the inner div.
    <div
      role="presentation"
      className="fixed inset-0 z-[9000] flex items-center justify-center bg-surface/80 backdrop-blur-sm"
      onClick={(e) => { if (dismissOnBackdropClick && e.target === e.currentTarget) onOpenChange(false); }}
      onKeyDown={(e) => { if (e.key === 'Escape') onOpenChange(false); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        tabIndex={-1}
        className="mx-4 w-full max-w-md rounded-xl border border-border-subtle bg-surface-2 p-6 shadow-2xl"
      >
        {children}
      </div>
    </div>
  );
}
