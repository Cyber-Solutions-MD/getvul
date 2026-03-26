"use client";
import { useEffect, useState } from "react";
import { X } from "lucide-react";

export interface ToastData {
  id: string;
  title?: string;
  message: string;
  variant?: "success" | "error" | "info";
}

interface ToastProps extends ToastData {
  onDismiss: (id: string) => void;
}

export default function Toast({ id, title, message, variant = "info", onDismiss }: ToastProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // slide in
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(id), 200);
    }, 3000);
    return () => clearTimeout(timer);
  }, [id, onDismiss]);

  const borderColor =
    variant === "success"
      ? "border-emerald-500/40"
      : variant === "error"
        ? "border-red-500/40"
        : "border-indigo-500/40";

  const accentColor =
    variant === "success"
      ? "text-emerald-400"
      : variant === "error"
        ? "text-red-400"
        : "text-indigo-400";

  return (
    <div
      className={`pointer-events-auto w-80 rounded-lg border ${borderColor} bg-gray-900 p-4 shadow-xl transition-all duration-200 ${
        visible ? "translate-x-0 opacity-100" : "translate-x-4 opacity-0"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {title && <p className={`text-sm font-medium ${accentColor}`}>{title}</p>}
          <p className={`text-sm text-gray-300 ${title ? "mt-0.5" : ""}`}>{message}</p>
        </div>
        <button
          onClick={() => {
            setVisible(false);
            setTimeout(() => onDismiss(id), 200);
          }}
          className="shrink-0 text-gray-500 hover:text-gray-300 transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
