'use client';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { AlertTriangle, Clock, Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { useExplainCache } from '@/lib/queries/use-explain-cache';
import { useExplainStream } from '@/lib/ai/use-explain-stream';
import { useAiStatus } from '@/lib/queries/use-ai-status';
import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion';
import { cn } from '@/lib/utils';
import { AiExplanationCitations } from './ai-explanation-citations';
// ai-feedback-control.tsx stays in components/vulnerabilities/ (24-09 Task 1
// moves only the section + citations components) -- it is already fully
// resourceType/resourceId-generalized (24-07), so a cross-directory alias
// import is the only change needed here.
import { AiFeedbackControl } from '@/components/vulnerabilities/ai-feedback-control';

// Section Placement (UI-SPEC D-11): identical h4 chrome to every sibling
// section in drill-content.tsx -- no new heading style.
const H4_CLASS = 'mb-2 text-xs uppercase tracking-wide text-text-muted';

// The one secondary-button chrome already established in this exact file's
// sibling (drill-content.tsx's own "Snooze 24h" button) -- "Explain this
// vuln" is deliberately a btn-secondary, never a second gradient CTA
// (foundation.md: the sunset gradient CTA stays reserved for "Create
// ticket").
const SECONDARY_BTN_CLASS =
  'inline-flex w-fit items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

type DegradedCardProps = {
  variant: 'neutral' | 'amber' | 'danger';
  heading: string;
  body: string;
  action?: { label: string; onClick?: () => void; href?: string };
  /**
   * Phase 26 (D-02/UI-SPEC §Color): additive icon override for the
   * `neutral` variant only -- defaults to 'sparkles' so every existing call
   * site (insufficient-evidence, no-key-configured) renders byte-identical.
   * 'clock' is reserved for the NEW queued/being-prepared card: same
   * violet-soft chip family as insufficient-evidence (deliberately not a
   * new hue), but a distinct glyph so the analyst can tell at a glance that
   * this state resolves on its own rather than being a terminal refusal.
   */
  icon?: 'sparkles' | 'clock';
};

// Phase 44 (44-03 Task 1): exported so the ask/ (NLQ) components can reuse
// this exact card verbatim for refusal/budget/safety/configure states
// (Pitfall 8) -- a one-line, zero-behavior-change diff. Every existing
// internal call site in this file is unaffected (still a plain local
// reference to the same function).
export function DegradedCard({ variant, heading, body, action, icon = 'sparkles' }: DegradedCardProps) {
  // Phase 25 UI-SPEC §Color: the `danger` variant reuses the EXACT
  // `border-danger bg-danger-soft text-danger` token combo already
  // established in ticket-provider-picker.tsx's error alert -- no new hex,
  // no new utility class. This is the ONE new color usage this phase
  // introduces, deliberately reserved for the safety-refusal card (Pitfall
  // 3: must never be visually confusable with the neutral/violet
  // insufficient-evidence card).
  const chipClass =
    variant === 'amber'
      ? 'bg-amber-soft text-[var(--color-amber-on-soft)]'
      : variant === 'danger'
        ? 'border border-danger bg-danger-soft text-danger'
        : 'bg-violet-soft text-[var(--color-violet-on-soft)]';
  return (
    <div role="status" className="rounded-lg border border-border-subtle bg-surface-2 p-5">
      <div className={cn('mb-3 flex h-8 w-8 items-center justify-center rounded-full', chipClass)}>
        {variant === 'amber' || variant === 'danger' ? (
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        ) : icon === 'clock' ? (
          <Clock className="h-4 w-4" aria-hidden="true" />
        ) : (
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        )}
      </div>
      <p className="text-sm font-medium text-text">{heading}</p>
      <p className="mt-1 text-sm text-text-muted">{body}</p>
      {action &&
        (action.href ? (
          <Link href={action.href} className={cn(SECONDARY_BTN_CLASS, 'mt-4')}>
            {action.label}
          </Link>
        ) : (
          <button type="button" onClick={action.onClick} className={cn(SECONDARY_BTN_CLASS, 'mt-4')}>
            {action.label}
          </button>
        ))}
    </div>
  );
}

// Phase 25 (AIR-02) UI-SPEC §Interaction Contract "Remediation guidance"
// section, Visual hierarchy: the cited prose is the focal read; this
// text-button is deliberately subordinate (12px label weight, no fill) --
// beneath the citations, above AiFeedbackControl.
function CopyToDescriptionButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-3 block text-xs font-medium text-text-muted underline-offset-2 hover:text-text hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
    >
      Copy into ticket description
    </button>
  );
}

