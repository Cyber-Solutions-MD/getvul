'use client';
/**
 * NotificationsPane — D-SET-08 three sub-sections in ONE scrollable pane.
 *
 * No nested tabs. Three section cards (per D-SET-08):
 *   Card 1 — Email / SMTP: host/port/username/password/from_email/tls/enabled
 *   Card 2 — Syslog forwarding: enabled/host/port/protocol/facility
 *   Card 3 — Alert categories: coming-soon EmptyState (no backend field exists)
 *
 * SMTP password handling (CR-01 / T-14-17):
 *   The backend never returns the real secret (it masks the stored value). We
 *   therefore seed the password field EMPTY and track an explicit
 *   `passwordTouched` flag. The password is included in the PATCH body ONLY
 *   when the user actually edited the field — otherwise it is omitted entirely
 *   so the backend keeps the stored value. This mirrors the connector form's
 *   per-field `touched` tracking and guarantees a displayed mask (of any
 *   length/shape) can never be round-tripped back as the real password.
 *
 * All three sections commit via ONE shared <SaveBar> (single dirty-state
 * across the pane) → useUpdateTenantSettings({ smtp_config, syslog_config }).
 *
 * No raw palette utilities (gray-N / indigo-N). No tab patterns in markup.
 * data-pane="notifications" for test hooks.
 *
 * Plan 14-05.
 */

import { useEffect } from 'react';
import { useTenantSettings, useUpdateTenantSettings } from '@/lib/queries/use-tenant-settings';
import { useDirtyState } from './use-dirty-state';
import { SaveBar } from './save-bar';
import { SkeletonTable } from '@/components/states';
import { PartialFailureBanner } from '@/components/states';
import { EmptyState } from '@/components/states';
import { queryKeys } from '@/lib/queries/keys';

// ── Types ─────────────────────────────────────────────────────────────────────

type SmtpFormValues = {
  enabled: boolean;
  host: string;
  port: string;
  username: string;
  /**
   * Always seeded EMPTY — never the mask. The stored secret is opaque to the
   * client; an empty field means "keep stored value" (see passwordTouched).
   */
  password: string;
  /**
   * True once the user edits the password field. Only when this is true is
   * `password` ever included in the PATCH body. This mirrors the connector
   * form's per-field `touched` tracking and guarantees a displayed mask can
   * never be persisted as the real secret (CR-01 / T-14-17).
   */
  passwordTouched: boolean;
  from_email: string;
  tls: boolean;
};

type SyslogFormValues = {
  enabled: boolean;
  host: string;
  port: string;
  protocol: 'udp' | 'tcp';
  facility: string;
};

type NotifFormValues = {
  smtp: SmtpFormValues;
  syslog: SyslogFormValues;
};

// Placeholder shown in the (empty) password field when a stored secret exists.
// Purely a UI hint — NEVER the field value, NEVER sent to the backend (CR-01).
const SMTP_PASSWORD_PLACEHOLDER = '••••••••';

function defaultSmtp(cfg: Record<string, unknown> | null): SmtpFormValues {
  if (!cfg) {
    return {
      enabled: false,
      host: '',
      port: '587',
      username: '',
      password: '',
      passwordTouched: false,
      from_email: '',
      tls: false,
    };
  }
  return {
    enabled: Boolean(cfg.enabled),
    host: String(cfg.host ?? ''),
    port: String(cfg.port ?? '587'),
    username: String(cfg.username ?? ''),
    // Seed EMPTY — the backend never returns the real secret and we must never
    // round-trip a mask back as the password (CR-01 / T-14-17). An empty field
    // with passwordTouched=false means "keep the stored value".
    password: '',
    passwordTouched: false,
    from_email: String(cfg.from_email ?? ''),
    tls: Boolean(cfg.tls || cfg.use_tls),
  };
}

