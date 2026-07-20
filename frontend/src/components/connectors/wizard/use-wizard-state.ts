/**
 * useWizardState — the four-step add-connector wizard's gating state machine
 * (19-00 Task 2). Step 1 "Provider" lives outside the dialog (D-01, the category
 * grid); this hook owns the three in-dialog steps: credentials -> test -> confirm.
 *
 * PLANNER DECISION (19-00): all fields treated required (fields: string[] wire
 * contract; GET /connectors/types flattens field metadata server-side — see
 * 19-RESEARCH Pitfall 1). Gating = all-non-empty. 100% of connector-type fields
 * are `required: True` today; if a future connector type ships an optional field,
 * this proxy will need revisiting (flagged in RESEARCH assumptions log, not a
 * Phase-19 blocker).
 *
 * D-08 (re-test invalidation, tamper-evident): editing ANY credential field after
 * a passing test clears the effective pass on the very first keystroke (onChange,
 * not onBlur) via `credentialsChangedSinceTest`. `testResult` itself is retained
 * (not nulled) so callers can distinguish "never tested" from "tested but stale" —
 * see `isTestStale` vs `testResult === null`.
 */
import { useReducer, useCallback, useMemo } from 'react';

export type WizardStep = 'credentials' | 'test' | 'confirm';

export interface WizardState {
  step: WizardStep;
  values: Record<string, string>;
  touched: Record<string, boolean>;
  testResult: { success: boolean; message: string } | null;
  credentialsChangedSinceTest: boolean;
  syncInterval: number;
}

export const SYNC_INTERVALS = [5, 15, 30, 60] as const;

const STEP_ORDER: WizardStep[] = ['credentials', 'test', 'confirm'];

type Action =
  | { type: 'UPDATE_FIELD'; name: string; value: string }
  | { type: 'SET_TEST_RESULT'; result: { success: boolean; message: string } }
  | { type: 'SET_SYNC_INTERVAL'; minutes: number }
  | { type: 'ADVANCE' }
  | { type: 'BACK' };

function initialState(): WizardState {
  return {
    step: 'credentials',
    values: {},
    touched: {},
    testResult: null,
    credentialsChangedSinceTest: false,
    syncInterval: 15,
  };
}

function canAdvanceFrom(state: WizardState, fields: string[]): boolean {
  switch (state.step) {
    case 'credentials':
      return fields.every((f) => (state.values[f] ?? '').trim() !== '');
    case 'test':
      return state.testResult?.success === true && !state.credentialsChangedSinceTest;
    case 'confirm':
      return true;
    default:
      return false;
  }
}

function reducer(state: WizardState, action: Action, fields: string[]): WizardState {
  switch (action.type) {
    case 'UPDATE_FIELD': {
      const values = { ...state.values, [action.name]: action.value };
      // D-08: first keystroke after a passing test invalidates it immediately.
      const credentialsChangedSinceTest =
        state.testResult !== null ? true : state.credentialsChangedSinceTest;
      return { ...state, values, touched: { ...state.touched, [action.name]: true }, credentialsChangedSinceTest };
    }
    case 'SET_TEST_RESULT':
      return { ...state, testResult: action.result, credentialsChangedSinceTest: false };
    case 'SET_SYNC_INTERVAL':
      return { ...state, syncInterval: action.minutes };
    case 'ADVANCE': {
      if (!canAdvanceFrom(state, fields)) return state;
      const idx = STEP_ORDER.indexOf(state.step);
      const next = STEP_ORDER[Math.min(idx + 1, STEP_ORDER.length - 1)];
      return { ...state, step: next };
    }
    case 'BACK': {
      const idx = STEP_ORDER.indexOf(state.step);
      const prev = STEP_ORDER[Math.max(idx - 1, 0)];
      return { ...state, step: prev };
    }
    default:
      return state;
  }
}

export function useWizardState(fields: string[]): {
  state: WizardState;
  allFieldsFilled: boolean;
  isTestStale: boolean;
  testPassed: boolean;
  canAdvance: boolean;
  updateField: (name: string, value: string) => void;
  setTestResult: (r: { success: boolean; message: string }) => void;
  setSyncInterval: (m: number) => void;
  advance: () => void;
  back: () => void;
  buildCredentials: () => Record<string, string> | undefined;
} {
  const [state, dispatch] = useReducer(
    (s: WizardState, a: Action) => reducer(s, a, fields),
    undefined,
    initialState,
  );

  const allFieldsFilled = useMemo(
    () => fields.every((f) => (state.values[f] ?? '').trim() !== ''),
    [fields, state.values],
  );

  const isTestStale = state.testResult !== null && state.credentialsChangedSinceTest;
  const testPassed = state.testResult?.success === true && !state.credentialsChangedSinceTest;

  const canAdvance = useMemo(() => canAdvanceFrom(state, fields), [state, fields]);

  const updateField = useCallback((name: string, value: string) => {
    dispatch({ type: 'UPDATE_FIELD', name, value });
  }, []);

  const setTestResult = useCallback((result: { success: boolean; message: string }) => {
    dispatch({ type: 'SET_TEST_RESULT', result });
  }, []);

  const setSyncInterval = useCallback((minutes: number) => {
    dispatch({ type: 'SET_SYNC_INTERVAL', minutes });
  }, []);

  const advance = useCallback(() => dispatch({ type: 'ADVANCE' }), []);
  const back = useCallback(() => dispatch({ type: 'BACK' }), []);

  // D-12: add-path — include only non-empty fields, never the sentinel literal
  // (add mode never displays a sentinel, so the literal can't appear in `values`).
  const buildCredentials = useCallback((): Record<string, string> | undefined => {
    const creds: Record<string, string> = {};
    for (const f of fields) {
      const v = state.values[f];
      if (v && v.trim() !== '') creds[f] = v;
    }
    return Object.keys(creds).length > 0 ? creds : undefined;
  }, [fields, state.values]);

  return {
    state,
    allFieldsFilled,
    isTestStale,
    testPassed,
    canAdvance,
    updateField,
    setTestResult,
    setSyncInterval,
    advance,
    back,
    buildCredentials,
  };
}
