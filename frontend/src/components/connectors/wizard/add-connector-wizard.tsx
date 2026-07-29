'use client';
/**
 * AddConnectorWizard — the wizard container (19-03, integration wave).
 *
 * Owns `useWizardState` and renders the `WizardStepper` + exactly one step
 * `<section>` at a time (Credentials → Test → Confirm), plus the gated
 * Back/Next footer. Step 1 "Provider" lives on the page grid (D-01) —
 * `connectorType`/`providerName` arrive already picked.
 *
 * `fields`/`permissions` are optional props: page.tsx (19-03 Task 3) already
 * has this data via its own `useConnectorTypes()` call and can pass it
 * straight through, but this component also calls `useConnectorTypes()`
 * itself and derives both from the matching connector type when the caller
 * doesn't supply them (this is exactly what the Wave-0 RED scaffolds
 * (`add-connector-wizard.test.tsx` / `.a11y.test.tsx`) exercise — they only
 * pass `connectorType`/`providerName`/`onClose`). This keeps the component
 * usable standalone while still allowing the parent to skip a second lookup.
 *
 * Hooks used in this subtree, and ONLY these three (T-19-01 scope guard):
 * `useConnectorTypes` (here), `useTestConnector` (TestStep), `useCreateConnector`
 * (ConfirmStep) — no new hook introduced.
 */
import { useEffect, useId, useRef } from 'react';
import { cn } from '@/lib/utils';
import { useConnectorTypes } from '@/lib/queries/use-connectors-admin';
import type { ConnectorTypePermission, ConnectorFieldSpec } from '@/lib/queries/use-connectors-admin';
import { useWizardState } from './use-wizard-state';
import { WizardStepper } from './wizard-stepper';
import { CredentialsStep } from './credentials-step';
import { TestStep } from './test-step';
import { ConfirmStep } from './confirm-step';
import { WIZARD_COPY } from '../microcopy';

export type AddConnectorWizardProps = {
  connectorType: string;
  providerName: string;
  /** Optional — derived from `useConnectorTypes()` when omitted. */
  fields?: string[];
  /** Optional — derived from `useConnectorTypes()` when omitted. */
  permissions?: ConnectorTypePermission[];
  onClose: () => void;
};

const NAV_BUTTON_BASE =
  'inline-flex min-h-[44px] items-center gap-2 rounded-md px-4 py-2 text-sm transition-colors max-[767px]:min-h-[44px] focus-visible:outline-2 focus-visible:outline-violet';

