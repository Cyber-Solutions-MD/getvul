'use client';
/**
 * StarterQuestions -- exactly the 4 curated UI-SPEC starter-question chips
 * (D-11), click-to-fill. Copy is VERBATIM from 44-UI-SPEC.md's Copywriting
 * Contract -- never paraphrased.
 *
 * Chip chrome reuses EmptyState.Suggestion's exact violet-soft token pair
 * (bg-violet-soft + text-[var(--color-violet-on-soft)] -- see
 * frontend/src/components/states/empty-state.tsx) verbatim; EmptyState.
 * Suggestion itself is a single non-interactive hint block, so this renders
 * the same classes on a real <button> per chip rather than importing the
 * div component multiple times.
 *
 * Backstop (44-UI-SPEC.md §E3 long-text): chips flex-wrap onto multiple
 * lines rather than truncate -- the longest chip label is ~70 chars.
 */

// Verbatim from 44-UI-SPEC.md Copywriting Contract, D-11 (exactly 4).
export const STARTER_QUESTIONS = [
  'Which internet-facing hosts have an unremediated KEV older than 30 days?',
  'Show critical vulns breaching SLA',
  'Open tickets for asset prod-db-01',
  'Vulnerabilities on internet-facing assets with an active exploit',
] as const;

export type StarterQuestionsProps = {
  onSelect: (question: string) => void;
};

export function StarterQuestions({ onSelect }: StarterQuestionsProps) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Starter questions">
      {STARTER_QUESTIONS.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onSelect(question)}
          className="min-h-11 rounded-md bg-violet-soft px-3 py-2 text-left text-sm text-[var(--color-violet-on-soft)] transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
