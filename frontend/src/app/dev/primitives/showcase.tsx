'use client';
import Link from 'next/link';
import {
  Bell,
  Plus,
  ChevronDown,
  ShieldAlert,
  Clock,
  Flame,
  TrendingDown,
  Lightbulb,
} from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SsoButton } from '@/components/ui/sso-button';
import { GradientText } from '@/components/ui/gradient-text';
import { Card } from '@/components/ui/card';
import { Stat } from '@/components/ui/stat';
import { StatStrip } from '@/components/ui/stat-strip';
import { ActivityFeed, type ActivityItem } from '@/components/ui/activity-feed';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  PerSourceStatusStrip,
} from '@/components/states';

// BL-05: this client showcase is loaded dynamically from `page.tsx` ONLY in
// dev builds. In production builds the parent server component short-circuits
// with notFound() before this module is referenced, so Next can tree-shake
// it out of the production bundle. All heavy imports (lucide icons, Bomb /
// Section / Row demo components) now live here rather than at the route
// entry, which is what the bundle audit cared about.
//
// Previously this entire surface lived in page.tsx with a runtime NODE_ENV
// guard. Next.js doesn't tree-shake based on runtime gates, so the heavy
// imports shipped to production despite the route 404-ing.

// Deterministic timestamps for the ActivityFeed showcase so the relative-time
// strings don't shift with wall-clock during dev navigation. Each is anchored
// off Date.now() at module-load.
const NOW = Date.now();
const SAMPLE_ACTIVITY: ActivityItem[] = [
  {
    id: 'a1',
    category: 'new_critical_vuln',
    title: 'Qualys detected CVE-2024-3094',
    body: 'liblzma 5.6.0 backdoor — 12 hosts affected',
    occurred_at: new Date(NOW - 12 * 60 * 1000).toISOString(),
    href: '/dashboard/vulnerabilities',
  },
  {
    id: 'a2',
    category: 'sla_breach',
    title: 'SLA breach: 3 tickets overdue',
    body: 'CRITICAL severity past 7d window',
    occurred_at: new Date(NOW - 2 * 60 * 60 * 1000).toISOString(),
    href: '/dashboard/tickets',
  },
  {
    id: 'a3',
    category: 'sync_failure',
    title: 'Tenable sync failed',
    body: 'HTTP 503 · Tried 3 times',
    occurred_at: new Date(NOW - 28 * 60 * 1000).toISOString(),
  },
  {
    id: 'a4',
    category: 'risk_change',
    title: 'asset-9341 risk dropped (87 → 62)',
    body: null,
    occurred_at: new Date(NOW - 4 * 60 * 60 * 1000).toISOString(),
  },
];

function Bomb({ boom }: { boom: boolean }) {
  if (boom) throw new Error('Synthetic dev error for ErrorBoundary showcase');
  return (
    <p className="text-sm text-text-muted">
      Children rendering normally. Click below to trigger.
    </p>
  );
}

