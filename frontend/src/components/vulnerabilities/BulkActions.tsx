"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface Props {
  selectedCount: number;
  selectedIds: string[];
  onComplete: () => void;
}

const ACTIONS = [
  { status: "IN_PROGRESS", label: "Mark In Progress", icon: AlertTriangle, color: "text-yellow-400" },
  { status: "REMEDIATED", label: "Mark Remediated", icon: CheckCircle2, color: "text-emerald-400" },
  { status: "SUPPRESSED", label: "Suppress", icon: XCircle, color: "text-gray-400" },
  { status: "FALSE_POSITIVE", label: "False Positive", icon: XCircle, color: "text-gray-500" },
];

export default function BulkActions({ selectedCount, selectedIds, onComplete }: Props) {
  const [loading, setLoading] = useState(false);

  async function handleAction(status: string) {
    setLoading(true);
    try {
      await api("/api/v1/vulnerabilities/bulk-status", {
        method: "POST",
        body: JSON.stringify({
          vulnerability_ids: selectedIds,
          status,
        }),
      });
      onComplete();
    } catch (e) {
      console.error("Bulk action failed:", e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-2.5">
      <span className="text-sm font-medium text-indigo-400">
        {selectedCount} selected
      </span>
      <div className="h-4 w-px bg-indigo-500/30" />
      {ACTIONS.map((action) => (
        <button
          key={action.status}
          onClick={() => handleAction(action.status)}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:bg-gray-800"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <action.icon className={`h-3.5 w-3.5 ${action.color}`} />
          )}
          {action.label}
        </button>
      ))}
    </div>
  );
}
