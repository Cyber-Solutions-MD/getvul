/**
 * RiskCard — STUB for Plan 12-08.
 *
 * Plan 12-07 ships the real implementation. This file is a placeholder that
 * exposes the documented prop contract (`asset: AssetDetail`) and renders a
 * minimal node with `data-testid="risk-card"` so the /assets/[id] page can
 * compose against it. The orchestrator will replace this file when merging
 * 12-07.
 */
import type { AssetDetail } from '@/lib/queries/use-asset-detail';

export function RiskCard({ asset }: { asset: AssetDetail }) {
  return (
    <div data-testid="risk-card" data-stub-from="12-08" data-asset-id={asset.id}>
      <div className="rounded-lg border border-border-subtle bg-surface-2 p-4 text-sm text-text-muted">
        Risk · {asset.risk_score ?? '—'}
      </div>
    </div>
  );
}
