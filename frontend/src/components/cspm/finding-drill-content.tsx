'use client';
/**
 * FindingDrillContent — D-D-01 slot content for the shared DrillPanel chrome.
 *
 * Mirrors ticket-drill-content.tsx structure for the finding slot:
 *   Header: ConnectorMark + rule_id (mono) + close button
 *   Body (scrollable): severity glyph + rule_name; resource block; framework
 *     mappings; rule_description; remediation_info + link; CspmStatusPill
 *   Loading → skeleton; error/!data → PartialFailureBanner
 *
 * Props: { findingId: string; onClose: () => void }
 *
 * T-13-16 equivalent: remediation_url is an href text node only — no dangerouslySetInnerHTML.
 * T-14-12: ConnectorMark uses literal lookup; unknown cloud_provider → neutral mark.
 *
 * Plan 14-03.
 */
import { X, ExternalLink } from 'lucide-react';
import { ConnectorMark } from '@/components/connectors/connector-mark';
import type { ConnectorProvider } from '@/components/connectors/types';
import { CspmStatusPill } from './cspm-status-pill';
import { SEVERITY_GLYPH, SEVERITY_CLASS } from './microcopy';
import { PartialFailureBanner } from '@/components/states';
import { useCspmDetail } from '@/lib/queries/use-cspm-detail';

// T-14-12: literal lookup — unknown cloud_provider falls through to undefined
const CLOUD_PROVIDER_MAP: Record<string, ConnectorProvider> = {
  aws:   'crowdstrike',
  azure: 'azure_entra_id',
  gcp:   'google_workspace',
};

export type FindingDrillContentProps = {
  findingId: string;
  onClose: () => void;
};

export function FindingDrillContent({ findingId, onClose }: FindingDrillContentProps) {
  const { data, isPending, isError } = useCspmDetail(findingId);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isPending) {
    return (
      <div aria-busy="true" className="flex h-full flex-col">
        {/* Skeleton header */}
        <div className="flex items-start justify-between border-b border-border-subtle px-5 py-4">
          <div className="flex items-center gap-2">
            <div data-skeleton className="h-3.5 w-3.5 rounded-[3px] bg-surface-2 animate-pulse" />
            <div className="h-3 w-32 rounded bg-surface-2 animate-pulse" />
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="ml-2 shrink-0 rounded-md p-1 text-text-muted hover:bg-surface-2"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        {/* Skeleton body */}
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {[100, 180, 140, 200, 120].map((w, i) => (
            <div key={i} className="h-3 rounded animate-pulse bg-surface-2" style={{ width: w }} />
          ))}
        </div>
      </div>
    );
  }

  // ── Error or missing data ────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between border-b border-border-subtle px-5 py-4">
          <span className="text-sm text-text-muted">Finding detail</span>
          <button type="button" onClick={onClose} aria-label="Close" className="ml-2 p-1 text-text-muted hover:text-text">
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="flex-1 p-5">
          <PartialFailureBanner
            errors={[{ code: 'ERR', requestId: '' }]}
          />
        </div>
      </div>
    );
  }

  const glyph = SEVERITY_GLYPH[data.severity] ?? '○';
  const glyphClass = SEVERITY_CLASS[data.severity] ?? 'text-text-muted';
  const cloudKey = data.cloud_provider?.toLowerCase();
  const markProvider = CLOUD_PROVIDER_MAP[cloudKey] as ConnectorProvider | undefined;

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ── */}
      <div className="flex items-start justify-between border-b border-border-subtle px-5 py-4">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          {markProvider ? (
            <ConnectorMark provider={markProvider} className="mt-0.5 shrink-0" />
          ) : (
            <span
              className="mt-0.5 inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] bg-surface-2 text-[8px] font-bold leading-none text-text-muted"
              aria-label={data.cloud_provider ?? 'unknown'}
            >
              {data.cloud_provider?.slice(0, 1) ?? '?'}
            </span>
          )}
          <div className="min-w-0">
            <span className="font-mono text-sm font-semibold text-text">{data.rule_id}</span>
            <p className="mt-0.5 truncate text-sm text-text-muted">{data.rule_name}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="ml-2 shrink-0 rounded-md p-1 text-text-muted hover:bg-surface-2 hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* ── Body (scrollable) ── */}
      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        {/* Severity + title */}
        <section aria-labelledby="fdrill-title-h">
          <div className="flex items-center gap-2 mb-1">
            <span aria-label={data.severity} className={glyphClass}>{glyph}</span>
            <CspmStatusPill status={data.status} />
          </div>
          <h4 id="fdrill-title-h" className="text-sm font-medium text-text">
            {data.rule_name}
          </h4>
        </section>

        {/* Resource block */}
        <section aria-labelledby="fdrill-resource-h">
          <h4 id="fdrill-resource-h" className="mb-2 text-xs uppercase tracking-wide text-text-muted">
            Resource
          </h4>
          <div className="space-y-1 text-sm">
            <p className="font-mono text-xs text-text break-all">{data.resource_id}</p>
            {data.resource_name && <p className="text-text-muted">{data.resource_name}</p>}
            {data.resource_region && (
              <p className="text-text-faint text-xs">{data.resource_region}</p>
            )}
            {data.cloud_account_name && (
              <p className="text-text-faint text-xs">{data.cloud_account_name}</p>
            )}
          </div>
        </section>

        {/* Framework mappings */}
        {data.frameworks?.length > 0 && (
          <section aria-labelledby="fdrill-frameworks-h">
            <h4 id="fdrill-frameworks-h" className="mb-2 text-xs uppercase tracking-wide text-text-muted">
              Compliance
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {data.frameworks.map((fw) => (
                <span
                  key={`${fw.name}-${fw.control_id}`}
                  className="inline-flex items-center gap-1 rounded border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[10px] text-text-muted"
                >
                  {fw.name}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Rule description */}
        {data.rule_description && (
          <section aria-labelledby="fdrill-desc-h">
            <h4 id="fdrill-desc-h" className="mb-2 text-xs uppercase tracking-wide text-text-muted">
              Description
            </h4>
            <p className="text-sm text-text leading-snug">{data.rule_description}</p>
          </section>
        )}

        {/* Remediation */}
        {(data.remediation_info || data.remediation_url) && (
          <section aria-labelledby="fdrill-remediation-h">
            <h4 id="fdrill-remediation-h" className="mb-2 text-xs uppercase tracking-wide text-text-muted">
              Remediation
            </h4>
            {data.remediation_info && (
              <p className="text-sm text-text">{data.remediation_info}</p>
            )}
            {data.remediation_url && (
              <a
                href={data.remediation_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs text-violet hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
              >
                View remediation <ExternalLink size={10} aria-hidden="true" />
              </a>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
