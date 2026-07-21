'use client';
/**
 * TestStep — wizard step 3 (Test).
 *
 * Explicit "Test connection" button only (D-06) — NEVER auto-fires on step
 * entry. Reuses `useTestConnector` + the connector-form.tsx inline result
 * block structure, with the success color corrected to `--color-success`
 * green per UI-SPEC §Color reconciliation (source lavender stays a
 * DESIGN-SYSTEM GAP, fixed separately in Plan 19-02).
 *
 * This step renders ONLY the raw test result. Gating (Next disable) and the
 * stale/gate hints live in the wizard footer (19-03) — not duplicated here.
 */
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTestConnector } from '@/lib/queries/use-connectors-admin';
import { WIZARD_COPY } from '../microcopy';

export type TestStepProps = {
  connectorType: string;
  buildCredentials: () => Record<string, string> | undefined;
  testResult: { success: boolean; message: string } | null;
  onResult: (r: { success: boolean; message: string }) => void;
  headingRef?: React.Ref<HTMLHeadingElement>;
  headingId?: string;
};

export function TestStep({
  connectorType,
  buildCredentials,
  testResult,
  onResult,
  headingRef,
  headingId,
}: TestStepProps) {
  const testMutation = useTestConnector();

  function handleTest() {
    testMutation.mutate(
      {
        connector_type: connectorType.toUpperCase(),
        credentials: buildCredentials() ?? {},
      },
      {
        onSuccess: (data) => onResult(data),
        onError: (err) => onResult({ success: false, message: err.message }),
      },
    );
  }

  return (
    <section aria-labelledby={headingId}>
      <h3
        ref={headingRef}
        tabIndex={-1}
        id={headingId}
        className="mb-4 text-base font-semibold text-text"
      >
        Test
      </h3>

      <div className="flex flex-col gap-4">
        <button
          type="button"
          onClick={handleTest}
          disabled={testMutation.isPending}
          className={cn(
            'inline-flex min-h-[44px] items-center gap-2 self-start rounded-md border border-border-subtle px-4 py-2 text-sm text-text-muted',
            'hover:border-border hover:text-text transition-colors',
            'focus-visible:outline-2 focus-visible:outline-violet',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {testMutation.isPending && (
            <Loader2 size={14} className="motion-safe:animate-spin" aria-hidden="true" />
          )}
          {testMutation.isPending ? WIZARD_COPY.testingLabel : WIZARD_COPY.testLabel}
        </button>

        {testResult?.success === true && (
          <div
            role="status"
            aria-live="polite"
            className={cn(
              'flex items-start gap-2 rounded-md border p-3 text-sm',
              'border-[var(--color-success)]/30 bg-[var(--color-success)]/10 text-[var(--color-success)]',
            )}
          >
            <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{'✓ ' + testResult.message}</span>
          </div>
        )}

        {testResult && !testResult.success && (
          <div
            role="alert"
            className={cn(
              'flex items-start gap-2 rounded-md border p-3 text-sm',
              'border-severity-critical/30 bg-severity-critical/10 text-[var(--color-severity-critical-on-soft)]',
            )}
          >
            <XCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{'✗ ' + testResult.message}</span>
          </div>
        )}
      </div>
    </section>
  );
}
