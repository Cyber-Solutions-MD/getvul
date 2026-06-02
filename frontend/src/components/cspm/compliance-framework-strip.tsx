'use client';
/**
 * ComplianceFrameworkStrip — horizontal rail of compliance framework pass-rate cells.
 *
 * Renders one compact cell per framework:
 *   - Framework name
 *   - pass_rate as "{n}%"
 *   - Thin progress bar (bg-severity-low for the passed portion)
 *
 * Sunset tokens only. No raw palette colors.
 * data-framework-strip attribute for test hooks.
 *
 * Plan 14-03.
 */
import React from 'react';
import { cn } from '@/lib/utils';

export type FrameworkData = {
  name: string;
  total_controls: number;
  passed: number;
  failed: number;
  suppressed: number;
  pass_rate: number;
};

export type ComplianceFrameworkStripProps = {
  frameworks: FrameworkData[];
  className?: string;
};

export function ComplianceFrameworkStrip({ frameworks, className }: ComplianceFrameworkStripProps) {
  return (
    <div
      data-framework-strip
      className={cn(
        'flex gap-3 overflow-x-auto rounded-lg border border-border-subtle bg-surface px-3 py-2',
        className,
      )}
    >
      {frameworks.length === 0 ? (
        <span className="text-xs text-text-faint py-0.5">No compliance data</span>
      ) : (
        frameworks.map((fw) => (
          <div
            key={fw.name}
            className="flex min-w-[120px] shrink-0 flex-col gap-1.5 rounded border border-border-subtle bg-surface-2 px-3 py-2"
          >
            {/* Framework name */}
            <p className="text-xs font-medium text-text truncate" title={fw.name}>
              {fw.name}
            </p>

            {/* Pass rate percentage */}
            <p className="font-mono text-sm font-semibold text-severity-low">
              {Math.round(fw.pass_rate)}%
            </p>

            {/* Progress bar */}
            <div className="h-1 w-full overflow-hidden rounded-full bg-border-subtle">
              <div
                className="h-full rounded-full bg-severity-low"
                style={{ width: `${Math.min(100, Math.max(0, fw.pass_rate))}%` }}
              />
            </div>

            {/* Controls count */}
            <p className="text-[10px] text-text-faint">
              {fw.passed}/{fw.total_controls} controls
            </p>
          </div>
        ))
      )}
    </div>
  );
}
