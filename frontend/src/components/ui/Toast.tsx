"use client";
import { useEffect, useState } from "react";
import { X } from "lucide-react";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastData {
  id: string;
  title?: string;
  message: string;
  variant?: "success" | "error" | "info";
  // Phase 10: default 3000ms (Phase 9 backward compat). D-H-08 callers pass 8000.
  duration?: number;
  // Phase 10: optional inline action (e.g., Undo on Snooze toast). Renders as
  // an underlined button below the message; consumer-supplied onClick fires
  // in the user's own session per T-10-15a (action is caller-controlled).
  action?: ToastAction;
}

interface ToastProps extends ToastData {
  onDismiss: (id: string) => void;
}

// Sunset CSS-variable tokens (consumed via tailwind.config.ts color mappings):
//   border-success / text-success → var(--color-success)
//   border-danger  / text-danger  → var(--color-danger)
//   border-info    / text-info    → var(--color-info)
//   bg-surface-2                  → var(--color-surface-2) (elevated card surface)
//   text-text-muted               → var(--color-text-muted)
//   text-text                     → var(--color-text)
// Phase 9 pattern (login alert): solid border + accent text, no opacity modifiers
// (CSS-var colors in this config don't carry an <alpha-value> placeholder).
export default function Toast({
  id,
  title,
  message,
  variant = "info",
  duration = 3000,
  action,
  onDismiss,
}: ToastProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // slide in
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(id), 200);
    }, duration);
    return () => clearTimeout(timer);
  }, [id, duration, onDismiss]);

  const borderClass =
    variant === "success"
      ? "border-success"
      : variant === "error"
        ? "border-danger"
        : "border-info";

  const accentClass =
    variant === "success"
      ? "text-success"
      : variant === "error"
        ? "text-danger"
        : "text-info";

  return (
    <div
      className={[
        "pointer-events-auto w-80 rounded-lg border p-4 shadow-card",
        "bg-surface-2",
        borderClass,
        // motion-reduce: keep visible state but skip the slide animation.
        "transition-all duration-200 motion-reduce:transition-none",
        visible
          ? "translate-x-0 opacity-100"
          : "translate-x-4 opacity-0 motion-reduce:translate-x-0",
      ].join(" ")}
      role={variant === "error" ? "alert" : "status"}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {title && <p className={`text-sm font-medium ${accentClass}`}>{title}</p>}
          <p className={`text-sm text-text-muted ${title ? "mt-0.5" : ""}`}>{message}</p>
          {action && (
            <button
              type="button"
              onClick={action.onClick}
              className={[
                "mt-2 text-xs font-medium underline underline-offset-2",
                accentClass,
                "hover:opacity-80",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
              ].join(" ")}
            >
              {action.label}
            </button>
          )}
        </div>
        <button
          type="button"
          aria-label="Dismiss"
          onClick={() => {
            setVisible(false);
            setTimeout(() => onDismiss(id), 200);
          }}
          className="shrink-0 text-text-faint hover:text-text transition motion-reduce:transition-none"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