export function AddConnectorWizard({
  connectorType,
  providerName,
  fields: fieldsProp,
  permissions: permissionsProp,
  onClose,
}: AddConnectorWizardProps) {
  // Used directly by this container (not "transitively via a step") to derive
  // fields/permissions when the caller doesn't pass them — see file header.
  const typesQuery = useConnectorTypes();
  const typeInfo = typesQuery.data?.find((t) => t.type === connectorType);
  const fields = fieldsProp ?? typeInfo?.fields ?? [];
  const permissions = permissionsProp ?? typeInfo?.permissions ?? [];
  // 24-01: richer per-field metadata (select options, required, config vs
  // credentials routing) — always sourced from this component's OWN
  // useConnectorTypes() call (fieldsProp only ever carries plain names, page.tsx
  // has no separate prop for this), defaulting to {} (all-required,
  // all-credentials — today's behavior) while the query is still loading.
  const fieldSpecs: Record<string, ConnectorFieldSpec> = typeInfo?.field_specs ?? {};

  const w = useWizardState(fields, fieldSpecs);

  const credentialsHeadingId = useId();
  const testHeadingId = useId();
  const confirmHeadingId = useId();
  const hintId = useId();

  // Focus management (UX-D-02-06 / RESEARCH Pattern 3): move focus to the new
  // step's <h3> on every step change, on BOTH desktop and mobile — unlike the
  // ConfirmModal focus-to-ref precedent, which skips the move on narrow
  // viewports (its content is static; vaul only grabs focus once at Drawer
  // open, but this wizard's content changes underneath an already-open sheet,
  // so the move must run on every viewport too).
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, [w.state.step]);

  // Hint live region (UX-D-02-02 announce-why / D-08 re-test invalidation).
  // On the credentials step the gate is "fill every field"; past it,
  // retestHint takes priority (D-08) and testGateHint applies on the test
  // step before any test has run. WR-02: without the credentials branch the
  // aria-describedby target resolved to an empty paragraph, so a screen-reader
  // user on a dimmed step-2 Next heard no reason the gate was closed.
  let hintText = '';
  if (w.state.step === 'credentials') {
    if (!w.canAdvance) {
      hintText = WIZARD_COPY.credentialsGateHint;
    }
  } else if (w.isTestStale) {
    hintText = WIZARD_COPY.retestHint;
  } else if (w.state.step === 'test' && w.state.testResult === null && !w.canAdvance) {
    hintText = WIZARD_COPY.testGateHint;
  }

  function handleNextClick() {
    // T-19-01: aria-disabled alone is not enforcement — this click guard is
    // the real gate. On the test step canAdvance === testPassed (success AND
    // not stale), enforcing D-05/D-08.
    if (!w.canAdvance) return;
    w.advance();
  }

  return (
    <div>
      <WizardStepper currentStep={w.state.step} />

      <div className="mt-6">
        {w.state.step === 'credentials' && (
          <CredentialsStep
            fields={fields}
            values={w.state.values}
            onFieldChange={w.updateField}
            syncInterval={w.state.syncInterval}
            onSyncIntervalChange={w.setSyncInterval}
            headingRef={headingRef}
            headingId={credentialsHeadingId}
            fieldSpecs={fieldSpecs}
          />
        )}
        {w.state.step === 'test' && (
          <TestStep
            connectorType={connectorType}
            buildCredentials={w.buildCredentials}
            buildConfig={w.buildConfig}
            testResult={w.state.testResult}
            onResult={w.setTestResult}
            headingRef={headingRef}
            headingId={testHeadingId}
          />
        )}
        {w.state.step === 'confirm' && (
          <ConfirmStep
            providerName={providerName}
            connectorType={connectorType}
            permissions={permissions}
            syncInterval={w.state.syncInterval}
            credentials={w.buildCredentials()}
            config={w.buildConfig()}
            onSuccess={onClose}
            headingRef={headingRef}
            headingId={confirmHeadingId}
          />
        )}
      </div>

      <p id={hintId} aria-live="polite" className="mt-2 min-h-[1em] text-xs text-text-muted">
        {hintText}
      </p>

      {/* Footer — sticky at the bottom of the vaul sheet on mobile so it stays
          reachable while credential fields scroll (UI-SPEC Responsive). */}
      <div className="flex items-center justify-between pt-8 max-[767px]:sticky max-[767px]:bottom-0 max-[767px]:bg-surface max-[767px]:pb-2">
        {w.state.step === 'credentials' ? (
          <button
            type="button"
            onClick={onClose}
            className={cn(
              NAV_BUTTON_BASE,
              'border border-border-subtle text-text-muted hover:border-border hover:text-text',
            )}
          >
            {WIZARD_COPY.cancelLabel}
          </button>
        ) : (
          <button
            type="button"
            onClick={w.back}
            className={cn(
              NAV_BUTTON_BASE,
              'border border-border-subtle text-text-muted hover:border-border hover:text-text',
            )}
          >
            {WIZARD_COPY.backLabel}
          </button>
        )}

        {/* The step-4 "Add connector" CTA lives INSIDE ConfirmStep — no
            right-hand button is rendered here on the confirm step. */}
        {w.state.step !== 'confirm' && (
          <button
            type="button"
            aria-disabled={!w.canAdvance}
            aria-describedby={hintId}
            onClick={handleNextClick}
            style={w.canAdvance ? { background: 'var(--gradient-sunset)' } : undefined}
            className={cn(
              NAV_BUTTON_BASE,
              'font-semibold text-white shadow-[var(--glow-cta)]',
              w.canAdvance
                ? 'hover:-translate-y-px transition-all'
                : 'cursor-not-allowed border border-border-subtle !bg-none !text-text-faint opacity-50',
            )}
          >
            {WIZARD_COPY.nextLabel}
          </button>
        )}
      </div>
    </div>
  );
}
