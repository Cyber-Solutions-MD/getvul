/**
 * StatusPill — 4-state ticket status pill with leading dot.
 *
 * UX-05-03 / D-P-04: Status uses a separate color family from severity
 * (Open=violet, In progress=amber, Completed=severity-low, Blocked=severity-critical).
 * When blocked=true, renders BOTH the provider-status pill AND a Blocked pill
 * side-by-side ("Open · Blocked") — not a replacement.
 *
 * T-13-14 mitigation: externalStatus is normalized via toLowerCase() then
 * mapped through a literal class-lookup object. Unknown input falls through
 * to a neutral default (renders nothing for provider status). No raw hex;
 * all colors via Tailwind tokens.
 */
import { cn } from '@/lib/utils';
import type { TicketStatus } from './types';

// Pill base classes (all pills share this chrome)
const BASE =
  'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs';

// Status → Tailwind classes map (D-P-04 — locked contract)
type StatusConfig = {
  classes: string;
  label: string;
};

const STATUS_MAP: Record<string, StatusConfig> = {
  open: {
    classes: 'border-violet/40 bg-violet-soft text-violet',
    label: 'Open',
  },
  in_progress: {
    classes: 'border-amber/40 bg-amber/10 text-amber',
    label: 'In progress',
  },
  'in progress': {
    classes: 'border-amber/40 bg-amber/10 text-amber',
    label: 'In progress',
  },
  completed: {
    classes: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
    label: 'Completed',
  },
};

const BLOCKED_CONFIG: StatusConfig = {
  classes:
    'border-severity-critical/40 bg-severity-critical/10 text-severity-critical',
  label: 'Blocked',
};

// Leading dot — a 6×6 solid-current-color circle per visual-language.md
function Dot() {
  return <span className="size-1.5 rounded-full bg-current" />;
}

type PillProps = {
  config: StatusConfig;
  className?: string;
};

function Pill({ config, className }: PillProps) {
  return (
    <span
      data-status
      className={cn(BASE, config.classes, className)}
    >
      <Dot />
      {config.label}
    </span>
  );
}

export type StatusPillProps = {
  /** The external_status string from the backend (case-insensitive). */
  externalStatus: string | null;
  /** When true, render a second Blocked pill alongside the provider pill. */
  blocked?: boolean;
  className?: string;
};

export function StatusPill({ externalStatus, blocked, className }: StatusPillProps) {
  // Normalize case-insensitively; map through lookup (T-13-14: no arbitrary injection).
  const normalized = externalStatus?.toLowerCase() ?? null;
  const providerConfig = normalized ? STATUS_MAP[normalized] ?? null : null;

  if (!providerConfig && !blocked) {
    return null;
  }

  if (!blocked) {
    return providerConfig ? <Pill config={providerConfig} className={className} /> : null;
  }

  // blocked=true: render provider pill (if any) AND Blocked pill side by side.
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      {providerConfig && <Pill config={providerConfig} />}
      <Pill config={BLOCKED_CONFIG} />
    </span>
  );
}
