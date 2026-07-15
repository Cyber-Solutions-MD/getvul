import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// D-31 / BL-05: /dev/primitives is a dev-only showcase. The route must render
// the primitives loader in non-production builds and 404 (notFound) in
// production — the NODE_ENV branch is what lets Next dead-code-eliminate the
// heavy showcase chunk out of the prod bundle (verified independently by the
// route-size check in 11-08-SUMMARY.md). These tests pin the runtime gate.

// notFound() throws a sentinel so the production branch is observable.
const notFound = vi.fn(() => {
  throw new Error('NEXT_NOT_FOUND');
});
vi.mock('next/navigation', () => ({ notFound }));

// Stub the heavy dev-only loader (lucide icons + next/dynamic ssr:false) so the
// lazy import resolves to a light node under jsdom.
vi.mock('./showcase-client-loader', () => ({
  ShowcaseClientLoader: () => (
    <div data-testid="showcase-loader">primitives showcase</div>
  ),
}));

describe('/dev/primitives route gate (D-31, BL-05)', () => {
  beforeEach(() => {
    vi.resetModules();
    notFound.mockClear();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders the primitives showcase in non-production (dev) builds', async () => {
    vi.stubEnv('NODE_ENV', 'development');
    const { default: DevPrimitivesPage } = await import('./page');
    render(<DevPrimitivesPage />);
    expect(await screen.findByTestId('showcase-loader')).toBeInTheDocument();
    expect(notFound).not.toHaveBeenCalled();
  });

  it('404s (calls notFound) in production builds — showcase never rendered', async () => {
    vi.stubEnv('NODE_ENV', 'production');
    const { default: DevPrimitivesPage } = await import('./page');
    // React re-attempts the throwing render, so notFound fires more than once;
    // asserting it fired at all (and the showcase never mounted) is the contract.
    expect(() => render(<DevPrimitivesPage />)).toThrow('NEXT_NOT_FOUND');
    expect(notFound).toHaveBeenCalled();
    expect(screen.queryByTestId('showcase-loader')).not.toBeInTheDocument();
  });
});
