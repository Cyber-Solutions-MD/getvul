/**
 * StatusPill — 4-state ticket status pill with leading dot.
 *
 * UX-05-03 / D-P-04: Status uses a separate color family from severity
 * (Open=violet, In progress=amber, Completed=success green, Blocked=severity-critical).
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
    // Phase-15 a11y (UX-07-03): text-violet on violet-soft is 4.35:1 (< AA 4.5).
    // Lift to the brighter same-hue shade (violet-300) = canonical
    // --color-violet-on-soft, documented in the design system (BL-04):
    // visual-language.md "Text on -soft fills".
    // Phase-16 (UX-D-03-04): replaced text-[#C4B5FD] JIT literal with
    // var(--color-violet-on-soft) so the light-mode override in globals.css
    // takes effect (dark: #C4B5FD via BL-04; light: #5B21B6 via Phase-16).
    classes: 'border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]',
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
    classes: 'border-success/40 bg-success/10 text-success',
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
