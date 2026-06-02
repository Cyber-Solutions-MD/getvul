'use client';
import { useEffect, useRef } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { DrillContent } from './drill-content';

// UX-03-03 + D-P-01/02/05/06 — desktop 420px right-aside drill panel.
// Open/close state lives in the URL (`?cve=<id>&open=drill`); the page
// passes the `cveId` through but the panel reads the open key itself so
// Esc / clickaway / × can flip it without coupling to the parent.
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
  // Aria label for the aside. Defaults to 'Vulnerability detail'.
  ariaLabel?: string;
  // Optional origin row ref — when supplied, focus returns there on close.
  originRowRef?: React.RefObject<HTMLElement | null> | null;
};

export function DrillPanel({ cveId, id, idKey, renderContent, ariaLabel, originRowRef }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const panelRef = useRef<HTMLElement>(null);

  // Resolve effective entity id and URL key with vuln-preserving defaults.
  const effectiveId = id ?? cveId ?? null;
  const key = idKey ?? 'cve';

  // Open is URL-driven (D-P-02). When `?open=drill` is present AND we have
  // an id to render against, the panel mounts. Removing `?open=drill`
  // (via × / Esc / clickaway) closes it.
  const isOpen = params?.get('open') === 'drill' && effectiveId !== null;

  const close = () => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    sp.delete('open');
    sp.delete(key);
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), {
      scroll: false,
    });
    // D-P-06 — return focus to originating row on close.
    originRowRef?.current?.focus();
  };

  // D-P-01 — Esc closes
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // D-P-01 — outside-click closes. mousedown (not click) so the listener
  // fires before any in-panel buttons receive their click. The same-tick
  // opening event is gated by the `isOpen` guard: the panel only mounts
  // (and the listener only attaches) AFTER the URL has flipped to
  // `?open=drill`, which itself happens through router.replace — a
  // separate frame from the original row-click. No setTimeout indirection
  // needed (Pitfall 4 only matters if open is driven by a synchronous
  // useState toggle in the same handler that consumes the row click).
  useEffect(() => {
    if (!isOpen) return;
    const onMouseDown = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        close();
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen || !effectiveId) return null;

  return (
    <aside
      ref={panelRef}
      role="dialog"
      aria-modal="false"
      aria-label={ariaLabel ?? 'Vulnerability detail'}
      data-drill-panel=""
      className="fixed right-0 top-0 z-30 h-full w-[420px] border-l border-border bg-surface shadow-elevated"
    >
      {renderContent
        ? renderContent({ id: effectiveId, onClose: close })
        : <DrillContent idOrCve={effectiveId} onClose={close} />}
    </aside>
  );
}
