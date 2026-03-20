"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, Loader2, Ticket } from "lucide-react";
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
  const [ticketLoading, setTicketLoading] = useState(false);
  const [ticketResult, setTicketResult] = useState<string | null>(null);

  async function handleAction(status: string) {
    setLoading(true);
    try {
      await api("/api/v1/vulnerabilities/bulk-status", {
        method: "POST",
        body: JSON.stringify({ vulnerability_ids: selectedIds, status }),
      });
      onComplete();
    } catch (e) {
      console.error("Bulk action failed:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateTicket() {
    setTicketLoading(true);
    setTicketResult(null);
    try {
      const result = await api<{ created: number; tickets: any[] }>("/api/v1/tickets", {
        method: "POST",
        body: JSON.stringify({
          vulnerability_ids: selectedIds,
          provider: "ASANA",
          project_key: "",  // Uses default configured project
        }),
      });
      setTicketResult(`${result.created} ticket(s) created in Asana`);
      setTimeout(() => setTicketResult(null), 4000);
      onComplete();
    } catch (e: any) {
      setTicketResult(`Failed: ${e.message}`);
      setTimeout(() => setTicketResult(null), 5000);
    } finally {
      setTicketLoading(false);
    }
  }

  return (
    <div className="space-y-2">
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
        <div className="h-4 w-px bg-indigo-500/30" />
        <button
          onClick={handleCreateTicket}
          disabled={ticketLoading}
          className="flex items-center gap-1.5 rounded-lg bg-orange-600/20 border border-orange-500/30 px-3 py-1.5 text-xs font-medium text-orange-400 transition-colors hover:bg-orange-600/30"
        >
          {ticketLoading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Ticket className="h-3.5 w-3.5" />
          )}
          Create Ticket
        </button>
      </div>
      {ticketResult && (
        <div className={`rounded-lg px-4 py-2 text-xs font-medium ${
          ticketResult.startsWith("Failed") ? "bg-red-500/10 text-red-400" : "bg-emerald-500/10 text-emerald-400"
        }`}>
          {ticketResult}
        </div>
      )}
    </div>
  );
}
