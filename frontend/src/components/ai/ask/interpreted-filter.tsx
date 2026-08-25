'use client';
/**
 * InterpretedFilter -- the D-04 "Interpreted as:" summary card. Renders the
 * model-emitted, backend-executed filter (VulnFilterInput / AssetFilterInput
 * / TicketFilterInput, backend/app/ai/schemas.py) as human-readable mono
 * predicate tokens joined by " · ", so a misread is always visible before
 * the analyst trusts the result set (T-44-09: rendered as plain text, never
 * dangerouslySetInnerHTML -- React escapes by default).
 *
 * Backstop (44-UI-SPEC.md §E4 overflow): tokens flex-wrap onto multiple
 * lines rather than truncate or scroll.
 */

// Known *FilterInput field -> friendly token label, mirroring the
// UI-SPEC's own example verbatim ("severity=Critical · KEV=true ·
// first_seen>30d · exposure=internet-facing"). Any field not in this map
// (future additive predicates) falls back to a generic `key=value` token
// rather than being silently dropped -- this must never hide a predicate
// the model actually applied (prohibition: "must never silently widen or
// narrow the interpreted filter without showing it").
function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function formatListOrScalar(value: string[] | string): string {
  if (Array.isArray(value)) return value.map(titleCase).join(',');
  return titleCase(value);
}

function tokenFor(key: string, value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (Array.isArray(value) && value.length === 0) return null;

  switch (key) {
    case 'severity':
      return `severity=${formatListOrScalar(value as string[] | string)}`;
    case 'status':
      return `status=${formatListOrScalar(value as string[] | string)}`;
    case 'cisa_kev':
      return `KEV=${String(value)}`;
    case 'exploit_available':
      return `exploit=${String(value)}`;
    case 'age_days_min':
      return `first_seen>${String(value)}d`;
    case 'asset_internet_facing':
    case 'internet_facing':
      return `exposure=${value ? 'internet-facing' : 'not-internet-facing'}`;
    case 'sla_breached':
      return `SLA=${value ? 'breached' : 'not-breached'}`;
    case 'asset_hostname':
      return `host=${String(value)}`;
    case 'device_category':
      return `device_category=${String(value)}`;
    default:
      // Additive-predicate fallback (never silently dropped).
      return `${key}=${Array.isArray(value) ? value.join(',') : String(value)}`;
  }
}

function tokensFor(filter: Record<string, unknown>): string[] {
  return Object.entries(filter)
    .map(([key, value]) => tokenFor(key, value))
    .filter((token): token is string => token !== null);
}

// 44-04 (Plan 04, D-04): exported so the zero-results EmptyState body
// ("Interpreted as: {predicate summary}. Try broadening a term...") can
// reuse the EXACT SAME token-formatting logic this card renders -- the
// predicate summary can never drift between the two surfaces since both
// read from this one function.
export function formatInterpretedFilterSummary(filter: Record<string, unknown>): string {
  return tokensFor(filter).join(' · ');
}

export type InterpretedFilterProps = {
  filter: Record<string, unknown>;
};

export function InterpretedFilter({ filter }: InterpretedFilterProps) {
  const tokens = tokensFor(filter);

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-2 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Interpreted as:</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-sm font-semibold text-text">
        {tokens.map((token, i) => (
          <span key={token} className="inline-flex items-center gap-2">
            <span>{token}</span>
            {i < tokens.length - 1 && (
              <span aria-hidden="true" className="text-text-faint">
                ·
              </span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
