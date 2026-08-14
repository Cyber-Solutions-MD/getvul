'use client';
import { forwardRef, useEffect, useMemo, useRef, useState } from 'react';
import { X } from 'lucide-react';
import Link from 'next/link';
import {
  useVulnerabilityDetail,
  type RiskBreakdownComponent,
} from '@/lib/queries/use-vulnerability-detail';
import { RiskRing } from '@/components/ui/RiskRing';
import { useCreateTicketMutation } from '@/lib/mutations/use-create-ticket';
import { useSnoozeMutation } from '@/lib/mutations/use-snooze';
import { useToast } from '@/components/ui/ToastProvider';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { TicketProviderPicker } from './ticket-provider-picker';
import type { TicketProvider } from '@/lib/ticketing/providers';
import { microcopy } from './microcopy';
import { cn } from '@/lib/utils';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
// 24-09 Task 1: AiExplanationSection moved to the shared, view-agnostic
// components/ai/ directory (D-15) so the host/remediation views can mount
// it verbatim alongside this vuln drill. Phase 27 (AID-01, Plan 03): the
// gap-fill row's "Analyzing…" state reuses the exact exported
// AnalyzingIndicator pulsing-dot (D-12) -- never a second spinner.
import { AiExplanationSection, AnalyzingIndicator } from '@/components/ai/ai-explanation-section';
// Phase 27 (AID-01, Plan 02): the three GET cache-check reads the ticket
// draft composer needs (D-02: free, zero model call) + the pure
// composition functions themselves (RESEARCH Pattern 1).
import { useExplainCache } from '@/lib/queries/use-explain-cache';
import {
  composeTicketTitle,
  composeTicketDescription,
  type CacheSection,
} from '@/lib/tickets/compose-ticket-draft';
// Phase 27 (AID-01, Plan 03): the gap-fill row's role/key gating source --
// reused verbatim from ai-explanation-section.tsx (RESEARCH "Don't
// Hand-Roll" -- never re-derive this check).
import { useAuth } from '@/lib/auth';
import { useAiStatus } from '@/lib/queries/use-ai-status';
// Phase 27 (AID-01, Plan 03): the gap-fill row calls useExplainStream
// DIRECTLY (bypassing AiExplanationSection entirely, 27-PATTERNS.md Analog
// 4) -- the same per-resource SSE trigger the drill panel's own sections
// already use, no new endpoint.
import { useExplainStream, type ExplainStreamState } from '@/lib/ai/use-explain-stream';
// Phase 36 (SLA-01/02, D-11): server-truth SLA state pill, matching the
// finding row (vuln-table.tsx). Phase 36 (SLA-03, D-07): the escalation-fire
// history list, its own query hook mirroring the drill panel's other
// per-resource data hooks.
import { SlaPill, type SlaPillState } from '@/components/tickets/sla-pill';
import { useVulnEscalations, type VulnEscalationEvent } from '@/lib/queries/use-vuln-escalations';

// D-P-05 — shared section order: Header → CVSS → Affected hosts →
// Description → Remediation → Activity → Actions. Used by both desktop
// DrillPanel (420px right aside) and DrillPanelMobile (vaul bottom-sheet).
//
// The detail shape is intentionally loose — the production query returns
// the locked VulnerabilityDetail type, but tests inject inline mocks. We
// fall back to '—' for any missing field so the component renders without
// crashing on either shape.

type FlexibleDetail = {
  id?: string;
  cve_id?: string | null;
  vulnerability_name?: string | null;
  // Test-shape extras (not in production type):
  title?: string | null;
  description?: string | null;
  remediation?: string | null;
  affected_hosts?: Array<{ host?: string; ip?: string }>;
  activity?: Array<unknown>;
  // Production-shape fields:
  cvss_v3_score?: number | null;
  cvss_v3_vector?: string | null;
  severity?: string;
  cisa_kev?: boolean;
  exploit_available?: boolean;
  asset_id?: string | null;
  asset_hostname?: string | null;
  source?: string;
  affected_product?: string | null;
  remediation_info?: string | null;
  status?: string;
  first_detected_at?: string;
  last_seen_at?: string;
  // Phase 33 Plan 04 (RISK-05): shadow/preview per-finding risk-exposure
  // score + its per-input breakdown. Null until the first post-Phase-33
  // sync shadow-computes it.
  risk_exposure_score?: number | null;
  risk_exposure_breakdown?: RiskBreakdownComponent[] | null;
  risk_model_version?: string | null;
  // Phase 36 (SLA-01/02, D-11): server-computed risk-tier SLA state. Never
  // re-derived client-side — absent/undefined means "server didn't send a
  // state" (older detail shape / test mock), in which case the pill is not
  // rendered rather than falling back to a client-computed guess (T-36-01).
  sla_state?: SlaPillState | null;
  sla_due_at?: string | null;
};

// Phase 27 (AID-01, Plan 03): the gap-fill row's per-section render state.
// 'trigger' covers both the true-idle case and the one-render window right
// after a grounded 'done' resolves (before `visible` flips false via the
// gapFillAppended guard below) -- see the GapFillDescriptor construction
// inside DrillContent for why 'done' itself never needs its own branch here.
type GapFillPhase = 'trigger' | 'analyzing' | 'busy' | 'budget_exceeded' | 'refused' | 'unsafe';

