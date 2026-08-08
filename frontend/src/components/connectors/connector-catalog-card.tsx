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
import { ConnectorLogo } from './connector-logo';
import { CATALOG_COPY } from './microcopy';

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
  return (
    <div
      data-connector-catalog-card={type}
      className="group flex min-h-[168px] flex-col rounded-xl border border-border-subtle bg-surface-2 p-5 transition-all hover:-translate-y-0.5 hover:border-border hover:shadow-card"
    >
      {/* Header: prominent vendor logo tile + name */}
      <div className="flex items-center gap-3">
        <ConnectorLogo type={type} name={name} className="size-11 text-lg" />
        <span className="min-w-0 truncate text-base font-semibold text-text">{name}</span>
      </div>

      {/* Short description */}
      {description ? (
        <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-text-muted">{description}</p>
      ) : (
        <p className="mt-3 text-sm leading-relaxed text-text-faint">{CATALOG_COPY.noDescription}</p>
      )}

      {/* Footer pinned to the bottom for even card heights */}
      <div className="mt-auto flex items-center justify-between gap-2 pt-5">
        <button
          type="button"
          data-add-connector={type}
          onClick={() => onConfigure(type)}
          className="inline-flex items-center rounded-md border border-border-subtle px-3.5 py-2 text-sm font-medium text-text-muted transition-colors hover:border-violet hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
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
