// @vitest-environment jsdom
/**
 * use-wizard-state.test.ts — TDD RED-phase tests for useWizardState (19-00 Task 2).
 *
 * Test A (UX-D-02-01 ordering): initial step, advance()/back() sequencing.
 * Test B (UX-D-02-02 credentials gate): canAdvance false until all fields non-empty.
 * Test C (test gate): canAdvance false until testResult.success === true.
 * Test D (D-08 first-keystroke invalidation): editing a field after a pass sets
 *   isTestStale === true and re-gates canAdvance on the test step.
 * Test E (Pitfall 4 bounce — MUST pass): test pass -> confirm -> back -> back ->
 *   credentials-changed -> re-test pass -> advance twice -> isTestStale === false.
 * Test F (buildCredentials add-path, D-12): non-empty fields only, undefined when
 *   all empty, never contains the sentinel literal.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useWizardState } from './use-wizard-state';

const FIELDS = ['api_token', 'domain'];

describe('useWizardState (19-00)', () => {
  it('Test A: initial step is credentials; advance/back sequence follows credentials -> test -> confirm', () => {
    const { result } = renderHook(() => useWizardState(FIELDS));
    expect(result.current.state.step).toBe('credentials');

    // Fill fields so advance is not blocked by the credentials gate.
    act(() => {
      result.current.updateField('api_token', 'tok');
      result.current.updateField('domain', 'example.com');
    });
    act(() => {
      result.current.advance();
    });
    expect(result.current.state.step).toBe('test');

    act(() => {
      result.current.setTestResult({ success: true, message: 'ok' });
    });
    act(() => {
      result.current.advance();
    });
    expect(result.current.state.step).toBe('confirm');

    act(() => {
      result.current.back();
    });
    expect(result.current.state.step).toBe('test');
  });

  it('Test B: canAdvance on credentials step is false until BOTH fields are non-empty (whitespace does not count)', () => {
    const { result } = renderHook(() => useWizardState(FIELDS));
    expect(result.current.canAdvance).toBe(false);

    act(() => {
      result.current.updateField('api_token', 'tok');
    });
    expect(result.current.canAdvance).toBe(false);

    act(() => {
      result.current.updateField('domain', '   ');
    });
    expect(result.current.canAdvance).toBe(false);

    act(() => {
      result.current.updateField('domain', 'example.com');
    });
    expect(result.current.canAdvance).toBe(true);
  });

  it('Test B2 (WR-03): canAdvance on credentials step is false when fields is empty (vacuous-every gate hole)', () => {
    const { result } = renderHook(() => useWizardState([]));
    // With no fields, `[].every()` would be vacuously true — the gate must
    // stay closed so a wizard mounted before useConnectorTypes() resolves
    // cannot advance / submit empty credentials.
    expect(result.current.state.step).toBe('credentials');
    expect(result.current.canAdvance).toBe(false);
  });

  it('Test C: canAdvance on test step is false until a successful test result; stays false after a failure', () => {
    const { result } = renderHook(() => useWizardState(FIELDS));
    act(() => {
      result.current.updateField('api_token', 'tok');
      result.current.updateField('domain', 'example.com');
      result.current.advance();
    });
    expect(result.current.state.step).toBe('test');
    expect(result.current.canAdvance).toBe(false);

    act(() => {
      result.current.setTestResult({ success: false, message: 'nope' });
    });
    expect(result.current.canAdvance).toBe(false);

    act(() => {
      result.current.setTestResult({ success: true, message: 'ok' });
    });
    expect(result.current.canAdvance).toBe(true);
  });

  it('Test D (D-08): editing a field after a passing test sets isTestStale and re-gates canAdvance', () => {
    const { result } = renderHook(() => useWizardState(FIELDS));
    act(() => {
      result.current.updateField('api_token', 'tok');
      result.current.updateField('domain', 'example.com');
      result.current.advance();
    });
    act(() => {
      result.current.setTestResult({ success: true, message: 'ok' });
    });
    expect(result.current.isTestStale).toBe(false);
    expect(result.current.canAdvance).toBe(true);

    // First keystroke after a pass — must clear the gate immediately.
    act(() => {
      result.current.updateField('api_token', 'tok-changed');
    });
    expect(result.current.isTestStale).toBe(true);
    expect(result.current.canAdvance).toBe(false);
    // isTestStale is distinct from testResult === null — the raw result is retained.
    expect(result.current.state.testResult).not.toBeNull();
  });

  it('Test E (Pitfall 4 bounce scenario — MUST pass): a fresh passing re-test after an edit is NOT stale at confirm', () => {
    const { result } = renderHook(() => useWizardState(FIELDS));
    act(() => {
      result.current.updateField('api_token', 'tok');
      result.current.updateField('domain', 'example.com');
      result.current.advance(); // -> test
    });
    act(() => {
      result.current.setTestResult({ success: true, message: 'ok' });
    });
    act(() => {
      result.current.advance(); // -> confirm
    });
    expect(result.current.state.step).toBe('confirm');

    act(() => {
      result.current.back(); // -> test
    });
    act(() => {
      result.current.back(); // -> credentials
    });
    expect(result.current.state.step).toBe('credentials');

    // Edit — invalidates the prior test.
    act(() => {
      result.current.updateField('api_token', 'tok-edited');
    });
    expect(result.current.isTestStale).toBe(true);

    // Re-test successfully.
    act(() => {
      result.current.setTestResult({ success: true, message: 'ok again' });
    });
    expect(result.current.isTestStale).toBe(false);

    act(() => {
      result.current.advance(); // -> test
    });
    act(() => {
      result.current.advance(); // -> confirm
    });
    expect(result.current.state.step).toBe('confirm');
    expect(result.current.isTestStale).toBe(false);
  });

  it('Test F (D-12): buildCredentials returns only non-empty fields, undefined when all empty, never the sentinel', () => {
    const { result } = renderHook(() => useWizardState(FIELDS));
    expect(result.current.buildCredentials()).toBeUndefined();

    act(() => {
      result.current.updateField('api_token', 'tok');
      result.current.updateField('domain', '   ');
    });
    const creds = result.current.buildCredentials();
    expect(creds).toEqual({ api_token: 'tok' });
    expect(JSON.stringify(creds)).not.toContain('••••••');
  });
});
