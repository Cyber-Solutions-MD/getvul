// Phase 11 sunset restyle (D-T-03 + RESEARCH Open Question 2).
// Mono numbers, active page pink with pink-soft chrome, disabled prev opacity-30.
// API unchanged from v1 — Phase 11 page.tsx + future Phase 12+/Phase 13+ consumers
// call with the same props.
"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

const NAV_BTN_BASE =
  "inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet focus-visible:outline-offset-2";

const PAGE_BTN_BASE =
  "inline-flex min-w-[32px] h-8 items-center justify-center rounded-md border px-2 font-mono text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet focus-visible:outline-offset-2";

export default function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
}: PaginationProps) {
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const atFirst = page <= 1;
  const atLast = page >= totalPages;

  return (
    <nav
      role="navigation"
      aria-label="Pagination"
      className="flex items-center justify-between border-t border-border-subtle px-1 pt-4"
    >
      <span className="font-mono text-xs text-text-muted">
        {total > 0
          ? `${start}–${end} of ${total.toLocaleString()}`
          : "No results"}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={atFirst}
          aria-label="Previous page"
          className={cn(
            NAV_BTN_BASE,
            atFirst
              ? "cursor-not-allowed text-text-faint opacity-30"
              : "text-text-muted hover:bg-surface-2 hover:text-text"
          )}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        {buildPageWindow(page, totalPages).map((pageNum, idx) =>
          pageNum === "…" ? (
            <span
              key={`gap-${idx}`}
              aria-hidden="true"
              className="px-1 font-mono text-sm text-text-faint"
            >
              …
            </span>
          ) : (
            <button
              key={pageNum}
              type="button"
              onClick={() => onPageChange(pageNum)}
              aria-current={pageNum === page ? "page" : undefined}
              aria-label={`Page ${pageNum}`}
              className={cn(
                PAGE_BTN_BASE,
                pageNum === page
                  ? "border-pink bg-pink-soft text-pink"
                  : "border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text"
              )}
            >
              {pageNum}
            </button>
          )
        )}
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={atLast}
          aria-label="Next page"
          className={cn(
            NAV_BTN_BASE,
            atLast
              ? "cursor-not-allowed text-text-faint opacity-30"
              : "text-text-muted hover:bg-surface-2 hover:text-text"
          )}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </nav>
  );
}

// Build the visible page window. Up to 5 page slots — preserves the v1 visible
// count so the surface doesn't visually drift. The slot array can contain "…"
// to render an ellipsis cell between non-contiguous ranges.
function buildPageWindow(
  page: number,
  totalPages: number
): Array<number | "…"> {
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  if (page <= 3) {
    return [1, 2, 3, 4, 5];
  }
  if (page >= totalPages - 2) {
    return [
      totalPages - 4,
      totalPages - 3,
      totalPages - 2,
      totalPages - 1,
      totalPages,
    ];
  }
  return [page - 2, page - 1, page, page + 1, page + 2];
}
