'use client';
/**
 * AlertingDigestsPane — "Alerting & Digests" admin settings pane (Phase 40 / D-17).
 *
 * Structural clone of sla-escalation-pane.tsx: useAuth() + useTenantSettings()/
 * useUpdateTenantSettings() + useDirtyState<T>() + onDirtyChange, a single
 * shared <SaveBar>, mandatory SkeletonTable/PartialFailureBanner/EmptyState,
 * a data-pane test hook (root element below), design tokens only (no raw hex).
 *
 * Three section cards (40-UI-SPEC.md Copywriting Contract — verbatim):
 *   1. New exposure alerts — KEV toggle + EPSS threshold (ALERT-01, D-05/D-06).
 *   2. Scheduled digests   — cadence + send-hour + per-owner/per-team toggles
 *                            (ALERT-02, D-08/D-11/D-12).
 *   3. Delivery channels   — per-alert-type routing referencing the SAME
 *                            Slack/Teams/PagerDuty/Email channels configured
 *                            under SLA & Escalation (D-19 — this pane never
 *                            re-collects or displays a channel secret; only
 *                            the channels that are already ENABLED there are
 *                            offered as routing targets here).
 *
 * RBAC (T-40-19): GET /tenant/settings is require_admin, PATCH is
 * require_owner (asymmetric, matches sla-escalation-pane.tsx's isOwner
 * pattern) — every control in this pane, including "Send test digest", is
 * disabled for a non-OWNER viewer. The server PATCH require_owner check is
 * authoritative; this is defense-in-depth, not the control.
 *
 * Send test digest (Plan 04's POST /settings/alerting/test-digest, E1
 * backstop): previews the ACTING tenant's current digest to the ACTING
 * admin's own email only. The response's `status` distinguishes three
 * outcomes so a legitimately-quiet tenant never reads as a false-positive
 * error: "sent" | "empty" (D-14 suppression — not an error) | "error".
 *
 * Plan 40-05.
 */

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { useTenantSettings, useUpdateTenantSettings } from '@/lib/queries/use-tenant-settings';
import { useDirtyState } from './use-dirty-state';
import { SaveBar } from './save-bar';
import { SkeletonTable, PartialFailureBanner, EmptyState } from '@/components/states';
import { queryKeys } from '@/lib/queries/keys';

// ── Copy (40-UI-SPEC.md Copywriting Contract — verbatim) ────────────────────

const COPY = {
  section1Heading: 'New exposure alerts',
  section1Subtitle:
    "Fire a real-time alert when a CVE newly qualifies for CISA KEV or crosses your EPSS threshold on one of your assets.",
  kevToggleLabel: 'Alert on new CISA KEV listings',
  epssThresholdLabel: 'EPSS threshold',
  epssThresholdHelper: "Fire when a CVE's EPSS score reaches this value or higher. Default 0.5.",
  section2Heading: 'Scheduled digests',
  section2Subtitle:
    'Send owners and teams a daily or weekly summary of due, breaching, newly-critical, and expiring-exception findings.',
  cadenceLabel: 'Cadence',
  sendHourLabel: 'Send at',
  sendHourHelper: "Time is in your workspace's configured timezone.",
  perOwnerLabel: 'Send per-owner digests',
  perTeamLabel: 'Send per-team digests',
  section3Heading: 'Delivery channels',
  section3Subtitle:
    'Alerts and digests reuse the Slack, Teams, PagerDuty, and email channels configured under SLA & Escalation — choose which ones each alert type uses.',
  emptyChannelsTitle: 'No delivery channels configured',
  emptyChannelsBody:
    'Configure a Slack, Teams, PagerDuty, or email channel under SLA & Escalation, then come back here to route alerts and digests to it.',
  sendTestDigest: 'Send test digest',
  sendingTestDigest: 'Sending…',
  testDigestEmpty:
    'Nothing to send right now — no due, breaching, newly-critical, or expiring-exception findings match your current settings.',
  testDigestSent: 'Test digest sent — check your inbox.',
  testDigestError:
    "Test digest couldn't be sent. Check your channel configuration under SLA & Escalation and try again.",
} as const;

// ── Types ─────────────────────────────────────────────────────────────────────

type ChannelKey = 'slack' | 'teams' | 'pagerduty' | 'email';

