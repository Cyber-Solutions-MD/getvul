// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { axe } from 'vitest-axe';
import {
  QueryClient,
  QueryClientProvider,
  type QueryKey,
} from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Wave 1 (Plan 11-04) will create this file. Import is the RED signal.
import { PartialFailureBanner } from './partial-failure-banner';

function wrap(client: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

describe('<PartialFailureBanner> (D-S-03 — hybrid hook+props mode + amber-not-red)', () => {
  it('props mode — renders role="alert" + mono HTTP code + mono request ID', () => {
    render(
      <PartialFailureBanner
        errors={[
          { code: 503, requestId: 'req_8f2a91c', message: 'Tenable unreachable' },
        ]}
        source="Tenable"
      />
    );
    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert.textContent).toContain('503');
    expect(alert.textContent).toContain('req_8f2a91c');
    // HTTP code and request ID should land in mono-font elements
    const monoEls = alert.querySelectorAll('.font-mono');
    expect(monoEls.length).toBeGreaterThanOrEqual(2);
  });

  it('props mode — onRetry callback fires on Retry button click', () => {
    const onRetry = vi.fn();
    render(
      <PartialFailureBanner
        errors={[{ code: 503, requestId: 'req_abc', message: 'down' }]}
        source="Tenable"
        onRetry={onRetry}
      />
    );
    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('default mode — given watchKeys + failed query in QueryClient, banner appears', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    qc.getQueryCache().build(qc, {
      queryKey: ['vulnerabilities', 'list'],
      queryFn: () => Promise.reject(new Error('500')),
    });
    const query = qc
      .getQueryCache()
      .find({ queryKey: ['vulnerabilities', 'list'] });
    query?.setState({
      data: undefined,
      error: new Error('500'),
      status: 'error',
      fetchStatus: 'idle',
    } as Parameters<NonNullable<typeof query>['setState']>[0]);

    render(
      <PartialFailureBanner watchKeys={[['vulnerabilities'] as QueryKey]} />,
      { wrapper: wrap(qc) }
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('default mode — returns null (renders nothing) when no errors present', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { container } = render(
      <PartialFailureBanner watchKeys={[['vulnerabilities'] as QueryKey]} />,
      { wrapper: wrap(qc) }
    );
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it('copy includes partial-data phrasing (consumer-provided source surfaces in copy)', () => {
    render(
      <PartialFailureBanner
        errors={[{ code: 503, requestId: 'req_abc', message: 'down' }]}
        source="Tenable"
      />
    );
    // Banner copy names the failing connector (consumer-provided via `source`)
    expect(screen.getByRole('alert').textContent).toMatch(/Tenable/);
  });

  it('amber not red — banner uses amber-soft / amber, not danger-soft (partial failure ≠ down)', () => {
    const { container } = render(
      <PartialFailureBanner
        errors={[{ code: 503, requestId: 'req_abc', message: 'down' }]}
        source="Tenable"
      />
    );
    const alert = container.querySelector('[role="alert"]') as HTMLElement;
    expect(alert.className).toMatch(/amber/);
    expect(alert.className).not.toMatch(/danger-soft/);
  });

  it('axe — no violations on the canonical 503-Tenable variant', async () => {
    const { container } = render(
      <PartialFailureBanner
        errors={[
          { code: 503, requestId: 'req_8f2a91c', message: 'Tenable unreachable' },
        ]}
        source="Tenable"
        onRetry={() => {}}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('stale-row source surfaced — banner exposes data-failed-sources for D-V-04 consumers', () => {
    const { container } = render(
      <PartialFailureBanner
        errors={[{ code: 503, requestId: 'req_abc', message: 'down' }]}
        source="Tenable"
      />
    );
    const alert = container.querySelector('[role="alert"]') as HTMLElement;
    // Either via `data-failed-sources` attribute or equivalent surface
    const attr = alert.getAttribute('data-failed-sources');
    expect(attr).not.toBeNull();
    expect(attr).toContain('Tenable');
  });
});
