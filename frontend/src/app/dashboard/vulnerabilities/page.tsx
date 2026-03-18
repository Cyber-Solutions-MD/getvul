"use client";

import { useCallback, useEffect, useState } from "react";
import { Bug, Download, RefreshCw, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import VulnFilters, {
  type VulnFilterState,
} from "@/components/vulnerabilities/VulnFilters";
import VulnTable from "@/components/vulnerabilities/VulnTable";
import BulkActions from "@/components/vulnerabilities/BulkActions";
import Pagination from "@/components/ui/Pagination";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface PaginatedVulns {
  items: VulnerabilitySummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const DEFAULT_FILTERS: VulnFilterState = {
  search: "",
  severity: [],
  source: [],
  status: [],
  exploit_available: null,
  cisa_kev: null,
};

export default function VulnerabilitiesPage() {
  const [data, setData] = useState<PaginatedVulns | null>(null);
  const [filters, setFilters] = useState<VulnFilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(pageSize));

      if (filters.search) params.set("search", filters.search);
      filters.severity.forEach((s) => params.append("severity", s));
      filters.source.forEach((s) => params.append("source", s));
      filters.status.forEach((s) => params.append("status", s));
      if (filters.exploit_available !== null)
        params.set("exploit_available", String(filters.exploit_available));
      if (filters.cisa_kev !== null)
        params.set("cisa_kev", String(filters.cisa_kev));

      const result = await api<PaginatedVulns>(
        `/api/v1/vulnerabilities?${params.toString()}`
      );
      setData(result);
    } catch (e) {
      console.error("Failed to fetch vulnerabilities:", e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  useEffect(() => {
    const debounce = setTimeout(fetchData, 300);
    return () => clearTimeout(debounce);
  }, [fetchData]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
  }, [filters]);

  function handleSelectToggle(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSelectAll(ids: string[]) {
    if (ids.length === 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(ids));
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bug className="h-6 w-6 text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Vulnerabilities</h1>
            {data && (
              <p className="text-sm text-gray-400">
                {data.total.toLocaleString()} total vulnerabilities
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-800"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <VulnFilters filters={filters} onChange={setFilters} />

      {/* Bulk actions */}
      {selectedIds.size > 0 && (
        <BulkActions
          selectedCount={selectedIds.size}
          selectedIds={Array.from(selectedIds)}
          onComplete={() => {
            setSelectedIds(new Set());
            fetchData();
          }}
        />
      )}

      {/* Table */}
      {loading && !data ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      ) : (
        <>
          <VulnTable
            vulnerabilities={data?.items || []}
            selectedIds={selectedIds}
            onSelectToggle={handleSelectToggle}
            onSelectAll={handleSelectAll}
          />

          {data && data.total_pages > 1 && (
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              total={data.total}
              pageSize={data.page_size}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}
