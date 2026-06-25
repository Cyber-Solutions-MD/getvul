'use client';
import { useState, useRef } from 'react';
import type { ReactNode } from 'react';
import { Sidebar } from './sidebar';
import { Topbar } from './topbar';
import { BottomNav } from './bottom-nav';
import { NavDrawer } from './nav-drawer';

export function AppShell({ children }: { children: ReactNode }) {
  // Tablet drawer open state — lifted here so Topbar's hamburger and NavDrawer share it.
  const [drawerOpen, setDrawerOpen] = useState(false);
  // Hamburger ref — passed to Topbar and NavDrawer so focus is restored after close.
  const hamburgerRef = useRef<HTMLButtonElement>(null);

  return (
    <div className="min-h-screen bg-bg text-text">
      {/* Tablet slide-in drawer (768–999px) — rendered outside the flex row so it
          overlays independently. Kept mounted with translate for motion-safe transition. */}
      <NavDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        hamburgerRef={hamburgerRef}
      />

      {/* Desktop (>=1000px): 220px sidebar + flexible main. Viewports <=999px: sidebar hidden per D-41 verbatim. */}
      <div className="flex">
        <Sidebar />
        <div className="flex-1 min-w-0">
          <Topbar
            onMenuClick={() => setDrawerOpen(true)}
            hamburgerRef={hamburgerRef}
          />
          {/* main bottom padding on phone clears the fixed bottom-nav bar.
              calc(64px + env(safe-area-inset-bottom)) = approx bar height + safe area.
              At 768px+ the bottom-nav is hidden so revert to standard py-6.
              Desktop lg:px-8 / lg:py-8 padding preserved as-is. */}
          <main className="px-6 py-6 lg:px-8 lg:py-8 pb-[calc(64px+env(safe-area-inset-bottom))] min-[768px]:pb-6">
            {children}
          </main>
        </div>
      </div>

      {/* Phone bottom-nav (< 768px) — fixed to the bottom via its own classes.
          Rendered once at shell level so it persists across all authenticated routes. */}
      <BottomNav />
    </div>
  );
}
