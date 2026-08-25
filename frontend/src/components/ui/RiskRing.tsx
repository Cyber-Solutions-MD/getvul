/**
 * RiskRing — UX-04-03 risk-score visualization.
 *
 * Sketch 005 variant B is the locked design. Single sunset gradient stroke ALWAYS
 * (locked_decisions item 5); the band tints only affect center text via the
 * `BAND_TINT` map. Math per RESEARCH §7.
 *
 * Edge cases (D-R-03):
 *   score = 0    → no fg arc; center "—" + "No exposures"
 *   score = 100  → full arc (offset 0); center number tinted danger
 *   score = null → no fg arc; center "—" + "Risk unavailable"
 *
 * The three hex codes inside the SVG <defs> below (#EC4899, #A78BFA, #F59E0B)
 * are the sketch-locked sunset gradient triplet and are permitted to live as
 * literal stops on the gradient. CLAUDE.md "no freehand hex" applies to layout
 * tokens — the gradient is a brand asset reproduced verbatim from the sketch.
 */
import { cn } from '@/lib/utils';

export type RiskBand = 'critical' | 'high' | 'medium' | 'low' | 'unavailable';

export function getRiskBand(score: number | null): RiskBand {
  if (score === null) return 'unavailable';
  if (score >= 80) return 'critical';
  if (score >= 50) return 'high';
  if (score >= 20) return 'medium';
  return 'low';
}

const BAND_LABEL: Record<RiskBand, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  unavailable: 'Unavailable',
};

// D-R-01: band → center text tint. Stroke is ALWAYS sunset gradient.
// text-text-faint substitutes for the plan's text-text-subtle (token not in tailwind.config.ts).
const BAND_TINT: Record<RiskBand, string> = {
  critical: 'text-[var(--color-severity-critical-on-soft)]',
  high: 'text-[var(--color-severity-high-on-soft)]',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  unavailable: 'text-text-faint',
};

const CIRCUMFERENCE = 2 * Math.PI * 40; // ~251.3

export type RiskRingProps = {
  score: number | null;
  size?: number; // default 120 (sketch 005 size)
  className?: string;
  /**
   * Phase 38 (38-05, CAMP-03) additive escape hatch — overrides the center
   * score text's risk-band (severity) tint class entirely. Every existing
   * risk-score call site omits this and keeps the default BAND_TINT lookup
   * unchanged; the campaign burndown card passes a neutral tint since
   * pct_remediated is a status concept, never a severity concept (the
   * UI-SPEC explicitly prohibits severity red/orange/yellow on the
   * burndown ring — reusing RiskRing "verbatim" means not forking its SVG
   * arc math, not inheriting its severity-color lookup for a non-severity
   * number).
   */
  tintClassName?: string;
  /**
   * Phase 38 (38-05) additive escape hatch — overrides the auto-derived
   * caption ("Risk unavailable" / "No exposures", both risk-score-specific
   * copy). Pass `null` to suppress the caption entirely (the caller renders
   * its own stat text instead), or a string for custom copy. Omit to keep
   * the default risk-score-derived caption — every existing call site
   * omits this.
   */
  caption?: string | null;
  /** Phase 38 (38-05) additive escape hatch — overrides the default
   * risk-score aria-label. Omit to keep the default. */
  ariaLabel?: string;
};

export function RiskRing({
  score,
  size = 120,
  className,
  tintClassName,
  caption: captionProp,
  ariaLabel: ariaLabelProp,
}: RiskRingProps) {
  const band = getRiskBand(score);
  const showArc = score !== null && score > 0;
  const offset =
    score !== null ? CIRCUMFERENCE * (1 - score / 100) : CIRCUMFERENCE;
  const caption =
    captionProp !== undefined
      ? captionProp
      : score === null
        ? 'Risk unavailable'
        : score === 0
          ? 'No exposures'
          : null;
  const ariaLabel =
    ariaLabelProp !== undefined
      ? ariaLabelProp
      : score === null
        ? 'Risk score unavailable'
        : score === 0
          ? 'Risk score 0 — no exposures'
          : `Risk score ${score} — ${BAND_LABEL[band]}`;

  return (
    <div
      className={cn(
        'relative inline-flex flex-col items-center justify-center',
        className,
      )}
      style={{ width: size, height: size }}
      role="img"
      aria-label={ariaLabel}
      data-band={band}
    >
      <svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        style={{ transform: 'rotate(-90deg)' }}
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id="sunset-grad"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor="#EC4899" />
            <stop offset="50%" stopColor="#A78BFA" />
            <stop offset="100%" stopColor="#F59E0B" />
          </linearGradient>
        </defs>
        <circle
          cx="50"
          cy="50"
          r="40"
          className="ring-bg"
          fill="none"
          stroke="var(--color-border-subtle, rgba(255,255,255,0.08))"
          strokeWidth="8"
        />
        {showArc && (
          <circle
            cx="50"
            cy="50"
            r="40"
            className="ring-fg"
            fill="none"
            stroke="url(#sunset-grad)"
            strokeWidth="8"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ filter: 'drop-shadow(0 0 8px currentColor)' }}
          />
        )}
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn(
            'font-mono text-3xl font-semibold tabular-nums',
            tintClassName ?? BAND_TINT[band],
          )}
          data-testid="risk-ring-score"
        >
          {score === null || score === 0 ? '—' : score}
        </span>
        {caption && (
          <span className="mt-1 text-xs text-text-faint">{caption}</span>
        )}
      </div>
    </div>
  );
}
