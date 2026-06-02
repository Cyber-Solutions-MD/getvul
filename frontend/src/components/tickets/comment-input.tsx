/**
 * CommentInput — local comment input below the activity timeline.
 *
 * D-C-04 (renders below the timeline):
 * - <textarea> with microcopy.commentPlaceholder, maxLength=10000.
 * - Send button ("Post note") — peer voice per copy-voice.md.
 * - Disabled while empty/whitespace (T-13-21 client-side guard).
 * - Calls onSubmit(trimmedBody) only when 1 <= len <= 10000.
 * - Shows subtle char-count warning near the limit.
 * - Disables controls while submitting=true.
 *
 * T-13-20: maxLength=10000 mirrors backend Pydantic bound (defense in depth).
 * T-13-21: trim + blank check before onSubmit; whitespace-only → button disabled.
 */
'use client';

import { useState, useCallback } from 'react';
import { microcopy } from './microcopy';

const MAX_LENGTH = 10000;
const WARN_THRESHOLD = 9500;

export type CommentInputProps = {
  onSubmit: (body: string) => void;
  submitting?: boolean;
};

export function CommentInput({ onSubmit, submitting = false }: CommentInputProps) {
  const [body, setBody] = useState('');

  const trimmed = body.trim();
  const isEmpty = trimmed.length === 0;
  const isDisabled = isEmpty || submitting;
  const charsLeft = MAX_LENGTH - body.length;
  const showCount = body.length >= WARN_THRESHOLD;

  const handleSubmit = useCallback(() => {
    if (isEmpty || submitting) return;
    onSubmit(trimmed);
    setBody('');
  }, [trimmed, isEmpty, submitting, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Ctrl+Enter / Cmd+Enter submits
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <div className="mt-4 border-t border-border-subtle pt-4">
      <div className="flex flex-col gap-2">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={microcopy.commentPlaceholder}
          maxLength={MAX_LENGTH}
          rows={3}
          disabled={submitting}
          className="w-full resize-none rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:opacity-50"
          aria-label="Comment body"
        />

        <div className="flex items-center justify-between">
          {/* Subtle char-count near the limit */}
          {showCount ? (
            <span className="font-mono text-xs text-text-muted">
              {microcopy.charLimitWarning(charsLeft)}
            </span>
          ) : (
            <span />
          )}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={isDisabled}
            className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-sunset px-3 py-1.5 text-sm font-semibold text-white shadow-glow-cta transition hover:-translate-y-px hover:shadow-pink/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0"
          >
            {submitting ? 'Posting…' : microcopy.postNote}
          </button>
        </div>
      </div>
    </div>
  );
}
