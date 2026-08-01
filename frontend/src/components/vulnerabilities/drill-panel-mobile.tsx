'use client';
import { useEffect } from 'react';
import { Drawer } from 'vaul';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { DrillContent } from './drill-content';
import type { GapFillDescriptor } from './drill-content';
import { TicketProviderPicker } from './ticket-provider-picker';
import { useMediaQuery } from '@/hooks/use-media-query';
import { microcopy } from './microcopy';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
// Phase 27 (AID-01, Plan 03): the gap-fill row's in-flight state reuses the
// exact exported AnalyzingIndicator pulsing-dot (D-12) -- never a second
// spinner. Same import drill-content.tsx uses.
import { AnalyzingIndicator } from '@/components/ai/ai-explanation-section';

// Phase 27 (AID-01, Plan 03, 27-UI-SPEC.md §4): renders ONE gap-fill row
// item from its threaded descriptor. This is a DUPLICATE of
// drill-content.tsx's own renderGapFillItem (not an import) -- mobile is a
// genuinely separate render path (Pitfall 5, never imports the desktop
// confirm-dialog primitive), and the locked caption/trigger strings must
// appear literally in THIS file's source (matches the established Pitfall
// 6 precedent: hardcode inline, duplicated in both files, rather than
// share JSX cross-file). Only the STATE (visible/phase/onClick/canRaiseCap)
// is shared, via the
// threaded `gapFill` descriptor computed once in DrillContent.
function renderGapFillItem(
  item: GapFillDescriptor['description'],
  kind: 'description' | 'remediation',
) {
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

// UX-03-06 + D-P-03 — mobile bottom-sheet variant of the drill panel.
// Renders ONLY at <900px (Pitfall 3 — desktop branch covers >=900px).
// Open state is URL-driven (?open=drill), same as DrillPanel desktop.
// Nested confirmation uses Drawer.NestedRoot (Pitfall 7 — vaul Esc cascade).
//
// D-D-02 (additive refactor): generalized with a content slot + parameterized
// URL key. Existing vuln callers pass only `cveId` → identical behavior
// (idKey defaults to 'cve', content defaults to <DrillContent>).

type Props = {
  // Back-compat alias: vuln callers keep using cveId unchanged.
  cveId?: string | null;
  // Generic entity id — takes precedence over cveId when both provided.
  id?: string | null;
  // URL param key that holds the entity id. Defaults to 'cve' so existing
  // `?cve=...&open=drill` contracts are preserved.
  idKey?: string;
  // Content slot — when provided, replaces the default <DrillContent>.
  // Receives the resolved id and the close handler.
  renderContent?: (args: { id: string; onClose: () => void }) => React.ReactNode;
  // Aria label for the drawer content. Defaults to 'Vulnerability detail'.
  ariaLabel?: string;
};

export function DrillPanelMobile({ cveId, id, idKey, renderContent, ariaLabel }: Props) {
  const isMobile = useMediaQuery('(max-width: 899px)');
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // Resolve effective entity id and URL key with vuln-preserving defaults.
  const effectiveId = id ?? cveId ?? null;
  const key = idKey ?? 'cve';

  const openFromUrl =
    params?.get('open') === 'drill' && effectiveId !== null;
  const open = isMobile && openFromUrl;

  const close = () => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    sp.delete('open');
    sp.delete(key);
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), {
      scroll: false,
    });
  };

  // D-P-01 (mobile parity) — Esc closes. vaul handles Esc internally via
  // its dialog primitive, but jsdom does not propagate the cascade
  // reliably. Add a document-level listener so test parity with desktop
  // holds; the listener only attaches while the drawer is open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!isMobile) return null;
  // When the drawer is closed, render nothing — vaul keeps some chrome
  // mounted under `open={false}` (focus guards / portal stubs) which
  // breaks the `queryByRole('dialog') === null` contract from the test.
  if (!open) return null;

  const resolvedAriaLabel = ariaLabel ?? 'Vulnerability detail';

  return (
    <Drawer.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) close();
      }}
      direction="bottom"
    >
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-[9000] bg-bg-darker/60" />
        <Drawer.Content
          className="fixed inset-x-0 bottom-0 z-[9001] h-[92dvh] rounded-t-lg border-t border-border-subtle bg-surface"
          aria-label={resolvedAriaLabel}
        >
          <Drawer.Title className="sr-only">{resolvedAriaLabel}</Drawer.Title>
          {effectiveId && (
            renderContent
              ? renderContent({ id: effectiveId, onClose: close })
              : (
                <DrillContent
                  idOrCve={effectiveId}
                  onClose={close}
                  renderConfirm={({
                    open: confirmOpen,
                    onConfirm,
                    onCancel,
                    cveLabel,
                    ticketProvider,
                    onProviderChange,
                    description,
                    onDescriptionChange,
                    title,
                    onTitleChange,
                    gapFill,
                  }) => {
                    if (!confirmOpen) return null;
                    // Pitfall 7 — nested confirmation inside the drawer. Vaul's
                    // `Drawer.NestedRoot` is the canonical pattern; the test
                    // expects an additional `role="dialog"` node, so we use a
                    // NestedRoot here for the rich gesture inheritance and
                    // fall back to a plain role="dialog" surface inside its
                    // Content (jsdom doesn't always promote NestedRoot itself
                    // to a dialog role, so the inner aside guarantees the
                    // second-dialog contract).
                    return (
                      <Drawer.NestedRoot
                        open={confirmOpen}
                        onOpenChange={(o) => {
                          if (!o) onCancel();
                        }}
                        direction="bottom"
                      >
                        <div
                          role="dialog"
                          aria-modal="true"
                          aria-label="Confirm create ticket"
                          className="fixed inset-x-0 bottom-0 z-[9101] rounded-t-lg border-t border-border-subtle bg-surface p-5"
                        >
                          <h3 className="text-base font-semibold text-text">
                            {microcopy.ticket.confirmTitle(cveLabel)}
                          </h3>
                          <p className="mt-2 text-sm text-text-muted">
                            {microcopy.ticket.confirmBody}
                          </p>
                          <div className="mt-4">
                            <TicketProviderPicker
                              value={ticketProvider}
                              onChange={onProviderChange}
                            />
                          </div>
                          {/* Phase 27 (AID-01, Plan 03): mirrors the
                              desktop confirm dialog's Phase 27 insertion
                              exactly -- shared "AI-drafted" caption
                              (supersedes Phase 25's field-scoped caption
                              below), editable Title Input, the gap-fill row
                              (rendered from the threaded descriptor -- same
                              gating/copy/append behavior as desktop, no
                              separate logic), then the composed Description
                              Textarea (updated label/placeholder). Mobile
                              builds its own Drawer.NestedRoot markup
                              (Pitfall 5), never imports the desktop
                              confirm-dialog primitive. */}
                          <p className="mt-4 text-xs font-medium text-text-muted">
                            AI-drafted — review before creating.
                          </p>
                          <div className="mt-4">
                            <label
                              htmlFor="ticket-title-input-mobile"
                              className="mb-1 block text-xs font-medium text-text-muted"
                            >
                              Title
                            </label>
                            <Input
                              id="ticket-title-input-mobile"
                              value={title}
                              onChange={(e) => onTitleChange(e.target.value)}
                            />
                          </div>
                          {gapFill.rowVisible && (
                            <div className="mt-4 flex flex-wrap items-start gap-2">
                              {renderGapFillItem(gapFill.description, 'description')}
                              {renderGapFillItem(gapFill.remediation, 'remediation')}
                            </div>
                          )}
                          <div className="mt-4">
                            <label
                              htmlFor="ticket-description-textarea-mobile"
                              className="mb-1 block text-xs font-medium text-text-muted"
                            >
                              Description
                            </label>
                            <Textarea
                              id="ticket-description-textarea-mobile"
                              value={description}
                              onChange={(e) => onDescriptionChange(e.target.value)}
                              placeholder="No AI draft available yet — add a description or leave blank."
                              rows={4}
                            />
                          </div>
                          <div className="mt-4 flex justify-end gap-2">
                            <button
                              type="button"
                              onClick={onCancel}
                              className="rounded-md border border-border-subtle bg-surface-2 px-3 py-1.5 text-sm text-text-muted hover:text-text"
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              onClick={onConfirm}
                              disabled={ticketProvider === null}
                              className="rounded-md bg-gradient-sunset px-3 py-1.5 text-sm font-medium text-text-inverse shadow-glow-cta disabled:opacity-50 disabled:pointer-events-none"
                            >
                              {microcopy.drill.createTicket}
                            </button>
                          </div>
                        </div>
                      </Drawer.NestedRoot>
                    );
                  }}
                />
              )
          )}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
