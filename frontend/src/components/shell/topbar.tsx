'use client';
import { forwardRef } from 'react';
import { Search, Bell, HelpCircle, Menu } from 'lucide-react';
import { UserChip } from './user-chip';

type TopbarProps = {
  /** Called when the tablet hamburger is clicked (768–999px only) */
  onMenuClick?: () => void;
  /** Forwarded ref for the hamburger button — used to restore focus after drawer closes */
  hamburgerRef?: React.RefObject<HTMLButtonElement | null>;
};

export function Topbar({ onMenuClick, hamburgerRef }: TopbarProps) {
  return (
    <header className="flex h-14 items-center gap-3 border-b border-border bg-bg px-4 lg:px-6">
      {/* Hamburger — tablet-only (768–999px): hidden <768px (bottom-nav covers phone),
          hidden >=1000px (sidebar covers desktop). Only rendered when onMenuClick provided. */}
      {onMenuClick && (
        <button
          ref={hamburgerRef}
          type="button"
          aria-label="Open navigation menu"
          onClick={onMenuClick}
          className="hidden min-[768px]:max-[999px]:inline-flex items-center justify-center rounded-md p-2 text-text-muted hover:text-text hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet"
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
      )}

      {/* Search field — D-37 visual only, no onSubmit */}
      <div className="flex flex-1 max-w-md items-center gap-2 rounded-md border border-border-subtle bg-surface px-3 py-1.5">
        <Search className="h-4 w-4 text-text-faint" aria-hidden />
        <input
          type="text"
          placeholder="Search…"
          className="flex-1 bg-transparent text-sm text-text placeholder:text-text-faint focus:outline-none"
          aria-label="Search"
          readOnly
        />
        <kbd className="hidden sm:inline-flex items-center gap-1 rounded border border-border-subtle bg-bg-darker px-1.5 py-0.5 text-[10px] font-mono text-text-faint">
          <span>⌘</span><span>K</span>
        </kbd>
      </div>

      {/* Spacer push right */}
      <div className="flex-1" />

      {/* Bell + Help — D-37 visual only. Hidden below sm (640px) so the phone
          topbar (search + avatar) fits without horizontal overflow at 360/390px. */}
      <button
        type="button"
        aria-label="Notifications"
        className="hidden sm:inline-flex rounded-md p-2 text-text-muted hover:text-text hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet"
      >
        <Bell className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label="Help"
        className="hidden sm:inline-flex rounded-md p-2 text-text-muted hover:text-text hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet"
      >
        <HelpCircle className="h-4 w-4" aria-hidden />
      </button>

      <UserChip />
    </header>
  );
}
