'use client';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { AlertTriangle, Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { useExplainCache } from '@/lib/queries/use-explain-cache';
import { useExplainStream } from '@/lib/ai/use-explain-stream';
import { useConnectorsList } from '@/lib/queries/use-connectors-admin';
import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion';
import { cn } from '@/lib/utils';
import { AiExplanationCitations } from './ai-explanation-citations';

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
  variant: 'neutral' | 'amber';
  heading: string;
  body: string;
  action?: { label: string; onClick?: () => void; href?: string };
};

function DegradedCard({ variant, heading, body, action }: DegradedCardProps) {
  const chipClass =
    variant === 'amber' ? 'bg-amber-soft text-[var(--color-amber-on-soft)]' : 'bg-violet-soft text-[var(--color-violet-on-soft)]';
  return (
    <div role="status" className="rounded-lg border border-border-subtle bg-surface-2 p-5">
      <div className={cn('mb-3 flex h-8 w-8 items-center justify-center rounded-full', chipClass)}>
        {variant === 'amber' ? (
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
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

function AnalyzingIndicator() {
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
};

export function AiExplanationSection({ resourceType, resourceId }: Props) {
  const { user } = useAuth();
  const role = user?.role ?? 'VIEWER';
  const isAdminOrOwner = role === 'OWNER' || role === 'ADMIN';
  const isAnalystOrAbove = isAdminOrOwner || role === 'ANALYST';

  const cacheQuery = useExplainCache(resourceType, resourceId);
  // GET /api/v1/connectors is require_admin-gated on the backend -- Analyst/
  // Viewer's request here will 403. Called unconditionally anyway (matching
  // the existing /dashboard/connectors page's own precedent) so
  // connectorsQuery.isError genuinely reflects "couldn't verify" for those
  // roles, which the derivation below treats as an optimistic pass-through
  // rather than a hard "no key" -- otherwise Analyst could never see the
  // trigger button at all, breaking the tracer for the very role it exists
  // for. The backend remains the authoritative control regardless (Plan 04's
  // require_analyst gate + the stream hook's defensive no_key fallback).
  const connectorsQuery = useConnectorsList();
  const { state, start } = useExplainStream(resourceType, resourceId);
  const prefersReducedMotion = usePrefersReducedMotion();

  const keyConfigured = connectorsQuery.isError
    ? true
    : Boolean(connectorsQuery.data?.some((c) => c.connector_type === 'ANTHROPIC' && c.is_enabled));

  const prereqsPending = cacheQuery.isPending || connectorsQuery.isPending;

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
      <DegradedCard
        variant="neutral"
        heading="Not enough finding data to explain this reliably"
        body="The correlated record is missing detail — CVE description, CVSS vector, or host context — the assistant needs to ground a faithful explanation. It declined to guess."
      />
    ) : (
      <AiExplanationCitations data={state.data} animateReveal={!prefersReducedMotion} />
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
    body = (
      <DegradedCard
        variant="neutral"
        heading="Not enough finding data to explain this reliably"
        body="The correlated record is missing detail — CVE description, CVSS vector, or host context — the assistant needs to ground a faithful explanation. It declined to guess."
      />
    );
  } else if (cacheQuery.data?.cached === true) {
    const cached = cacheQuery.data;
    body = !cached.grounded ? (
      <DegradedCard
        variant="neutral"
        heading="Not enough finding data to explain this reliably"
        body="The correlated record is missing detail — CVE description, CVSS vector, or host context — the assistant needs to ground a faithful explanation. It declined to guess."
      />
    ) : (
      // D-09: a cache hit on mount renders immediately -- no replay
      // animation (that's reserved for the just-clicked -> analyzing ->
      // done transition, D-12).
      <AiExplanationCitations data={cached} animateReveal={false} />
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
  } else if (isAnalystOrAbove) {
    // D-17: only Analyst+ ever sees the paid-call trigger.
    body = (
      <button type="button" onClick={() => void start()} className={SECONDARY_BTN_CLASS}>
        Explain this vuln
      </button>
    );
  } else {
    // D-17: Viewers never trigger a paid call -- muted text, no button.
    body = <p className="text-sm text-text-muted">No AI explanation generated yet.</p>;
  }

  // The <section aria-labelledby="drill-ai-h"> landmark itself is owned by
  // drill-content.tsx (the sibling-section precedent + this plan's own
  // artifact list) -- this component renders only the h4 + body so the two
  // never nest as <section><section>.
  return (
    <>
      <h4 id="drill-ai-h" className={H4_CLASS}>
        AI Explanation
      </h4>
      {body}
    </>
  );
}
