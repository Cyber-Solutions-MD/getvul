'use client';
/**
 * ConfirmStep — wizard step 4, the "here's what you're granting" review screen.
 *
 * Renders provider name, the connection-test ✓ result, the connector type's
 * required permissions[] (scope + purpose, D-10), and the selected sync interval,
 * then submits POST /connectors via useCreateConnector on the single gradient
 * "Add connector" CTA (D-09). Reuses the buildCredentials() add-path output and
 * the gradient-CTA / error-block markup from connector-form.tsx verbatim
 * (connector-form.tsx lines 292-297, 326-340).
 *
 * T-19-02: only permissions[] (scope/access/purpose) and the sync interval are
 * rendered here — credential VALUES are passed to `mutate` but never rendered
 * in the review DOM.
 */
import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useCreateConnector } from '@/lib/queries/use-connectors-admin';
import type { ConnectorTypePermission } from '@/lib/queries/use-connectors-admin';
import { cn } from '@/lib/utils';
import { WIZARD_COPY } from '../microcopy';

export type ConfirmStepProps = {
  providerName: string;
  connectorType: string;
  permissions: ConnectorTypePermission[];
  syncInterval: number;
  credentials: Record<string, string> | undefined;
  /** 24-01: config-destined field values (model, monthly_budget_usd, ...) —
   * plaintext, round-trips into ConnectorConfig.config (D-06). */
  config?: Record<string, unknown>;
  onSuccess: () => void;
  headingRef?: React.Ref<HTMLHeadingElement>;
  headingId?: string;
};

function formatSyncInterval(minutes: number): string {
  return minutes === 60 ? '1 hr' : `${minutes} min`;
}

export function ConfirmStep({
  providerName,
  connectorType,
  permissions,
  syncInterval,
  credentials,
  config,
  onSuccess,
  headingRef,
  headingId,
}: ConfirmStepProps) {
  const createMutation = useCreateConnector();
  const [formError, setFormError] = useState<string | null>(null);

  function handleAddConnector() {
    setFormError(null);
    createMutation.mutate(
      {
        connector_type: connectorType.toUpperCase(),
        credentials: credentials ?? {},
        config,
        sync_interval_minutes: syncInterval,
      },
      {
        onSuccess: () => onSuccess(),
        onError: (err) => setFormError(err.message),
      },
    );
  }

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-6">
      <h3
        ref={headingRef}
        tabIndex={-1}
        id={headingId}
        className="text-base font-semibold text-text focus:outline-none"
      >
        Confirm
      </h3>

      <div className="flex flex-col gap-3">
        {/* Provider */}
        <div className="rounded-md border border-border-subtle bg-surface-2 p-3">
          <div className="text-xs font-medium text-text-muted">
            {WIZARD_COPY.confirmSectionProvider}
          </div>
          <div className="mt-1 text-sm text-text">{providerName}</div>
        </div>

        {/* Connection */}
        <div className="rounded-md border border-border-subtle bg-surface-2 p-3">
          <div className="text-xs font-medium text-text-muted">
            {WIZARD_COPY.confirmSectionConnection}
          </div>
          <div
            role="status"
            aria-live="polite"
            className="mt-1 text-sm text-[var(--color-success)]"
          >
            {WIZARD_COPY.confirmConnectionOk}
          </div>
        </div>

        {/* Required access */}
        <div className="rounded-md border border-border-subtle bg-surface-2 p-3">
          <div className="text-xs font-medium text-text-muted">
            {WIZARD_COPY.confirmSectionAccess}
          </div>
          {permissions.length === 0 ? (
            <div className="mt-1 text-sm text-text">{WIZARD_COPY.noScopes}</div>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {permissions.map((perm) => (
                <li key={`${perm.scope}-${perm.access}`} className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-text">{perm.scope}</span>
                    <span className="rounded-full border border-border-subtle px-2 py-0.5 text-xs text-text-muted">
                      {perm.access}
                    </span>
                  </div>
                  <span className="text-xs text-text-muted">{perm.purpose}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Sync interval */}
        <div className="rounded-md border border-border-subtle bg-surface-2 p-3">
          <div className="text-xs font-medium text-text-muted">
            {WIZARD_COPY.confirmSectionSync}
          </div>
          <div className="mt-1 font-mono text-sm text-text">
            {formatSyncInterval(syncInterval)}
          </div>
        </div>
      </div>

      {/* Submit-level error (POST /connectors fails) — reuse red block markup verbatim */}
      {formError && (
        <div
          role="alert"
          className="rounded-md border border-severity-critical/30 bg-severity-critical/10 p-3 text-sm text-[var(--color-severity-critical-on-soft)]"
        >
          {formError}
        </div>
      )}

      {/* Primary CTA — the ONLY gradient element on this screen (accent reserved) */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={handleAddConnector}
          disabled={createMutation.isPending}
          style={{ background: 'var(--gradient-sunset)' }}
          className={cn(
            'inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-[var(--glow-cta)]',
            'hover:-translate-y-px transition-all',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {createMutation.isPending && (
            <Loader2 size={14} className="motion-safe:animate-spin" />
          )}
          {WIZARD_COPY.addLabel}
        </button>
      </div>
    </section>
  );
}
