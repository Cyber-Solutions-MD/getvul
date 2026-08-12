/**
 * SourceBadgeGroup — non-overclaiming scanner-provenance badge, shared across
 * Vulnerabilities/Assets/CSPM/Tickets (Plan 05 reuses this verbatim).
 *
 * SRC-01 / CONTEXT [RESOLVED A3]: a single scanner finding must never read as
 * "confirmed" — a finding seen by only ONE scanner renders ONE neutral
 * provider mark with no corroboration chrome, no check, no "confirmed"/
 * "verified" copy. A finding corroborated by 2+ scanners renders the group of
 * marks plus a subtle "N sources" label using the SLA-ok green tint
 * (visual-language.md `.sla-pill.ok` chrome, reused here to mean
 * corroboration — a reviewable new mapping, not a discovered precedent).
 *
 * T-35-04 mitigation (mirrors ProviderMark/ConnectorMark T-13-14/T-14-01):
 * every source code resolves through a LITERAL lookup object, never string
 * concatenation into a `var(--...)` name. Unknown codes (e.g. Assets-surface
 * enrichment sources like JAMF) fall through to a neutral fallback mark —
 * never a crash, never a wrong-provider gradient.
 */
import { cn } from '@/lib/utils';

export type VulnSourceValue =
  | 'CROWDSTRIKE'
  | 'NESSUS'
  | 'DEFENDER'
  | 'WIZ'
  | 'QUALYS'
  | 'RAPID7';

// Literal lookup: source code -> CSS variable gradient reference. These
// `--gradient-provider-*` scanner tokens already exist in globals.css
// (added alongside ConnectorMark) — reused verbatim, not re-defined.
const SOURCE_GRADIENTS: Record<VulnSourceValue, string> = {
  CROWDSTRIKE: 'var(--gradient-provider-crowdstrike)',
  NESSUS: 'var(--gradient-provider-nessus)',
  DEFENDER: 'var(--gradient-provider-defender)',
  WIZ: 'var(--gradient-provider-wiz)',
  QUALYS: 'var(--gradient-provider-qualys)',
  RAPID7: 'var(--gradient-provider-rapid7)',
};

// Single-letter glyph, text node only (React escapes — no injection risk).
const SOURCE_GLYPH: Record<VulnSourceValue, string> = {
  CROWDSTRIKE: 'C',
  NESSUS: 'N',
  DEFENDER: 'D',
  WIZ: 'W',
  QUALYS: 'Q',
  RAPID7: 'R',
};

function isKnownSource(source: string): source is VulnSourceValue {
  return Object.prototype.hasOwnProperty.call(SOURCE_GRADIENTS, source);
}

// A single provider mark. Unknown codes (e.g. an Assets-surface enrichment
// value like 'JAMF') render a neutral fallback square — muted surface-2,
// first-letter glyph, NO gradient lookup-miss/injection risk.
function SourceMark({ source }: { source: string }) {
  const known = isKnownSource(source);
  const glyph = known ? SOURCE_GLYPH[source] : (source.charAt(0).toUpperCase() || '?');

  if (!known) {
    return (
      <span
        className="inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] bg-surface-2 text-[8px] font-bold leading-none text-text-muted"
        role="img"
        aria-label={source}
      >
        {glyph}
      </span>
    );
  }

  return (
    <span
      className="inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] text-[8px] font-bold leading-none text-white"
      style={{ background: SOURCE_GRADIENTS[source] }}
      role="img"
      aria-label={source}
    >
      {glyph}
    </span>
  );
}

export type SourceBadgeGroupProps = {
  /** Raw source codes for this finding. May include non-scanner enrichment
   * codes on the Assets surface (e.g. 'JAMF') — rendered with the neutral
   * fallback mark, never a crash. */
  sources: string[];
  /** sources_count from the API; falls back to sources.length when omitted. */
  count?: number;
  className?: string;
};

export function SourceBadgeGroup({ sources, count, className }: SourceBadgeGroupProps) {
  const n = count ?? sources.length;

  // Defensive zero-source state — never a crash, never implies "unknown"
  // beyond a neutral em-dash (D-01/CONTEXT A1: correlation rows are pruned
  // once a finding is no longer OPEN/IN_PROGRESS on 2+ sources).
  if (n <= 0 || sources.length === 0) {
    return (
      <span
        className={cn('text-xs text-text-faint', className)}
        aria-hidden="true"
        data-source-badge-group="empty"
      >
        —
      </span>
    );
  }

  if (n <= 1) {
    // Single source — neutral container, no corroboration tint, no copy.
    // SRC-01: structurally impossible to read this as "confirmed".
    return (
      <span
        className={cn('inline-flex items-center gap-1', className)}
        data-source-badge-group="single"
      >
        {sources.map((s, i) => (
          <SourceMark key={`${s}-${i}`} source={s} />
        ))}
      </span>
    );
  }

  // Multi-source corroborated — group of marks + subtle "N sources" count,
  // corroboration tint = the SLA-ok green chrome (visual-language.md
  // `.sla-pill.ok`), reused here per CONTEXT.md [RESOLVED A3].
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-1.5 py-0.5',
        className,
      )}
      style={{
        background: 'rgba(74, 222, 128, 0.12)',
        borderColor: 'rgba(74, 222, 128, 0.3)',
      }}
      data-source-badge-group="multi"
    >
      <span className="inline-flex items-center gap-0.5">
        {sources.map((s, i) => (
          <SourceMark key={`${s}-${i}`} source={s} />
        ))}
      </span>
      <span
        className="font-mono text-[10px] font-medium leading-none"
        style={{ color: 'var(--color-success)' }}
      >
        {n} sources
      </span>
    </span>
  );
}