type GapFillItemState = {
  visible: boolean;
  phase: GapFillPhase;
  onClick: () => void;
  // Admin/Owner-only "Raise the cap" link (mirrors the existing budget
  // card's role-gated action, ai-explanation-section.tsx:260).
  canRaiseCap: boolean;
};

export type GapFillDescriptor = {
  rowVisible: boolean;
  description: GapFillItemState;
  remediation: GapFillItemState;
};

// Maps a raw useExplainStream() state onto the gap-fill row's own 6-state
// vocabulary. 'done' with grounded=false is a defensive backstop (the real
// engine never emits it, mirroring ai-explanation-section.tsx's own
// UI-SPEC-backstop comment) -- treated the same as the terminal
// grounded_false refusal.
function gapFillPhaseFrom(state: ExplainStreamState): GapFillPhase {
  if (state.phase === 'analyzing') return 'analyzing';
  if (state.phase === 'done') return state.data.grounded ? 'trigger' : 'refused';
  if (state.phase === 'error') {
    switch (state.kind) {
      case 'busy':
      case 'unknown':
        return 'busy';
      case 'budget_exceeded':
        return 'budget_exceeded';
      case 'grounded_false':
        return 'refused';
      case 'unsafe':
        return 'unsafe';
    }
  }
  return 'trigger'; // 'idle'
}

// Phase 27 (AID-01, Plan 03, 27-UI-SPEC.md §4): renders ONE gap-fill row
// item from its descriptor. Module-level (not a hook, no closure over
// component state) so drill-panel-mobile.tsx defines an IDENTICAL copy for
// its own divergent render path (Pitfall 6 precedent: hardcode/duplicate
// copy across the two files rather than share JSX cross-file) -- the
// LOCKED caption/trigger strings are literal here (grep-provable), driven
// only by the threaded descriptor's mechanical state (visible/phase/
// onClick/canRaiseCap). Uses the exact CopyToDescriptionButton text-button
// chrome (ai-explanation-section.tsx:92-102) -- never a button-shaped CTA.
function renderGapFillItem(item: GapFillItemState, kind: 'description' | 'remediation') {
  if (!item.visible) return null;
  if (item.phase === 'analyzing') return <AnalyzingIndicator />;
  if (item.phase === 'refused') {
    return (
      <p className="text-xs font-medium text-text-muted">
        {kind === 'description'
          ? 'Not enough finding data to explain this reliably'
          : 'Not enough vendor guidance to recommend a fix'}
      </p>
    );
  }
  if (item.phase === 'unsafe') {
    return <p className="text-xs font-medium text-danger">This guidance was withheld for safety</p>;
  }
  if (item.phase === 'budget_exceeded') {
    return (
      <p className="text-xs font-medium text-amber">
        AI budget exceeded
        {item.canRaiseCap && (
          <>
            {' '}
            <Link href="/dashboard/connectors" className="underline underline-offset-2 hover:text-text">
              Raise the cap
            </Link>
          </>
        )}
      </p>
    );
  }
  // 'trigger' or 'busy' -- both render the clickable button; busy
  // additionally shows the amber retry caption beneath it (D-25: retry
  // stays allowed, never a terminal state).
  return (
    <div>
      <button
        type="button"
        onClick={item.onClick}
        className="text-xs font-medium text-text-muted underline-offset-2 hover:text-text hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
      >
        {kind === 'description' ? 'Draft description with AI' : 'Draft remediation with AI'}
      </button>
      {item.phase === 'busy' && (
        <p className="mt-1 text-xs font-medium text-amber">AI busy — try again in a moment</p>
      )}
    </div>
  );
}

// ── Escalation-history list (Phase 36, SLA-03, D-07) ─────────────────────────
//
// Module-level (not a hook) — pure render of the escalationsQuery result,
// mirroring the gap-fill row's own module-level render helpers above.
// ActivityTimeline-style (dot + connecting line + chronological rows) but a
// local implementation rather than importing the shared `ActivityTimeline`
// component: that component's TimelineEntry union (comment | sync) has no
// slot for a failed-delivery amber tint / audit-only "no retry" contract, and
// this plan's file scope does not include activity-timeline.tsx.

const CHANNEL_LABEL: Record<string, string> = {
  slack: 'Slack',
  teams: 'Microsoft Teams',
  pagerduty: 'PagerDuty',
  email: 'Email',
};

const STATE_LABEL: Record<string, string> = {
  on_track: 'On track',
  approaching: 'Approaching',
  breached: 'Breached',
  not_tracked: 'Not tracked',
};

function formatFiredAt(iso: string): string {
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return '—';
  return `${d.toISOString().slice(11, 16)} UTC`;
}