const CHANNEL_LABELS: Record<ChannelKey, string> = {
  slack: 'Slack',
  teams: 'Microsoft Teams',
  pagerduty: 'PagerDuty',
  email: 'Email',
};

type AlertTypeKey = 'new_kev_epss' | 'digest_owner' | 'digest_team';

// Row labels are distinct from the section-1/section-2 headings above (which
// use the exact UI-SPEC copy) to avoid an ambiguous duplicate-text render —
// these rows live inside Section 3 ("Delivery channels") and name the alert
// TYPE being routed, not the feature section that configures it.
const ALERT_TYPES: ReadonlyArray<{ key: AlertTypeKey; label: string }> = [
  { key: 'new_kev_epss', label: 'Real-time alerts' },
  { key: 'digest_owner', label: 'Owner digests' },
  { key: 'digest_team', label: 'Team digests' },
];

type RoutingFormValues = Record<AlertTypeKey, string[]>;

type AlertingFormValues = {
  kevEnabled: boolean;
  /** 0-1 fraction, kept as a string for the controlled numeric input. */
  epssThreshold: string;
  cadence: 'daily' | 'weekly';
  /** 0-23, kept as a string for the controlled numeric input. */
  sendHour: string;
  perOwnerDigests: boolean;
  perTeamDigests: boolean;
  routing: RoutingFormValues;
};

type TestDigestState = 'idle' | 'sending' | 'sent' | 'empty' | 'error';

// ── Defaults / seed builders ──────────────────────────────────────────────────
// Mirrors DEFAULT_ALERTING_CONFIG (backend/app/notifications/alerting_config.py)
// so an untouched tenant (alerting_config === null) pre-fills with the same
// values the backend's merged_alerting_config() would compute.

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' ? (v as Record<string, unknown>) : {};
}

function defaultAlertingForm(cfg: Record<string, unknown> | null): AlertingFormValues {
  const c = cfg ?? {};
  const routing = asRecord(c.routing);
  return {
    kevEnabled: c.kev_enabled === undefined ? true : Boolean(c.kev_enabled),
    epssThreshold: String(typeof c.epss_threshold === 'number' ? c.epss_threshold : 0.5),
    cadence: c.cadence === 'weekly' ? 'weekly' : 'daily',
    sendHour: String(typeof c.send_hour === 'number' ? c.send_hour : 8),
    perOwnerDigests: c.per_owner_digests === undefined ? true : Boolean(c.per_owner_digests),
    perTeamDigests: c.per_team_digests === undefined ? true : Boolean(c.per_team_digests),
    routing: {
      new_kev_epss: Array.isArray(routing.new_kev_epss) ? (routing.new_kev_epss as string[]) : ['slack'],
      digest_owner: Array.isArray(routing.digest_owner) ? (routing.digest_owner as string[]) : ['email'],
      digest_team: Array.isArray(routing.digest_team) ? (routing.digest_team as string[]) : ['slack'],
    },
  };
}

// ── Shared control primitives (duplicated from sla-escalation-pane.tsx —
// that file doesn't export them, and this pane is a structural clone) ──────

function ToggleSwitch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={[
        'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        checked ? 'bg-violet' : 'bg-surface-2 border border-border',
      ].join(' ')}
    >
      <span
        className={[
          'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-6' : 'translate-x-1',
        ].join(' ')}
      />
    </button>
  );
}

const FIELD_CLASS =
  'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

// ── Component ─────────────────────────────────────────────────────────────────

