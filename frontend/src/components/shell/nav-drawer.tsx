'use client';
import { useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { ALL_ITEMS, isActive } from './nav-items';
import { getFocusable, trapTabKey } from '@/components/ui/focus-trap';

// Tablet (768–999px) slide-in navigation drawer (D-05).
// Opened by the hamburger button in Topbar (AppShell lifts state).
// Lists all 9 destinations from ALL_ITEMS with icon + label + gradient-strip active state.
//
// a11y:
// - aria-label="Navigation menu" (distinct from sidebar's "Primary navigation" to avoid
//   landmark-unique axe violation — Pitfall 3)
// - Focus trap: Tab/Shift+Tab cycles within the drawer panel while open
// - Esc calls onClose (matches ConfirmModal pattern)
// - On open: first link is focused; on close: focus is returned to the hamburger button
//   (caller passes hamburgerRef for restore; AppShell stores the ref)
//
// Reduced motion: slide uses motion-safe:transition-transform so users with
// prefers-reduced-motion: reduce get an instant toggle (no transform transition fires).
// The globals.css blanket already covers transition-duration as a fallback.

type Props = {
  open: boolean;
  onClose: () => void;
  /** Ref to the hamburger button so focus can be restored on close */
  hamburgerRef?: React.RefObject<HTMLButtonElement | null>;
};

export function NavDrawer({ open, onClose, hamburgerRef }: Props) {
  const pathname = usePathname();
  const panelRef = useRef<HTMLElement>(null);
  const lastFocusRef = useRef<Element | null>(null);

  // Capture focus target before drawer opens so we can restore it on close
  useEffect(() => {
    if (open) {
      lastFocusRef.current = document.activeElement;
      // Focus the first focusable element in the drawer
      const raf = requestAnimationFrame(() => {
        if (panelRef.current) {
          const focusable = getFocusable(panelRef.current);
          if (focusable.length > 0) {
            focusable[0].focus();
          }
        }
      });
      return () => cancelAnimationFrame(raf);
    } else {
      // Restore focus to hamburger (or previous active element as fallback)
      if (hamburgerRef?.current) {
        hamburgerRef.current.focus();
      } else if (lastFocusRef.current && typeof (lastFocusRef.current as HTMLElement).focus === 'function') {
        (lastFocusRef.current as HTMLElement).focus();
      }
    }
  }, [open, hamburgerRef]);

  // Keyboard handlers: Tab trap + Esc close
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key === 'Tab' && panelRef.current) {
        const focusable = getFocusable(panelRef.current);
        trapTabKey(e, focusable);
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  // Keep mounted with translate so enter/exit transition works.
  // When closed: aria-hidden + pointer-events-none so screen readers and
  // mouse cannot interact with the invisible drawer.
  return (
    <>
      {/* Backdrop — only interactive when open */}
      {open && (
        <div
          className="fixed inset-0 z-[9000] bg-bg-darker/60"
          aria-hidden
          onClick={onClose}
        />
      )}

      {/* Slide-in panel — kept mounted; reduced-motion-safe transition via motion-safe: prefix */}
      <nav
        ref={panelRef}
        aria-label="Navigation menu"
        aria-hidden={!open}
        className={cn(
          'fixed inset-y-0 left-0 z-[9001] w-[280px] bg-bg-darker border-r border-border overflow-y-auto',
          'motion-safe:transition-transform motion-safe:[transition-duration:220ms] motion-safe:[transition-timing-function:cubic-bezier(0,0,0,1)]',
          open ? 'translate-x-0' : '-translate-x-full',
          !open && 'pointer-events-none',
        )}
      >
        <div className="px-3 py-4">
          <ul className="space-y-0.5">
            {ALL_ITEMS.map((item) => {
              const active = isActive(pathname, item);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={onClose}
                    tabIndex={open ? undefined : -1}
                    className={cn(
                      'group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet',
                      active
                        ? 'text-text bg-surface'
                        : 'text-text-muted hover:text-text hover:bg-surface/60',
                    )}
                  >
                    {/* Gradient active strip on the left edge, consistent with sidebar */}
                    {active && (
                      <span
                        aria-hidden
                        className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r bg-gradient-sunset-vertical"
                      />
                    )}
                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                    <span className="flex-1">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>
    </>
  );
}
