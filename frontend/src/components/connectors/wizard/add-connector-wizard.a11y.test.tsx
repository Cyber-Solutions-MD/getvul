// RED scaffold (19-00) — GREEN target for Wave 2.
/**
 * add-connector-wizard.a11y.test.tsx — RED scaffold, component-level axe sweep
 * for AddConnectorWizard (UX-D-02-06). Mirrors dashboard.a11y.test.tsx's
 * mock+render+axe(container) pattern. Imports a component that does not
 * exist yet — intentionally failing until Wave 2 creates `./add-connector-wizard`.
 */
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { axe } from 'vitest-axe';

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

describe('AddConnectorWizard axe (19-00 RED scaffold, UX-D-02-06)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('has no axe violations', async () => {
    const { container } = render(
      <AddConnectorWizard
        connectorType="crowdstrike"
        providerName="CrowdStrike Spotlight"
        onClose={vi.fn()}
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
