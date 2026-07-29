/**
 * useWizardState — the four-step add-connector wizard's gating state machine
 * (19-00 Task 2). Step 1 "Provider" lives outside the dialog (D-01, the category
 * grid); this hook owns the three in-dialog steps: credentials -> test -> confirm.
 *
 * PLANNER DECISION (19-00): all fields treated required (fields: string[] wire
 * contract; GET /connectors/types flattens field metadata server-side — see
 * 19-RESEARCH Pitfall 1). Gating = all-non-empty. 100% of connector-type fields
 * were `required: True` at the time — that proxy is now revisited (24-01): an
 * optional `fieldSpecs` map (from GET /connectors/types' additive `field_specs`)
 * lets a field opt out of the all-non-empty gate via `required: false` (e.g.
 * the ANTHROPIC connector's `monthly_budget_usd`). Connector types with no
 * fieldSpecs entry for a field keep the original all-required behavior
 * (`required` defaults true when unspecified) — zero behavior change for the
 * 14 pre-existing connector types.
 *
 * `fieldSpecs` also carries a `config: boolean` per-field flag (24-01): fields
 * marked `config: true` (e.g. ANTHROPIC's `model`, `monthly_budget_usd`) are
 * NOT secrets — they route into `ConnectorConfig.config` (plaintext JSONB) at
 * submit time via `buildConfig()`, not the Fernet-encrypted `credentials` blob
 * `buildCredentials()` still produces. Fields with no fieldSpecs entry default
 * to `config: false` (credentials), matching every existing connector type.
 *
 * D-08 (re-test invalidation, tamper-evident): editing ANY credential field after
 * a passing test clears the effective pass on the very first keystroke (onChange,
 * not onBlur) via `credentialsChangedSinceTest`. `testResult` itself is retained
 * (not nulled) so callers can distinguish "never tested" from "tested but stale" —
 * see `isTestStale` vs `testResult === null`.
 */
import { useReducer, useCallback, useMemo } from 'react';
import type { ConnectorFieldSpec } from '@/lib/queries/use-connectors-admin';

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

type FieldSpecs = Record<string, ConnectorFieldSpec>;

type Action =
  | { type: 'UPDATE_FIELD'; name: string; value: string }
  | { type: 'SET_TEST_RESULT'; result: { success: boolean; message: string } }
  | { type: 'SET_SYNC_INTERVAL'; minutes: number }
  | { type: 'ADVANCE' }
  | { type: 'BACK' };

function isRequired(fieldSpecs: FieldSpecs, field: string): boolean {
  return fieldSpecs[field]?.required !== false;
}

function isConfigField(fieldSpecs: FieldSpecs, field: string): boolean {
  return fieldSpecs[field]?.config === true;
}

function initialState(fields: string[], fieldSpecs: FieldSpecs): WizardState {
  // Pre-populate `select` fields with their first option's value so a
  // required select is never "empty" from the gate's perspective, and so
  // TestStep/ConfirmStep send a real value even if the analyst never
  // touches the dropdown (D-01's default = the first option, e.g. Sonnet 5).
  const values: Record<string, string> = {};
  for (const f of fields) {
    const spec = fieldSpecs[f];
    if (spec?.type === 'select' && spec.options && spec.options.length > 0) {
      values[f] = spec.options[0].value;
    }
  }
  return {
    step: 'credentials',
    values,
    touched: {},
    testResult: null,
    credentialsChangedSinceTest: false,
    syncInterval: 15,
  };
}

function canAdvanceFrom(state: WizardState, fields: string[], fieldSpecs: FieldSpecs): boolean {
  switch (state.step) {
    case 'credentials':
      // WR-03: `[].every()` is vacuously true, so require at least one field
      // before the gate can open — otherwise a wizard mounted before
      // useConnectorTypes() resolves (fields === []) would enable Next with
      // zero inputs rendered and let the user advance / submit empty creds.
      return (
        fields.length > 0 &&
        fields.every((f) => !isRequired(fieldSpecs, f) || (state.values[f] ?? '').trim() !== '')
      );
    case 'test':
      return state.testResult?.success === true && !state.credentialsChangedSinceTest;
    case 'confirm':
      return true;
    default:
      return false;
  }
}

function reducer(state: WizardState, action: Action, fields: string[], fieldSpecs: FieldSpecs): WizardState {
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
      if (!canAdvanceFrom(state, fields, fieldSpecs)) return state;
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

export function useWizardState(
  fields: string[],
  fieldSpecs: FieldSpecs = {},
): {
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
  buildConfig: () => Record<string, unknown> | undefined;
} {
  const [state, dispatch] = useReducer(
    (s: WizardState, a: Action) => reducer(s, a, fields, fieldSpecs),
    undefined,
    () => initialState(fields, fieldSpecs),
  );

  const allFieldsFilled = useMemo(
    () => fields.every((f) => !isRequired(fieldSpecs, f) || (state.values[f] ?? '').trim() !== ''),
    [fields, fieldSpecs, state.values],
  );

  const isTestStale = state.testResult !== null && state.credentialsChangedSinceTest;
  const testPassed = state.testResult?.success === true && !state.credentialsChangedSinceTest;

  const canAdvance = useMemo(() => canAdvanceFrom(state, fields, fieldSpecs), [state, fields, fieldSpecs]);

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

  // D-12: add-path — include only non-empty, non-config fields, never the
  // sentinel literal (add mode never displays a sentinel, so the literal
  // can't appear in `values`). config:true fields (24-01) are routed to
  // buildConfig() instead — never Fernet-encrypted.
  const buildCredentials = useCallback((): Record<string, string> | undefined => {
    const creds: Record<string, string> = {};
    for (const f of fields) {
      if (isConfigField(fieldSpecs, f)) continue;
      const v = state.values[f];
      if (v && v.trim() !== '') creds[f] = v;
    }
    return Object.keys(creds).length > 0 ? creds : undefined;
  }, [fields, fieldSpecs, state.values]);

  // 24-01: config:true fields (model, monthly_budget_usd) round-trip into
  // ConnectorConfig.config (plaintext) — never into the encrypted credentials
  // blob. `number`-typed fields coerce from the input's string value; an
  // empty optional field is omitted entirely (D-06: no budget cap set).
  const buildConfig = useCallback((): Record<string, unknown> | undefined => {
    const cfg: Record<string, unknown> = {};
    for (const f of fields) {
      if (!isConfigField(fieldSpecs, f)) continue;
      const v = state.values[f];
      if (v === undefined || v.trim() === '') continue;
      cfg[f] = fieldSpecs[f]?.type === 'number' ? Number(v) : v;
    }
    return Object.keys(cfg).length > 0 ? cfg : undefined;
  }, [fields, fieldSpecs, state.values]);

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
    buildConfig,
  };
}