function EscalationHistoryList({
  isPending,
  isError,
  events,
}: {
  isPending: boolean;
  isError: boolean;
  events: VulnEscalationEvent[];
}) {
  if (isPending) {
    return <p className="text-sm text-text-muted">Loading…</p>;
  }
  if (isError) {
    return <p className="text-sm text-danger">Couldn’t load escalation history.</p>;
  }
  if (events.length === 0) {
    // E3 empty: compact inline empty — NOT the full gradient-icon EmptyState
    // shell (that shell is reserved for filtered-to-zero list views, not a
    // sub-section inside an already-open drill panel).
    return (
      <div>
        <p className="text-sm font-medium text-text">No escalations yet</p>
        <p className="mt-1 text-sm text-text-faint">
          This finding hasn&apos;t crossed the approaching or breach threshold — new
          entries appear here the moment it does.
        </p>
      </div>
    );
  }

  return (
    <ul role="list" className="space-y-2">
      {events.map((ev) => {
        const failed = ev.delivery_status === 'failed';
        const channelLabel = CHANNEL_LABEL[ev.channel] ?? ev.channel;
        const fromLabel = STATE_LABEL[ev.from_state] ?? ev.from_state;
        const toLabel = STATE_LABEL[ev.to_state] ?? ev.to_state;
        const firedLabel = formatFiredAt(ev.fired_at);

        return (
          <li
            key={ev.id}
            className={
              failed
                ? 'rounded-md border border-amber bg-amber-soft p-3'
                : 'rounded-md border border-border-subtle bg-surface-2 p-3'
            }
          >
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-md border border-border-subtle bg-surface px-2 py-0.5 font-mono text-[11px] font-medium text-text-muted">
                {channelLabel}
              </span>
              <span className="text-text">
                {fromLabel} → {toLabel}
              </span>
              <span className="ml-auto font-mono text-text-faint">{firedLabel}</span>
            </div>
            {/* D-08: audit-only — amber-tinted, no retry button. The
                transition record above stays visible even on failure (D-07). */}
            {failed && (
              <p
                className="mt-1 truncate text-xs text-[var(--color-amber-on-soft)]"
                title={`${channelLabel} delivery failed — ${ev.error_message ?? 'unknown error'} · fired ${firedLabel}`}
              >
                {channelLabel} delivery failed — {ev.error_message ?? 'unknown error'} · fired {firedLabel}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

type Props = {
  idOrCve: string;
  onClose: () => void;
  // Slot for a per-host nested confirmation pattern (Drawer.NestedRoot on
  // mobile). When `renderConfirm` is provided, the drill content delegates
  // confirmation rendering to the caller; otherwise it uses ConfirmModal.
  renderConfirm?: (args: {
    open: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    cveLabel: string;
    ticketProvider: TicketProvider | null;
    onProviderChange: (p: TicketProvider) => void;
    // Phase 25 (AIR-02, Plan 07): analyst-reviewed ticket description,
    // pre-filled from the "Copy into ticket description" affordance,
    // freely editable/clearable, threaded into fireTicket()'s mutation
    // body. Mirrors the ticketProvider/onProviderChange controlled-prop
    // shape above (D-09 scope fence: description-only).
    description: string;
    onDescriptionChange: (v: string) => void;
    // Phase 27 (AID-01, Plan 02): analyst-reviewed ticket title, auto-
    // composed DETERMINISTICALLY (D-01, zero AI call) the first time the
    // confirm dialog opens for a given vuln. Freely editable/clearable,
    // threaded into fireTicket()'s mutation body. Mirrors the
    // description/onDescriptionChange controlled-prop shape above.
    title: string;
    onTitleChange: (v: string) => void;
    // Phase 27 (AID-01, Plan 03): the gap-fill row descriptor -- computed
    // here (hooks run in DrillContent's body: useAuth/useAiStatus/
    // useExplainStream x2) and threaded through so mobile's renderConfirm
    // can render an IDENTICAL row from the same data without duplicating
    // the role/key-gating or stream-triggering logic (D-05 divergence
    // lesson). Mobile's OWN JSX still literally contains the locked copy
    // strings (renderGapFillItem is duplicated, not imported, per Pitfall
    // 6's established precedent) -- only the STATE is shared.
    gapFill: GapFillDescriptor;
  }) => React.ReactNode;
};

export const DrillContent = forwardRef<HTMLDivElement, Props>(function DrillContent(
  { idOrCve, onClose, renderConfirm },
  ref,
) {
  const q = useVulnerabilityDetail(idOrCve);
  const createTicket = useCreateTicketMutation();
  const snooze = useSnoozeMutation();
  const { toast } = useToast();
  const [confirmOpen, setConfirmOpen] = useState(false);
  // D-14 (Plan 23-08): analyst-chosen ticketing provider, replacing the
  // hardcoded 'ASANA'. TicketProviderPicker default-selects the first
  // tenant-configured provider once its query loads.
  const [ticketProvider, setTicketProvider] = useState<TicketProvider | null>(null);
  // Phase 25 (AIR-02, Plan 07): analyst-reviewed ticket description. Starts
  // empty; pre-filled via onCopyToDescription from the remediation-guidance
  // AiExplanationSection mount below. Freely editable/clearable before the
  // existing "Create ticket" confirm click (D-08). Never a required field.
  const [description, setDescription] = useState('');
  // Phase 27 (AID-01, Plan 02): analyst-reviewed ticket title. Starts
  // empty; auto-composed DETERMINISTICALLY (D-01, zero AI call) the first
  // time the confirm dialog opens for a given vuln -- see the compose-on-
  // open effect below. Freely editable/clearable, never a required field.
  const [title, setTitle] = useState('');
  // Phase 27 (AID-01, Plan 03): tracks whether THIS dialog-life has already
  // successfully gap-filled each section -- the authoritative "hide the
  // button" signal (independent of the cache-derived `missing` check, which
  // never updates just because a local append happened). Reset inside the
  // SAME compose-on-open effect that resets `composedForId`, so a genuine
  // vuln switch (Pitfall 3) makes the row reconsider both sections fresh,
  // rather than staying permanently hidden because of a DIFFERENT vuln's
  // stale useExplainStream state.
  const [gapFillAppended, setGapFillAppended] = useState({ description: false, remediation: false });

  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const panelInteractivesRef = useRef<HTMLDivElement>(null);
  // Phase 27 (AID-01, Plan 02, RESEARCH Pattern 4): the resourceId the
  // compose-on-open effect below last composed a draft for. A ref KEYED TO
  // resourceId -- not a blank-string check -- so (a) an analyst's edits (or
  // a deliberately-cleared field) survive re-opening the SAME vuln's
  // dialog, and (b) switching to a DIFFERENT vuln while the panel stays
  // mounted (idOrCve changes, no remount) still recomposes, closing
  // Pitfall 3 (cross-vuln carryover).
  const composedForId = useRef<string | null>(null);

  // D-P-06 — focus moves to the close button on mount. Using a ref +
  // useEffect rather than the `autoFocus` JSX prop so the focus call
  // happens synchronously in jsdom (which doesn't honor autoFocus
  // consistently across React versions).
  useEffect(() => {
    closeBtnRef.current?.focus();
  }, [idOrCve]);

  // Phase 27 (AID-01, Plan 02): `v` and its cache-read/compose-relevant
  // derived fields are computed here -- unconditionally, BEFORE the
  // pending/error early returns below -- because Rules of Hooks requires
  // the cache reads + compose-on-open effect (both hooks) to run on every
  // render regardless of loading state. `q.data ?? {}` defends against `v`
  // being read while the detail query is still pending; once `q.data`
  // resolves, `v` reflects it exactly as it did before this restructure.
  const v = (q.data ?? {}) as unknown as FlexibleDetail;
  const cveLabel = v.cve_id ?? v.id ?? idOrCve;
  const hostsLine =
    v.affected_hosts && v.affected_hosts.length > 0
      ? v.affected_hosts.map((h) => h.host ?? h.ip ?? '—').join(', ')
      : (v.asset_hostname ?? '—');
  const sevLower = (v.severity ?? '').toString().toLowerCase();
  const sevLabel =
    sevLower.length > 0
      ? sevLower.charAt(0).toUpperCase() + sevLower.slice(1)
      : '—';

  // Phase 27 (AID-01, Plan 02): the three cache-check reads the composer
  // needs -- cheap, non-streaming GETs (D-09), never a model call. Reading
  // them here (rather than only inside AiExplanationSection's own mounts)
  // lets the compose-on-open effect below build the full multi-section
  // description without waiting for those sections to render.
  const explainCacheQuery = useExplainCache('vuln', v.id ?? idOrCve);
  const remediationGuidanceCacheQuery = useExplainCache('remediation-guidance', v.id ?? idOrCve);
  const prioritizationCacheQuery = useExplainCache('prioritization', v.id ?? idOrCve);

  // Phase 27 (AID-01, Plan 03): hoisted OUT of the compose-on-open effect
  // (Plan 02 had these as effect-local consts) so the gap-fill row's
  // "missing" detection below can reuse the IDENTICAL grounded-cache-hit
  // derivation the composer itself uses -- one source of truth for "is
  // this section present in the composed body." `prioritizationSection`
  // has no gap-fill trigger of its own (D-02 discretion: "include when
  // cached" only) but stays alongside its siblings for the compose effect.
  // Memoized (keyed on the underlying TanStack Query `.data` reference,
  // which is itself stable across re-renders until the query result
  // actually changes) so the compose-on-open effect's dependency array
  // below can depend on these directly -- satisfies exhaustive-deps
  // without re-running compose logic on every unrelated render.
  const explainSection: CacheSection = useMemo(
    () =>
      explainCacheQuery.data?.cached === true
        ? { grounded: explainCacheQuery.data.grounded, summary: explainCacheQuery.data.summary }
        : null,
    [explainCacheQuery.data],
  );
  const remediationGuidanceSection: CacheSection = useMemo(
    () =>
      remediationGuidanceCacheQuery.data?.cached === true
        ? {
            grounded: remediationGuidanceCacheQuery.data.grounded,
            summary: remediationGuidanceCacheQuery.data.summary,
          }
        : null,
    [remediationGuidanceCacheQuery.data],
  );
  const prioritizationSection: CacheSection = useMemo(
    () =>
      prioritizationCacheQuery.data?.cached === true
        ? { grounded: prioritizationCacheQuery.data.grounded, summary: prioritizationCacheQuery.data.summary }
        : null,
    [prioritizationCacheQuery.data],
  );

  // Phase 27 (AID-01, Plan 03): role/key gating source for the gap-fill row
  // -- reused verbatim from ai-explanation-section.tsx (RESEARCH "Don't
  // Hand-Roll"), never re-derived.
  const { user } = useAuth();
  const role = user?.role ?? 'VIEWER';
  const isAdminOrOwner = role === 'OWNER' || role === 'ADMIN';
  const isAnalystOrAbove = isAdminOrOwner || role === 'ANALYST';
  const aiStatusQuery = useAiStatus();
  const keyConfigured = Boolean(aiStatusQuery.data?.configured);

  // Phase 27 (AID-01, Plan 03): the gap-fill row's two direct triggers --
  // bypassing AiExplanationSection entirely (27-PATTERNS.md Analog 4). Each
  // is the SAME per-resource useExplainStream(resourceType, resourceId)
  // the drill panel's own sections already use; no new endpoint.
  const explainGapFill = useExplainStream('vuln', v.id ?? idOrCve);
  const remediationGapFill = useExplainStream('remediation-guidance', v.id ?? idOrCve);

  // Phase 36 (SLA-03, D-07): escalation-fire history for the drill panel's
  // new "Escalation history" section. Called unconditionally (before the
  // pending/error early returns) like the other per-resource hooks above.
  const escalationsQuery = useVulnEscalations(v.id ?? idOrCve);

  // Phase 27 (AID-01, Plan 02, D-02/D-04): compose-on-open. Runs once per
  // resourceId, the first time the confirm dialog transitions open --
  // reads only already-cached GET results + already-loaded local fields,
  // zero network calls. Never re-composes over an analyst's edits on a
  // same-vuln re-open (Pitfall 2: the pre-existing "Copy into ticket
  // description" button writes the SAME `description` state, but the
  // guard is keyed on "have I composed for THIS id," not "is description
  // empty," so the first genuine dialog open always composes the full
  // Title + body regardless of what the copy button already wrote). DOES
  // recompose when `v.id ?? idOrCve` changes to a different vuln while the
  // panel stays mounted (Pitfall 3) -- and (Plan 03) resets the gap-fill
  // row's own "already filled this dialog-life" tracking at the same
  // moment, so a genuine vuln switch makes both gap-fill buttons reconsider
  // fresh instead of staying hidden because of a DIFFERENT vuln's stale
  // useExplainStream state.
  useEffect(() => {
    if (!confirmOpen) return;
    const id = v.id ?? idOrCve;
    if (composedForId.current === id) return;
    composedForId.current = id;
    setGapFillAppended({ description: false, remediation: false });

    setTitle(composeTicketTitle({ sevLabel, cveLabel, hostsLine }));
    setDescription(
      composeTicketDescription({
        explain: explainSection,
        remediationGuidance: remediationGuidanceSection,
        prioritization: prioritizationSection,
        hostsLine,
        affectedProduct: v.affected_product ?? null,
        sevLabel,
        cisaKev: Boolean(v.cisa_kev),
        exploitAvailable: Boolean(v.exploit_available),
      }),
    );
  }, [
    confirmOpen,
    v.id,
    idOrCve,
    sevLabel,
    cveLabel,
    hostsLine,
    v.affected_product,
    v.cisa_kev,
    v.exploit_available,
    explainSection,
    remediationGuidanceSection,
    prioritizationSection,
  ]);

  // Phase 27 (AID-01, Plan 03): on a grounded 'done', append the labeled
  // section to the CURRENT description (blank line first, only if
  // non-empty) -- never overwriting an analyst's edits, and never firing
  // while the dialog is closed (avoids appending onto the pristine '' state
  // before compose-on-open has ever run, which the next genuine open would
  // otherwise silently discard). Guarded on !gapFillAppended.description so
  // this fires exactly once per successful fill.
  useEffect(() => {
    if (!confirmOpen) return;
    if (
      explainGapFill.state.phase === 'done' &&
      explainGapFill.state.data.grounded &&
      !gapFillAppended.description
    ) {
      setGapFillAppended((prev) => ({ ...prev, description: true }));
      const section = `Description:\n${explainGapFill.state.data.summary}`;
      setDescription((prev) => (prev ? `${prev}\n\n${section}` : section));
    }
  }, [confirmOpen, explainGapFill.state, gapFillAppended.description]);

  useEffect(() => {
    if (!confirmOpen) return;
    if (
      remediationGapFill.state.phase === 'done' &&
      remediationGapFill.state.data.grounded &&
      !gapFillAppended.remediation
    ) {
      setGapFillAppended((prev) => ({ ...prev, remediation: true }));
      const section = `Remediation:\n${remediationGapFill.state.data.summary}`;
      setDescription((prev) => (prev ? `${prev}\n\n${section}` : section));
    }
  }, [confirmOpen, remediationGapFill.state, gapFillAppended.remediation]);

  // D-P-06 (focus trap): Tab on the close button moves focus to the next
  // interactive element inside the panel. Shift-Tab cycles backward.
  // This is a minimal trap — sufficient for the Plan 02 test contract
  // (assert focus moves OFF close), not a full WCAG focus-trap.
  const onCloseKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== 'Tab') return;
    const container = panelInteractivesRef.current;
    if (!container) return;
    const focusables = Array.from(
      container.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusables.length === 0) return;
    e.preventDefault();
    const direction = e.shiftKey ? -1 : 1;
    // Close button is the current focus; advance to next interactive.
    const target =
      direction === 1
        ? focusables[0]
        : focusables[focusables.length - 1];
    target?.focus();
  };

  if (q.isPending) {
    return (
      <div ref={ref} aria-busy="true" className="p-6 text-text-muted">
        Loading…
      </div>
    );
  }
  if (q.isError || !q.data) {
    return (
      <div ref={ref} role="alert" className="p-6 text-danger">
        Couldn’t load this vulnerability.
      </div>
    );
  }

  // `v`, `cveLabel`, `hostsLine`, and `sevLabel` are already computed above
  // (unconditionally, before the pending/error early returns, so the cache
  // reads + compose-on-open effect can use them) -- reused here unchanged.
  // Renamed from `description` (Phase 25 Plan 07): the vuln's own CVE
  // description text, unrelated to the new ticket-description state below
  // -- the two shared the same identifier before this plan, which is now a
  // name collision (Rule 1 auto-fix).
  const vulnDescriptionText =
    v.description ?? v.vulnerability_name ?? v.title ?? '—';
  const remediation = v.remediation ?? v.remediation_info ?? '—';

  // Phase 27 (AID-01, Plan 03): the gap-fill row descriptor. "missing" =
  // the section is not a grounded cache hit (the SAME derivation
  // composeTicketDescription uses to decide whether to include it) --
  // zero missing sections renders no buttons at all (27-UI-SPEC.md §4).
  // The whole row is gated on keyConfigured && isAnalystOrAbove (D-17): no
  // key OR Viewer role -> both items stay invisible regardless of what's
  // missing.
  const gateOpen = keyConfigured && isAnalystOrAbove;
  const descriptionGapFillVisible = gateOpen && !explainSection?.grounded && !gapFillAppended.description;
  const remediationGapFillVisible =
    gateOpen && !remediationGuidanceSection?.grounded && !gapFillAppended.remediation;
  const gapFill: GapFillDescriptor = {
    rowVisible: descriptionGapFillVisible || remediationGapFillVisible,
    description: {
      visible: descriptionGapFillVisible,
      phase: gapFillPhaseFrom(explainGapFill.state),
      onClick: () => void explainGapFill.start(),
      canRaiseCap: isAdminOrOwner,
    },
    remediation: {
      visible: remediationGapFillVisible,
      phase: gapFillPhaseFrom(remediationGapFill.state),
      onClick: () => void remediationGapFill.start(),
      canRaiseCap: isAdminOrOwner,
    },
  };

  const fireTicket = async () => {
    try {
      const result = (await createTicket.mutateAsync({
        vulnerability_ids: [v.id ?? idOrCve],
        // T-23-23: the client-chosen provider is not the trust anchor — the
        // backend re-coerces via TicketProvider(...) (Plan 04). The
        // `?? 'ASANA'` is only a type-guard fallback; TicketProviderPicker
        // default-selects the first configured provider on load and the
        // Confirm action is disabled while ticketProvider is still null.
        provider: ticketProvider ?? 'ASANA',
        // Phase 27 (AID-01, Plan 02): analyst-reviewed title, threaded to
        // the Plan 01 backend contract. Blank/whitespace-only collapses to
        // undefined so the backend's own fallback (the deterministic
        // "[sev] cve on host" auto-build) applies unchanged -- never sends
        // an empty-string title.
        title: title || undefined,
        // Phase 25 (AIR-02): analyst-reviewed description, threaded to the
        // Plan 06 backend contract. Blank/whitespace-only collapses to
        // undefined so the backend's own fallback (_build_task_description)
        // applies unchanged -- never sends an empty-string description.
        description: description || undefined,
      })) as { tickets?: Array<{ external_ticket_id: string; external_ticket_url: string }> };
      const first = result.tickets?.[0];
      if (first) {
        toast({
          variant: 'success',
          message: microcopy.ticket.toastSuccess(first.external_ticket_id),
          action: {
            label: microcopy.ticket.toastViewAction,
            onClick: () => window.open(first.external_ticket_url, '_blank'),
          },
        });
      }
      setConfirmOpen(false);
    } catch (err) {
      toast({ variant: 'error', message: (err as Error).message });
    }
  };

  const fireSnooze = async () => {
    try {
      await snooze.mutateAsync({ id: v.id ?? idOrCve });
      toast({ variant: 'success', message: `Snoozed ${cveLabel} for 24h` });
    } catch (err) {
      toast({ variant: 'error', message: (err as Error).message });
    }
  };

  const cancelConfirm = () => setConfirmOpen(false);

  return (
    <div ref={ref} className="flex h-full flex-col">
      {/* Drill header — D-P-05 */}
      <div className="flex items-start justify-between border-b border-border-subtle px-5 py-4">
        <div>
          <h3 className="font-mono text-lg font-semibold text-text">
            {cveLabel}
          </h3>
          <div className="mt-1 flex flex-wrap gap-2 text-xs">
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
                sevLower === 'critical'
                  ? 'border-severity-critical bg-pink-soft text-[var(--color-severity-critical-on-soft)]'
                  : 'border-border-subtle bg-surface-2 text-text-muted',
              )}
            >
              {sevLabel}
            </span>
            {/* Phase 36 (SLA-01/02, D-11): server-truth SLA state, matching
                the finding row (vuln-table.tsx). Only rendered when the
                server actually sent a state — never a client-computed
                fallback guess for the drill panel (T-36-01). */}
            {v.sla_state != null && (
              <SlaPill state={v.sla_state} dueAt={v.sla_due_at ?? null} />
            )}
            {v.cisa_kev && (
              <span className="rounded-md bg-pink-soft px-2 py-0.5 font-mono text-[10px] font-medium uppercase text-[var(--color-severity-critical-on-soft)]">
                ★ CISA KEV
              </span>
            )}
            {v.exploit_available && (
              <span className="rounded-md bg-amber-soft px-2 py-0.5 text-[var(--color-amber-on-soft)]">
                ⚡ exploit available
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          ref={closeBtnRef}
          onClick={onClose}
          onKeyDown={onCloseKeyDown}
          aria-label={microcopy.drill.closeAria}
          className="rounded-md p-1 text-text-muted hover:bg-surface-2 hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <div
        ref={panelInteractivesRef}
        className="flex-1 space-y-6 overflow-y-auto p-5"
      >
        <section aria-labelledby="drill-cvss-h">
          <h4
            id="drill-cvss-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            {microcopy.drill.sections.cvss}
          </h4>
          <div className="font-mono text-sm text-text">
            Score: {v.cvss_v3_score?.toFixed(1) ?? '—'} · Vector:{' '}
            {v.cvss_v3_vector ?? '—'}
          </div>
        </section>

        {/* Phase 33 Plan 04 (RISK-05): shadow/preview per-finding Risk
            Exposure breakdown -- read-only, the sole permitted reader of
            the new score this phase (RISK-06 zero-consumer gate). Guarded
            on score+breakdown both present (state-patterns: null-safe
            absent state, no crash). Data-driven .map over the server-
            computed breakdown array -- no frontend re-derivation of the
            scoring formula. */}
        {v.risk_exposure_score != null && v.risk_exposure_breakdown && (
          <section aria-labelledby="drill-risk-exposure-h">
            <h4
              id="drill-risk-exposure-h"
              className="mb-2 text-xs uppercase tracking-wide text-text-muted"
            >
              {microcopy.drill.sections.riskExposure}
            </h4>
            <div className="flex items-center gap-3">
              <RiskRing score={v.risk_exposure_score} size={56} />
              {v.risk_exposure_breakdown.some((c) => c.key === 'kev_floor') && (
                <span className="rounded-md bg-pink-soft px-2 py-0.5 font-mono text-[10px] font-medium uppercase text-[var(--color-severity-critical-on-soft)]">
                  {microcopy.drill.riskExposure.kevFloorChip}
                </span>
              )}
            </div>
            <div className="mt-2 space-y-0">
              {v.risk_exposure_breakdown.map((c) => (
                <div
                  key={c.key}
                  className="flex items-center justify-between border-t border-border-subtle py-2 text-sm"
                  data-testid={`risk-exposure-row-${c.key}`}
                >
                  <span className="text-text-muted">{c.label}</span>
                  <span className="font-mono tabular-nums text-text">
                    {c.raw_value} · {c.points}/{c.max_points} pts
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-xs text-text-faint">
              {microcopy.drill.riskExposure.previewCaption}
            </p>
          </section>
        )}

        <section aria-labelledby="drill-hosts-h">
          <h4
            id="drill-hosts-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            {microcopy.drill.sections.hosts}
          </h4>
          <div className="font-mono text-sm text-text">{hostsLine}</div>
        </section>

        <section aria-labelledby="drill-desc-h">
          <h4
            id="drill-desc-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            {microcopy.drill.sections.description}
          </h4>
          <p className="text-sm text-text">{vulnDescriptionText}</p>
        </section>

        {/* Section Placement (UI-SPEC D-11): AI Explanation sits between
            Description and Remediation. drill-panel-mobile.tsx renders
            DrillContent directly, so this one insertion covers both desktop
            and mobile. */}
        <section aria-labelledby="drill-ai-h">
          <AiExplanationSection resourceType="vuln" resourceId={v.id ?? idOrCve} />
        </section>

        {/* Phase 26 (D-03/D-09, 26-UI-SPEC.md locked placement): "Prioritization"
            sits AFTER "AI Explanation" and BEFORE the raw scanner Remediation
            text -- the analyst reads what this vuln IS, then why it should
            jump the queue, before reading what the vendor says to do about
            it. Exactly 3 props (resourceType/resourceId/headingId) --
            onCopyToDescription is deliberately omitted (that affordance is
            scoped to the remediation-guidance mount only). drill-panel-
            mobile.tsx renders DrillContent directly, so this one insertion
            covers both desktop and mobile. */}
        <section aria-labelledby="drill-prioritization-h">
          <AiExplanationSection
            resourceType="prioritization"
            resourceId={v.id ?? idOrCve}
            headingId="drill-prioritization-h"
          />
        </section>

        <section aria-labelledby="drill-remed-h">
          <h4
            id="drill-remed-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            {microcopy.drill.sections.remediation}
          </h4>
          <p className="text-sm text-text">{remediation}</p>
        </section>

        {/* Phase 25 D-06 placement: "Remediation guidance" sits AFTER the
            raw scanner Remediation text and BEFORE Activity -- the analyst
            reads the vendor text first, then requests the OS/package-aware
            actionable interpretation of exactly that text ("cite before
            interpret", D-03). drill-panel-mobile.tsx renders DrillContent
            directly, so this one insertion covers both desktop and mobile.
            AIR-02's onCopyToDescription callback is intentionally NOT wired
            here -- that is Plans 06/07, after this tracer plan. */}
        <section aria-labelledby="drill-remediation-guidance-h">
          <AiExplanationSection
            resourceType="remediation-guidance"
            resourceId={v.id ?? idOrCve}
            headingId="drill-remediation-guidance-h"
            onCopyToDescription={setDescription}
          />
        </section>

        <section aria-labelledby="drill-activity-h">
          <h4
            id="drill-activity-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            {microcopy.drill.sections.activity}
          </h4>
          <p className="text-sm text-text-muted">
            {v.source ? `Detected by ${v.source}` : 'No activity recorded'}
            {v.last_seen_at
              ? ` · last seen ${new Date(v.last_seen_at).toLocaleDateString()}`
              : ''}
          </p>
        </section>

        {/* Phase 36 (SLA-03, D-07): escalation-fire history — an
            ActivityTimeline-style chronological list of every approaching/
            breach transition fired for this finding, audit-only (D-08: no
            retry affordance on a failed delivery row; the transition record
            itself always stays visible). Opens inside an already-loaded
            drill panel — the sub-list uses a plain muted "Loading…" text,
            matching this panel's own top-level loading treatment (line
            ~474), rather than a separate skeleton (UI-SPEC E3 loading). */}
        <section aria-labelledby="drill-escalations-h">
          <h4
            id="drill-escalations-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            Escalation history
          </h4>
          <EscalationHistoryList
            isPending={escalationsQuery.isPending}
            isError={escalationsQuery.isError}
            events={escalationsQuery.data ?? []}
          />
        </section>

        <section aria-labelledby="drill-actions-h">
          <h4
            id="drill-actions-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            {microcopy.drill.sections.actions}
          </h4>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              className="btn-cta inline-flex items-center justify-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
            >
              {microcopy.drill.createTicket}
            </button>
            <button
              type="button"
              onClick={fireSnooze}
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
            >
              {microcopy.drill.snooze24h}
            </button>
          </div>
        </section>
      </div>

      {/* D-P-04 confirmation. Mobile path can override via renderConfirm
          to nest the confirm inside Drawer.NestedRoot (Pitfall 7). */}
      {renderConfirm
        ? renderConfirm({
            open: confirmOpen,
            onConfirm: fireTicket,
            onCancel: cancelConfirm,
            cveLabel,
            ticketProvider,
            onProviderChange: setTicketProvider,
            description,
            onDescriptionChange: setDescription,
            title,
            onTitleChange: setTitle,
            gapFill,
          })
        : (
          <ConfirmModal
            open={confirmOpen}
            title={microcopy.ticket.confirmTitle(cveLabel)}
            message={microcopy.ticket.confirmBody}
            confirmLabel={microcopy.drill.createTicket}
            confirmDisabled={!ticketProvider}
            onConfirm={fireTicket}
            onCancel={cancelConfirm}
          >
            <TicketProviderPicker value={ticketProvider} onChange={setTicketProvider} />
            {/* Phase 27 (AID-01, Plan 02): shared "AI-drafted" caption,
                covering both the Title and Description fields below
                (27-UI-SPEC.md Copywriting Contract + Spacing Scale --
                sits once, above the Title field) -- supersedes Phase 25's
                field-scoped caption, now stale since Description composes
                from more than remediation guidance alone. */}
            <p className="mt-4 text-xs font-medium text-text-muted">
              AI-drafted — review before creating.
            </p>
            {/* Phase 27 (AID-01, Plan 02): editable Title, auto-composed
                DETERMINISTICALLY (D-01, zero AI call) on first open --
                27-UI-SPEC.md section 2. Subordinate to the provider picker
                above (UI-SPEC visual hierarchy); never a required field. */}
            <div className="mt-4">
              <label htmlFor="ticket-title-input" className="mb-1 block text-xs font-medium text-text-muted">
                Title
              </label>
              <Input
                id="ticket-title-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            {/* Phase 27 (AID-01, Plan 03): the compact "Draft with AI"
                gap-fill row -- at most two subordinate text-buttons (one per
                AI-sourced section currently missing from the composed body),
                role/key-gated (D-17), 8px gap when both render together
                (27-UI-SPEC.md §4). Renders NOTHING (not even the wrapper)
                when zero items are visible -- never an empty-looking
                placeholder row. */}
            {gapFill.rowVisible && (
              <div className="mt-4 flex flex-wrap items-start gap-2">
                {renderGapFillItem(gapFill.description, 'description')}
                {renderGapFillItem(gapFill.remediation, 'remediation')}
              </div>
            )}
            {/* Phase 25 (AIR-02): composed description body, subordinate to
                the provider picker + Title above (UI-SPEC visual
                hierarchy). Phase 27 (AID-01, Plan 02) widens the pre-fill
                from remediation-guidance-only to the full multi-section
                compose (Description / Remediation / Asset context /
                Prioritization) -- label + placeholder updated per the
                27-UI-SPEC.md Copywriting Contract (supersedes the stale
                Phase 25 copy). Never a required field (D-09). */}
            <div className="mt-4">
              <label htmlFor="ticket-description-textarea" className="mb-1 block text-xs font-medium text-text-muted">
                Description
              </label>
              <Textarea
                id="ticket-description-textarea"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="No AI draft available yet — add a description or leave blank."
                rows={4}
              />
            </div>
          </ConfirmModal>
        )}
    </div>
  );
});