// Phase 27 (AID-01, Plan 03): exported so drill-content.tsx's gap-fill row
// can reuse this exact pulsing-dot verbatim (D-12) -- no props, no closure
// over module-private state, so this is a safe, zero-risk export. Its own
// internal call site below (state.phase === 'analyzing') is unaffected.
export function AnalyzingIndicator() {
  return (
    <div className="flex items-center gap-2 text-sm text-text-muted">
      {/* D-12: reuses the app's one sanctioned pulsing-dot affordance
          (dashboard/hero.tsx's own eyebrow dot) -- never a new spinner. */}
      <span className="block h-2 w-2 rounded-full bg-violet motion-safe:animate-pulse" aria-hidden="true" />
      <span>Analyzing this finding…</span>
    </div>
  );
}

type Props = {
  resourceType: string;
  resourceId: string;
  /**
   * D-15 (24-09 Task 2): this shared component now mounts more than once on
   * a single page (e.g. a host-view mount alongside a per-ticket
   * remediation-view mount on /assets/[id]) -- a hardcoded DOM id on the
   * internal heading would collide (duplicate id, broken aria-labelledby
   * resolution) the moment two instances render together. Defaults to
   * 'drill-ai-h' so the vuln view's existing drill-content.tsx
   * aria-labelledby="drill-ai-h" wrapper needs no change; every other
   * mount site must pass its own unique id.
   */
  headingId?: string;
  /**
   * Phase 25 (AIR-02): fires the plain-text-flattened `summary` string
   * (never tinted/citation HTML, T-25-11) up to the caller when the
   * analyst clicks "Copy into ticket description" -- rendered ONLY in the
   * grounded-done/cache-hit branches (state 1/7), never in any degraded/
   * refuse/loading state. Omitted by every mount except drill-content.tsx's
   * resourceType="remediation-guidance" mount, so vuln/host/remediation
   * mounts render no button (D-09 scope fence: this affordance is specific
   * to the remediation-guidance view).
   */
  onCopyToDescription?: (text: string) => void;
};

