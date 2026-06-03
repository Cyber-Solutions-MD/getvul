'use client';
/**
 * SamlPane — D-SET-07 provider-first SAML/OIDC pane.
 *
 * Provider picker:
 *   Three options: LOCAL / GOOGLE / AZURE (radio-style buttons).
 *   Bound to local dirty copy of idp_provider via useDirtyState seeded from
 *   useTenantSettings().
 *
 * Enforce SSO toggle:
 *   - DISABLED (with inline explainer) when the local idp_provider is 'LOCAL'
 *     (mirrors backend guard D-SET-07).
 *   - Choosing LOCAL forces sso_enforced=false in local state and shows a
 *     warning ("Switching to local sign-in turns SSO enforcement off.").
 *
 * Saves via shared <SaveBar> → useUpdateTenantSettings({ idp_provider, sso_enforced }).
 * Resets dirty on success.
 *
 * No raw palette utilities (gray-N / indigo-N).
 * data-pane="saml" for test hooks.
 *
 * Plan 14-05.
 */

import { useEffect } from 'react';
import { useTenantSettings, useUpdateTenantSettings } from '@/lib/queries/use-tenant-settings';
import { useDirtyState } from './use-dirty-state';
import { SaveBar } from './save-bar';
import { SkeletonTable } from '@/components/states';
import { PartialFailureBanner } from '@/components/states';
import { queryKeys } from '@/lib/queries/keys';

// ── Types ─────────────────────────────────────────────────────────────────────

type IdpProvider = 'LOCAL' | 'GOOGLE' | 'AZURE';

type SamlFormValues = {
  idp_provider: IdpProvider;
  sso_enforced: boolean;
};

// ── Provider options ──────────────────────────────────────────────────────────

