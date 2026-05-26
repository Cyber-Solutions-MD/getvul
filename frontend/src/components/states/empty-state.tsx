'use client';
import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

// D-S-02 + D-S-07: compound EmptyState. role="status" + aria-live="polite"
// make screen readers announce the empty state without yanking focus.
//
// Heading uses <h2> so axe will not flag h-jumping when consumers nest
// under page <h1>. Consumers can override className via prop spread but
// MUST NOT change the tag — that is the compound contract.
//
// Mirrors the Phase 10 Card primitive compound pattern: Object.assign(
//   Root, { Title, Body, Actions, Suggestion }
// ).

const EmptyStateRoot = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="status"
      aria-live="polite"
      className={cn(
        'mx-auto max-w-xl rounded-lg border border-border-subtle bg-surface p-10 text-center',
        className
      )}
      {...props}
    />
  )
);
EmptyStateRoot.displayName = 'EmptyState';

const EmptyStateTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h2 ref={ref} className={cn('text-xl font-semibold text-text', className)} {...props} />
  )
);
EmptyStateTitle.displayName = 'EmptyState.Title';

const EmptyStateBody = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn('mt-3 text-text-muted', className)} {...props} />
  )
);
EmptyStateBody.displayName = 'EmptyState.Body';

const EmptyStateActions = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('mt-6 flex flex-wrap justify-center gap-3', className)}
      {...props}
    />
  )
);
EmptyStateActions.displayName = 'EmptyState.Actions';

const EmptyStateSuggestion = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-empty-suggestion=""
      className={cn(
        'mt-6 inline-flex items-start gap-2 rounded-md bg-violet-soft p-3 text-left text-sm text-violet',
        className
      )}
      {...props}
    />
  )
);
EmptyStateSuggestion.displayName = 'EmptyState.Suggestion';

export const EmptyState = Object.assign(EmptyStateRoot, {
  Title: EmptyStateTitle,
  Body: EmptyStateBody,
  Actions: EmptyStateActions,
  Suggestion: EmptyStateSuggestion,
});
