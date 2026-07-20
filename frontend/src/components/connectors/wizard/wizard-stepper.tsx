// NET-NEW pattern: no design-system stepper exists (interaction-patterns.md).
// Built from foundation.md tokens; promote to shared primitive only if a 2nd
// wizard appears (CONTEXT deferred).
import { CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { WIZARD_COPY } from '../microcopy';
import type { WizardStep } from './use-wizard-state';

type StepStatus = 'complete' | 'current' | 'upcoming';

// Interactive steps hosted inside the dialog (Provider — index 0 — lives on
// the page grid and is always rendered complete, D-01/D-03).
const INTERACTIVE_STEPS: WizardStep[] = ['credentials', 'test', 'confirm'];

export function WizardStepper({ currentStep }: { currentStep: WizardStep }) {
  const currentIndex = INTERACTIVE_STEPS.indexOf(currentStep);
  const labels = WIZARD_COPY.stepLabels;

  return (
    <nav aria-label="Wizard progress">
      <ol className="flex items-center gap-6 max-[767px]:gap-4">
        {labels.map((label, i) => {
          // i === 0 is "Provider" — always complete (grid already picked it).
          // i === 1..3 map to INTERACTIVE_STEPS[i - 1].
          let status: StepStatus;
          if (i === 0) {
            status = 'complete';
          } else {
            const stepIdx = i - 1;
            if (stepIdx < currentIndex) status = 'complete';
            else if (stepIdx === currentIndex) status = 'current';
            else status = 'upcoming';
          }

          const isLast = i === labels.length - 1;

          const stepContent = (
            <>
              <span className="flex items-center gap-2">
                <span
                  className={cn(
                    'flex h-6 w-6 shrink-0 items-center justify-center rounded-full max-[767px]:h-5 max-[767px]:w-5',
                    'motion-safe:transition-colors motion-safe:duration-[120ms]',
                    status === 'complete' && 'bg-[var(--color-success)]',
                    status === 'upcoming' && 'border border-border-subtle bg-transparent',
                  )}
                  style={
                    status === 'current' ? { background: 'var(--gradient-sunset)' } : undefined
                  }
                >
                  {status === 'complete' ? (
                    <>
                      <CheckCircle2 size={14} className="text-text-inverse" aria-hidden="true" />
                      <span className="sr-only"> (completed)</span>
                    </>
                  ) : (
                    <span
                      className={cn(
                        'text-xs',
                        status === 'current' && 'font-semibold text-white',
                        status === 'upcoming' && 'text-text-faint',
                      )}
                      aria-hidden="true"
                    >
                      {i + 1}
                    </span>
                  )}
                </span>
                <span
                  className={cn(
                    'text-xs font-medium',
                    status === 'complete' && 'text-text-muted',
                    status === 'current' && 'font-semibold text-text',
                    status === 'upcoming' && 'text-text-faint',
                  )}
                >
                  {label}
                </span>
              </span>
              {!isLast && (
                <span
                  aria-hidden="true"
                  className={cn(
                    'h-px w-6 max-[767px]:w-4',
                    status === 'complete' ? 'bg-[var(--color-success)]/40' : 'bg-border-subtle',
                  )}
                />
              )}
            </>
          );

          // aria-current="step" is the documented value for a non-interactive
          // progress indicator (distinct from "page"/"location"/"date"/"time").
          // Rendered as a literal attribute (not a spread) only on the current
          // step's <li> — the other two states carry no aria-current at all.
          return status === 'current' ? (
            <li key={label} aria-current="step" className="flex items-center gap-2">
              {stepContent}
            </li>
          ) : (
            <li key={label} className="flex items-center gap-2">
              {stepContent}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
