'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/states';
import { microcopy } from './microcopy';

// WR-14: `Date.toLocaleString()` is timezone-AND-locale dependent. The
// SSR (Node) and CSR (browser) values diverge whenever Node and the
// browser disagree on either, producing a hydration warning in
// production logs plus a brief flicker for the user. Render '—' on the
// server / first client render, then refresh to the formatted string
// after mount. Same approach as ActivityFeed's <RelativeTime>.
function LocalizedTimestamp({ iso }: { iso: string }) {
  const [formatted, setFormatted] = useState<string>('—');
  useEffect(() => {
    try {
      setFormatted(new Date(iso).toLocaleString());
    } catch {
      // Bad ISO — keep the em-dash placeholder rather than crashing
      // the panel.
    }
  }, [iso]);
  return <>{formatted}</>;
}

// D-O-01..04: Onboarding full-page panels for 'no_scanners' and 'no_data_yet'
// states. Phase 11 D-S-06 retrofit: chrome is delegated to <EmptyState>
// (canonical compound primitive) rather than hand-rolled <section>.

type OnboardingPanelProps = {
  state: 'no_scanners' | 'no_data_yet';
  lastSyncAt?: string | null;
  onRefresh?: () => void;
};

export function OnboardingPanel({ state, lastSyncAt, onRefresh }: OnboardingPanelProps) {
  if (state === 'no_scanners') {
    return (
      <EmptyState aria-labelledby="onb-h">
        <EmptyState.Title id="onb-h" className="text-2xl">
          {microcopy.onboarding.noScannersTitle}
        </EmptyState.Title>
        <EmptyState.Body>{microcopy.onboarding.noScannersBody}</EmptyState.Body>
        <EmptyState.Actions>
          <Button asChild variant="cta">
            <Link href="/dashboard/connectors">{microcopy.onboarding.noScannersCta}</Link>
          </Button>
        </EmptyState.Actions>
      </EmptyState>
    );
  }

  return (
    <EmptyState aria-labelledby="onb-h">
      <EmptyState.Title id="onb-h" className="text-2xl">
        {microcopy.onboarding.noDataYetTitle}
      </EmptyState.Title>
      <EmptyState.Body>{microcopy.onboarding.noDataYetBody}</EmptyState.Body>
      {lastSyncAt && (
        <p className="mt-1 font-mono text-xs text-text-muted">
          Last sync attempted: <LocalizedTimestamp iso={lastSyncAt} />
        </p>
      )}
      <EmptyState.Actions>
        <Button variant="secondary" onClick={onRefresh}>
          {microcopy.onboarding.noDataYetCta}
        </Button>
      </EmptyState.Actions>
    </EmptyState>
  );
}
