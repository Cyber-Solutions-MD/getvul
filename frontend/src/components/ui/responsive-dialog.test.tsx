/**
 * responsive-dialog.test.tsx — Vitest coverage for the `dismissOnBackdropClick`
 * opt-out prop (19-03 Task 2, D-13).
 *
 * jsdom renders the desktop branch (`useMediaQuery` returns false on first
 * render), matching the existing ConfirmModal test assumption.
 */
import { render, fireEvent, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ResponsiveDialog } from './responsive-dialog';

describe('ResponsiveDialog dismissOnBackdropClick (19-03 Task 2, D-13)', () => {
  it('Test 1: default parity — backdrop click dismisses (dismissOnBackdropClick unset)', () => {
    const onOpenChange = vi.fn();
    render(
      <ResponsiveDialog open onOpenChange={onOpenChange}>
        <div>content</div>
      </ResponsiveDialog>,
    );
    const overlay = screen.getByRole('presentation');
    fireEvent.click(overlay);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('Test 2: D-13 opt-out — backdrop click is a no-op, Esc still closes', () => {
    const onOpenChange = vi.fn();
    render(
      <ResponsiveDialog open onOpenChange={onOpenChange} dismissOnBackdropClick={false}>
        <div>content</div>
      </ResponsiveDialog>,
    );
    const overlay = screen.getByRole('presentation');

    fireEvent.click(overlay);
    expect(onOpenChange).not.toHaveBeenCalled();

    fireEvent.keyDown(overlay, { key: 'Escape' });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('Test 3: clicking inside the inner dialog panel never dismisses (default)', () => {
    const onOpenChange = vi.fn();
    render(
      <ResponsiveDialog open onOpenChange={onOpenChange}>
        <div>content</div>
      </ResponsiveDialog>,
    );
    fireEvent.click(screen.getByRole('dialog'));
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it('Test 4: clicking inside the inner dialog panel never dismisses (opt-out)', () => {
    const onOpenChange = vi.fn();
    render(
      <ResponsiveDialog open onOpenChange={onOpenChange} dismissOnBackdropClick={false}>
        <div>content</div>
      </ResponsiveDialog>,
    );
    fireEvent.click(screen.getByRole('dialog'));
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
