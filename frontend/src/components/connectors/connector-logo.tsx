'use client';
/**
 * ConnectorLogo — vendor logo tile for the connectors marketplace.
 *
 * Product decision (overrides design-system D-CONN-01 "gradient marks, not logos"
 * at the owner's request): the connector catalog shows real vendor branding.
 *
 * Each vendor renders as a rounded logo tile:
 *   - Vendors with a simple, accurately-reproducible mark get an inline SVG on a
 *     light tile (Microsoft family, Asana, Okta, GitHub).
 *   - Everyone else gets a clean tile in the vendor's OFFICIAL brand color with a
 *     bold monogram — a real "logo tile" look, not the old gradient monogram.
 *
 * To drop in an official SVG later, add a `mark` to that vendor's BRANDS entry —
 * nothing else changes. Injection-safe: `type` maps through a literal lookup;
 * unknown types fall through to a neutral tile (no style interpolation).
 */
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

type Brand = {
  /** Official brand color — tile background for monogram vendors, accent otherwise. */
  color: string;
  /** Monogram shown when there is no `mark`. */
  letter: string;
  /** Text color on the brand-color tile (default white). */
  fg?: string;
  /** Inline SVG mark; when present it renders on a light tile instead of a monogram. */
  mark?: ReactNode;
};

// Microsoft's four-square mark — shared by Defender, Entra ID, and Intune.
const MICROSOFT_MARK: ReactNode = (
  <svg viewBox="0 0 24 24" aria-hidden className="size-[62%]">
    <rect x="1" y="1" width="10" height="10" fill="#F25022" />
    <rect x="13" y="1" width="10" height="10" fill="#7FBA00" />
    <rect x="1" y="13" width="10" height="10" fill="#00A4EF" />
    <rect x="13" y="13" width="10" height="10" fill="#FFB900" />
  </svg>
);

// Literal registry — verbatim strings only (T-14-01 injection guard).
const BRANDS: Record<string, Brand> = {
  crowdstrike: { color: '#E01A22', letter: 'C' },
  nessus: { color: '#00A3B4', letter: 'N' },
  defender: { color: '#FFFFFF', letter: 'D', mark: MICROSOFT_MARK },
  wiz: { color: '#3A0CA3', letter: 'W' },
  qualys: { color: '#ED1C24', letter: 'Q' },
  rapid7: { color: '#FF5100', letter: 'R' },
  google_workspace: { color: '#4285F4', letter: 'G' },
  azure_entra_id: { color: '#FFFFFF', letter: 'A', mark: MICROSOFT_MARK },
  okta: {
    color: '#FFFFFF',
    letter: 'O',
    mark: (
      <svg viewBox="0 0 24 24" aria-hidden className="size-[60%]">
        <circle cx="12" cy="12" r="8" fill="none" stroke="#007DC1" strokeWidth="6" />
      </svg>
    ),
  },
  jamf: { color: '#00A3E0', letter: 'J' },
  intune: { color: '#FFFFFF', letter: 'I', mark: MICROSOFT_MARK },
  humaans: { color: '#5B4FE0', letter: 'H' },
  jira: { color: '#2684FF', letter: 'J' },
  asana: {
    color: '#FFFFFF',
    letter: 'A',
    mark: (
      <svg viewBox="0 0 24 24" aria-hidden fill="#F06A6A" className="size-[62%]">
        <circle cx="12" cy="15.6" r="4.2" />
        <circle cx="6.3" cy="8.4" r="4.2" />
        <circle cx="17.7" cy="8.4" r="4.2" />
      </svg>
    ),
  },
  github: {
    color: '#181717',
    letter: 'G',
    mark: (
      <svg viewBox="0 0 24 24" aria-hidden fill="#FFFFFF" className="size-[64%]">
        <path d="M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.84 2.81 1.31 3.5 1 .11-.78.42-1.31.76-1.61-2.67-.3-5.47-1.34-5.47-5.95 0-1.31.47-2.39 1.24-3.23-.12-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 016 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.66.24 2.88.12 3.18.77.84 1.24 1.92 1.24 3.23 0 4.62-2.81 5.64-5.49 5.94.43.37.82 1.1.82 2.22v3.29c0 .32.22.7.83.58C20.56 22.29 24 17.8 24 12.5 24 5.87 18.63.5 12 .5z" />
      </svg>
    ),
  },
  anthropic: { color: '#D97757', letter: 'A' },
};

export type ConnectorLogoProps = {
  /** Backend connector_type (e.g. "CROWDSTRIKE") or already-lowercased provider. */
  type: string;
  /** Accessible label — the vendor's human name. */
  name: string;
  className?: string;
};

export function ConnectorLogo({ type, name, className }: ConnectorLogoProps) {
  const brand = BRANDS[type.toLowerCase()];

  const tileBase =
    'inline-grid shrink-0 place-items-center overflow-hidden rounded-xl ring-1 ring-inset ring-black/10';

  // Real SVG mark → light tile so the colored mark reads on the dark theme.
  if (brand?.mark) {
    return (
      <span
        role="img"
        aria-label={name}
        className={cn(tileBase, 'bg-white', className)}
        style={brand.color !== '#FFFFFF' ? { backgroundColor: brand.color } : undefined}
      >
        {brand.mark}
      </span>
    );
  }

  // Monogram on the vendor's official brand color.
  return (
    <span
      role="img"
      aria-label={name}
      className={cn(tileBase, 'font-bold leading-none', className)}
      style={{ backgroundColor: brand?.color ?? 'var(--color-surface-3, #241b3d)', color: brand?.fg ?? '#FFFFFF' }}
    >
      {brand?.letter ?? name.slice(0, 1).toUpperCase()}
    </span>
  );
}
