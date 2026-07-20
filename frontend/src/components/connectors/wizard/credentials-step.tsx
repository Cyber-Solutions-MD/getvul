'use client';
/**
 * CredentialsStep — wizard step 2 (Credentials).
 *
 * Renders one input per field (lifted verbatim from connector-form.tsx's
 * add-mode field markup) + the sync-interval chip selector. Delegates all
 * state to the parent's `useWizardState` hook via props — this component
 * owns only the local per-field Eye/EyeOff reveal toggle (visual-only state).
 *
 * T-19-02: add mode starts empty and never renders the "••••••" sentinel;
 * onFieldChange forwards straight to the parent's updateField (D-08 owns the
 * re-test invalidation), so the sentinel literal can never enter this tree.
 */
import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import { FORM_COPY } from '../microcopy';

// PLANNER DECISION (19-00): fields stays string[] (wire contract); detect
// secret fields with the existing name heuristic, same as connector-form.tsx.
function isSecretField(fieldName: string): boolean {
  return (
    fieldName.includes('secret') ||
    fieldName.includes('key') ||
    fieldName.includes('password') ||
    fieldName.includes('token')
  );
}

function fieldLabel(fieldName: string): string {
  return fieldName.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

const SYNC_INTERVALS = [5, 15, 30, 60] as const;

export type CredentialsStepProps = {
  fields: string[];
  values: Record<string, string>;
  onFieldChange: (name: string, value: string) => void;
  syncInterval: number;
  onSyncIntervalChange: (m: number) => void;
  headingRef?: React.Ref<HTMLHeadingElement>;
  headingId?: string;
};

export function CredentialsStep({
  fields,
  values,
  onFieldChange,
  syncInterval,
  onSyncIntervalChange,
  headingRef,
  headingId,
}: CredentialsStepProps) {
  // Per-field Eye/EyeOff visibility state — visual only, never persisted.
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});

  function toggleReveal(fieldName: string) {
    setRevealed((prev) => ({ ...prev, [fieldName]: !prev[fieldName] }));
  }

  return (
    <section aria-labelledby={headingId}>
      <h3
        ref={headingRef}
        tabIndex={-1}
        id={headingId}
        className="mb-4 text-base font-semibold text-text"
      >
        Connector credentials
      </h3>

      <div className="space-y-4">
        {fields.map((field) => {
          const isSecret = isSecretField(field);
          const isRevealed = !!revealed[field];
          const inputType = isSecret && !isRevealed ? 'password' : 'text';

          return (
            <div key={field}>
              <label
                htmlFor={`field-${field}`}
                className="mb-1.5 block text-sm font-medium text-text-muted"
              >
                {fieldLabel(field)}
              </label>
              <div className="relative">
                <input
                  id={`field-${field}`}
                  name={field}
                  type={inputType}
                  // WR-02: every connector field is mandatory (all-non-empty
                  // gate); signal that to assistive tech.
                  aria-required="true"
                  value={values[field] ?? ''}
                  onChange={(e) => onFieldChange(field, e.target.value)}
                  placeholder="Paste API token"
                  className={cn(
                    'w-full rounded-md border border-border-subtle bg-surface-2 px-3 py-2.5 text-sm text-text',
                    'placeholder:text-text-faint',
                    'focus:border-violet focus:outline-none focus:ring-2 focus:ring-violet/30',
                    'min-h-[44px] max-[767px]:min-h-[44px]',
                    isSecret && 'pr-10',
                  )}
                />
                {isSecret && (
                  <button
                    type="button"
                    data-eye-toggle
                    data-field={field}
                    aria-label={isRevealed ? `Hide ${fieldLabel(field)}` : `Show ${fieldLabel(field)}`}
                    onClick={() => toggleReveal(field)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-faint hover:text-text-muted focus-visible:outline-2 focus-visible:outline-violet"
                  >
                    {isRevealed ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                )}
              </div>
            </div>
          );
        })}

        {/* Sync interval */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-text-muted">
            {FORM_COPY.syncIntervalLabel}
          </label>
          <div className="flex flex-wrap gap-2">
            {SYNC_INTERVALS.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => onSyncIntervalChange(m)}
                className={cn(
                  'min-h-[44px] rounded-md border px-3 py-1.5 text-xs font-medium transition-colors max-[767px]:min-h-[44px]',
                  syncInterval === m
                    ? 'border-violet/60 bg-violet/10 text-[var(--color-violet-on-soft)]'
                    : 'border-border-subtle bg-surface text-text-muted hover:border-border hover:text-text',
                )}
              >
                {m === 60 ? '1 hr' : `${m} min`}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
