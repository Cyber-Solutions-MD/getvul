/**
 * ProviderMark — 14px gradient square identifying a ticket provider.
 *
 * UX-05-02: gradient marks, NOT real logos. Each provider gets its own
 * CSS-variable gradient defined ONCE in globals.css (D-PROV-03).
 *
 * T-13-14 mitigation: provider string maps through a literal lookup object;
 * arbitrary input falls through to undefined (no class/var injection).
 * No inline hex — the gradient lives entirely in CSS variables.
 */
import { cn } from '@/lib/utils';
import type { TicketProvider } from './types';

// Literal lookup: maps provider → CSS variable gradient reference.
// Using a lookup object (not string concatenation) ensures the var name is
// exact and prevents injection of arbitrary CSS var names via user data.
const PROVIDER_GRADIENTS: Record<TicketProvider, string> = {
  jira:   'var(--gradient-provider-jira)',
  asana:  'var(--gradient-provider-asana)',
  github: 'var(--gradient-provider-github)',
};

// Short text glyph for each provider — a text node only, never an <img>.
// T-13-14: React renders text nodes as escaped text content.
const PROVIDER_GLYPH: Record<TicketProvider, string> = {
  jira:   'J',
  asana:  'A',
  github: 'G',
};

export type ProviderMarkProps = {
  provider: TicketProvider;
  className?: string;
};

export function ProviderMark({ provider, className }: ProviderMarkProps) {
  const gradient = PROVIDER_GRADIENTS[provider];
  const glyph = PROVIDER_GLYPH[provider];

  return (
    <span
      className={cn(
        'inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] text-[8px] font-bold leading-none text-white',
        className,
      )}
      style={{ background: gradient }}
      role="img"
      aria-label={provider}
    >
      {/* T-13-14: text node only — React escapes text, no dangerouslySetInnerHTML */}
      {glyph}
    </span>
  );
}
