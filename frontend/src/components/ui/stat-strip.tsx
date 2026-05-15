'use client';
import { Children, type HTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

// D-P-03 + D-M-02: Responsive grid for 1–6 Stat children.
// - Mobile  (≤640px): 1 column
// - Tablet  (768–1279px): 2 columns
// - Desktop (≥1280px): N columns where N = child count, capped at 4
//
// Caller does NOT manage breakpoint columns — StatStrip owns the ladder.
// Tailwind needs literal class names to tree-shake, so we map count → class
// rather than templating xl:grid-cols-${count}.

export type StatStripProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
};

export function StatStrip({ children, className, ...rest }: StatStripProps) {
  const count = Children.count(children);
  const desktop = Math.min(count, 4);
  const desktopClass =
    desktop <= 1
      ? 'xl:grid-cols-1'
      : desktop === 2
      ? 'xl:grid-cols-2'
      : desktop === 3
      ? 'xl:grid-cols-3'
      : 'xl:grid-cols-4';
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-4 md:grid-cols-2',
        desktopClass,
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
