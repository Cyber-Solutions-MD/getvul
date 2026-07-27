'use client';
/**
 * TicketProviderPicker — analyst chooses the ticketing provider (Asana /
 * Jira / GitHub) when creating a ticket from the vuln drill panel (D-14),
 * filtered to the tenant's configured+enabled providers (D-15 endpoint).
 *
 * Mandatory loading/empty/error states per state-patterns.md (T-23-24):
 *   - loading: shimmer skeleton, not a blank/empty surface
 *   - error:   amber-adjacent alert (mirrors auth/error-alert.tsx), never silent
 *   - empty:   canonical EmptyState deep-linking to /dashboard/connectors —
 *              sourced from the endpoint returning [] (not a client-side
 *              filtered array), so an unconfigured tenant never sees a
 *              doomed create action
 *   - populated: one radio option per configured provider, default-selects
 *              the first on load
 *
 * T-23-22 mitigation: only renders what the tenant-scoped endpoint returns.
 */
import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import { ConnectorMark } from '@/components/connectors/connector-mark';
import type { ConnectorProvider } from '@/components/connectors/types';
import { EmptyState } from '@/components/states';
import { useTicketingProviders } from '@/lib/queries/use-ticketing-providers';
import { PROVIDER_LABELS, type TicketProvider } from '@/lib/ticketing/providers';
import { cn } from '@/lib/utils';

export type TicketProviderPickerProps = {
  value: TicketProvider | null;
  onChange: (provider: TicketProvider) => void;
};

// Ticket providers are always a subset of the broader ConnectorProvider
// union (D-14) — maps the uppercase wire TicketProvider to the lowercase
// ConnectorMark gradient-mark key rather than inventing a new glyph set.
const TO_CONNECTOR_MARK: Record<TicketProvider, ConnectorProvider> = {
  ASANA: 'asana',
  JIRA: 'jira',
  GITHUB: 'github',
};

export function TicketProviderPicker({ value, onChange }: TicketProviderPickerProps) {
  const { isLoading, isError, data } = useTicketingProviders();
  const providers = data ?? [];

  // Default-select the first configured+enabled provider once the list
  // loads. Re-fires only when the set of providers actually changes.
  const providerKey = providers.map((p) => p.provider).join(',');
  useEffect(() => {
    if (!value && providers.length > 0) {
      onChange(providers[0].provider);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerKey]);

  if (isLoading) {
    return (
      <div
        aria-busy="true"
        aria-live="polite"
        data-testid="provider-picker-skeleton"
        className="flex gap-2"
      >
        <div className="h-8 w-20 rounded-md bg-surface-2 motion-safe:animate-pulse" />
        <div className="h-8 w-20 rounded-md bg-surface-2 motion-safe:animate-pulse" />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="flex items-start gap-2 rounded-md border border-danger bg-danger-soft px-3 py-2.5 text-sm text-danger"
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>Couldn’t load ticketing providers.</span>
      </div>
    );
  }

  if (providers.length === 0) {
    return (
      <EmptyState aria-labelledby="provider-picker-empty-h" className="mx-0 max-w-none p-4 text-left">
        <EmptyState.Title id="provider-picker-empty-h" className="text-sm font-semibold">
          No ticketing provider configured yet
        </EmptyState.Title>
        <EmptyState.Body className="mt-1 text-xs">
          Connect Jira, Asana, or GitHub to create tickets from here.
        </EmptyState.Body>
        <EmptyState.Actions className="mt-3 justify-start">
          <Link
            href="/dashboard/connectors"
            className="text-sm font-medium text-violet hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
          >
            Go to Connectors
          </Link>
        </EmptyState.Actions>
      </EmptyState>
    );
  }

  return (
    <div role="radiogroup" aria-label="Ticketing provider" className="flex flex-wrap gap-2">
      {providers.map(({ provider }) => {
        const selected = provider === value;
        return (
          <button
            key={provider}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(provider)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
              selected
                ? 'border-violet bg-violet-soft text-[var(--color-violet-on-soft)]'
                : 'border-border-subtle bg-surface text-text-muted hover:border-border hover:text-text',
            )}
          >
            <ConnectorMark provider={TO_CONNECTOR_MARK[provider]} />
            {PROVIDER_LABELS[provider]}
          </button>
        );
      })}
    </div>
  );
}
