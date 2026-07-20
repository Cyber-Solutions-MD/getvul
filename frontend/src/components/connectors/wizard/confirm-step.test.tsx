// RED scaffold (19-00) — GREEN target for Wave 2.
/**
 * confirm-step.test.tsx — RED scaffold for ConfirmStep (UX-D-02-04).
 * Imports a component that does not exist yet — this file is intentionally
 * failing (module-resolution error) until Wave 2 creates `./confirm-step`.
 *
 * Mirrors the `vi.mock('@/lib/queries/use-connectors-admin', ...)` pattern
 * from connector-form.test.tsx.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockCreate = vi.fn();

vi.mock('@/lib/queries/use-connectors-admin', () => ({
  useCreateConnector: () => ({ mutate: mockCreate, isPending: false }),
}));

import { ConfirmStep } from './confirm-step';

describe('ConfirmStep (19-00 RED scaffold, UX-D-02-04)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Test 1: renders required scope + purpose when permissions are present', () => {
    render(
      <ConfirmStep
        connectorType="crowdstrike"
        providerName="CrowdStrike Spotlight"
        permissions={[{ scope: 'Scans', access: 'Read', purpose: 'List scan results' }]}
        syncInterval={15}
        credentials={{ api_token: 'tok' }}
      />,
    );
    expect(screen.getByText('Scans')).toBeInTheDocument();
    expect(screen.getByText('List scan results')).toBeInTheDocument();
  });

  it('Test 2: renders "No special scopes required." when permissions is empty', () => {
    render(
      <ConfirmStep
        connectorType="crowdstrike"
        providerName="CrowdStrike Spotlight"
        permissions={[]}
        syncInterval={15}
        credentials={{ api_token: 'tok' }}
      />,
    );
    expect(screen.getByText('No special scopes required.')).toBeInTheDocument();
  });

  it('Test 3: clicking "Add connector" invokes useCreateConnector().mutate with uppercased connector_type + sync_interval_minutes', () => {
    render(
      <ConfirmStep
        connectorType="crowdstrike"
        providerName="CrowdStrike Spotlight"
        permissions={[]}
        syncInterval={30}
        credentials={{ api_token: 'tok' }}
      />,
    );
    const addBtn = screen.getByRole('button', { name: /add connector/i });
    fireEvent.click(addBtn);
    expect(mockCreate).toHaveBeenCalled();
    const args = mockCreate.mock.calls[0][0] as {
      connector_type: string;
      sync_interval_minutes: number;
    };
    expect(args.connector_type).toBe('CROWDSTRIKE');
    expect(args.sync_interval_minutes).toBe(30);
  });
});
