/**
 * focus-trap — minimal keyboard focus-trap helpers for modal dialogs (WR-04).
 *
 * No external dependency: we collect the focusable descendants of a container
 * and wrap Tab / Shift+Tab at the boundaries so focus cannot escape to the page
 * behind a modal backdrop while it is open.
 */

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/** Returns the visible, focusable elements inside `container`, in DOM order. */
export function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => el.offsetParent !== null || el === document.activeElement);
}

/**
 * Given a Tab keydown event and the ordered focusable elements of a dialog,
 * wrap focus at the first/last element. Call only when `e.key === 'Tab'`.
 */
export function trapTabKey(e: KeyboardEvent, focusable: HTMLElement[]): void {
  if (focusable.length === 0) {
    // Nothing focusable — keep focus from leaving by swallowing the Tab.
    e.preventDefault();
    return;
  }

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;

  if (e.shiftKey) {
    if (active === first || !focusable.includes(active as HTMLElement)) {
      e.preventDefault();
      last.focus();
    }
  } else {
    if (active === last || !focusable.includes(active as HTMLElement)) {
      e.preventDefault();
      first.focus();
    }
  }
}
