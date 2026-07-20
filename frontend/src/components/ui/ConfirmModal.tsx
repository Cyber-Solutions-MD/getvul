"use client";
/**
 * ConfirmModal — danger/warning/info confirmation dialog.
 *
 * D-07 (Phase 15-03): Now routes through ResponsiveDialog which renders a vaul
 * bottom sheet on mobile (<768px) and the existing centered modal on desktop.
 *
 * PUBLIC API IS UNCHANGED — all 5 call sites work without modification:
 *   connectors/page.tsx, settings/page.tsx, components/settings/workspace-pane.tsx,
 *   components/tickets/ticket-bulk-bar.tsx, components/vulnerabilities/drill-content.tsx
 */
import { useEffect, useRef } from "react";
import { ResponsiveDialog } from "./responsive-dialog";
import { useMediaQuery } from "@/hooks/use-media-query";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "info";
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "info",
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  // SSR-safe: false on server / first render → desktop path (same as ResponsiveDialog).
  const isMobile = useMediaQuery("(max-width: 767px)");

  // Focus the confirm button on open.
  // Guard: on mobile, vaul manages focus — one programmatic focus is tolerated
  // but we skip it to avoid racing vaul's internal focus management.
  useEffect(() => {
    if (open && !isMobile) {
      confirmRef.current?.focus();
    }
  }, [open, isMobile]);

  // WR-01: the desktop Esc handler + Tab focus-trap now live in ResponsiveDialog
  // itself (document-level), so ConfirmModal no longer wires its own — keeping
  // both would double-handle Esc (calling onCancel twice) and double-run the
  // Tab trap on the same modal. On mobile vaul owns focus + Esc as before.

  // Sunset token mapping — Phase 14 restyle (Pitfall 2, D-CONN-06).
  // No raw palette utilities (gray-*, indigo-*, red-600, yellow-*).
  const btnColor =
    variant === "danger"
      ? "bg-severity-critical text-white hover:bg-severity-critical/90"
      : variant === "warning"
        ? "bg-amber text-surface hover:bg-amber/90"
        : "bg-violet text-white hover:bg-violet/90";

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onCancel();
      }}
      ariaLabel={title}
    >
      {/* Content wrapper. Focus containment (desktop Tab trap) is handled by
          ResponsiveDialog's panelRef around this subtree; on mobile vaul's
          Drawer.Content is the focus scope. */}
      <div>
        {/* Mobile: add top padding for the drag handle + comfortable reading */}
        <div className="px-2 pt-4 pb-2 min-[768px]:p-0">
          <h3 className="text-lg font-semibold text-text">{title}</h3>
          <p className="mt-2 text-sm text-text-muted whitespace-pre-wrap">{message}</p>
          <div className="mt-6 flex justify-end gap-3 pb-[env(safe-area-inset-bottom)]">
            <button
              onClick={onCancel}
              className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-text-muted hover:text-text hover:bg-surface transition"
            >
              {cancelLabel}
            </button>
            <button
              ref={confirmRef}
              onClick={onConfirm}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-surface-2 ${btnColor}`}
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </ResponsiveDialog>
  );
}
