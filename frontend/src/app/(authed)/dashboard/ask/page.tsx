'use client';
/**
 * /dashboard/ask — Phase 44 Plan 04 (NLQ-01/NLQ-03): the full D-09
 * natural-language "Ask" workflow. Composes every piece Plan 03 (the SSE
 * hook + presentational ask/ components) and Plan 05 (the D-17 deep-link)
 * built, but wires none of the model-calling path itself — this page is
 * pure composition + copy.
 *
 * Composition mirrors dashboard/compliance/page.tsx:
 *   ErrorBoundary > Suspense > AskPageInner
 *
 * The ONLY page-load query is useAiStatus() (D-12 gate) — everything else
 * is driven by useQueryStream's local state machine, submit-triggered only
 * (44-PATTERNS.md WATCH-OUT: unlike every other dashboard list page, this
 * page fetches nothing on mount besides the AI-configured check).
 *
 * State branches (WR-13 order — error/loading checked first):
 *   aiStatusQ error                              -> PartialFailureBanner
 *   aiStatusQ pending                             -> lightweight skeleton
 *   !configured OR stream phase 'no_key'          -> D-12 Configure-AI card
 *   else (configured)                             -> QueryBox always visible,
 *     stacked with whichever of idle/interpreting/refuse/error/interpreted/
 *     results/streaming/done applies (D-15 results-first: interpretation +
 *     result table render BEFORE the narrative, D-04 interpretation always
 *     shown alongside any answer, D-17 Open-in deep-link beside it).
 *
 * Error-kind -> DegradedCard mapping (the plan's own `<action>` block, one
 * of `QueryStreamErrorKind`'s 4 literal values per bucket — no dead
 * branches):
 *   budget_exceeded -> amber ("budget" bucket)
 *   grounded_false  -> danger ("safety" bucket — the structured-output
 *                      recheck/exclusivity gate tripping IS this pipeline's
 *                      injection/safety backstop, D-01/D-13; distinct from
 *                      the Explain flow's own grounded_false, which renders
 *                      NEUTRAL there for a different reason (insufficient
 *                      evidence, not a rejected/exclusivity-violating
 *                      structured output) — see 44-04-SUMMARY.md Decisions)
 *   busy | unknown  -> transient error banner ("transient" bucket)
 */
import { Suspense, useCallback, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { PartialFailureBanner, EmptyState } from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useAuth } from '@/lib/auth';
import { useAiStatus } from '@/lib/queries/use-ai-status';
import { useQueryStream, type NlqEntity, type QueryStreamState } from '@/lib/ai/use-query-stream';
import { buildNlqDeepLink, type NlqDeepLinkFilter } from '@/lib/ai/nlq-deep-link';
import { DegradedCard } from '@/components/ai/ai-explanation-section';
import { AiExplanationCitations } from '@/components/ai/ai-explanation-citations';
import { QueryBox } from '@/components/ai/ask/query-box';
import { StarterQuestions } from '@/components/ai/ask/starter-questions';
import { InterpretedFilter, formatInterpretedFilterSummary } from '@/components/ai/ask/interpreted-filter';
import { ResultTable } from '@/components/ai/ask/result-table';
import { cn } from '@/lib/utils';

const PAGE_TITLE = 'Ask';

// Mirrors compliance/page.tsx's CTA_SECONDARY constant verbatim — every
// secondary action on this page (Open in {list}, View trace) is bordered
// secondary chrome per the UI-SPEC Copywriting Contract ("never a second
// gradient" — the gradient CTA stays reserved for the QueryBox's "Ask"
// button).
const CTA_SECONDARY =
  'inline-flex w-fit items-center gap-1.5 rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

const ENTITY_LABEL: Record<NlqEntity, string> = {
  vulnerabilities: 'Vulnerabilities',
  assets: 'Assets',
  tickets: 'Tickets',
};

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">{PAGE_TITLE}</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

const SKELETON_BAR = 'inline-block rounded bg-gradient-to-r from-surface-2 via-border to-surface-2 bg-[length:200%_100%] motion-safe:animate-shimmer';

function AskPageSkeleton() {
  return (
    <div className="space-y-4 p-6" aria-busy="true" aria-label="Loading Ask">
      <h1 className="sr-only">{PAGE_TITLE}</h1>
      <span className={cn(SKELETON_BAR, 'h-8 w-24')} />
      <span className={cn(SKELETON_BAR, 'h-24 w-full max-w-2xl')} />
    </div>
  );
}

