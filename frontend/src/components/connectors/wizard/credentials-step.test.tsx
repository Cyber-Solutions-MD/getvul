// RED scaffold (19-00) — GREEN target for Wave 1.
/**
 * credentials-step.test.tsx — RED scaffold for CredentialsStep (UX-D-02-03).
 * Imports a component that does not exist yet — this file is intentionally
 * failing (module-resolution error) until Wave 1 creates `./credentials-step`.
 *
 * Pins: two inputs render for two fields; a secret-named field (api_token)
 * renders as type="password" with an Eye toggle (`button[data-eye-toggle]`);
 * typing calls the injected onFieldChange; the D-12 non-empty-only rule is
 * mirrored at the values-prop boundary the wizard hook feeds this component.
 */
import { render, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { CredentialsStep } from './credentials-step';

const FIELDS = ['api_token', 'domain'];

describe('CredentialsStep (19-00 RED scaffold, UX-D-02-03)', () => {
  it('renders one input per field', () => {
    render(<CredentialsStep fields={FIELDS} values={{}} onFieldChange={vi.fn()} />);
    const inputs = document.querySelectorAll('input[type="text"], input[type="password"]');
    expect(inputs.length).toBe(FIELDS.length);
  });

  it('renders a secret-named field (api_token) as type="password" with an Eye toggle', () => {
    render(<CredentialsStep fields={FIELDS} values={{}} onFieldChange={vi.fn()} />);
    const secretInput = document.querySelector('input[name="api_token"]');
    expect(secretInput).not.toBeNull();
    expect((secretInput as HTMLInputElement).type).toBe('password');
    expect(
      document.querySelector('button[data-eye-toggle][data-field="api_token"]'),
    ).not.toBeNull();
  });

  it('typing into a field calls onFieldChange with the field name and new value', () => {
    const onFieldChange = vi.fn();
    render(<CredentialsStep fields={FIELDS} values={{}} onFieldChange={onFieldChange} />);
    const domainInput = document.querySelector('input[name="domain"]') as HTMLInputElement;
    fireEvent.change(domainInput, { target: { value: 'example.com' } });
    expect(onFieldChange).toHaveBeenCalledWith('domain', 'example.com');
  });

  it('reflects the values prop into rendered inputs (single source of truth for buildCredentials)', () => {
    const values = { api_token: 'tok', domain: '  ' };
    render(<CredentialsStep fields={FIELDS} values={values} onFieldChange={vi.fn()} />);
    const domainInput = document.querySelector('input[name="domain"]') as HTMLInputElement;
    expect(domainInput.value).toBe('  ');
    // Whitespace-only values must never be treated as "filled" downstream (D-12) —
    // asserted here as a value-shape contract; useWizardState owns the actual gate.
    expect(domainInput.value.trim()).toBe('');
  });
});
