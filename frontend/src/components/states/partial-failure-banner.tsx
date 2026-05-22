'use client';
import { useMemo } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { useQueryErrors, type QueryError } from '@/lib/queries/use-query-errors';
import { cn } from '@/lib/utils';
import type { QueryKey } from '@tanstack/react-query';

// D-S-03: hybrid mode. Default — pass watchKeys; banner subscribes via
// useQueryErrors(). Override — pass `errors` directly (for sites where one
// specific query is the "main" failure source, e.g., Phase 10 retrofit).
// D-S-07: role="alert" announces failures to AT.
// state-patterns.md: AMBER, not red — partial failure is degraded, not down.
// T-11-15 (Information Disclosure): banner renders ONLY error.code (HTTP) +
// error.requestId + the optional `source` label + the optional sanitized
// `message`. No raw stack. Mirrors Phase 10 D-E-02.

type ErrorRow = {
  code: number | string;
  requestId: string;
  message?: string;
};

export type PartialFailureBannerProps = {
  watchKeys?: readonly QueryKey[];
  errors?: ReadonlyArray<ErrorRow>;
  onRetry?: () => void;
  /** Connector name surfaced in copy, e.g. "Tenable" */
  source?: string;
  className?: string;
};

export function PartialFailureBanner({
  watchKeys,
  errors,
  onRetry,
  source,
  className,
}: PartialFailureBannerProps): JSX.Element | null {
  // Default mode: subscribe to QueryCache.
  const cacheErrors: QueryError[] = useQueryErrors(watchKeys ?? []);
  const rows: ReadonlyArray<ErrorRow> = useMemo(() => {
    if (errors && errors.length > 0) return errors;
    return cacheErrors.map((e) => ({
      code: e.code,
      requestId: e.requestId,
      message: e.error.message,
    }));
  }, [errors, cacheErrors]);

  if (rows.length === 0) return null;

  // Surface the first error as the headline; pull from `source` prop for the title.
  const primary = rows[0];
  const title = source
    ? `${source} connector is unreachable`
    : 'Some data is incomplete';

  return (
    <div
      role="alert"
      className={cn(
        // AMBER, NOT red — degraded != down (state-patterns.md)
        'flex items-start gap-3 rounded-md border border-amber bg-amber-soft p-4 text-sm',
        className
      )}
      data-failed-keys={rows.length}
    >
      <span className="mt-0.5 text-amber" aria-hidden="true">
        <AlertTriangle size={18} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-medium text-text">{title}</div>
        <div className="mt-1 text-text-muted">
          {primary.message && <span>{primary.message} · </span>}
          <span>
            HTTP <span className="font-mono">{String(primary.code)}</span>
          </span>
          <span> · Request ID </span>
          <span className="font-mono">{primary.requestId}</span>
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-xs font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          <RefreshCw size={14} />
          Retry now
        </button>
      )}
    </div>
  );
}