// D-12: reuses the app's one sanctioned pulsing-dot affordance (the same
// markup AnalyzingIndicator uses in ai-explanation-section.tsx) — never a
// new spinner. Parametrized so this one small component covers both the
// "Interpreting your question…" (E1 loading) and "Answering…" (E6
// streaming) copy without inventing a second visual pattern.
function PulseIndicator({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-2 text-sm text-text-muted">
      <span className="block h-2 w-2 rounded-full bg-violet motion-safe:animate-pulse" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

// Type guards narrow QueryStreamState's discriminated union so the shared
// interpretation/result-set render blocks below (D-04 always-shown
// interpretation, D-15 results-first, D-17 Open-in deep-link) apply
// identically across every phase that carries entity/filter/rows, without
// repeating the same JSX four times.
function hasFilter(
  s: QueryStreamState,
): s is Extract<QueryStreamState, { entity: NlqEntity; filter: Record<string, unknown> }> {
  return s.phase === 'interpreted' || s.phase === 'results' || s.phase === 'streaming' || s.phase === 'done';
}

function hasResults(
  s: QueryStreamState,
): s is Extract<QueryStreamState, { entity: NlqEntity; filter: Record<string, unknown>; rows: unknown[]; total: number }> {
  return s.phase === 'results' || s.phase === 'streaming' || s.phase === 'done';
}

function AskPageInner() {
  useDocumentTitle(PAGE_TITLE);
  const router = useRouter();
  const { user } = useAuth();
  const role = user?.role ?? 'VIEWER';
  const isAdminOrOwner = role === 'OWNER' || role === 'ADMIN';

  const aiStatusQ = useAiStatus();
  const { state, start } = useQueryStream();
  const [question, setQuestion] = useState('');

  const configured = Boolean(aiStatusQ.data?.configured);
  const isPending =
    state.phase === 'interpreting' ||
    state.phase === 'interpreted' ||
    state.phase === 'results' ||
    state.phase === 'streaming';

  const handleAsk = useCallback(
    (q: string) => {
      setQuestion(q);
      void start(q);
    },
    [start],
  );

  const handleRetry = useCallback(() => {
    const trimmed = question.trim();
    if (trimmed) void start(trimmed);
  }, [question, start]);

  // D-17 is read-only: opening a row navigates to the SAME real detail/drill
  // surface every other list page already uses for that entity — never a
  // new view. Vulnerabilities reuse the existing `?cve=…&open=drill`
  // deep-link contract (vulnerabilities/page.tsx); assets/tickets navigate
  // straight to their existing `[id]` detail routes.
  const handleRowOpen = useCallback(
    (idOrCve: string, entity: NlqEntity) => {
      if (entity === 'vulnerabilities') {
        router.push(`/dashboard/vulnerabilities?cve=${encodeURIComponent(idOrCve)}&open=drill`);
      } else if (entity === 'assets') {
        router.push(`/dashboard/assets/${encodeURIComponent(idOrCve)}`);
      } else {
        router.push(`/dashboard/tickets/${encodeURIComponent(idOrCve)}`);
      }
    },
    [router],
  );

  let gate: ReactNode = null;
  if (aiStatusQ.isError) {
    gate = (
      <PartialFailureBanner
        errors={[{ code: 'network', requestId: 'unknown' }]}
        onRetry={() => void aiStatusQ.refetch()}
      />
    );
  } else if (aiStatusQ.isPending) {
    gate = <AskPageSkeleton />;
  } else if (!configured || state.phase === 'no_key') {
    // D-23/D-12 precedent (ai-explanation-section.tsx): never an error — an
    // onboarding-flavored, role-gated card. Verbatim UI-SPEC copy.
    gate = (
      <DegradedCard
        variant="neutral"
        heading="AI isn't set up yet"
        body={
          isAdminOrOwner
            ? 'Turn on AI with your own Anthropic key to ask plain-English questions over your vulnerabilities, assets, and tickets.'
            : "Ask needs AI turned on — ask an admin to configure GetVul's AI connector."
        }
        action={isAdminOrOwner ? { label: 'Configure AI', href: '/dashboard/connectors' } : undefined}
      />
    );
  }

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        {/* 44-UI-SPEC.md Typography: sr-only h1, 32px/600 — mirrors the
            Coverage/Analytics/Compliance precedent where the visible page
            title lives in the topbar breadcrumb, not a visible <h1>. */}
        <h1 className="sr-only text-3xl font-semibold text-text">{PAGE_TITLE}</h1>
      </header>

      {gate ?? (
        <div className="space-y-4">
          <QueryBox value={question} onChange={setQuestion} onAsk={handleAsk} pending={isPending} />

          {state.phase === 'idle' && (
            <EmptyState className="mx-0 max-w-none text-left">
              <EmptyState.Title>Ask a question about your vulnerabilities, assets, or tickets</EmptyState.Title>
              <EmptyState.Body>
                Answers stay scoped to your own tenant data and a fixed set of filters — no free-form
                queries, no guesswork on counts. Try one of these:
              </EmptyState.Body>
              <EmptyState.Actions className="justify-start">
                <StarterQuestions onSelect={setQuestion} />
              </EmptyState.Actions>
            </EmptyState>
          )}

          {state.phase === 'interpreting' && <PulseIndicator label="Interpreting your question…" />}

          {state.phase === 'refuse' && (
            <DegradedCard
              variant="neutral"
              heading="Can't answer that one"
              body="Ask covers vulnerabilities, assets, and tickets — filtered by things like severity, exposure, SLA status, or KEV. Try a starter question below, or rephrase using those terms."
            />
          )}

          {state.phase === 'error' && state.kind === 'budget_exceeded' && (
            <DegradedCard
              variant="amber"
              heading="This tenant's monthly AI budget is used up"
              body="Ask an admin to raise the budget in AI settings, or wait until next month."
            />
          )}

          {state.phase === 'error' && state.kind === 'grounded_false' && (
            <DegradedCard
              variant="danger"
              heading="This answer was withheld"
              body="The assistant's response didn't pass GetVul's safety and grounding checks, so nothing was shown. Try rephrasing your question, or use a starter question below."
            />
          )}

          {state.phase === 'error' && (state.kind === 'busy' || state.kind === 'unknown') && (
            <div className="space-y-2">
              <PartialFailureBanner
                errors={[
                  {
                    code: state.httpStatus ?? 'network',
                    requestId: state.requestId ?? 'unknown',
                    message: "Couldn't translate that question",
                  },
                ]}
                onRetry={handleRetry}
              />
              <Link href="/dashboard/settings?category=ai" className={CTA_SECONDARY}>
                View trace
              </Link>
            </div>
          )}

          {hasFilter(state) && (
            <>
              <InterpretedFilter filter={state.filter} />
              <Link
                href={buildNlqDeepLink(state.entity, state.filter as unknown as NlqDeepLinkFilter)}
                className={CTA_SECONDARY}
              >
                Open in {ENTITY_LABEL[state.entity]}
              </Link>
            </>
          )}

          {state.phase === 'interpreted' && <PulseIndicator label="Loading results…" />}

          {hasResults(state) &&
            (state.rows.length === 0 ? (
              <EmptyState className="mx-0 max-w-none text-left">
                <EmptyState.Title>Nothing matches that</EmptyState.Title>
                <EmptyState.Body>
                  Interpreted as: {formatInterpretedFilterSummary(state.filter)}. Try broadening a term —
                  for example, dropping the age or exposure predicate.
                </EmptyState.Body>
              </EmptyState>
            ) : (
              <ResultTable
                entity={state.entity}
                rows={state.rows}
                total={state.total}
                onRowOpen={(id) => handleRowOpen(id, state.entity)}
              />
            ))}

          {state.phase === 'streaming' && state.rows.length > 0 && <PulseIndicator label="Answering…" />}

          {state.phase === 'done' &&
            state.rows.length > 0 &&
            (state.answer.grounded ? (
              <AiExplanationCitations data={state.answer} animateReveal />
            ) : (
              // Defensive backstop (mirrors ai-explanation-section.tsx's own
              // "even a just-streamed result is re-checked" comment): the
              // real engine never emits `done` for an ungrounded response,
              // but this never trusts that invariant blindly.
              <DegradedCard
                variant="neutral"
                heading="Couldn't produce a grounded answer"
                body="The assistant's narrative didn't cite the shown results reliably, so nothing was shown — the result set above is still accurate."
              />
            ))}
        </div>
      )}
    </div>
  );
}

const PAGE_FALLBACK = <AskPageSkeleton />;

export default function AskPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="AskPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <AskPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
