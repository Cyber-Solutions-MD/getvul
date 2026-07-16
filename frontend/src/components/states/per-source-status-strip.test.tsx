// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';

// Mock the connectors query — the hook lands in Wave 1 (Plan 11-03).
// vi.mock succeeds without the real file existing; the component import below
// is the RED signal.
vi.mock('@/lib/queries/use-connectors', () => ({
  useConnectors: vi.fn(),
}));
import { useConnectors } from '@/lib/queries/use-connectors';

// Wave 1 (Plan 11-04) will create this file. Import is the RED signal.
import { PerSourceStatusStrip } from './per-source-status-strip';

const useConnectorsMock = vi.mocked(useConnectors);

const okStatus = {
  isPending: false,
  isError: false,
  isSuccess: true,
  data: [
    { id: 'c1', type: 'QUALYS', last_sync_status: 'ok' },
    { id: 'c2', type: 'TENABLE', last_sync_status: 'failed' },
    { id: 'c3', type: 'AWS_INSPECTOR', last_sync_status: 'syncing' },
    { id: 'c4', type: 'RAPID7', last_sync_status: null },
  ],
} as unknown as ReturnType<typeof useConnectors>;

describe('<PerSourceStatusStrip> (D-V-02 + D-S-07 aria-live)', () => {
  it('renders one chip per connector returned by useConnectors', () => {
    useConnectorsMock.mockReturnValue(okStatus);
    render(
      <PerSourceStatusStrip
        facets={{ QUALYS: 287, TENABLE: 192, AWS_INSPECTOR: 64, RAPID7: 0 }}
      />
    );
    expect(screen.getByText(/QUALYS/)).toBeInTheDocument();
    expect(screen.getByText(/TENABLE/)).toBeInTheDocument();
    expect(screen.getByText(/AWS_INSPECTOR/)).toBeInTheDocument();
    expect(screen.getByText(/RAPID7/)).toBeInTheDocument();
  });

  it('chip shows connector type (mono font) + per-source count from facets prop', () => {
    useConnectorsMock.mockReturnValue(okStatus);
    const { container } = render(
      <PerSourceStatusStrip
        facets={{ QUALYS: 287, TENABLE: 192, AWS_INSPECTOR: 64, RAPID7: 0 }}
      />
    );
    const monoEls = container.querySelectorAll('.font-mono');
    expect(monoEls.length).toBeGreaterThanOrEqual(4);
    // Counts surface from facets prop
    expect(container.textContent).toContain('287');
    expect(container.textContent).toContain('192');
  });

  it("state-aware coloring — ok → success-soft; failed → danger-soft; syncing → pink-soft; null → surface-2", () => {
    useConnectorsMock.mockReturnValue(okStatus);
    const { container } = render(
      <PerSourceStatusStrip
        facets={{ QUALYS: 287, TENABLE: 192, AWS_INSPECTOR: 64, RAPID7: 0 }}
      />
    );
    const chips = container.querySelectorAll('[data-status-chip]');
    expect(chips.length).toBe(4);

    // QUALYS = ok
    const qualys = Array.from(chips).find((c) =>
      c.textContent?.includes('QUALYS')
    ) as HTMLElement;
    expect(qualys.className).toMatch(/bg-success-soft/);
    expect(qualys.className).toMatch(/text-success/);

    // TENABLE = failed
    const tenable = Array.from(chips).find((c) =>
      c.textContent?.includes('TENABLE')
    ) as HTMLElement;
    expect(tenable.className).toMatch(/bg-danger-soft/);
    expect(tenable.className).toMatch(/text-danger/);

    // AWS_INSPECTOR = syncing
    const aws = Array.from(chips).find((c) =>
      c.textContent?.includes('AWS_INSPECTOR')
    ) as HTMLElement;
    expect(aws.className).toMatch(/bg-pink-soft/);
    // Phase-16 (WR-04): pink text lifted to the on-soft token for AA on cream.
    expect(aws.className).toContain('text-[var(--color-pink-on-soft)]');

    // RAPID7 = null → neutral surface-2
    const rapid7 = Array.from(chips).find((c) =>
      c.textContent?.includes('RAPID7')
    ) as HTMLElement;
    expect(rapid7.className).toMatch(/bg-surface-2/);
    expect(rapid7.className).toMatch(/text-text-muted/);
  });

  it('role="status" + aria-live="polite" on the wrapping element (D-S-07)', () => {
    useConnectorsMock.mockReturnValue(okStatus);
    const { container } = render(
      <PerSourceStatusStrip
        facets={{ QUALYS: 287, TENABLE: 192, AWS_INSPECTOR: 64, RAPID7: 0 }}
      />
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root.getAttribute('role')).toBe('status');
    expect(root.getAttribute('aria-live')).toBe('polite');
  });

  it('returns null while connectors query is pending', () => {
    useConnectorsMock.mockReturnValue({
      isPending: true,
      isError: false,
      isSuccess: false,
      data: undefined,
    } as unknown as ReturnType<typeof useConnectors>);
    const { container } = render(
      <PerSourceStatusStrip facets={{}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('returns null on connectors query error (PartialFailureBanner covers it)', () => {
    useConnectorsMock.mockReturnValue({
      isPending: false,
      isError: true,
      isSuccess: false,
      data: undefined,
    } as unknown as ReturnType<typeof useConnectors>);
    const { container } = render(
      <PerSourceStatusStrip facets={{}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('axe — no violations with a mixed status set (ok/failed/syncing/null)', async () => {
    useConnectorsMock.mockReturnValue(okStatus);
    const { container } = render(
      <PerSourceStatusStrip
        facets={{ QUALYS: 287, TENABLE: 192, AWS_INSPECTOR: 64, RAPID7: 0 }}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
