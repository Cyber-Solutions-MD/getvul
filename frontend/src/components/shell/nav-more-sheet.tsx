'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Drawer } from 'vaul';
import { cn } from '@/lib/utils';
import { MORE_ITEMS, isActive } from './nav-items';

// Vaul bottom sheet listing the 6 secondary destinations (D-06):
// Assets, CSPM, Rules, Connectors, Users, Settings.
// Follows the drill-panel-mobile.tsx precedent exactly:
//   Drawer.Root → Drawer.Portal → Drawer.Overlay + Drawer.Content → Drawer.Title sr-only
// When !open, return null so no lingering portal/dialog role chrome remains in the DOM.

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

export function NavMoreSheet({ open, onOpenChange }: Props) {
  const pathname = usePathname();

  // Match drill-panel-mobile guard: closed state leaves no portal chrome in DOM
  if (!open) return null;

  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange} direction="bottom">
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-[9000] bg-bg-darker/60" />
        <Drawer.Content
          className="fixed inset-x-0 bottom-0 z-[9001] rounded-t-lg border-t border-border-subtle bg-surface"
          aria-label="More navigation"
        >
          <Drawer.Title className="sr-only">More navigation</Drawer.Title>

          {/* Sheet handle bar (visual affordance) */}
          <div className="mx-auto mt-3 mb-2 h-1 w-10 rounded-full bg-border" aria-hidden />

          <nav aria-label="Secondary navigation" className="pb-6">
            <ul className="px-3">
              {MORE_ITEMS.map((item) => {
                const active = isActive(pathname, item);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? 'page' : undefined}
                      onClick={() => onOpenChange(false)}
                      className={cn(
                        'group relative flex items-center gap-3 rounded-md px-3 py-3 text-sm transition-colors',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet',
                        active
                          ? 'text-text bg-surface-2'
                          : 'text-text-muted hover:text-text hover:bg-surface/60',
                      )}
                    >
                      {/* Gradient active strip on the left edge, like the sidebar */}
                      {active && (
                        <span
                          aria-hidden
                          className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r bg-gradient-sunset-vertical"
                        />
                      )}
                      <Icon className="h-5 w-5 shrink-0" aria-hidden />
                      <span className="flex-1">{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
