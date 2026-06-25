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
import { getFocusable, trapTabKey } from "./focus-trap";
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
  const panelRef = useRef<HTMLDivElement>(null);

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

  // WR-04: Escape to dismiss (belt-and-suspenders — vaul also handles Esc on mobile).
  // Desktop Tab trap — keeps focus inside the dialog while on desktop.
  // On mobile the Tab trap is dropped: vaul's dialog primitive manages focus
  // natively and the Drawer.Content is the focus scope.
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCancel();
        return;
      }
      // Desktop-only Tab trap — panelRef resolves to the inner div on desktop;
      // on mobile panelRef may be null if the children render inside the Drawer.
      if (e.key === "Tab" && panelRef.current && !isMobile) {
        trapTabKey(e, getFocusable(panelRef.current));
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onCancel, isMobile]);

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
      {/* This inner wrapper is referenced by panelRef for the desktop focus trap.
          On mobile the children render inside Drawer.Content which is vaul's
          focus scope — panelRef is still attached but trapTabKey is skipped
          (isMobile guard above). */}
      <div ref={panelRef}>
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
