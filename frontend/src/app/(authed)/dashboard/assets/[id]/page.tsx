'use client';
/**
 * /assets/[id] — UX-04-02 two-column detail page.
 *
 * Layout (>=900px):
 *   +----------------------+ rail 340px +
 *   | Breadcrumb           | RiskCard   |
 *   | H1 hostname + tags   | OwnerCard  |
 *   | SeverityRibbon       | Identity   |
 *   | AssetVulnsList       |   Metadata |
 *   | RemediationTimeline  |            |
 *   +----------------------+------------+
 *
 * Layout (<900px): rail stacks below main; DrillPanelMobile (vaul) handles
 * the drill bottom-sheet. Both surfaces gate at min-[900px] so the drill
 * panel desktop branch (D-P-03) and the rail split track together.
 *
 * Drill: clicking a vuln row sets ?cve=<id>&open=drill via router.replace.
 * Phase 11 DrillPanel reads the URL itself (D-P-02 contract); we only feed
 * it cveId.
 *
 * RiskCard + OwnerCard imports resolve to local stubs in this worktree;
 * Plan 12-07 ships the real implementations and the orchestrator merges
 * them in. The stubs render testid-bearing nodes so the composition test
 * is meaningful even before 12-07 lands.
 */
import { Suspense, useCallback } from 'react';
import { usePathname, useRouter, useSearchParams, useParams } from 'next/navigation';
import { Breadcrumb, Crumb } from '@/components/ui/Breadcrumb';
import { RiskCard } from '@/components/assets/risk-card';
import { OwnerCard } from '@/components/assets/owner-card';
import { IdentityMetadataRail } from '@/components/assets/identity-metadata-rail';
import { SeverityRibbon } from '@/components/assets/severity-ribbon';
import { AssetVulnsList } from '@/components/assets/asset-vulns-list';
import { RemediationTimeline } from '@/components/assets/remediation-timeline';
import { DrillPanel } from '@/components/vulnerabilities/drill-panel';
import { DrillPanelMobile } from '@/components/vulnerabilities/drill-panel-mobile';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useAsset } from '@/lib/queries/use-asset-detail';
import {
  useAssetVulnerabilities,
  type VulnerabilitiesResponse,
} from '@/lib/queries/use-asset-vulnerabilities';
import { useAssetRemediations } from '@/lib/queries/use-asset-remediations';
import type { VulnerabilitySummary } from '@/lib/queries/use-vulnerabilities';

const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'pill', width: 24 },
  { kind: 'mono', width: 130 },
  { kind: 'text', width: 280 },
  { kind: 'mono', width: 50 },
];

function AssetDetailInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { id } = useParams<{ id: string }>();

  const asset = useAsset(id);
  const vulns = useAssetVulnerabilities(id);
  const remediations = useAssetRemediations(id);

  const cveId = params?.get('cve') ?? null;

  const onRowOpen = useCallback(
    (cveOrId: string) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      sp.set('cve', cveOrId);
      sp.set('open', 'drill');
      router.replace(`${pathname}?${sp.toString()}`, { scroll: false });
    },
    [router, pathname, params],
  );

  if (asset.isLoading) {
    return <SkeletonTable columns={SKELETON_COLUMNS} rows={8} />;
  }

  if (asset.error || !asset.data) {
    return (
      <PartialFailureBanner
        errors={[
          {
            code: 'http_error',
            requestId: String(
              (asset.error as Error)?.message || 'unknown',
            ).slice(0, 40),
          },
        ]}
        onRetry={() => asset.refetch()}
      />
    );
  }

  const a = asset.data;
  // useAssetVulnerabilities wraps useVulnerabilities, which returns a union
  // (items: VulnerabilitySummary[] | VulnerabilityByHost[]). On the per-host
  // page we always feed asset_id without `group=host`, so items is
  // VulnerabilitySummary[] — narrow explicitly.
  const vulnRows = (((vulns.data as VulnerabilitiesResponse | undefined)?.items ??
    []) as VulnerabilitySummary[]);

  return (
    <>
      {/* W7: explicit 900px gate matches sketch 005 variant B AND Phase 11
          D-P-03 drill-panel mobile threshold. Tailwind `md:` defaults to
          768px which would split the rail before the drill panel switches
          to the mobile sheet — using a min-[900px] arbitrary class keeps
          both surfaces consistent. */}
      <div className="grid grid-cols-1 gap-6 p-6 min-[900px]:grid-cols-[1fr_340px]">
        {/* Main column */}
        <main className="space-y-6">
          <header className="space-y-2">
            <Breadcrumb>
              <Crumb href="/assets">Assets</Crumb>
              <Crumb>{a.hostname ?? '—'}</Crumb>
            </Breadcrumb>
            <div className="flex flex-wrap items-baseline gap-3">
              <h1 className="font-mono text-2xl text-text">{a.hostname ?? '—'}</h1>
              <span
                className="flex flex-wrap gap-1"
                data-testid="header-tags"
              >
                {(a.tags ?? []).map((t) => (
                  <span
                    key={t}
                    className="rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-xs text-text-muted"
                  >
                    {t}
                  </span>
                ))}
              </span>
            </div>
          </header>

          <section aria-label="Severity breakdown">
            <SeverityRibbon
              counts={{
                critical: a.vuln_counts?.critical ?? 0,
                high: a.vuln_counts?.high ?? 0,
                medium: a.vuln_counts?.medium ?? 0,
                low: a.vuln_counts?.low ?? 0,
                info: 0,
              }}
            />
          </section>

          <section
            aria-label="Vulnerabilities on this host"
            className="rounded-lg border border-border-subtle"
          >
            {vulns.isLoading && (
              <SkeletonTable columns={SKELETON_COLUMNS} rows={5} />
            )}
            {!vulns.isLoading && vulnRows.length === 0 && (
              <EmptyState>
                <EmptyState.Title>No active vulnerabilities</EmptyState.Title>
                <EmptyState.Body>
                  This host has no open or in-progress vulnerabilities right
                  now.
                </EmptyState.Body>
              </EmptyState>
            )}
            {!vulns.isLoading && vulnRows.length > 0 && (
              <AssetVulnsList rows={vulnRows} onRowOpen={onRowOpen} />
            )}
          </section>

          <section aria-label="Remediation timeline" className="space-y-2">
            <h2 className="text-sm uppercase tracking-wide text-text-muted">
              Remediation
            </h2>
            {remediations.error && (
              <PartialFailureBanner
                errors={[{ code: 'http_error', requestId: 'remediations' }]}
                onRetry={() => remediations.refetch()}
              />
            )}
            {remediations.isLoading ? (
              <SkeletonTable columns={SKELETON_COLUMNS.slice(0, 2)} rows={3} />
            ) : (remediations.data?.items.length ?? 0) === 0 ? (
              <EmptyState>
                <EmptyState.Title>No remediation tickets</EmptyState.Title>
                <EmptyState.Body>
                  Create a ticket from a vulnerability above to start tracking
                  remediation.
                </EmptyState.Body>
              </EmptyState>
            ) : (
              <RemediationTimeline tickets={remediations.data!.items} />
            )}
          </section>
        </main>

        {/* Right rail — sticky at >=900px (W7 gate matches Phase 11 D-P-03). */}
        <aside
          className="space-y-4 min-[900px]:sticky min-[900px]:top-4 min-[900px]:self-start"
          data-testid="asset-detail-rail"
        >
          <RiskCard asset={a} />
          <OwnerCard asset={a} />
          <IdentityMetadataRail asset={a} />
        </aside>
      </div>

      {/* Phase 11 DrillPanel reuse — D-D-03 verbatim. The panel reads
          ?open=drill from the URL itself, so we only pipe cveId through. */}
      <DrillPanel cveId={cveId} originRowRef={null} />
      <DrillPanelMobile cveId={cveId} />
    </>
  );
}

export default function AssetDetailPage() {
  return (
    <ErrorBoundary
      fallback={(err, reset) => (
        <PartialFailureBanner
          errors={[{ code: 'crash', requestId: err.message.slice(0, 40) }]}
          onRetry={reset}
        />
      )}
    >
      <Suspense
        fallback={<SkeletonTable columns={SKELETON_COLUMNS} rows={8} />}
      >
        <AssetDetailInner />
      </Suspense>
    </ErrorBoundary>
  );
}