export function AlertingDigestsPane({
  onDirtyChange,
}: {
  onDirtyChange?: (dirty: boolean) => void;
} = {}) {
  const { user } = useAuth();
  // PATCH /tenant/settings is require_owner-gated (asymmetric with GET's
  // require_admin) — mirrors SlaEscalationPane's isOwner disable pattern
  // (T-40-19). "Send test digest" is disabled under the same gate even
  // though the backend endpoint itself is require_admin, so this pane
  // reads as fully-disabled-for-a-viewer rather than partially editable.
  const isOwner = user?.role === 'OWNER';

  const { data: settings, isPending, isError } = useTenantSettings();
  const updateSettings = useUpdateTenantSettings();

  const { values, setField, isDirty, reset } = useDirtyState<AlertingFormValues>(
    defaultAlertingForm(null),
  );

  const [testDigestState, setTestDigestState] = useState<TestDigestState>('idle');
  const [testDigestError, setTestDigestError] = useState<string | null>(null);

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  // Seed form from fetched settings.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (settings) {
      reset(defaultAlertingForm((settings.alerting_config as Record<string, unknown> | null) ?? null));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  // Delivery channels (D-19): only channels already ENABLED under SLA &
  // Escalation are offered as routing targets — this pane never configures
  // a channel's credentials itself.
  const slaChannels = asRecord(asRecord(settings?.sla_config).channels);
  const enabledChannels: ChannelKey[] = (['slack', 'teams', 'pagerduty', 'email'] as const).filter(
    (channel) => Boolean(asRecord(slaChannels[channel]).enabled),
  );
  const anyChannelEnabled = enabledChannels.length > 0;

  function toggleRouting(alertType: AlertTypeKey, channel: ChannelKey, checked: boolean) {
    const current = values.routing[alertType];
    const next = checked ? [...current, channel] : current.filter((c) => c !== channel);
    setField('routing', { ...values.routing, [alertType]: next });
  }

  async function handleSave() {
    const epssRaw = parseFloat(values.epssThreshold);
    const epssThreshold = Number.isFinite(epssRaw) ? Math.min(1, Math.max(0, epssRaw)) : 0.5;
    const sendHourRaw = parseInt(values.sendHour, 10);
    const sendHour = Number.isFinite(sendHourRaw) ? Math.min(23, Math.max(0, sendHourRaw)) : 8;

    await updateSettings.mutateAsync({
      alerting_config: {
        kev_enabled: values.kevEnabled,
        epss_threshold: epssThreshold,
        cadence: values.cadence,
        send_hour: sendHour,
        per_owner_digests: values.perOwnerDigests,
        per_team_digests: values.perTeamDigests,
        routing: values.routing,
      },
    });
    reset();
  }

  function handleDiscard() {
    reset(defaultAlertingForm((settings?.alerting_config as Record<string, unknown> | null) ?? null));
  }

  async function handleSendTestDigest() {
    setTestDigestState('sending');
    setTestDigestError(null);
    try {
      const result = await api<{ status: 'sent' | 'empty' | 'error'; error?: string }>(
        '/api/v1/tenant/settings/alerting/test-digest',
        { method: 'POST' },
      );
      setTestDigestState(result.status);
      if (result.status === 'error' && result.error) {
        setTestDigestError(result.error);
      }
    } catch {
      setTestDigestState('error');
    }
  }

  return (
    <div data-pane="alerting-digests" className="space-y-6 p-6">
      {isError && <PartialFailureBanner watchKeys={[queryKeys.settings.tenant()]} />}

      {isPending && (
        <SkeletonTable
          rows={4}
          columns={[
            { kind: 'text', width: 120 },
            { kind: 'text', width: 200 },
          ]}
        />
      )}

      {!isPending && !isError && (
        <>
          {/* Card 1 — New exposure alerts */}
          <section className="rounded-lg border border-border-subtle bg-surface p-6">
            <h2 className="mb-1 text-base font-semibold text-text">{COPY.section1Heading}</h2>
            <p className="mb-4 text-sm text-text-muted">{COPY.section1Subtitle}</p>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">{COPY.kevToggleLabel}</span>
                <ToggleSwitch
                  label={COPY.kevToggleLabel}
                  checked={values.kevEnabled}
                  disabled={!isOwner}
                  onChange={(next) => setField('kevEnabled', next)}
                />
              </div>

              <div>
                <label
                  htmlFor="alerting-epss-threshold"
                  className="mb-1 block text-sm font-medium text-text"
                >
                  {COPY.epssThresholdLabel}
                </label>
                <input
                  id="alerting-epss-threshold"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  disabled={!isOwner}
                  value={values.epssThreshold}
                  onChange={(e) => setField('epssThreshold', e.target.value)}
                  className={`${FIELD_CLASS} max-w-xs font-mono`}
                />
                <p className="mt-1 text-xs text-text-muted">{COPY.epssThresholdHelper}</p>
              </div>
            </div>
          </section>

          {/* Card 2 — Scheduled digests */}
          <section className="rounded-lg border border-border-subtle bg-surface p-6">
            <h2 className="mb-1 text-base font-semibold text-text">{COPY.section2Heading}</h2>
            <p className="mb-4 text-sm text-text-muted">{COPY.section2Subtitle}</p>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="alerting-cadence" className="mb-1 block text-sm font-medium text-text">
                  {COPY.cadenceLabel}
                </label>
                <select
                  id="alerting-cadence"
                  disabled={!isOwner}
                  value={values.cadence}
                  onChange={(e) => setField('cadence', e.target.value as 'daily' | 'weekly')}
                  className={FIELD_CLASS}
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
              </div>

              <div>
                <label htmlFor="alerting-send-hour" className="mb-1 block text-sm font-medium text-text">
                  {COPY.sendHourLabel}
                </label>
                <input
                  id="alerting-send-hour"
                  type="number"
                  min={0}
                  max={23}
                  disabled={!isOwner}
                  value={values.sendHour}
                  onChange={(e) => setField('sendHour', e.target.value)}
                  className={`${FIELD_CLASS} font-mono`}
                />
                <p className="mt-1 text-xs text-text-muted">{COPY.sendHourHelper}</p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">{COPY.perOwnerLabel}</span>
                <ToggleSwitch
                  label={COPY.perOwnerLabel}
                  checked={values.perOwnerDigests}
                  disabled={!isOwner}
                  onChange={(next) => setField('perOwnerDigests', next)}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text">{COPY.perTeamLabel}</span>
                <ToggleSwitch
                  label={COPY.perTeamLabel}
                  checked={values.perTeamDigests}
                  disabled={!isOwner}
                  onChange={(next) => setField('perTeamDigests', next)}
                />
              </div>
            </div>
          </section>

          {/* Card 3 — Delivery channels */}
          <section className="rounded-lg border border-border-subtle bg-surface p-6">
            <h2 className="mb-1 text-base font-semibold text-text">{COPY.section3Heading}</h2>
            <p className="mb-4 text-sm text-text-muted">{COPY.section3Subtitle}</p>

            {!anyChannelEnabled && (
              <EmptyState className="mb-4 max-w-none p-6">
                <EmptyState.Title>{COPY.emptyChannelsTitle}</EmptyState.Title>
                <EmptyState.Body>{COPY.emptyChannelsBody}</EmptyState.Body>
              </EmptyState>
            )}

            {anyChannelEnabled && (
              <div className="space-y-4">
                {ALERT_TYPES.map(({ key, label }) => (
                  <div key={key} className="rounded-lg border border-border bg-surface-2 p-4">
                    <div className="mb-2 text-sm font-medium text-text">{label}</div>
                    <div className="flex flex-wrap items-center gap-4">
                      {enabledChannels.map((channel) => (
                        <label key={channel} className="flex items-center gap-2 text-xs text-text">
                          <input
                            type="checkbox"
                            disabled={!isOwner}
                            checked={values.routing[key].includes(channel)}
                            onChange={(e) => toggleRouting(key, channel, e.target.checked)}
                            className="rounded border-border"
                          />
                          {CHANNEL_LABELS[channel]}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border-subtle pt-4">
              <button
                type="button"
                disabled={!isOwner || testDigestState === 'sending'}
                onClick={handleSendTestDigest}
                className="rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm font-medium text-text hover:border-violet focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
              >
                {testDigestState === 'sending' ? COPY.sendingTestDigest : COPY.sendTestDigest}
              </button>
              {testDigestState === 'empty' && (
                <p className="text-sm text-text-muted">{COPY.testDigestEmpty}</p>
              )}
              {testDigestState === 'sent' && (
                <p className="text-sm text-success">{COPY.testDigestSent}</p>
              )}
              {testDigestState === 'error' && (
                <p className="text-sm text-danger">
                  {COPY.testDigestError}
                  {/* T-40-21: any server-echoed detail is rendered as plain React
                      text (auto-escaped), never dangerouslySetInnerHTML — the
                      fixed UI-SPEC copy above always leads. */}
                  {testDigestError && <span className="text-text-muted"> ({testDigestError})</span>}
                </p>
              )}
            </div>
          </section>
        </>
      )}

      <SaveBar
        isDirty={isDirty && isOwner}
        isSaving={updateSettings.isPending}
        onSave={handleSave}
        onDiscard={handleDiscard}
      />
    </div>
  );
}