export function AiExplanationSection({
  resourceType,
  resourceId,
  headingId = 'drill-ai-h',
  onCopyToDescription,
}: Props) {
  const { user } = useAuth();
  const role = user?.role ?? 'VIEWER';
  const isAdminOrOwner = role === 'OWNER' || role === 'ADMIN';
  const isAnalystOrAbove = isAdminOrOwner || role === 'ANALYST';

  const cacheQuery = useExplainCache(resourceType, resourceId);
  // D-23 gap closure (24-10, 24-VERIFICATION.md truth #2): GET
  // /api/v1/ai/status is require_viewer-gated -- every role gets a real,
  // non-error-coded boolean here (unlike the admin-gated GET
  // /api/v1/connectors this used to read, which always 403s for Analyst/
  // Viewer). No more optimistic "assume configured" guess off an error state.
  const statusQuery = useAiStatus();
  const { state, start } = useExplainStream(resourceType, resourceId);
  const prefersReducedMotion = usePrefersReducedMotion();

  const keyConfigured = Boolean(statusQuery.data?.configured);

  const prereqsPending = cacheQuery.isPending || statusQuery.isPending;

  // Phase 25 (D-06): "Remediation guidance" is a genuinely distinct
  // affordance from "Explain this vuln"/host/remediation-posture -- its own
  // trigger and its own cite-or-refuse output (CONTEXT D-06) -- so its
  // header/CTA/viewer-empty copy is locked verbatim in 25-UI-SPEC.md's
  // Copywriting Contract, distinct from the three original resourceTypes
  // this component already serves identically (D-15 three-view parity is
  // unaffected: it only ever governed vuln/host/remediation, never this 4th,
  // categorically different view). Every other card (no-key D-23, busy/
  // unknown D-25, budget-exceeded) stays byte-identical across all views.
  const isRemediationGuidance = resourceType === 'remediation-guidance';
  // Phase 26 (D-03/D-09, 26-UI-SPEC.md Copywriting Contract): a 5th
  // resourceType value, mirroring exactly how Phase 25 added
  // 'remediation-guidance' -- its own locked heading/trigger/viewer-empty/
  // insufficient-evidence copy, no other branch in this component touched.
  const isPrioritization = resourceType === 'prioritization';
  const heading = isPrioritization
    ? 'Prioritization'
    : isRemediationGuidance
      ? 'Remediation guidance'
      : 'AI Explanation';
  const triggerLabel = isPrioritization
    ? 'Explain the priority'
    : isRemediationGuidance
      ? 'Get remediation guidance'
      : 'Explain this vuln';
  const viewerEmptyText = isPrioritization
    ? 'No prioritization narrative generated yet.'
    : isRemediationGuidance
      ? 'No remediation guidance generated yet.'
      : 'No AI explanation generated yet.';
  // UI-SPEC state 8 renders the SAME card as state 3 (the model's own
  // grounded=false judgment and the deterministic pre-generation gate both
  // refuse into one honest card, D-02) -- this single copy source backs
  // every "insufficient evidence" render site below (done+!grounded,
  // kind===grounded_false, cached+!grounded, AND the new groundable===false
  // pre-refusal branch), so all four stay in lockstep for this resourceType.
  const insufficientEvidenceCopy = isPrioritization
    ? {
        heading: 'Not enough signal to explain priority reliably',
        body: "The correlated record is missing exploit, KEV, SLA, or severity signal — the assistant needs these facts to explain what's driving priority. It declined to guess.",
      }
    : isRemediationGuidance
      ? {
          heading: 'Not enough vendor guidance to recommend a fix',
          body: "The scanner didn't provide usable solution text for this finding — the assistant needs the vendor's own remediation text to ground safe, actionable steps. It declined to guess rather than invent one.",
        }
      : {
          heading: 'Not enough finding data to explain this reliably',
          body: 'The correlated record is missing detail — CVE description, CVSS vector, or host context — the assistant needs to ground a faithful explanation. It declined to guess.',
        };

  let body: ReactNode;

  if (prereqsPending) {
    // state-patterns.md: "single API request <300ms expected: don't
    // skeleton, just delay the render briefly" -- the cache-check is a
    // single cheap GET (D-09); a lightweight placeholder, not a heavy
    // skeleton or new copy, covers this near-instant gap.
    body = <div aria-hidden="true" className="h-4 w-40 animate-pulse rounded bg-surface-2" />;
  } else if (state.phase === 'analyzing') {
    body = <AnalyzingIndicator />;
  } else if (state.phase === 'done') {
    // UI-SPEC backstop: even a just-streamed result is re-checked for
    // grounded=false here -- the real engine never emits 'done' for an
    // ungrounded response, but this never trusts that invariant blindly.
    body = !state.data.grounded ? (
      <DegradedCard variant="neutral" heading={insufficientEvidenceCopy.heading} body={insufficientEvidenceCopy.body} />
    ) : (
      <>
        <AiExplanationCitations data={state.data} animateReveal={!prefersReducedMotion} />
        {onCopyToDescription && (
          <CopyToDescriptionButton onClick={() => onCopyToDescription(state.data.summary)} />
        )}
        <AiFeedbackControl resourceType={resourceType} resourceId={resourceId} />
      </>
    );
  } else if (state.phase === 'error' && (state.kind === 'busy' || state.kind === 'unknown')) {
    // D-25: 'unknown' is treated as transient/retryable, never a generic
    // error card -- the SAME amber card as a real rate-limit.
    body = (
      <DegradedCard
        variant="amber"
        heading="AI busy — try again in a moment"
        body="The AI provider is rate-limiting requests right now — this usually clears in under a minute."
        action={{ label: 'Try again', onClick: () => void start() }}
      />
    );
  } else if (state.phase === 'error' && state.kind === 'budget_exceeded') {
    body = (
      <DegradedCard
        variant="amber"
        heading="AI budget exceeded"
        body="This month's AI budget is used up — an admin's been notified."
        action={isAdminOrOwner ? { label: 'Raise the cap', href: '/dashboard/connectors' } : undefined}
      />
    );
  } else if (state.phase === 'error' && state.kind === 'grounded_false') {
    // D-24: a feature, not an error -- neutral/violet, never amber/red.
    body = <DegradedCard variant="neutral" heading={insufficientEvidenceCopy.heading} body={insufficientEvidenceCopy.body} />;
  } else if (state.phase === 'error' && state.kind === 'unsafe') {
    // Phase 25 D-04/T-25-02: a dangerous-pattern denylist hit refuses the
    // ENTIRE guidance -- danger/red, the ONE new color usage this phase
    // introduces, deliberately never confusable with the neutral
    // insufficient-evidence card above (Pitfall 3). The engine (25-03)
    // never cached or streamed the dangerous payload -- this branch never
    // receives or renders it, only the refusal.
    body = (
      <DegradedCard
        variant="danger"
        heading="This guidance was withheld for safety"
        body="The generated steps included a pattern GetVul treats as too risky to surface automatically (for example, a destructive command or disabling a security control). Nothing was shown — see the Remediation section above for the scanner's own solution text."
      />
    );
  } else if (cacheQuery.data?.cached === true) {
    const cached = cacheQuery.data;
    body = !cached.grounded ? (
      <DegradedCard variant="neutral" heading={insufficientEvidenceCopy.heading} body={insufficientEvidenceCopy.body} />
    ) : (
      // D-09: a cache hit on mount renders immediately -- no replay
      // animation (that's reserved for the just-clicked -> analyzing ->
      // done transition, D-12).
      <>
        <AiExplanationCitations data={cached} animateReveal={false} />
        {onCopyToDescription && (
          <CopyToDescriptionButton onClick={() => onCopyToDescription(cached.summary)} />
        )}
        <AiFeedbackControl resourceType={resourceType} resourceId={resourceId} />
      </>
    );
  } else if (!keyConfigured) {
    // D-23: never an error -- an onboarding-flavored, role-gated card.
    body = (
      <DegradedCard
        variant="neutral"
        heading="AI isn't set up yet"
        body={
          isAdminOrOwner
            ? 'Turn on AI with your own Anthropic key to get grounded explanations and business-risk framing on any finding.'
            : "AI explanations aren't available yet — ask an admin to configure GetVul's AI connector."
        }
        action={isAdminOrOwner ? { label: 'Configure AI', href: '/dashboard/connectors' } : undefined}
      />
    );
  } else if (cacheQuery.data?.cached === false && cacheQuery.data?.groundable === false) {
    // Phase 25 D-01/UI-SPEC state 3: the deterministic pre-generation gate
    // already knows this finding has no usable vendor guidance -- the
    // client never offers an action that's already known to be
    // unsatisfiable, so no button ever renders here and no model call is
    // spent (T-25-09). Checked `=== false` explicitly, not falsy: the
    // vuln/host/remediation-posture GET routes never return `groundable` at
    // all, so their cache-miss mounts fall through to the trigger below
    // completely unaffected.
    body = <DegradedCard variant="neutral" heading={insufficientEvidenceCopy.heading} body={insufficientEvidenceCopy.body} />;
  } else if (cacheQuery.data?.cached === false && cacheQuery.data?.queued === true) {
    // Phase 26 D-02/UI-SPEC states 3/4: this finding is part of the
    // tenant's currently-in-flight or upcoming Message Batches submission
    // (Plan 06 populates `queued`; this branch stays structurally in place
    // but dark until then). The SAME neutral/violet card family as
    // insufficient-evidence -- deliberately not a new hue -- but the Clock
    // icon (not Sparkles) signals "this resolves on its own," never a
    // terminal refusal. Driven ENTIRELY by the backend boolean, checked
    // `=== true` explicitly: every OTHER resourceType's GET route never
    // returns `queued` at all, so this branch must never match `undefined`
    // (UI-SPEC "partial" backstop -- never a client-side timing heuristic).
    // Analyst+ gets the subordinate on-demand escape hatch; Viewer gets the
    // identical card with no action (D-17 -- Viewers never trigger a paid
    // call, even this one).
    body = (
      <DegradedCard
        variant="neutral"
        icon="clock"
        heading="Prioritization narrative is being prepared"
        body="This finding is in the next scheduled batch — narratives typically land within 24h."
        action={isAnalystOrAbove ? { label: 'Generate it now', onClick: () => void start() } : undefined}
      />
    );
  } else if (isAnalystOrAbove) {
    // D-17: only Analyst+ ever sees the paid-call trigger.
    body = (
      <button type="button" onClick={() => void start()} className={SECONDARY_BTN_CLASS}>
        {triggerLabel}
      </button>
    );
  } else {
    // D-17: Viewers never trigger a paid call -- muted text, no button.
    body = <p className="text-sm text-text-muted">{viewerEmptyText}</p>;
  }

  // The wrapping <section aria-labelledby={headingId}> landmark is owned by
  // the CALLER (drill-content.tsx for vuln; assets/[id]/page.tsx for host;
  // remediation-timeline.tsx per row) -- this component renders only the h4
  // + body so the two never nest as <section><section>. headingId defaults
  // to 'drill-ai-h' (vuln view, unchanged) but must be unique per mount when
  // more than one instance renders on the same page (D-15 Task 2).
  return (
    <>
      <h4 id={headingId} className={H4_CLASS}>
        {heading}
      </h4>
      {body}
    </>
  );
}
