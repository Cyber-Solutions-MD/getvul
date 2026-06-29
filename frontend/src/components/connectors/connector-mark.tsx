/**
 * ConnectorMark — 14px gradient square identifying a connector provider.
 *
 * D-CONN-01: gradient marks, NOT real logos. Each provider's gradient is
 * defined ONCE in globals.css; this component is the sole consumer.
 *
 * T-14-01 / T-13-14 mitigation: connector_type string maps through a literal
 * lookup object; arbitrary input falls through to undefined (no CSS var
 * injection possible). Never uses string interpolation such as
 * `var(--gradient-provider-${p})` — that would defeat the injection guard.
 *
 * Caller responsibility: the page layer lowercases the backend connector_type
 * before passing to this component (e.g. "CROWDSTRIKE" → "crowdstrike").
 */
import { cn } from '@/lib/utils';
import type { ConnectorProvider } from './types';

// Literal lookup: maps each provider to its CSS variable gradient.
// IMPORTANT: entries must be verbatim strings, never template literals.
// Unknown connector types silently fall through to undefined (no background).
const PROVIDER_GRADIENTS: Record<ConnectorProvider, string> = {
  crowdstrike:      'var(--gradient-provider-crowdstrike)',
  nessus:           'var(--gradient-provider-nessus)',
  defender:         'var(--gradient-provider-defender)',
  wiz:              'var(--gradient-provider-wiz)',
  qualys:           'var(--gradient-provider-qualys)',
  rapid7:           'var(--gradient-provider-rapid7)',
  google_workspace: 'var(--gradient-provider-google_workspace)',
  azure_entra_id:   'var(--gradient-provider-azure_entra_id)',
  okta:             'var(--gradient-provider-okta)',
  jamf:             'var(--gradient-provider-jamf)',
  intune:           'var(--gradient-provider-intune)',
  humaans:          'var(--gradient-provider-humaans)',
  jira:             'var(--gradient-provider-jira)',
  asana:            'var(--gradient-provider-asana)',
  github:           'var(--gradient-provider-github)',
};

// Single uppercase letter glyph for each provider.
// T-14-01: React renders text nodes as escaped text content — no injection risk.
const PROVIDER_GLYPH: Record<ConnectorProvider, string> = {
  crowdstrike:      'C',
  nessus:           'N',
  defender:         'D',
  wiz:              'W',
  qualys:           'Q',
  rapid7:           'R',
  google_workspace: 'G',
  azure_entra_id:   'A',
  okta:             'O',
  jamf:             'J',
  intune:           'I',
  humaans:          'H',
  jira:             'J',
  asana:            'A',
  github:           'G',
};

export type ConnectorMarkProps = {
  provider: ConnectorProvider;
  className?: string;
};

export function ConnectorMark({ provider, className }: ConnectorMarkProps) {
  // Lookup returns undefined for unknown provider types (injection guard).
  const gradient = PROVIDER_GRADIENTS[provider];
  const glyph = PROVIDER_GLYPH[provider];

  return (
    <span
      className={cn(
        'inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] text-[8px] font-bold leading-none text-white',
        className,
      )}
      // undefined background is treated as no background by the browser —
      // unknown provider renders a plain span with no gradient.
      style={{ background: gradient }}
      role="img"
      aria-label={provider}
    >
      {/* T-14-01: text node only — React escapes text, no dangerouslySetInnerHTML */}
      {glyph}
    </span>
  );
}
