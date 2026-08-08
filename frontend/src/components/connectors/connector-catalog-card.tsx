'use client';
/**
 * ConnectorCatalogCard — a marketplace card for an AVAILABLE (not-yet-configured)
 * connector type on /dashboard/connectors.
 *
 * The connectors page is a catalog: each category shows the apps you CAN connect,
 * each with its gradient mark, name, and a short description sourced from the
 * backend `/connectors/types` metadata (description). Selecting "Configure" opens
 * the add-connector wizard for that specific type (D-01 keeps provider selection
 * on the grid, so the wizard opens straight at Credentials).
 *
 * A "Setup guide ↗" link surfaces the provider's `setup_url` when present, so a
 * user can read the vendor's own key/permission docs before configuring. The
 * fuller step-by-step `notes` are shown in the config dialog (page.tsx).
 *
 * e2e contract: the Configure button carries `data-add-connector={type}` — the
 * Playwright add-connector flow selects apps by this attribute.
 *
 * Sunset-tokenized: no raw gray or indigo utilities. Gradient is reserved for the
 * mark only (not the per-card button) to honor the "single gradient CTA" rule —
 * the page-level primary action stays singular, catalog buttons are restrained.
 */
import { ArrowUpRight } from 'lucide-react';
import { ConnectorMark } from './connector-mark';
import { CATALOG_COPY } from './microcopy';
import type { ConnectorProvider } from './types';

export type ConnectorCatalogCardProps = {
  /** Backend connector_type (e.g. "CROWDSTRIKE"). */
  type: string;
  /** Human name (e.g. "CrowdStrike Falcon"). */
  name: string;
  /** Short one-line description from /connectors/types. */
  description?: string;
  /** Vendor setup docs URL (setup_url); the "Setup guide" link is hidden when empty. */
  setupUrl?: string;
  /** Opens the add-connector wizard for this type. */
  onConfigure: (type: string) => void;
};

export function ConnectorCatalogCard({
  type,
  name,
  description,
  setupUrl,
  onConfigure,
}: ConnectorCatalogCardProps) {
  // page-layer lowercases the backend type before the mark's injection-safe lookup.
  const provider = type.toLowerCase() as ConnectorProvider;

  return (
    <div
      data-connector-catalog-card={type}
      className="flex flex-col rounded-lg border border-border-subtle bg-surface-2 p-4 transition-all hover:-translate-y-px hover:border-border"
    >
      {/* Header: larger gradient mark + name */}
      <div className="flex items-center gap-3">
        <ConnectorMark provider={provider} className="size-9 rounded-lg text-sm" />
        <span className="min-w-0 truncate text-sm font-semibold text-text">{name}</span>
      </div>

      {/* Short description */}
      {description ? (
        <p className="mt-2.5 line-clamp-2 text-sm text-text-muted">{description}</p>
      ) : (
        <p className="mt-2.5 text-sm text-text-faint">{CATALOG_COPY.noDescription}</p>
      )}

      {/* Footer: Configure (primary per-card action) + optional setup guide link */}
      <div className="mt-4 flex items-center justify-between gap-2 pt-1">
        <button
          type="button"
          data-add-connector={type}
          onClick={() => onConfigure(type)}
          className="inline-flex items-center rounded-md border border-border-subtle px-3 py-1.5 text-sm font-medium text-text-muted transition-colors hover:border-violet hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          {CATALOG_COPY.configureLabel}
        </button>

        {setupUrl ? (
          <a
            href={setupUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-text-faint transition-colors hover:text-violet focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
          >
            {CATALOG_COPY.setupGuideLabel}
            <ArrowUpRight size={12} aria-hidden />
          </a>
        ) : null}
      </div>
    </div>
  );
}
