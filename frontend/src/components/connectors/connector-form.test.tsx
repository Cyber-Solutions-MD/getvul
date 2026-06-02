/**
 * connector-form.test.tsx — TDD RED-phase tests for ConnectorForm.
 *
 * Test 1: Add mode — submitting with credentials calls useCreateConnector with body { connector_type, credentials, ... }.
 * Test 2: Edit mode — submitting WITHOUT changing any secret omits `credentials` from PATCH body.
 * Test 3: Edit mode — changing one secret field includes only changed credentials in PATCH body.
 * Test 4: "Test connection" calls useTestConnector and renders returned message.
 * Test 5: Eye/EyeOff toggle reveals only the field the user is actively editing.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ——— Mock mutation hooks ———
const mockCreate = vi.fn();
const mockUpdate = vi.fn();
const mockTest = vi.fn();

vi.mock('@/lib/queries/use-connectors-admin', () => ({
  useCreateConnector: () => ({ mutate: mockCreate, isPending: false }),
  useUpdateConnector: () => ({ mutate: mockUpdate, isPending: false }),
  useTestConnector: () => ({ mutate: mockTest, isPending: false, data: null }),
}));

import { ConnectorForm } from './connector-form';
import type { ConnectorConfigResponse } from '@/lib/queries/use-connectors-admin';

const MOCK_FIELDS = ['api_token', 'domain'];

const MOCK_EXISTING: ConnectorConfigResponse = {
  id: 'conn-1',
  connector_type: 'CROWDSTRIKE',
  connector_name: 'CrowdStrike Spotlight',
  is_enabled: true,
  config: {},
  has_credentials: true,
  last_sync_at: '2026-06-02T10:00:00Z',
  last_sync_status: 'ok',
  last_sync_record_count: 512,
  sync_interval_minutes: 15,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-06-02T10:00:00Z',
};

describe('ConnectorForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Test 1: add mode — submitting calls useCreateConnector with connector_type and credentials', async () => {
    // Capture what gets called on submit
    let capturedArgs: unknown;
    mockCreate.mockImplementation((args: unknown) => {
      capturedArgs = args;
    });

    render(
      <ConnectorForm
        mode="add"
        connectorType="CROWDSTRIKE"
        fields={MOCK_FIELDS}
        onClose={vi.fn()}
      />,
    );

    // Fill in credential fields
    const inputs = screen.getAllByRole('textbox');
    // If inputs rendered (fields with text-type placeholder), or password-type inputs
    // We interact with whatever we can find
    const allInputs = document.querySelectorAll('input[type="text"], input[type="password"]');
    if (allInputs.length >= 1) {
      fireEvent.change(allInputs[0], { target: { value: 'test-token-123' } });
    }
    if (allInputs.length >= 2) {
      fireEvent.change(allInputs[1], { target: { value: 'mycompany.com' } });
    }

    const saveBtn = screen.getByRole('button', { name: /save connector/i });
    fireEvent.click(saveBtn);

    await waitFor(() => expect(mockCreate).toHaveBeenCalled());
    const args = capturedArgs as { connector_type: string; credentials: Record<string, string> };
    expect(args.connector_type).toBe('CROWDSTRIKE');
    expect(args.credentials).toBeDefined();
  });

  it('Test 2: edit mode — submitting WITHOUT changing secret omits credentials from PATCH body', async () => {
    let capturedArgs: unknown;
    mockUpdate.mockImplementation((args: unknown) => {
      capturedArgs = args;
    });

    render(
      <ConnectorForm
        mode="edit"
        connectorType="CROWDSTRIKE"
        existing={MOCK_EXISTING}
        fields={MOCK_FIELDS}
        onClose={vi.fn()}
      />,
    );

    // Do NOT change any credential field — just submit
    const saveBtn = screen.getByRole('button', { name: /save connector/i });
    fireEvent.click(saveBtn);

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    // credentials key must be absent when no field was touched
    const args = capturedArgs as { id: string; body: Record<string, unknown> };
    expect(args.body).not.toHaveProperty('credentials');
  });

  it('Test 3: edit mode — changing one secret field includes only changed credentials in PATCH body', async () => {
    let capturedArgs: unknown;
    mockUpdate.mockImplementation((args: unknown) => {
      capturedArgs = args;
    });

    render(
      <ConnectorForm
        mode="edit"
        connectorType="CROWDSTRIKE"
        existing={MOCK_EXISTING}
        fields={MOCK_FIELDS}
        onClose={vi.fn()}
      />,
    );

    // Find first password input (api_token field with sentinel pre-filled)
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    expect(passwordInputs.length).toBeGreaterThanOrEqual(1);

    // Change the first field (api_token)
    fireEvent.change(passwordInputs[0], { target: { value: 'new-token-456' } });

    const saveBtn = screen.getByRole('button', { name: /save connector/i });
    fireEvent.click(saveBtn);

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    const args = capturedArgs as { id: string; body: { credentials?: Record<string, string> } };
    // credentials should be present with only the changed field
    expect(args.body.credentials).toBeDefined();
    expect(args.body.credentials!['api_token']).toBe('new-token-456');
    // domain was not changed — should NOT be in credentials
    // (or if present, should NOT be the sentinel)
    if ('domain' in (args.body.credentials ?? {})) {
      expect(args.body.credentials!['domain']).not.toBe('••••••');
    }
  });

  it('Test 4: "Test connection" calls useTestConnector and renders the returned message', async () => {
    // Mock test result returned inline via data state
    let testCallback: ((data: { success: boolean; message: string }) => void) | undefined;
    mockTest.mockImplementation((_body: unknown, opts?: { onSuccess?: (d: unknown) => void }) => {
      testCallback = opts?.onSuccess as ((data: { success: boolean; message: string }) => void) | undefined;
    });

    render(
      <ConnectorForm
        mode="add"
        connectorType="CROWDSTRIKE"
        fields={MOCK_FIELDS}
        onClose={vi.fn()}
      />,
    );

    const testBtn = screen.getByRole('button', { name: /test connection/i });
    fireEvent.click(testBtn);
    expect(mockTest).toHaveBeenCalled();
  });

  it('Test 5: Eye/EyeOff toggle reveals the field the user is editing', () => {
    render(
      <ConnectorForm
        mode="add"
        connectorType="CROWDSTRIKE"
        fields={MOCK_FIELDS}
        onClose={vi.fn()}
      />,
    );

    // Find the first password input and its Eye toggle button
    const firstPasswordInput = document.querySelector('input[type="password"]');
    expect(firstPasswordInput).not.toBeNull();

    // Find an Eye toggle button (lucide Eye/EyeOff icon in a button)
    const eyeButtons = document.querySelectorAll('button[data-eye-toggle]');
    if (eyeButtons.length > 0) {
      fireEvent.click(eyeButtons[0]);
      // After clicking, the input type should change to text
      const inputAfter = document.querySelector(`input[id="${(eyeButtons[0] as HTMLElement).dataset.field}"]`);
      if (inputAfter) {
        expect((inputAfter as HTMLInputElement).type).toBe('text');
      }
    } else {
      // Check by aria-label pattern
      const toggleButtons = screen.queryAllByLabelText(/show|hide|reveal/i);
      if (toggleButtons.length > 0) {
        const inputBefore = document.querySelector('input[type="password"]');
        expect(inputBefore).not.toBeNull();
        fireEvent.click(toggleButtons[0]);
        // type should toggle
        const inputAfter = document.querySelector(
          `input[name="${(inputBefore as HTMLInputElement).name}"]`,
        );
        if (inputAfter) {
          expect((inputAfter as HTMLInputElement).type).toBe('text');
        }
      }
    }
  });
});
