'use client';
/**
 * QueryBox -- the free-text question input + "Ask" CTA (44-UI-SPEC.md §E1/§E2).
 *
 * Mirrors CommentInput's (frontend/src/components/tickets/comment-input.tsx)
 * char-cap + counter convention exactly: maxLength on the <textarea> itself
 * (defense-in-depth alongside the backend's own Field(min_length=1,
 * max_length=500), T-44-05), a subtle mono char-count-warning near the
 * limit, and a disabled/pending state while a request is in flight.
 *
 * Backstops (44-UI-SPEC.md §UI Considerations E1):
 *   - long-text: bounded to 500 chars with a live counter; text never clips.
 *   - overflow: soft-wraps and grows to a bounded height, then scrolls
 *     internally (max-h-40 overflow-y-auto) rather than clipping.
 */
import { useCallback, useState, type KeyboardEvent } from 'react';
import { Sparkles } from 'lucide-react';

const MAX_LENGTH = 500;
const WARN_THRESHOLD = 450;

export type QueryBoxProps = {
  onAsk: (question: string) => void;
  /** True while a question is in-flight (translate/execute/narrate) -- disables the field + CTA. */
  pending?: boolean;
};

export function QueryBox({ onAsk, pending = false }: QueryBoxProps) {
  const [question, setQuestion] = useState('');

  const trimmed = question.trim();
  const isEmpty = trimmed.length === 0;
  const isDisabled = isEmpty || pending;
  const charsLeft = MAX_LENGTH - question.length;
  const showCount = question.length >= WARN_THRESHOLD;

  const handleAsk = useCallback(() => {
    if (isEmpty || pending) return;
    onAsk(trimmed);
  }, [trimmed, isEmpty, pending, onAsk]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Ctrl+Enter / Cmd+Enter asks -- mirrors CommentInput's submit shortcut.
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleAsk();
      }
    },
    [handleAsk],
  );

  return (
    <div className="rounded-lg border border-border-subtle bg-surface p-4">
      <div className="flex flex-col gap-2">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Which internet-facing hosts have an unremediated KEV older than 30 days?"
          maxLength={MAX_LENGTH}
          rows={2}
          disabled={pending}
          className="max-h-40 w-full resize-none overflow-y-auto rounded-md border border-border-subtle bg-surface-2 px-3 py-2 text-base text-text placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-soft disabled:opacity-50"
          aria-label="Ask a question about your vulnerabilities, assets, or tickets"
        />

        <div className="flex items-center justify-between">
          {showCount ? (
            <span className="font-mono text-xs text-text-muted">{charsLeft} characters left</span>
          ) : (
            <span />
          )}

          <button
            type="button"
            onClick={handleAsk}
            disabled={isDisabled}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-lg bg-gradient-sunset px-4 py-2 text-sm font-semibold text-white shadow-glow-cta transition hover:-translate-y-px hover:shadow-pink/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0"
          >
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            {pending ? 'Asking…' : 'Ask'}
          </button>
        </div>
      </div>
    </div>
  );
}
