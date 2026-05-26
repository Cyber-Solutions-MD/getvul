'use client';
import { useEffect } from 'react';
import { Drawer } from 'vaul';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { DrillContent } from './drill-content';
import { useMediaQuery } from '@/hooks/use-media-query';
import { microcopy } from './microcopy';

// UX-03-06 + D-P-03 — mobile bottom-sheet variant of the drill panel.
// Renders ONLY at <900px (Pitfall 3 — desktop branch covers >=900px).
// Open state is URL-driven (?open=drill), same as DrillPanel desktop.
// Nested confirmation uses Drawer.NestedRoot (Pitfall 7 — vaul Esc cascade).

type Props = {
  cveId: string | null;
};

export function DrillPanelMobile({ cveId }: Props) {
  const isMobile = useMediaQuery('(max-width: 899px)');
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const openFromUrl =
    params?.get('open') === 'drill' && cveId !== null;
  const open = isMobile && openFromUrl;

  const close = () => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    sp.delete('open');
    sp.delete('cve');
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
          aria-label="Vulnerability detail"
        >
          <Drawer.Title className="sr-only">Vulnerability detail</Drawer.Title>
          {cveId && (
            <DrillContent
              idOrCve={cveId}
              onClose={close}
              renderConfirm={({ open: confirmOpen, onConfirm, onCancel, cveLabel }) => {
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
                          className="rounded-md bg-gradient-sunset px-3 py-1.5 text-sm font-medium text-text-inverse shadow-glow-cta"
                        >
                          {microcopy.drill.createTicket}
                        </button>
                      </div>
                    </div>
                  </Drawer.NestedRoot>
                );
              }}
            />
          )}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
