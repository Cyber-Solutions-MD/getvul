'use client';
/**
 * AiFeedbackControl — thumbs (up/down) + optional 500-char correction note,
 * mounted beneath a validated AI explanation (section state 1 only, D-21).
 *
 * Capture-only (D-21): submits to POST /api/v1/ai/feedback/{resourceType}/
 * {resourceId} via useAiFeedback — nothing here reads feedback back; Phase
 * 28 owns the flywheel/dashboard surfacing. A thumb alone is a valid
 * submission — the note never blocks (partial submit is fine, UI-SPEC). On
 * a submit failure the thumb state silently reverts to its prior value —
 * no error toast/card (low-stakes accuracy signal, UI-SPEC user decision).
 *
 * The "optimistic mark + silent revert" lives here (component-local state),
 * not in the mutation hook — there is no other reader of "this analyst's
 * thumb state for this resource" anywhere else in the app this phase
 * (capture-only), so a local snapshot/revert is the correct minimal shape,
 * not a shortcut (see use-ai-feedback.ts's own doc comment).
 */
import { useEffect, useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAiFeedback, type FeedbackVerdict } from '@/lib/queries/use-ai-feedback';

const MAX_NOTE_CHARS = 500;

const THUMB_BASE_CLASS =
  'inline-flex h-8 w-8 items-center justify-center rounded-md border focus:outline-none focus-visible:ring-2 focus-visible:ring-violet';
const THUMB_ACTIVE_CLASS = 'border-violet bg-violet-soft text-[var(--color-violet-on-soft)]';
const THUMB_INACTIVE_CLASS = 'border-border-subtle text-text-muted hover:text-text';

type Props = {
  resourceType: string;
  resourceId: string;
};

export function AiFeedbackControl({ resourceType, resourceId }: Props) {
  const [activeThumb, setActiveThumb] = useState<FeedbackVerdict | null>(null);
  const [note, setNote] = useState('');
  const feedback = useAiFeedback(resourceType, resourceId);

  // Defend against a stale thumb/note leaking across resources: DrillPanel
  // reuses this component instance across id changes (no `key` remount),
  // so without this reset an analyst could see "already voted up" carried
  // over from a DIFFERENT finding.
  useEffect(() => {
    setActiveThumb(null);
    setNote('');
  }, [resourceType, resourceId]);

  function handleThumb(verdict: FeedbackVerdict) {
    const previousThumb = activeThumb;
    setActiveThumb(verdict); // optimistic (D-21)
    feedback.mutate(
      { verdict, note: note.trim() || null },
      {
        // Silent revert — no toast/error card (low-stakes signal, UI-SPEC).
        onError: () => setActiveThumb(previousThumb),
      },
    );
  }

  function handleNoteBlur() {
    // A note typed AFTER a thumb is already active is still worth
    // capturing — resubmit with the current note attached to the same
    // verdict. Idempotent on the backend (D-22 upsert); harmless if
    // unchanged. No verdict yet → nothing to attach the note to.
    if (activeThumb === null) return;
    feedback.mutate({ verdict: activeThumb, note: note.trim() || null });
  }

  return (
    <div className="mt-4 flex flex-col gap-2 rounded-lg bg-surface-2 p-3">
      <span className="text-xs font-medium text-text-muted">Was this explanation accurate?</span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label="Accurate"
          aria-pressed={activeThumb === 'up'}
          onClick={() => handleThumb('up')}
          className={cn(THUMB_BASE_CLASS, activeThumb === 'up' ? THUMB_ACTIVE_CLASS : THUMB_INACTIVE_CLASS)}
        >
          <ThumbsUp className="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          aria-label="Not accurate"
          aria-pressed={activeThumb === 'down'}
          onClick={() => handleThumb('down')}
          className={cn(THUMB_BASE_CLASS, activeThumb === 'down' ? THUMB_ACTIVE_CLASS : THUMB_INACTIVE_CLASS)}
        >
          <ThumbsDown className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        onBlur={handleNoteBlur}
        placeholder="What was off? (optional)"
        maxLength={MAX_NOTE_CHARS}
        rows={2}
        className="w-full resize-none rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet"
        aria-label="Feedback note"
      />
    </div>
  );
}
