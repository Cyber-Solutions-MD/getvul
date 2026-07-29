'use client';
import { Fragment, useMemo } from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { Citation, ExplainVulnResponse } from '@/lib/ai/use-explain-stream';

// Citation Rendering Contract (UI-SPEC, D-13/D-14): each Citation in the
// validated response is matched as a substring against the ASSEMBLED
// summary + business_risk text and wrapped in place -- one flowing
// paragraph, never a separate citations-list block. Uncited text renders
// unstyled; citations only ever ADD styling, never remove it.
type TextSegment = { kind: 'text'; text: string };
type CitationSegment = { kind: 'citation'; text: string; source: Citation['source']; sourceField: string | null };
type Segment = TextSegment | CitationSegment;

function buildSegments(fullText: string, citations: Citation[]): Segment[] {
  type Range = { start: number; end: number; citation: Citation };
  const ranges: Range[] = [];

  for (const citation of citations) {
    if (!citation.text) continue;
    // Find the first occurrence of this citation's text that doesn't
    // overlap a range already claimed by an earlier citation. AI-SPEC's own
    // grounding gate should prevent a citation whose text never appears in
    // the response, but this never throws on that edge case -- it just
    // skips the citation (rendered as plain, unstyled prose instead).
    let idx = fullText.indexOf(citation.text);
    while (idx !== -1 && ranges.some((r) => idx < r.end && idx + citation.text.length > r.start)) {
      idx = fullText.indexOf(citation.text, idx + 1);
    }
    if (idx === -1) continue;
    ranges.push({ start: idx, end: idx + citation.text.length, citation });
  }

  ranges.sort((a, b) => a.start - b.start);

  const segments: Segment[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start > cursor) segments.push({ kind: 'text', text: fullText.slice(cursor, r.start) });
    segments.push({
      kind: 'citation',
      text: fullText.slice(r.start, r.end),
      source: r.citation.source,
      sourceField: r.citation.source_field,
    });
    cursor = r.end;
  }
  if (cursor < fullText.length) segments.push({ kind: 'text', text: fullText.slice(cursor) });
  return segments;
}

function tooltipLabel(source: Citation['source'], sourceField: string | null): string {
  if (source === 'scanner_verbatim') {
    return sourceField ? `Scanner-verbatim · from ${sourceField}` : 'Scanner-verbatim';
  }
  return sourceField ? `AI-interpreted · from ${sourceField}` : 'AI-interpreted';
}

type Props = {
  data: ExplainVulnResponse;
  /**
   * D-12: true only for a just-streamed ('done') result rendered right
   * after the analyst clicks Explain, and only when motion is allowed. A
   * cache hit (D-09) always renders statically -- the replay is specific
   * to the click -> analyzing -> result transition, never to a
   * drill-panel-open cache hit. Purely a CSS animate-in/fade-in stagger;
   * every segment is present in the DOM from the first render regardless
   * (no content is ever gated on a timer), so this only changes the visual
   * presentation, never what's queryable.
   */
  animateReveal?: boolean;
};

export function AiExplanationCitations({ data, animateReveal = false }: Props) {
  const fullText = `${data.summary} ${data.business_risk}`;
  const segments = useMemo(() => buildSegments(fullText, data.citations), [fullText, data.citations]);

  return (
    <TooltipProvider delayDuration={200}>
      <p className="text-sm text-text">
        {segments.map((seg, i) => {
          const delayStyle = animateReveal
            ? { animationDelay: `${i * 60}ms`, animationDuration: '220ms', animationFillMode: 'backwards' as const }
            : undefined;
          const animateClass = animateReveal ? 'motion-safe:animate-in motion-safe:fade-in-0' : undefined;

          if (seg.kind === 'text') {
            // No wrapping element at all in the static (non-animated) case --
            // uncited text renders as genuinely plain prose, not merely
            // unstyled-but-still-wrapped.
            if (!animateReveal) return <Fragment key={i}>{seg.text}</Fragment>;
            return (
              <span key={i} style={delayStyle} className={animateClass}>
                {seg.text}
              </span>
            );
          }

          const label = tooltipLabel(seg.source, seg.sourceField);

          if (seg.source === 'scanner_verbatim') {
            return (
              <Tooltip key={i}>
                <TooltipTrigger asChild>
                  <span
                    tabIndex={0}
                    style={delayStyle}
                    className={cn(
                      'cursor-help rounded-[3px] bg-violet-soft px-1 -mx-0.5 text-[var(--color-violet-on-soft)]',
                      animateClass,
                    )}
                  >
                    {seg.text}
                  </span>
                </TooltipTrigger>
                <TooltipContent>{label}</TooltipContent>
              </Tooltip>
            );
          }

          // ai_interpreted: normal prose immediately followed by the 10px
          // "AI" superscript tag (the tag itself carries the tooltip, not
          // the preceding prose).
          return (
            <Fragment key={i}>
              {animateReveal ? (
                <span style={delayStyle} className={animateClass}>
                  {seg.text}
                </span>
              ) : (
                seg.text
              )}
              <Tooltip>
                <TooltipTrigger asChild>
                  <sup
                    tabIndex={0}
                    className="ml-0.5 cursor-help text-[10px] font-medium uppercase tracking-wide text-text-faint"
                  >
                    AI
                  </sup>
                </TooltipTrigger>
                <TooltipContent>{label}</TooltipContent>
              </Tooltip>
            </Fragment>
          );
        })}
      </p>
    </TooltipProvider>
  );
}