function defaultSyslog(cfg: Record<string, unknown> | null): SyslogFormValues {
  if (!cfg) {
    return { enabled: false, host: '', port: '514', protocol: 'udp', facility: 'local0' };
  }
  return {
    enabled: Boolean(cfg.enabled),
    host: String(cfg.host ?? ''),
    port: String(cfg.port ?? '514'),
    protocol: cfg.protocol === 'tcp' ? 'tcp' : 'udp',
    facility: String(cfg.facility ?? 'local0'),
  };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function NotificationsPane() {
  const { data: settings, isPending, isError } = useTenantSettings();
  const updateSettings = useUpdateTenantSettings();

  const { values, setField, isDirty, reset } = useDirtyState<NotifFormValues>({
    smtp: defaultSmtp(null),
    syslog: defaultSyslog(null),
  });

  // Seed form from fetched settings
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (settings) {
      reset({
        smtp: defaultSmtp(settings.smtp_config as Record<string, unknown> | null),
        syslog: defaultSyslog(settings.syslog_config as Record<string, unknown> | null),
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  function setSmtpField(key: keyof SmtpFormValues, val: unknown) {
    setField('smtp', { ...values.smtp, [key]: val } as SmtpFormValues);
  }

  function setSyslogField(key: keyof SyslogFormValues, val: unknown) {
    setField('syslog', { ...values.syslog, [key]: val } as SyslogFormValues);
  }

  async function handleSave() {
    const smtpPayload: Record<string, unknown> = {
      enabled: values.smtp.enabled,
      host: values.smtp.host,
      port: parseInt(values.smtp.port) || 587,
      username: values.smtp.username,
      from_email: values.smtp.from_email,
      tls: values.smtp.tls,
    };
    // CR-01 / T-14-17: Only include password if the user actually edited the
    // field. We track this with an explicit `passwordTouched` flag rather than
    // comparing against a hardcoded mask literal — so a displayed placeholder
    // (whatever its length/shape) can never be persisted as the real secret.
    // If the field was not touched, omit it entirely — backend keeps stored value.
    if (values.smtp.passwordTouched && values.smtp.password) {
      smtpPayload.password = values.smtp.password;
    }

    const syslogPayload = {
      enabled: values.syslog.enabled,
      host: values.syslog.host,
      port: parseInt(values.syslog.port) || 514,
      protocol: values.syslog.protocol,
      facility: values.syslog.facility,
    };

    await updateSettings.mutateAsync({
      smtp_config: smtpPayload,
      syslog_config: syslogPayload,
    });
    reset();
  }

  function handleDiscard() {
    if (settings) {
      reset({
        smtp: defaultSmtp(settings.smtp_config as Record<string, unknown> | null),
        syslog: defaultSyslog(settings.syslog_config as Record<string, unknown> | null),
      });
    } else {
      reset();
    }
  }

  return (
    <div data-pane="notifications" className="space-y-6 p-6">
      {/* Error banner */}
      {isError && (
        <PartialFailureBanner watchKeys={[queryKeys.settings.tenant()]} />
      )}

      {/* Loading skeleton */}
      {isPending && (
        <SkeletonTable
          rows={4}
          columns={[
            { kind: 'text', width: 120 },
            { kind: 'text', width: 200 },
          ]}
        />
      )}

      {/* Card 1 — Email / SMTP */}
      <section className="rounded-lg border border-border-subtle bg-surface p-6">
        <h2 className="mb-1 text-base font-semibold text-text">Email / SMTP</h2>
        <p className="mb-4 text-sm text-text-muted">
          Configure SMTP to deliver scheduled reports and alert notifications by email.
        </p>

        {/* Enable toggle */}
        <div className="mb-4 flex items-center justify-between rounded-lg border border-border bg-surface-2 px-4 py-3">
          <div>
            <p className="text-sm font-medium text-text">Enable email delivery</p>
            <p className="text-xs text-text-muted">Scheduled reports will be emailed to configured recipients.</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={values.smtp.enabled}
            onClick={() => setSmtpField('enabled', !values.smtp.enabled)}
            className={[
              'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors',
              values.smtp.enabled ? 'bg-violet' : 'bg-surface-2 border border-border',
            ].join(' ')}
          >
            <span
              className={[
                'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
                values.smtp.enabled ? 'translate-x-6' : 'translate-x-1',
              ].join(' ')}
            />
          </button>
        </div>

        {values.smtp.enabled && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-text">SMTP host</label>
              <input
                type="text"
                value={values.smtp.host}
                onChange={(e) => setSmtpField('host', e.target.value)}
                placeholder="smtp.gmail.com"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Port</label>
              <input
                type="text"
                value={values.smtp.port}
                onChange={(e) => setSmtpField('port', e.target.value)}
                placeholder="587"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Username</label>
              <input
                type="text"
                value={values.smtp.username}
                onChange={(e) => setSmtpField('username', e.target.value)}
                placeholder="apikey or email"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text">
                Password / API key
              </label>
              {/* CR-01 / T-14-17: field is seeded EMPTY; the bullet placeholder
                  is only a hint that a stored secret exists. Editing flips
                  passwordTouched, which is the sole condition under which the
                  password is sent. Leaving it blank keeps the stored value. */}
              <input
                type="password"
                value={values.smtp.password}
                onChange={(e) => {
                  setField('smtp', {
                    ...values.smtp,
                    password: e.target.value,
                    passwordTouched: true,
                  });
                }}
                placeholder={SMTP_PASSWORD_PLACEHOLDER}
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text">From email</label>
              <input
                type="email"
                value={values.smtp.from_email}
                onChange={(e) => setSmtpField('from_email', e.target.value)}
                placeholder="noreply@company.com"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="smtp-tls"
                checked={values.smtp.tls}
                onChange={(e) => setSmtpField('tls', e.target.checked)}
                className="rounded border-border"
              />
              <label htmlFor="smtp-tls" className="text-sm text-text">
                Use TLS (port 465)
              </label>
            </div>
          </div>
        )}
      </section>

      {/* Card 2 — Syslog forwarding */}
      <section className="rounded-lg border border-border-subtle bg-surface p-6">
        <h2 className="mb-1 text-base font-semibold text-text">Syslog forwarding</h2>
        <p className="mb-4 text-sm text-text-muted">
          Forward audit events to your SIEM (Splunk, QRadar, Sentinel, ELK) via syslog in CEF format.
        </p>

        {/* Enable toggle */}
        <div className="mb-4 flex items-center justify-between rounded-lg border border-border bg-surface-2 px-4 py-3">
          <div>
            <p className="text-sm font-medium text-text">Enable syslog forwarding</p>
            <p className="text-xs text-text-muted">All audit events will be sent to the configured syslog server.</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={values.syslog.enabled}
            onClick={() => setSyslogField('enabled', !values.syslog.enabled)}
            className={[
              'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors',
              values.syslog.enabled ? 'bg-violet' : 'bg-surface-2 border border-border',
            ].join(' ')}
          >
            <span
              className={[
                'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
                values.syslog.enabled ? 'translate-x-6' : 'translate-x-1',
              ].join(' ')}
            />
          </button>
        </div>

        {values.syslog.enabled && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Syslog host</label>
              <input
                type="text"
                value={values.syslog.host}
                onChange={(e) => setSyslogField('host', e.target.value)}
                placeholder="siem.company.com"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Port</label>
              <input
                type="text"
                value={values.syslog.port}
                onChange={(e) => setSyslogField('port', e.target.value)}
                placeholder="514"
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Protocol</label>
              <select
                value={values.syslog.protocol}
                onChange={(e) => setSyslogField('protocol', e.target.value)}
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text focus:border-violet focus:outline-none"
              >
                <option value="udp">UDP</option>
                <option value="tcp">TCP</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text">Facility</label>
              <select
                value={values.syslog.facility}
                onChange={(e) => setSyslogField('facility', e.target.value)}
                className="w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text focus:border-violet focus:outline-none"
              >
                {['local0', 'local1', 'local2', 'local3', 'auth', 'authpriv'].map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </section>

      {/* Card 3 — Alert categories (coming-soon — no backend field yet, Open Question #2 resolved) */}
      <section className="rounded-lg border border-border-subtle bg-surface p-6">
        <h2 className="mb-1 text-base font-semibold text-text">Alert categories</h2>
        <p className="mb-4 text-sm text-text-muted">
          Configure which alert types trigger email and syslog notifications.
        </p>
        <EmptyState>
          <EmptyState.Title>Alert category configuration coming soon</EmptyState.Title>
          <EmptyState.Body>
            Per-category alert preferences will be available in a future update.
          </EmptyState.Body>
        </EmptyState>
      </section>

      {/* Single SaveBar across all three sections */}
      <SaveBar
        isDirty={isDirty}
        isSaving={updateSettings.isPending}
        onSave={handleSave}
        onDiscard={handleDiscard}
      />
    </div>
  );
}