export default function PrimitivesShowcase() {
  const [boom, setBoom] = useState(false);

  return (
    <main className="min-h-screen bg-bg text-text p-12 font-sans">
      <header className="mb-12">
        <h1 className="text-3xl font-bold mb-2">
          <GradientText>Primitives</GradientText> — dev only
        </h1>
        <p className="text-text-muted text-sm">
          Loaded dynamically from a server-component shell that returns 404 in
          production. State matrix per D-31 / D-Test-04; replaces the
          out-of-scope Storybook playground.
        </p>
      </header>

      <Section title="Button — variants">
        <Row>
          <Button variant="cta">Start triage</Button>
          <Button variant="secondary">Snooze 1h</Button>
          <Button variant="ghost">View trace</Button>
          <Button variant="icon" aria-label="Notifications">
            <Bell className="h-4 w-4" aria-hidden />
          </Button>
        </Row>
      </Section>

      <Section title="Button — sizes (secondary)">
        <Row>
          <Button size="sm">Small</Button>
          <Button size="md">Medium</Button>
          <Button size="lg">Large</Button>
        </Row>
      </Section>

      <Section title="Button — states">
        <Row>
          <Button>Default</Button>
          <Button disabled>Disabled</Button>
          <Button loading loadingText="Signing in…">
            Sign in
          </Button>
          <Button leftIcon={<Plus className="h-4 w-4" aria-hidden />}>Left icon</Button>
          <Button rightIcon={<ChevronDown className="h-4 w-4" aria-hidden />}>
            Right icon
          </Button>
        </Row>
      </Section>

      <Section title="Button — asChild (renders as anchor)">
        <Row>
          <Button asChild variant="cta">
            <Link href="/dashboard">Go to dashboard</Link>
          </Button>
        </Row>
      </Section>

      <Section title="Input — types and states">
        <div className="grid grid-cols-2 gap-4 max-w-xl">
          <div>
            <label htmlFor="showcase-email" className="block text-sm">
              <span className="block mb-1 text-text-muted">Email</span>
            </label>
            <Input id="showcase-email" type="email" placeholder="you@company.com" />
          </div>
          <div>
            <label htmlFor="showcase-password" className="block text-sm">
              <span className="block mb-1 text-text-muted">Password (eye-toggle)</span>
            </label>
            <Input id="showcase-password" type="password" defaultValue="hunter2" />
          </div>
          <div>
            <label htmlFor="showcase-email-error" className="block text-sm">
              <span className="block mb-1 text-text-muted">Error state</span>
            </label>
            <Input id="showcase-email-error" type="email" defaultValue="bad@" aria-invalid="true" />
          </div>
          <div>
            <label htmlFor="showcase-disabled" className="block text-sm">
              <span className="block mb-1 text-text-muted">Disabled</span>
            </label>
            <Input id="showcase-disabled" type="text" disabled defaultValue="locked" />
          </div>
        </div>
      </Section>

      <Section title="SsoButton — providers">
        <div className="grid grid-cols-1 gap-3 max-w-sm">
          <SsoButton provider="google" />
          <SsoButton provider="microsoft" />
        </div>
      </Section>

      <Section title="GradientText — accent slot">
        <p className="text-2xl font-bold leading-snug">
          See your security posture{' '}
          <GradientText>without opening another tool.</GradientText>
        </p>
      </Section>

      {/* ───────────────── Phase 10 new primitives (D-Test-04) ───────────────── */}

      <Section title="Card — variants (D-P-01)">
        <div className="grid grid-cols-3 gap-4">
          <Card variant="surface">
            <Card.Header>
              <h3 className="text-sm font-medium">surface</h3>
            </Card.Header>
            <Card.Body>
              <p className="text-xs text-text-muted">
                Default raised card on the page background.
              </p>
            </Card.Body>
          </Card>
          <Card variant="elevated">
            <Card.Header>
              <h3 className="text-sm font-medium">elevated</h3>
            </Card.Header>
            <Card.Body>
              <p className="text-xs text-text-muted">
                One level above surface; gets a soft shadow.
              </p>
            </Card.Body>
            <Card.Footer>
              <span className="text-xs text-text-faint">footer slot</span>
            </Card.Footer>
          </Card>
          <Card variant="outline">
            <Card.Header>
              <h3 className="text-sm font-medium">outline</h3>
            </Card.Header>
            <Card.Body>
              <p className="text-xs text-text-muted">
                Transparent fill, strong border. Use sparingly.
              </p>
            </Card.Body>
          </Card>
        </div>
      </Section>

      <Section title="Card — padding (sm / md / lg)">
        <div className="grid grid-cols-3 gap-4">
          <Card padding="sm">
            <p className="text-xs">padding=sm (p-3)</p>
          </Card>
          <Card padding="md">
            <p className="text-xs">padding=md (p-5, default)</p>
          </Card>
          <Card padding="lg">
            <p className="text-xs">padding=lg (p-7)</p>
          </Card>
        </div>
      </Section>

      <Section title="Stat — direction matrix (D-P-02 + D-S-03)">
        <StatStrip>
          <Stat
            label="Critical · open"
            value={3}
            delta={1}
            deltaIsGood="down"
            icon={<ShieldAlert className="h-4 w-4" />}
          />
          <Stat
            label="SLA · at risk"
            value={12}
            delta={-2}
            deltaIsGood="down"
            icon={<Clock className="h-4 w-4" />}
          />
          <Stat
            label="MTTR · 30d"
            value="4.2d"
            delta={null}
            icon={<TrendingDown className="h-4 w-4" />}
          />
          <Stat
            label="CISA KEV"
            value={5}
            delta={0}
            deltaIsGood="down"
            icon={<Flame className="h-4 w-4" />}
          />
        </StatStrip>
        <p className="mt-3 text-xs text-text-faint">
          Critical (red ▲ +1, up is bad). SLA (green ▼ -2, down is good).
          MTTR (delta=null → Δ — per Pitfall 8). KEV (delta=0 → no arrow).
        </p>
      </Section>

      <Section title="StatStrip — column ladder (D-P-03 + D-M-02)">
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-xs uppercase tracking-wide text-text-faint">
              4 tiles → desktop 4-col, tablet 2-col, mobile 1-col
            </p>
            <StatStrip>
              <Stat label="a" value={1} />
              <Stat label="b" value={2} />
              <Stat label="c" value={3} />
              <Stat label="d" value={4} />
            </StatStrip>
          </div>
          <div>
            <p className="mb-2 text-xs uppercase tracking-wide text-text-faint">
              2 tiles → desktop 2-col
            </p>
            <StatStrip>
              <Stat label="a" value={1} />
              <Stat label="b" value={2} />
            </StatStrip>
          </div>
          <div>
            <p className="mb-2 text-xs uppercase tracking-wide text-text-faint">
              1 tile → single-column fallback
            </p>
            <StatStrip>
              <Stat label="a" value={1} />
            </StatStrip>
          </div>
        </div>
      </Section>

      <Section title="ActivityFeed — category mapping (D-P-04 + D-A-01..05)">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="mb-3 text-xs uppercase tracking-wide text-text-faint">
              4 categories — link + non-link variants
            </p>
            <ActivityFeed items={SAMPLE_ACTIVITY} />
          </div>
          <div>
            <p className="mb-3 text-xs uppercase tracking-wide text-text-faint">
              Empty state — D-A-03 verbatim
            </p>
            <ActivityFeed items={[]} />
          </div>
        </div>
      </Section>

      <Section title="ErrorBoundary — catch + reset (D-P-06)">
        <ErrorBoundary
          fallback={(err, reset) => (
            <div
              role="alert"
              className="rounded-md border border-danger-soft bg-surface p-4"
            >
              <p className="text-sm text-danger">Something went wrong here.</p>
              <p className="mt-1 font-mono text-xs text-text-muted">
                {err.message}
              </p>
              <button
                className="mt-3 inline-flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-xs text-text hover:bg-surface"
                onClick={() => {
                  setBoom(false);
                  reset();
                }}
              >
                Retry
              </button>
            </div>
          )}
        >
          <div className="rounded-md border border-border-subtle bg-surface p-4">
            <Bomb boom={boom} />
            <button
              className="mt-3 inline-flex items-center gap-2 rounded-md border border-danger-soft bg-surface-2 px-3 py-1.5 text-xs text-danger hover:bg-surface"
              onClick={() => setBoom(true)}
            >
              Click to throw
            </button>
          </div>
        </ErrorBoundary>
      </Section>

      {/* ── Phase 11 — State patterns (D-S-01..07 + D-V-02) ───────────────── */}
      <section aria-labelledby="states-h" className="mb-10 space-y-8">
        <div>
          <h2
            id="states-h"
            className="mb-1 text-sm font-medium uppercase tracking-wide text-text-faint"
          >
            State patterns (Phase 11)
          </h2>
          <p className="text-xs text-text-muted">
            Cross-phase primitives consumed by /dashboard/vulnerabilities (Phase
            11), /dashboard/assets (Phase 12), /dashboard/tickets (Phase 13).
            Sourced from <code className="font-mono">@/components/states</code>.
          </p>
        </div>

        {/* SkeletonTable — D-S-01 */}
        <div className="rounded-lg border border-border bg-surface p-6">
          <h3 className="text-base font-medium text-text">SkeletonTable</h3>
          <p className="mt-1 text-xs text-text-muted">
            Column-aware shimmer mirroring the eventual table shape (D-S-01).
            <code className="ml-2 font-mono">aria-busy=&quot;true&quot;</code>;
            <code className="ml-1 font-mono">motion-safe:animate-shimmer</code>{' '}
            gates the keyframe.
          </p>
          <div className="mt-4 rounded-md border border-border-subtle bg-bg p-4">
            <SkeletonTable
              rows={5}
              columns={[
                { kind: 'pill', width: 90 },
                { kind: 'mono', width: 130 },
                { kind: 'text', width: 200 },
                { kind: 'mono', width: 120 },
                { kind: 'mono', width: 40 },
                { kind: 'badge', width: 80 },
                { kind: 'mono', width: 60 },
              ]}
            />
          </div>
        </div>

        {/* EmptyState — D-S-02 compound */}
        <div className="rounded-lg border border-border bg-surface p-6">
          <h3 className="text-base font-medium text-text">EmptyState — compound</h3>
          <p className="mt-1 text-xs text-text-muted">
            Title + Body + Actions + Suggestion slots (D-S-02).{' '}
            <code className="font-mono">role=&quot;status&quot;</code>,{' '}
            <code className="font-mono">aria-live=&quot;polite&quot;</code>.
          </p>
          <div className="mt-4">
            <EmptyState>
              <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
              <EmptyState.Body>
                That&apos;s a tight net — relax one or two and try again.
              </EmptyState.Body>
              <EmptyState.Actions>
                <button
                  type="button"
                  className="rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse"
                >
                  Clear all filters
                </button>
                <button
                  type="button"
                  className="rounded-md border border-border bg-surface-2 px-4 py-2 text-sm text-text"
                >
                  Include Medium severity
                </button>
                <button
                  type="button"
                  className="rounded-md border border-border bg-surface-2 px-4 py-2 text-sm text-text"
                >
                  Search all sources
                </button>
              </EmptyState.Actions>
              <EmptyState.Suggestion>
                <Lightbulb size={16} aria-hidden="true" />
                <span>Try broadening severity or removing the date range.</span>
              </EmptyState.Suggestion>
            </EmptyState>
          </div>
        </div>

        {/* PartialFailureBanner — D-S-03 props mode */}
        <div className="rounded-lg border border-border bg-surface p-6">
          <h3 className="text-base font-medium text-text">
            PartialFailureBanner — props mode
          </h3>
          <p className="mt-1 text-xs text-text-muted">
            Amber-not-red banner with HTTP code + request ID + Retry. Hybrid
            hook+props API (D-S-03).{' '}
            <code className="font-mono">role=&quot;alert&quot;</code>; sanitized
            message only — no raw stack (T-11-15).
          </p>
          <div className="mt-4">
            <PartialFailureBanner
              errors={[
                {
                  code: 503,
                  requestId: 'req_8f2a91c',
                  message: 'Tenable connector is unreachable',
                },
              ]}
              onRetry={() => {
                // Showcase-only: real consumers wire to the query refetch.
                if (typeof window !== 'undefined') {
                  // eslint-disable-next-line no-alert
                  window.alert('Retry fired');
                }
              }}
              source="Tenable"
            />
          </div>
        </div>

        {/* PerSourceStatusStrip — D-V-02 */}
        <div className="rounded-lg border border-border bg-surface p-6">
          <h3 className="text-base font-medium text-text">PerSourceStatusStrip</h3>
          <p className="mt-1 text-xs text-text-muted">
            Per-connector status pills with{' '}
            <code className="font-mono">aria-live=&quot;polite&quot;</code>{' '}
            (D-V-02 + D-S-07). Composes <code className="font-mono">useConnectors()</code>{' '}
            + a <code className="font-mono">facets</code> prop. In this dev
            showcase the hook resolves with no data (no live backend), so the
            strip correctly returns null.
          </p>
          <div className="mt-4">
            <PerSourceStatusStrip
              facets={{ Tenable: 12, Qualys: 8, 'AWS Inspector': 3 }}
            />
            <p className="mt-2 text-xs italic text-text-faint">
              Strip returns null while <code className="font-mono">useConnectors</code>{' '}
              query is pending / errored (ChipBar + PartialFailureBanner cover
              those states). Visit{' '}
              <Link
                href="/dashboard/vulnerabilities"
                className="text-violet underline"
              >
                /dashboard/vulnerabilities
              </Link>{' '}
              against a seeded backend for the full demo.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="text-sm font-medium uppercase tracking-wide text-text-faint mb-3">
        {title}
      </h2>
      <div className="rounded-lg border border-border bg-surface p-6">{children}</div>
    </section>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3">{children}</div>;
}
