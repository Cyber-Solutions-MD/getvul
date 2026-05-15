"use client";
import { createContext, useCallback, useContext, useState } from "react";
import Toast, { type ToastData, type ToastAction } from "./Toast";

// ToastInput is the public API for callers. Phase 9 callers pass {title?, message, variant?}
// and continue to work — `duration` defaults to 3000 in Toast.tsx and `action` is optional.
interface ToastInput {
  title?: string;
  message: string;
  variant?: "success" | "error" | "info";
  // Phase 10 additions (D-H-08 — snooze undo flow):
  duration?: number;
  action?: ToastAction;
}

interface ToastContextValue {
  toast: (input: ToastInput) => void;
}

const ToastContext = createContext<ToastContextValue>({
  toast: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}

let toastCounter = 0;

export default function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const addToast = useCallback((input: ToastInput) => {
    const id = `toast-${++toastCounter}-${Date.now()}`;
    // Spread carries `duration` + `action` through to Toast (additive surface).
    setToasts((prev) => [...prev, { id, ...input }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      {/* Toast container — top-right */}
      <div className="fixed top-4 right-4 z-[60] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <Toast key={t.id} {...t} onDismiss={dismissToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
