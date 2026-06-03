'use client';
/**
 * ApiTokensPane — D-SET-02 coming-soon placeholder for API tokens.
 *
 * Renders an EmptyState with "Personal API tokens are coming soon."
 * No create capability — backend does not expose a token endpoint yet.
 *
 * No raw palette utilities (gray-N / indigo-N).
 * data-pane="api-tokens" for test hooks.
 *
 * Plan 14-05.
 */

import { EmptyState } from '@/components/states';

export function ApiTokensPane() {
  return (
    <div data-pane="api-tokens" className="p-6">
      <EmptyState>
        <EmptyState.Title>API tokens</EmptyState.Title>
        <EmptyState.Body>
          Personal API tokens are coming soon.
        </EmptyState.Body>
      </EmptyState>
    </div>
  );
}
