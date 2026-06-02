/**
 * save-bar.test.tsx — TDD RED phase tests for SaveBar + useDirtyState.
 *
 * SaveBar behaviors verified:
 * 1. isDirty=false: renders nothing
 * 2. isDirty=true: renders "Save changes" + "Discard" buttons
 * 3. Clicking Save calls onSave; clicking Discard calls onDiscard
 * 4. isSaving=true: Save button disabled and shows "Saving…"
 *
 * useDirtyState behaviors verified:
 * 5. Initial state: isDirty=false; after setField('a',2) isDirty=true; reset() isDirty=false
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { SaveBar } from './save-bar';
import { useDirtyState } from './use-dirty-state';

describe('SaveBar', () => {
  it('Test 1: renders nothing when isDirty=false', () => {
    const { container } = render(
      <SaveBar isDirty={false} isSaving={false} onSave={vi.fn()} onDiscard={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
    // The data-save-bar hook should not exist
    expect(container.querySelector('[data-save-bar]')).toBeNull();
  });

  it('Test 2: renders Save changes + Discard when isDirty=true', () => {
    render(
      <SaveBar isDirty={true} isSaving={false} onSave={vi.fn()} onDiscard={vi.fn()} />,
    );

    expect(screen.getByText('Save changes')).toBeDefined();
    expect(screen.getByText('Discard')).toBeDefined();
    expect(screen.getByText('Unsaved changes')).toBeDefined();
  });

  it('Test 3a: clicking Save calls onSave', () => {
    const onSave = vi.fn();
    render(
      <SaveBar isDirty={true} isSaving={false} onSave={onSave} onDiscard={vi.fn()} />,
    );

    fireEvent.click(screen.getByText('Save changes'));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it('Test 3b: clicking Discard calls onDiscard', () => {
    const onDiscard = vi.fn();
    render(
      <SaveBar isDirty={true} isSaving={false} onSave={vi.fn()} onDiscard={onDiscard} />,
    );

    fireEvent.click(screen.getByText('Discard'));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it('Test 4: isSaving=true disables Save button and shows Saving…', () => {
    render(
      <SaveBar isDirty={true} isSaving={true} onSave={vi.fn()} onDiscard={vi.fn()} />,
    );

    // Button label changes to "Saving…"
    const savingBtn = screen.getByText('Saving…');
    expect(savingBtn).toBeDefined();

    // "Save changes" text should not appear when saving
    expect(screen.queryByText('Save changes')).toBeNull();

    // The save button should be disabled
    const btn = savingBtn.closest('button');
    expect(btn?.disabled).toBe(true);
  });

  it('Test 4b: data-save-bar attribute is present when isDirty=true', () => {
    const { container } = render(
      <SaveBar isDirty={true} isSaving={false} onSave={vi.fn()} onDiscard={vi.fn()} />,
    );
    expect(container.querySelector('[data-save-bar]')).not.toBeNull();
  });
});

describe('useDirtyState', () => {
  it('Test 5: initial isDirty=false; setField makes dirty; reset clears', () => {
    const { result } = renderHook(() => useDirtyState({ a: 1 }));

    // Initial state — not dirty
    expect(result.current.isDirty).toBe(false);
    expect(result.current.values).toEqual({ a: 1 });

    // setField('a', 2) — dirty
    act(() => {
      result.current.setField('a', 2);
    });
    expect(result.current.isDirty).toBe(true);
    expect(result.current.values).toEqual({ a: 2 });

    // reset() — back to clean
    act(() => {
      result.current.reset();
    });
    expect(result.current.isDirty).toBe(false);
    // reset() with no args reverts to the current values as new baseline
  });

  it('Test 5b: reset(next) sets both baseline and values, clearing dirty', () => {
    const { result } = renderHook(() => useDirtyState({ a: 1, b: 'hello' }));

    act(() => {
      result.current.setField('a', 99);
    });
    expect(result.current.isDirty).toBe(true);

    // reset with new values — used after successful PATCH
    act(() => {
      result.current.reset({ a: 99, b: 'world' });
    });
    expect(result.current.isDirty).toBe(false);
    expect(result.current.values).toEqual({ a: 99, b: 'world' });
  });

  it('Test 5c: setField on a key that does not change value keeps isDirty=false', () => {
    const { result } = renderHook(() => useDirtyState({ x: 42 }));

    act(() => {
      result.current.setField('x', 42);
    });
    expect(result.current.isDirty).toBe(false);
  });
});
