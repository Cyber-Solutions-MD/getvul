/**
 * CampaignStatusRibbon — campaign lifecycle status pill (Active / Complete).
 *
 * Re-skins tickets/status-pill.tsx's dot-leading pill chrome with the
 * campaign-lifecycle color mapping from 38-UI-SPEC.md's Color table:
 *   ACTIVE   -> violet (--color-violet, "open-style pill")
 *   COMPLETE -> green  (--color-success, "completed-style pill")
 *
 * Status is a SEPARATE color family from severity (visual-language.md) —
 * this component never renders a severity (red/orange/yellow) class, so the
 * eye can always tell a campaign-status pill apart from a severity pill at
 * a glance, even in dense tabular data.
 */
import { cn } from '@/lib/utils';
import type { CampaignStatus } from '@/lib/queries/use-campaigns';

type StatusConfig = { classes: string; label: string };

// Status -> Tailwind classes map. No raw hex; sunset-token classes only.
const STATUS_MAP: Record<CampaignStatus, StatusConfig> = {
  ACTIVE: {
    // Mirrors status-pill.tsx's "open" treatment — text-violet on
    // violet-soft fails AA at small sizes, so the -on-soft shade is used
    // for the text (visual-language.md "Text on -soft fills").
    classes: 'border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]',
    label: 'Active',
  },
  COMPLETE: {
    classes: 'border-success/40 bg-success/10 text-success',
    label: 'Complete',
  },
};

// Leading dot — a 6x6 solid-current-color circle per visual-language.md's
// status-pill convention.
function Dot() {
  return <span className="size-1.5 rounded-full bg-current" />;
}

export type CampaignStatusRibbonProps = {
  status: CampaignStatus;
  className?: string;
};

export function CampaignStatusRibbon({ status, className }: CampaignStatusRibbonProps) {
  const config = STATUS_MAP[status];
  return (
    <span
      data-campaign-status={status}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs',
        config.classes,
        className,
      )}
    >
      <Dot />
      {config.label}
    </span>
  );
}
