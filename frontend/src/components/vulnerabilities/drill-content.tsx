'use client';
import { forwardRef, useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { useVulnerabilityDetail } from '@/lib/queries/use-vulnerability-detail';
import { useCreateTicketMutation } from '@/lib/mutations/use-create-ticket';
import { useSnoozeMutation } from '@/lib/mutations/use-snooze';
import { useToast } from '@/components/ui/ToastProvider';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { TicketProviderPicker } from './ticket-provider-picker';
import type { TicketProvider } from '@/lib/ticketing/providers';
import { microcopy } from './microcopy';
import { cn } from '@/lib/utils';
// 24-09 Task 1: AiExplanationSection moved to the shared, view-agnostic
// components/ai/ directory (D-15) so the host/remediation views can mount
// it verbatim alongside this vuln drill.
import { AiExplanationSection } from '@/components/ai/ai-explanation-section';

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
};

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

  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const panelInteractivesRef = useRef<HTMLDivElement>(null);

  // D-P-06 — focus moves to the close button on mount. Using a ref +
  // useEffect rather than the `autoFocus` JSX prop so the focus call
  // happens synchronously in jsdom (which doesn't honor autoFocus
  // consistently across React versions).
  useEffect(() => {
    closeBtnRef.current?.focus();
  }, [idOrCve]);

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

  const v = q.data as unknown as FlexibleDetail;
  const cveLabel = v.cve_id ?? v.id ?? idOrCve;
  const description =
    v.description ?? v.vulnerability_name ?? v.title ?? '—';
  const remediation = v.remediation ?? v.remediation_info ?? '—';
  const hostsLine =
    v.affected_hosts && v.affected_hosts.length > 0
      ? v.affected_hosts.map((h) => h.host ?? h.ip ?? '—').join(', ')
      : (v.asset_hostname ?? '—');
  const sevLower = (v.severity ?? '').toString().toLowerCase();
  const sevLabel =
    sevLower.length > 0
      ? sevLower.charAt(0).toUpperCase() + sevLower.slice(1)
      : '—';

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
          <p className="text-sm text-text">{description}</p>
        </section>

        {/* Section Placement (UI-SPEC D-11): AI Explanation sits between
            Description and Remediation. drill-panel-mobile.tsx renders
            DrillContent directly, so this one insertion covers both desktop
            and mobile. */}
        <section aria-labelledby="drill-ai-h">
          <AiExplanationSection resourceType="vuln" resourceId={v.id ?? idOrCve} />
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
          </ConfirmModal>
        )}
    </div>
  );
});
