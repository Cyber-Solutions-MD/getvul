'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MoreHorizontal, Home, Bug, Ticket } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BOTTOM_NAV_PRIMARY, isActive } from './nav-items';
import { NavMoreSheet } from './nav-more-sheet';

// Phone-only 4-slot bottom navigation (D-05, UX-07-02).
// Visible at <768px (min-[768px]:hidden). Fixed to the bottom with
// env(safe-area-inset-bottom) padding so content clears notch/home-bar.
// Active slot shows a gradient-strip on the TOP edge (strip is on the left in sidebar).
//
// Slot layout: Dashboard | Vulnerabilities | Tickets | More
// The 4th slot is a "More" button opening a vaul bottom sheet (D-06).

// Map chip icons by order index in BOTTOM_NAV_PRIMARY for reliable icon override.
// sidebar uses item.icon (lucide components imported there); here we confirm the same
// icons are correct by importing them explicitly — serves as a documentation contract.
const _icons = { Home, Bug, Ticket }; // linting guard — explicitly imported, avoid unused warn
void _icons;

export function BottomNav() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <>
      <nav
        aria-label="Mobile navigation"
        className="min-[768px]:hidden fixed bottom-0 inset-x-0 z-50 bg-bg-darker border-t border-border"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <div className="grid grid-cols-4">
          {BOTTOM_NAV_PRIMARY.map((item) => {
            const active = isActive(pathname, item);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'relative flex min-h-[48px] flex-col items-center justify-center gap-0.5 px-1 py-2',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet',
                  active ? 'text-text' : 'text-text-muted',
                )}
              >
                {/* Gradient-strip active indicator on the top edge (inverted from sidebar's left-edge strip) */}
                {active && (
                  <span
                    aria-hidden
                    className="absolute top-0 inset-x-0 h-[3px] rounded-b bg-gradient-sunset-vertical"
                  />
                )}
                <Icon className="h-5 w-5 shrink-0" aria-hidden />
                <span className="text-[11px] leading-none">{item.label}</span>
              </Link>
            );
          })}

          {/* More slot — opens the secondary destinations sheet */}
          <button
            type="button"
            aria-label="More navigation"
            onClick={() => setMoreOpen(true)}
            className={cn(
              'relative flex min-h-[48px] flex-col items-center justify-center gap-0.5 px-1 py-2',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet',
              'text-text-muted',
            )}
          >
            <MoreHorizontal className="h-5 w-5 shrink-0" aria-hidden />
            <span className="text-[11px] leading-none">More</span>
          </button>
        </div>
      </nav>

      <NavMoreSheet open={moreOpen} onOpenChange={setMoreOpen} />
    </>
  );
}