const PROVIDERS: Array<{ id: IdpProvider; label: string; description: string }> = [
  {
    id: 'LOCAL',
    label: 'Local',
    description: 'Email & password only. SSO enforcement is unavailable.',
  },
  {
    id: 'GOOGLE',
    label: 'Google Workspace',
    description: 'SSO via Google. Configure the Google Workspace connector to enable.',
  },
  {
    id: 'AZURE',
    label: 'Azure Entra ID',
    description: 'SSO via Microsoft. Configure the Azure Entra ID connector to enable.',
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export function SamlPane({
  onDirtyChange,
}: {
  /** Reports this pane's dirty state up to the settings page guard (WR-03). */
  onDirtyChange?: (dirty: boolean) => void;
} = {}) {
  const { data: settings, isPending, isError } = useTenantSettings();
  const updateSettings = useUpdateTenantSettings();

  const { values, setField, isDirty, reset } = useDirtyState<SamlFormValues>({
    idp_provider: (settings?.idp_provider as IdpProvider) ?? 'LOCAL',
    sso_enforced: settings?.sso_enforced ?? false,
  });

  // WR-03: report dirty state up instead of relying on DOM polling.
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  // Seed dirty-state from fetched settings
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (settings) {
      reset({
        idp_provider: settings.idp_provider as IdpProvider,
        sso_enforced: settings.sso_enforced,
      });
    }
  // Only re-seed when settings data changes (not when reset changes)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings?.idp_provider, settings?.sso_enforced]);

  // D-SET-07: enforce toggle disabled when idp_provider is LOCAL
  const isLocalProvider = values.idp_provider === 'LOCAL';

  function handleProviderChange(provider: IdpProvider) {
    setField('idp_provider', provider);
    // D-SET-07: setting LOCAL auto-disables sso_enforced
    if (provider === 'LOCAL') {
      setField('sso_enforced', false);
    }
  }

  async function handleSave() {
    await updateSettings.mutateAsync({
      idp_provider: values.idp_provider,
      sso_enforced: values.sso_enforced,
    });
    reset();
  }

  function handleDiscard() {
    if (settings) {
      reset({
        idp_provider: settings.idp_provider as IdpProvider,
        sso_enforced: settings.sso_enforced,
      });
    } else {
      reset();
    }
  }

  return (
    <div data-pane="saml" className="space-y-6 p-6">
      {/* Error banner */}
      {isError && (
        <PartialFailureBanner watchKeys={[queryKeys.settings.tenant()]} />
      )}

      {/* Loading skeleton */}
      {isPending && (
        <SkeletonTable
          rows={3}
          columns={[
            { kind: 'pill', width: 100 },
            { kind: 'text', width: 200 },
          ]}
        />
      )}

      {/* Provider picker */}
      <section className="rounded-lg border border-border-subtle bg-surface p-6">
        <h2 className="mb-1 text-base font-semibold text-text">Identity provider</h2>
        <p className="mb-4 text-sm text-text-muted">
          Choose how users authenticate. SSO requires a configured connector.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {PROVIDERS.map((p) => {
            const isSelected = values.idp_provider === p.id;
            return (
              <button
                key={p.id}
                type="button"
                data-provider={p.id}
                aria-pressed={isSelected}
                onClick={() => handleProviderChange(p.id)}
                className={[
                  'rounded-lg border p-4 text-left transition-colors',
                  isSelected
                    ? 'border-violet bg-violet/10'
                    : 'border-border bg-surface-2 hover:border-border-strong',
                ].join(' ')}
              >
                <p
                  className={`text-sm font-medium ${isSelected ? 'text-violet' : 'text-text'}`}
                >
                  {p.label}
                </p>
                <p className="mt-1 text-xs text-text-muted">{p.description}</p>
                {isSelected && (
                  <p className="mt-2 text-xs text-success">Active</p>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {/* Enforce SSO toggle */}
      <section className="rounded-lg border border-border-subtle bg-surface p-6">
        <h2 className="mb-1 text-base font-semibold text-text">Enforce SSO</h2>
        <p className="mb-4 text-sm text-text-muted">
          When enforced, all users must sign in via the configured identity provider.
        </p>

        {/* Warning when LOCAL was just selected AND the saved setting was non-LOCAL
            (i.e. dirty change to LOCAL from GOOGLE/AZURE) — mirrors D-SET-07 */}
        {isLocalProvider && isDirty && settings?.idp_provider !== 'LOCAL' && (
          <div className="mb-3 rounded-md border border-amber/30 bg-amber/5 px-4 py-3">
            <p className="text-sm text-amber">
              Switching to local sign-in turns SSO enforcement off.
            </p>
          </div>
        )}

        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-4 py-3">
          <div>
            <p className="text-sm font-medium text-text">Enforce SSO</p>
            {isLocalProvider ? (
              <p className="text-xs text-text-muted">
                Set a non-local identity provider before enforcing SSO.
              </p>
            ) : (
              <p className="text-xs text-text-muted">
                Users will be redirected to{' '}
                {values.idp_provider === 'GOOGLE' ? 'Google' : 'Microsoft'} for
                sign-in.
              </p>
            )}
          </div>
          {/* Toggle — disabled for LOCAL provider */}
          <button
            type="button"
            role="switch"
            aria-checked={values.sso_enforced}
            aria-label="Enforce SSO"
            data-field="sso_enforced"
            disabled={isLocalProvider}
            onClick={() => {
              if (!isLocalProvider) {
                setField('sso_enforced', !values.sso_enforced);
              }
            }}
            className={[
              'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors',
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
              'disabled:cursor-not-allowed disabled:opacity-40',
              values.sso_enforced && !isLocalProvider
                ? 'bg-violet'
                : 'bg-surface-2 border border-border',
            ].join(' ')}
          >
            <span
              className={[
                'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
                values.sso_enforced && !isLocalProvider
                  ? 'translate-x-6'
                  : 'translate-x-1',
              ].join(' ')}
            />
          </button>
        </div>
      </section>

      {/* Per-category SaveBar — shared dirty-state */}
      <SaveBar
        isDirty={isDirty}
        isSaving={updateSettings.isPending}
        onSave={handleSave}
        onDiscard={handleDiscard}
      />
    </div>
  );
}
