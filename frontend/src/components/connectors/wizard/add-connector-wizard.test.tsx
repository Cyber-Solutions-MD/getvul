// RED scaffold (19-00) — GREEN target for Wave 2.
/**
 * add-connector-wizard.test.tsx — RED scaffold for AddConnectorWizard
 * (UX-D-02-01, UX-D-02-05). Imports a component that does not exist yet —
 * this file is intentionally failing (module-resolution error) until Wave 2
 * creates `./add-connector-wizard`.
 *
 * Mirrors the `vi.mock('@/lib/queries/use-connectors-admin', ...)` pattern
 * from connector-form.test.tsx. Only the three documented hooks are mocked —
 * if a future implementation imports a hook beyond useCreateConnector /
 * useTestConnector / useConnectorTypes, this mock module will be missing it
 * and rendering will throw, catching an undocumented new-hook regression.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockCreate = vi.fn();
const mockTest = vi.fn();

const MOCK_TYPES = [
  {
    type: 'crowdstrike',
    name: 'CrowdStrike Spotlight',
    description: 'EDR + vulnerability scanner',
    fields: ['api_token', 'domain'],
    defaults: {},
    category: 'vulnerability_scanner',
    permissions: [{ scope: 'Scans', access: 'Read', purpose: 'List scan results' }],
    base_urls: {},
    setup_url: 'https://example.com/setup',
  },
];

vi.mock('@/lib/queries/use-connectors-admin', () => ({
  useCreateConnector: () => ({ mutate: mockCreate, isPending: false }),
  useTestConnector: () => ({ mutate: mockTest, isPending: false, data: null }),
  useConnectorTypes: () => ({ data: MOCK_TYPES, isPending: false, error: null }),
}));

import { AddConnectorWizard } from './add-connector-wizard';

describe('AddConnectorWizard (19-00 RED scaffold, UX-D-02-01, UX-D-02-05)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Test 1: renders the 4-label stepper with the credentials step visible first', () => {
    render(
      <AddConnectorWizard
        connectorType="crowdstrike"
        providerName="CrowdStrike Spotlight"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText('Provider')).toBeInTheDocument();
    expect(screen.getByText('Credentials')).toBeInTheDocument();
    expect(screen.getByText('Test')).toBeInTheDocument();
    expect(screen.getByText('Confirm')).toBeInTheDocument();
    expect(document.querySelector('input[name="api_token"]')).not.toBeNull();
  });

  it('Test 2: "Test connection" does not auto-fire on step entry (D-06) — only on click', () => {
    render(
      <AddConnectorWizard
        connectorType="crowdstrike"
        providerName="CrowdStrike Spotlight"
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(document.querySelector('input[name="api_token"]')!, {
      target: { value: 'tok' },
    });
    fireEvent.change(document.querySelector('input[name="domain"]')!, {
      target: { value: 'example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    // Arrived at the test step — mutate must NOT have fired yet.
    expect(mockTest).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /test connection/i }));
    expect(mockTest).toHaveBeenCalled();
  });

  it('Test 3: renders using only the three documented data hooks (no undocumented new hook)', () => {
    expect(() =>
      render(
        <AddConnectorWizard
          connectorType="crowdstrike"
          providerName="CrowdStrike Spotlight"
          onClose={vi.fn()}
        />,
      ),
    ).not.toThrow();
  });
});
