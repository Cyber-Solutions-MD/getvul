'use client';
/**
 * ConnectorLogo — vendor logo tile for the connectors marketplace.
 *
 * Product decision (overrides design-system D-CONN-01 "gradient marks, not logos"
 * at the owner's request): the connector catalog shows real vendor branding.
 *
 * Resolution order per vendor:
 *   1. Local brand SVG in /public/connector-logos/<type>.svg (pulled from Simple
 *      Icons, brand-colored) — rendered as an <img> on a light tile.
 *   2. Inline SVG mark for vendors Simple Icons doesn't carry but that are simple
 *      and iconic (Microsoft family → the four-square mark).
 *   3. A tile in the vendor's official brand color with a bold monogram, for
 *      security vendors with no available icon (CrowdStrike, Wiz, Rapid7, Nessus,
 *      Jamf, Humaans). Drop a file into connector-logos/ to promote any of these
 *      to a real logo — no code change beyond adding its type to IMAGE_LOGOS.
 *
 * Injection-safe: `type` maps through literal lookups; unknown types fall through
 * to a neutral monogram tile (no style/URL interpolation from arbitrary input).
 */
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

// Vendors with a local brand SVG in /public/connector-logos/<type>.svg.
// Keep in sync with the files committed under that folder.
const IMAGE_LOGOS = new Set<string>([
  'qualys',
  'google_workspace',
  'okta',
  'jira',
  'asana',
  'github',
  'anthropic',
]);

type Brand = {
  /** Official brand color — tile background for monogram vendors. */
  color: string;
  /** Monogram shown when there is no mark. */
  letter: string;
  /** Text color on the brand-color tile (default white). */
  fg?: string;
  /** Inline SVG mark (used only for vendors without a local image). */
  mark?: ReactNode;
};

// Microsoft's four-square mark — shared by Defender, Entra ID, and Intune
// (Simple Icons carries no colored Microsoft mark, and this is accurate).
const MICROSOFT_MARK: ReactNode = (
  <svg viewBox="0 0 24 24" aria-hidden className="size-[62%]">
    <rect x="1" y="1" width="10" height="10" fill="#F25022" />
    <rect x="13" y="1" width="10" height="10" fill="#7FBA00" />
    <rect x="1" y="13" width="10" height="10" fill="#00A4EF" />
    <rect x="13" y="13" width="10" height="10" fill="#FFB900" />
  </svg>
);

// Literal registry — verbatim strings only (T-14-01 injection guard). Only vendors
// NOT in IMAGE_LOGOS need an entry (Microsoft family marks + monogram fallbacks).
const BRANDS: Record<string, Brand> = {
  crowdstrike: { color: '#E01A22', letter: 'C' },
  nessus: { color: '#00A3B4', letter: 'N' },
  defender: { color: '#FFFFFF', letter: 'D', mark: MICROSOFT_MARK },
  wiz: { color: '#3A0CA3', letter: 'W' },
  rapid7: { color: '#FF5100', letter: 'R' },
  azure_entra_id: { color: '#FFFFFF', letter: 'A', mark: MICROSOFT_MARK },
  jamf: { color: '#00A3E0', letter: 'J' },
  intune: { color: '#FFFFFF', letter: 'I', mark: MICROSOFT_MARK },
  humaans: { color: '#5B4FE0', letter: 'H' },
};

export type ConnectorLogoProps = {
  /** Backend connector_type (e.g. "CROWDSTRIKE") or already-lowercased provider. */
  type: string;
  /** Accessible label — the vendor's human name. */
  name: string;
  className?: string;
};

const TILE_BASE =
  'inline-grid shrink-0 place-items-center overflow-hidden rounded-xl ring-1 ring-inset ring-black/10';

export function ConnectorLogo({ type, name, className }: ConnectorLogoProps) {
  const key = type.toLowerCase();

  // 1. Local brand SVG on a light tile so any brand color reads on the dark theme.
  if (IMAGE_LOGOS.has(key)) {
    return (
      <span role="img" aria-label={name} className={cn(TILE_BASE, 'bg-white', className)}>
        {/* alt="" — the tile already carries the accessible name. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`/connector-logos/${key}.svg`} alt="" className="size-[62%] object-contain" />
      </span>
    );
  }

  const brand = BRANDS[key];

  // 2. Inline SVG mark (Microsoft family) on a light tile.
  if (brand?.mark) {
    return (
      <span role="img" aria-label={name} className={cn(TILE_BASE, 'bg-white', className)}>
        {brand.mark}
      </span>
    );
  }

  // 3. Monogram on the vendor's official brand color.
  return (
    <span
      role="img"
      aria-label={name}
      className={cn(TILE_BASE, 'font-bold leading-none', className)}
      style={{ backgroundColor: brand?.color ?? 'var(--color-surface-3, #241b3d)', color: brand?.fg ?? '#FFFFFF' }}
    >
      {brand?.letter ?? name.slice(0, 1).toUpperCase()}
    </span>
  );
}
