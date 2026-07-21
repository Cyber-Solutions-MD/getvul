'use client';
/**
 * ConnectorForm — add/edit/test connector form with sentinel passthrough.
 *
 * ADD mode: empty credential fields. Submit → useCreateConnector({ connector_type, credentials, sync_interval_minutes }).
 *
 * EDIT mode (D-CONN-04 / Pitfall 5):
 *   - Pre-fills every credential field with the sentinel "••••••" (6 bullets).
 *   - Tracks per-field `touched` state. On submit, builds `credentials` from ONLY
 *     touched fields. If NO field is touched, OMITS the `credentials` key entirely
 *     from the PATCH body (backend keeps stored secret).
 *   - NEVER sends the literal "••••••" sentinel to the backend.
 *
 * Eye/EyeOff per field toggles input type text/password (default password).
 * "Test connection" → useTestConnector; renders result inline.
 * All sunset tokens; no raw gray-N or indigo-N.
 *
 * T-14-06: Backend never returns credential values — has_credentials boolean only.
 *   Pre-fill is the sentinel "••••••", not actual secret data.
 * T-14-07: Only OMIT credentials key when unchanged; never send "••••••" to backend.
 * T-14-09: connectorType is uppercased before sending to API — no reflected string reaches API path.
 */
import { useState, useCallback } from 'react';
import { Eye, EyeOff, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import {
  useCreateConnector,
  useUpdateConnector,
  useTestConnector,
} from '@/lib/queries/use-connectors-admin';
import type { ConnectorConfigResponse } from '@/lib/queries/use-connectors-admin';
import { cn } from '@/lib/utils';
import { FORM_COPY } from './microcopy';

// The sentinel displayed in edit-mode credential fields.
// NEVER sent to the backend — purely a UI hint that a stored credential exists.
const SENTINEL = FORM_COPY.credentialSentinel; // "••••••"

function isSecretField(fieldName: string): boolean {
  return (
    fieldName.includes('secret') ||
    fieldName.includes('key') ||
    fieldName.includes('password') ||
    fieldName.includes('token')
  );
}

function fieldLabel(fieldName: string): string {
  return fieldName
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const SYNC_INTERVALS = [5, 15, 30, 60] as const;

export type ConnectorFormProps = {
  mode: 'add' | 'edit';
  connectorType: string;
  /** Required in edit mode */
  existing?: ConnectorConfigResponse;
  /** Credential + config field names from /connectors/types `fields[]` */
  fields: string[];
  onClose: () => void;
};

export function ConnectorForm({
  mode,
  connectorType,
  existing,
  fields,
  onClose,
}: ConnectorFormProps) {
  const createMutation = useCreateConnector();
  const updateMutation = useUpdateConnector();
  const testMutation = useTestConnector();

  // In add mode: start with empty values.
  // In edit mode: pre-fill with sentinel "••••••" per D-CONN-04.
  const initialValues = useCallback(() => {
    const init: Record<string, string> = {};
    for (const f of fields) {
      init[f] = mode === 'edit' ? SENTINEL : '';
    }
    return init;
  }, [fields, mode]);

  const [values, setValues] = useState<Record<string, string>>(initialValues);
  // Track which fields the user has modified (T-14-07: only submit touched fields).
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  // Per-field Eye/EyeOff visibility state.
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  // Sync interval (minutes).
  const [syncInterval, setSyncInterval] = useState(existing?.sync_interval_minutes ?? 15);
  // Inline test result.
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  function handleFieldChange(fieldName: string, value: string) {
    setValues((prev) => ({ ...prev, [fieldName]: value }));
    setTouched((prev) => ({ ...prev, [fieldName]: true }));
  }

  function toggleReveal(fieldName: string) {
    setRevealed((prev) => ({ ...prev, [fieldName]: !prev[fieldName] }));
  }

  /**
   * Build the credentials body for submission.
   * ADD: include all non-empty fields.
   * EDIT: include ONLY touched fields (excluding sentinel value).
   *       If no fields were touched, OMIT credentials from PATCH entirely.
   */
  function buildCredentials(): Record<string, string> | undefined {
    if (mode === 'add') {
      const creds: Record<string, string> = {};
      for (const f of fields) {
        if (values[f] && values[f].trim() !== '') {
          creds[f] = values[f];
        }
      }
      return Object.keys(creds).length > 0 ? creds : undefined;
    }

    // Edit mode: only touched fields, never the sentinel literal.
    const touchedFields = Object.keys(touched).filter((f) => touched[f]);
    if (touchedFields.length === 0) return undefined; // omit credentials key

    const creds: Record<string, string> = {};
    for (const f of touchedFields) {
      const v = values[f];
      // Safety guard: never send the sentinel literal to the backend (T-14-07).
      if (v && v !== SENTINEL && v.trim() !== '') {
        creds[f] = v;
      }
    }
    return Object.keys(creds).length > 0 ? creds : undefined;
  }

  async function handleSave() {
    setFormError(null);
    const credentials = buildCredentials();

    if (mode === 'add') {
      createMutation.mutate(
        {
          connector_type: connectorType.toUpperCase(),
          credentials: credentials ?? {},
          sync_interval_minutes: syncInterval,
        },
        {
          onSuccess: () => onClose(),
          onError: (err) => setFormError(err.message),
        },
      );
    } else {
      if (!existing) return;
      const body: {
        credentials?: Record<string, string>;
        sync_interval_minutes: number;
      } = { sync_interval_minutes: syncInterval };

      // Only include credentials if at least one field was touched (T-14-07).
      if (credentials !== undefined) {
        body.credentials = credentials;
      }

      updateMutation.mutate(
        { id: existing.id, body },
        {
          onSuccess: () => onClose(),
          onError: (err) => setFormError(err.message),
        },
      );
    }
  }

  function handleTest() {
    setTestResult(null);
    const currentCreds = buildCredentials();
    testMutation.mutate(
      {
        connector_type: connectorType.toUpperCase(),
        credentials: currentCreds ?? {},
      },
      {
        onSuccess: (data) => setTestResult(data),
        onError: (err) => setTestResult({ success: false, message: err.message }),
      },
    );
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div
      data-connector-form
      data-mode={mode}
      className="flex flex-col gap-4"
    >
      {/* Credential fields */}
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
                  value={values[field] ?? ''}
                  onChange={(e) => handleFieldChange(field, e.target.value)}
                  placeholder={
                    mode === 'edit' ? 'Leave unchanged to keep stored value' : 'Paste API token'
                  }
                  className={cn(
                    'w-full rounded-md border border-border-subtle bg-surface-2 px-3 py-2.5 text-sm text-text',
                    'placeholder:text-text-faint',
                    'focus:border-violet focus:outline-none focus:ring-2 focus:ring-violet/30',
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
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-faint hover:text-text-muted"
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
                onClick={() => setSyncInterval(m)}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
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

      {/* Test connection result */}
      {testResult && (
        <div
          className={cn(
            'flex items-start gap-2 rounded-md border p-3 text-sm',
            testResult.success
              ? // reconciled lavender→green success token (Phase 19, UI-SPEC §Color / RESEARCH Pitfall 2)
                'border-[var(--color-success)]/30 bg-[var(--color-success)]/10 text-[var(--color-success)]'
              : 'border-severity-critical/30 bg-severity-critical/10 text-[var(--color-severity-critical-on-soft)]',
          )}
        >
          {testResult.success ? (
            <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
          ) : (
            <XCircle size={16} className="mt-0.5 shrink-0" />
          )}
          <span>{testResult.message}</span>
        </div>
      )}

      {/* Form-level error */}
      {formError && (
        <div className="rounded-md border border-severity-critical/30 bg-severity-critical/10 p-3 text-sm text-[var(--color-severity-critical-on-soft)]">
          {formError}
        </div>
      )}

      {/* Action row */}
      <div className="flex items-center justify-between pt-2">
        {/* Test connection (secondary) */}
        <button
          type="button"
          onClick={handleTest}
          disabled={testMutation.isPending}
          className={cn(
            'inline-flex items-center gap-2 rounded-md border border-border-subtle px-4 py-2 text-sm text-text-muted',
            'hover:border-border hover:text-text transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {testMutation.isPending && <Loader2 size={14} className="animate-spin" />}
          {FORM_COPY.testLabel}
        </button>

        <div className="flex items-center gap-3">
          {/* Cancel */}
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm text-text-muted hover:text-text transition-colors"
          >
            {FORM_COPY.cancelLabel}
          </button>

          {/* Save connector (primary gradient CTA) */}
          <button
            type="button"
            onClick={handleSave}
            disabled={isPending}
            style={{ background: 'var(--gradient-sunset)' }}
            className={cn(
              'inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-[var(--glow-cta)]',
              'hover:-translate-y-px transition-all',
              'disabled:cursor-not-allowed disabled:opacity-50',
            )}
          >
            {isPending && <Loader2 size={14} className="animate-spin" />}
            {FORM_COPY.saveLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
