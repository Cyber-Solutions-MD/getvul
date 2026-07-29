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
  // 24-01: data-driven ANTHROPIC case — mirrors the real GET /connectors/types
  // shape's additive `field_specs` (select options + hints, required: false).
  {
    type: 'ANTHROPIC',
    name: 'Anthropic',
    description: 'BYOK Claude access for AI-assisted triage',
    fields: ['api_key', 'model', 'monthly_budget_usd'],
    field_specs: {
      api_key: { type: 'password', label: 'Anthropic API Key', required: true, config: false },
      model: {
        type: 'select',
        label: 'Model',
        required: true,
        config: true,
        options: [
          { value: 'claude-sonnet-5', label: 'Sonnet 5', hint: 'Recommended balance of cost and quality' },
          { value: 'claude-opus-5', label: 'Opus 5', hint: 'Higher cost, highest quality' },
          { value: 'claude-haiku-4-5', label: 'Haiku', hint: 'Cheapest, lower grounding fidelity' },
        ],
      },
      monthly_budget_usd: {
        type: 'number',
        label: 'Monthly budget (USD)',
        required: false,
        config: true,
        help: 'Optional — AI calls pause for the rest of the month once this is reached.',
      },
    },
    defaults: {},
    category: 'ai_assistant',
    permissions: [{ scope: 'messages', access: 'Write', purpose: 'Generate grounded vulnerability explanations (BYOK)' }],
    base_urls: {},
    setup_url: 'https://console.anthropic.com/settings/keys',
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

describe('AddConnectorWizard — ANTHROPIC (24-01, D-01/D-05/D-06)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the model select with 3 fixed-order options, each with a D-05 guidance hint', () => {
    render(
      <AddConnectorWizard connectorType="ANTHROPIC" providerName="Anthropic" onClose={vi.fn()} />,
    );
    const select = document.querySelector('select[name="model"]') as HTMLSelectElement;
    expect(select).not.toBeNull();
    const optionValues = Array.from(select.options).map((o) => o.value);
    expect(optionValues).toEqual(['claude-sonnet-5', 'claude-opus-5', 'claude-haiku-4-5']);
    // Default selection is Sonnet 5 (D-01) — its D-05 hint shows immediately.
    expect(screen.getByText('Recommended balance of cost and quality')).toBeInTheDocument();
  });

  it('monthly_budget_usd is optional — Next enables with only api_key filled, budget left empty', () => {
    render(
      <AddConnectorWizard connectorType="ANTHROPIC" providerName="Anthropic" onClose={vi.fn()} />,
    );
    const nextButton = screen.getByRole('button', { name: /next/i });
    // Before filling api_key, the gate is closed.
    expect(nextButton).toHaveAttribute('aria-disabled', 'true');

    fireEvent.change(document.querySelector('input[name="api_key"]')!, {
      target: { value: 'sk-ant-fake-test-key' },
    });
    // model already defaults to claude-sonnet-5; monthly_budget_usd stays empty.
    expect(nextButton).toHaveAttribute('aria-disabled', 'false');
  });

  it('completes provider -> credentials -> test -> confirm and submits model/budget via config, not credentials', () => {
    mockTest.mockImplementation((_body, { onSuccess }: { onSuccess: (r: unknown) => void }) => {
      onSuccess({ success: true, message: 'Key validated for claude-sonnet-5' });
    });

    render(
      <AddConnectorWizard connectorType="ANTHROPIC" providerName="Anthropic" onClose={vi.fn()} />,
    );

    // Step 1 (Provider) is pre-picked outside the dialog — stepper starts on Credentials.
    expect(screen.getByText('Provider')).toBeInTheDocument();

    fireEvent.change(document.querySelector('input[name="api_key"]')!, {
      target: { value: 'sk-ant-fake-test-key' },
    });
    fireEvent.change(document.querySelector('input[name="monthly_budget_usd"]')!, {
      target: { value: '50' },
    });
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    // Test step — click "Test connection".
    fireEvent.click(screen.getByRole('button', { name: /test connection/i }));
    expect(mockTest).toHaveBeenCalledWith(
      expect.objectContaining({
        connector_type: 'ANTHROPIC',
        credentials: { api_key: 'sk-ant-fake-test-key' },
        config: { model: 'claude-sonnet-5', monthly_budget_usd: 50 },
      }),
      expect.anything(),
    );
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    // Confirm step — "Add connector" submits credentials + config split correctly.
    fireEvent.click(screen.getByRole('button', { name: /add connector/i }));
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        connector_type: 'ANTHROPIC',
        credentials: { api_key: 'sk-ant-fake-test-key' },
        config: { model: 'claude-sonnet-5', monthly_budget_usd: 50 },
      }),
      expect.anything(),
    );
    // The API key must never appear inside the submitted config.
    const createCallBody = mockCreate.mock.calls[0][0];
    expect(createCallBody.config).not.toHaveProperty('api_key');
  });
});
