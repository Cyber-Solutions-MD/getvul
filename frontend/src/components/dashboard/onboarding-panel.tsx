'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
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
// states. Replaces the entire dashboard when stats.onboarding_state matches.

type OnboardingPanelProps = {
  state: 'no_scanners' | 'no_data_yet';
  lastSyncAt?: string | null;
  onRefresh?: () => void;
};

export function OnboardingPanel({ state, lastSyncAt, onRefresh }: OnboardingPanelProps) {
  if (state === 'no_scanners') {
    return (
      <section
        aria-labelledby="onb-h"
        className="mx-auto max-w-xl rounded-lg border border-border-subtle bg-surface p-10 text-center"
      >
        <h2 id="onb-h" className="text-2xl font-semibold text-text">
          {microcopy.onboarding.noScannersTitle}
        </h2>
        <p className="mt-3 text-text-muted">{microcopy.onboarding.noScannersBody}</p>
        <div className="mt-6 flex justify-center">
          <Button asChild variant="cta">
            <Link href="/dashboard/connectors">{microcopy.onboarding.noScannersCta}</Link>
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="onb-h"
      className="mx-auto max-w-xl rounded-lg border border-border-subtle bg-surface p-10 text-center"
    >
      <h2 id="onb-h" className="text-2xl font-semibold text-text">
        {microcopy.onboarding.noDataYetTitle}
      </h2>
      <p className="mt-3 text-text-muted">{microcopy.onboarding.noDataYetBody}</p>
      {lastSyncAt && (
        <p className="mt-1 font-mono text-xs text-text-muted">
          Last sync attempted: <LocalizedTimestamp iso={lastSyncAt} />
        </p>
      )}
      <div className="mt-6 flex justify-center">
        <Button variant="secondary" onClick={onRefresh}>
          {microcopy.onboarding.noDataYetCta}
        </Button>
      </div>
    </section>
  );
}
