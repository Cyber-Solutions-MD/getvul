'use client';
import { useUrlState } from '@/hooks/use-url-state';
import { microcopy } from './microcopy';
import { cn } from '@/lib/utils';

// D-V-01 — By CVE / By Host segmented toggle. Switching only changes ?group=;
// severity / source / status / search are independent URL keys and survive.

const GROUPS = ['cve', 'host'] as const;
type Group = (typeof GROUPS)[number];

export function ViewToggle() {
  const [group, setGroup] = useUrlState<Group>('group', GROUPS, 'cve');

  return (
    <div
      role="group"
      aria-label="View grouping"
      className="inline-flex rounded-full border border-border-subtle bg-surface p-0.5"
    >
      <button
        type="button"
        onClick={() => setGroup('cve')}
        aria-pressed={group === 'cve'}
        className={cn(
          'rounded-full px-3 py-1 text-xs font-medium transition-colors',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
          group === 'cve'
            ? 'bg-surface-2 text-text'
            : 'text-text-muted hover:text-text',
        )}
      >
        {microcopy.viewToggle.byCve}
      </button>
      <button
        type="button"
        onClick={() => setGroup('host')}
        aria-pressed={group === 'host'}
        className={cn(
          'rounded-full px-3 py-1 text-xs font-medium transition-colors',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
          group === 'host'
            ? 'bg-surface-2 text-text'
            : 'text-text-muted hover:text-text',
        )}
      >
        {microcopy.viewToggle.byHost}
      </button>
    </div>
  );
}
