/**
 * useDirtyState — per-category dirty-tracking hook for Settings panes.
 *
 * Tracks whether the current form values differ from the baseline (last saved state).
 * Designed for flat settings payloads (shallow object comparison via JSON.stringify).
 *
 * Security note (T-14-05):
 *   Pure client state. No security impact — the backend validates every PATCH body
 *   via Pydantic regardless of what this hook reports. isDirty is a UX convenience only.
 *
 * Usage pattern (mirrors Phase 12 reassign-combobox dirty/cancel pattern):
 *   const { values, setField, isDirty, reset } = useDirtyState(initial);
 *   // On successful PATCH:
 *   reset(savedValues); // clears dirty + sets new baseline
 */

import { useCallback, useRef, useState } from 'react';

export interface DirtyStateResult<T extends Record<string, unknown>> {
  /** Current (possibly dirty) form values. */
  values: T;
  /** Set a single field by key. */
  setField: (key: keyof T, val: unknown) => void;
  /** True when current values differ from baseline. */
  isDirty: boolean;
  /**
   * Reset dirty state.
   * - reset() with no args: uses current values as the new baseline (dirty cleared).
   * - reset(next): replaces both baseline and values with next (used after successful PATCH).
   */
  reset: (next?: T) => void;
}

export function useDirtyState<T extends Record<string, unknown>>(
  initial: T,
): DirtyStateResult<T> {
  // State holds both values and a serialized snapshot of the baseline.
  // Keeping baselineJson in state ensures re-renders when reset() is called without args.
  const [values, setValues] = useState<T>(initial);
  const [baselineJson, setBaselineJson] = useState<string>(
    JSON.stringify(initial),
  );
  const baseline = useRef<T>(initial);

  const isDirty = JSON.stringify(values) !== baselineJson;

  const setField = useCallback(
    (key: keyof T, val: unknown) => {
      setValues((prev) => ({ ...prev, [key]: val } as T));
    },
    [],
  );

  const reset = useCallback(
    (next?: T) => {
      if (next !== undefined) {
        // Explicit next — set both baseline and values to next (post-save use case).
        baseline.current = next;
        const serialized = JSON.stringify(next);
        setBaselineJson(serialized);
        setValues(next);
      } else {
        // No arg — promote current values to the new baseline.
        // Use functional update to get the latest values atomically.
        setValues((current) => {
          baseline.current = current;
          setBaselineJson(JSON.stringify(current));
          return current;
        });
      }
    },
    [],
  );

  return { values, setField, isDirty, reset };
}
