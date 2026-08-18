'use client';
/**
 * CampaignBurndownCard — CAMP-03 right-rail card. Wraps `RiskRing`
 * (score=pct_remediated, sunset-gradient stroke ALWAYS — UI-SPEC's explicit
 * "reuse the asset-detail risk-ring's exact dimensions, do NOT fork the SVG
 * math" instruction) with a status-family breakdown row (violet=open,
 * amber=in progress, green=done — NEVER severity red/orange/yellow) and a
 * Campaign MTTR line.
 *
 * RiskRing's own center-number/caption logic is built for a RISK score
 * (0 = "no exposures", a GOOD outcome, rendered as "—"). That semantic
 * inverts for a burndown (0% = nothing remediated YET, a real, meaningful
 * value — not "unavailable"). Rather than forking RiskRing's math to fix
 * this, this component renders its OWN "{pct}% remediated" headline text
 * alongside the ring — that text is the source of truth for the E6
 * must_have ("zero-member campaign shows 0%"), decoupled from whatever
 * RiskRing's internal center glyph happens to render at score=0.
 *
 * Pitfall 5 (zero-member guard): `pctRemediated`/`open`/`inProgress`/`done`
 * are all passed in as plain numbers from the backend's already-computed
 * `CampaignDetail` response (`get_campaign_progress`'s own `round(done /
 * total * 100) if total else 0` guard) — this component never divides by
 * a denominator itself, so it can never crash on 0/0.
 *
 * Deviation (Rule 1 — bug found during Task 2): `RiskRing`'s DEFAULT
 * behavior bakes in a risk-band (severity) color lookup for its center
 * digit — a genuine conflict with this plan's explicit prohibition
 * ("never severity red/orange/yellow on the burndown ring"). Rather than
 * forking RiskRing's SVG arc math (still forbidden), `RiskRing` gained 3
 * new, purely-additive, backward-compatible optional props
 * (`tintClassName`/`caption`/`ariaLabel` — see RiskRing.tsx) that every
 * existing risk-score call site (RiskCard) omits and is therefore
 * unaffected by. This card is the first (and so far only) caller to use
 * them, passing a neutral tint + a suppressed caption (this card renders
 * its own "{pct}% remediated" text instead).
 */
import { RiskRing } from '@/components/ui/RiskRing';
import { cn } from '@/lib/utils';

export type CampaignBurndownCardProps = {
  pctRemediated: number;
  open: number;
  inProgress: number;
  done: number;
  /** D-12: null (never 0) when no member has ever been remediated. */
  mttrSeconds: number | null;
  className?: string;
};

// Format seconds -> "{d}d {h}h" per UI-SPEC's live-progress microcopy
// example ("4d 6h"). "—" when null.
export function formatMttr(seconds: number | null): string {
  if (seconds === null) return '—';
  const totalHours = Math.floor(seconds / 3600);
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  return `${days}d ${hours}h`;
}

export function CampaignBurndownCard({
  pctRemediated,
  open,
  inProgress,
  done,
  mttrSeconds,
  className,
}: CampaignBurndownCardProps) {
  return (
    <section
      className={cn('rounded-lg border border-border-subtle bg-surface-2 p-4', className)}
      aria-label="Campaign burndown"
      data-testid="campaign-burndown-card"
    >
      <div className="flex flex-col items-center gap-2 pb-3">
        <RiskRing
          score={pctRemediated}
          // Neutral tint (never severity-band) + suppressed caption (this
          // card renders its own "{pct}% remediated" text below) — see the
          // module docstring's deviation note.
          tintClassName="text-text"
          caption={null}
          ariaLabel={`Campaign burndown ${pctRemediated}% remediated`}
        />
        {/* Copywriting Contract: "{pct}% remediated" headline stat, mono. */}
        <span className="font-mono text-sm font-semibold text-text">
          {pctRemediated}% remediated
        </span>
      </div>

      {/* Status-family breakdown row — violet/amber/green, never severity
          red/orange/yellow. Verbatim copy shape from the UI-SPEC:
          "{open} open · {in_progress} in progress · {done} done". */}
      <div className="flex items-center justify-center gap-2 border-t border-border-subtle py-3 font-mono text-sm text-text-muted">
        <span className="text-violet">{open} open</span>
        <span aria-hidden="true">·</span>
        <span className="text-amber">{inProgress} in progress</span>
        <span aria-hidden="true">·</span>
        <span className="text-success">{done} done</span>
      </div>

      <div className="border-t border-border-subtle pt-3 text-sm text-text-muted">
        Campaign MTTR: <span className="font-mono text-text">{formatMttr(mttrSeconds)}</span>
      </div>
    </section>
  );
}
