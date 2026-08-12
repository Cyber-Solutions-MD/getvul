'use client';
/**
 * FindingCard — CSPM finding row card.
 *
 * Renders:
 *   - ConnectorMark for cloud provider (AWS→provider type mapping, see comment)
 *   - Severity glyph (colored) per visual-language.md
 *   - resource_id in font-mono text-sm
 *   - rule_name title
 *   - Framework tags (small chips)
 *   - CspmStatusPill
 *   - Selection checkbox for bulk actions
 *
 * Cloud provider mapping note (T-14-12 mitigate):
 *   The cloud_provider values from the CSPM backend are 'AWS' | 'AZURE' | 'GCP' (uppercase).
 *   ConnectorMark expects the ConnectorProvider union type (lowercase).
 *   Cloud providers are NOT in the ConnectorProvider type directly; we map to the
 *   nearest credential provider as a best-effort gradient fallback:
 *     AWS   → 'crowdstrike' (closest available; no gradient, shows neutral)
 *     AZURE → 'azure_entra_id' (direct match in ConnectorProvider)
 *     GCP   → 'google_workspace' (direct match in ConnectorProvider)
 *   Unknown cloud_provider falls through to undefined background (T-14-12 injection guard).
 *   TODO: add dedicated aws/azure/gcp entries to ConnectorProvider + globals.css when branding is finalized.
 *
 * Plan 14-03.
 */
import React from 'react';
import { cn } from '@/lib/utils';
import { ConnectorMark } from '@/components/connectors/connector-mark';
import type { ConnectorProvider } from '@/components/connectors/types';
import { CspmStatusPill } from './cspm-status-pill';
import { SEVERITY_GLYPH, SEVERITY_CLASS } from './microcopy';
import { SourceBadgeGroup } from '@/components/vulnerabilities/source-badge-group';
import type { MisconfigSummary } from '@/lib/queries/use-cspm-findings';

// T-14-12: literal lookup — unknown cloud_provider falls through to undefined (no gradient injection).
const CLOUD_PROVIDER_MAP: Record<string, ConnectorProvider> = {
  aws:   'crowdstrike',     // nearest available until aws-specific token added
  azure: 'azure_entra_id', // direct ConnectorProvider match
  gcp:   'google_workspace', // direct ConnectorProvider match
};

export type FindingCardProps = {
  finding: MisconfigSummary;
  selected: boolean;
  onSelect: (id: string, selected: boolean) => void;
  onOpen: (id: string) => void;
  /** Optional list of framework names — shown as tags if provided */
  frameworks?: string[];
};

export function FindingCard({ finding, selected, onSelect, onOpen, frameworks = [] }: FindingCardProps) {
  const glyph = SEVERITY_GLYPH[finding.severity] ?? '○';
  const glyphClass = SEVERITY_CLASS[finding.severity] ?? 'text-text-muted';

  // T-14-12: literal lookup through CLOUD_PROVIDER_MAP — undefined for unknown cloud providers
  const cloudKey = finding.cloud_provider?.toLowerCase();
  const markProvider = CLOUD_PROVIDER_MAP[cloudKey] as ConnectorProvider | undefined;

  return (
    <div
      data-finding-card
      className={cn(
        'flex items-start gap-3 rounded-lg border p-3 transition-colors',
        'border-border-subtle bg-surface hover:bg-surface-2',
        selected && 'border-border bg-surface-2',
      )}
    >
      {/* Checkbox for bulk selection */}
      <input
        type="checkbox"
        aria-label={`Select finding ${finding.rule_name}`}
        checked={selected}
        onChange={(e) => onSelect(finding.id, e.target.checked)}
        onClick={(e) => e.stopPropagation()}
        className="mt-0.5 shrink-0 accent-violet cursor-pointer"
      />

      {/* Clickable body */}
      <button
        type="button"
        onClick={() => onOpen(finding.id)}
        className="flex min-w-0 flex-1 items-start gap-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
      >
        {/* Cloud provider mark */}
        {markProvider ? (
          <ConnectorMark provider={markProvider} className="mt-0.5 shrink-0" />
        ) : (
          // Fallback neutral mark for unknown cloud providers (T-14-12)
          <span
            className="mt-0.5 inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] bg-surface-2 text-[8px] font-bold leading-none text-text-muted"
            aria-label={finding.cloud_provider ?? 'unknown'}
          >
            {finding.cloud_provider ? finding.cloud_provider.slice(0, 1) : '?'}
          </span>
        )}

        {/* Content */}
        <div className="min-w-0 flex-1 space-y-1">
          {/* Severity glyph + rule_id + rule_name */}
          <div className="flex items-center gap-2">
            <span aria-label={finding.severity} className={cn('shrink-0 text-xs', glyphClass)}>
              {glyph}
            </span>
            <span className="font-mono text-xs text-text-muted">{finding.rule_id}</span>
          </div>
          <p className="text-sm font-medium text-text">{finding.rule_name}</p>

          {/* resource_id in mono */}
          <p className="font-mono text-xs text-text-muted truncate" title={finding.resource_id}>
            {finding.resource_id}
          </p>

          {/* Phase 35 SRC-01/05 — shared SourceBadgeGroup: single vs
              multi-tool corroboration for this (rule_id, resource_id)
              group, never "confirmed" from one tool. Falls back to
              [finding.source] for pre-Plan-04 responses that lack the
              batched sources field. */}
          <SourceBadgeGroup
            sources={finding.sources ?? (finding.source ? [finding.source] : [])}
            count={finding.sources_count}
          />

          {/* Framework tags */}
          {frameworks.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {frameworks.slice(0, 3).map((fw) => (
                <span
                  key={fw}
                  className="inline-flex items-center rounded border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[10px] text-text-muted"
                >
                  {fw}
                </span>
              ))}
              {frameworks.length > 3 && (
                <span className="inline-flex items-center rounded border border-border-subtle bg-surface-2 px-1.5 py-0.5 text-[10px] text-text-muted">
                  +{frameworks.length - 3}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Status pill — right-aligned */}
        <CspmStatusPill status={finding.status} className="shrink-0" />
      </button>
    </div>
  );
}
