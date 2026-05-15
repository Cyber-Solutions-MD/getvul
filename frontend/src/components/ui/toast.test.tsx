import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { axe } from 'vitest-axe';
import Toast from './Toast';
import ToastProvider, { useToast } from './ToastProvider';

describe('<Toast> primitive (Phase 10 extension)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('defaults to 3000ms duration (Phase 9 backward compat)', () => {
    const onDismiss = vi.fn();
    render(<Toast id="x" message="hi" onDismiss={onDismiss} />);

    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(onDismiss).not.toHaveBeenCalled();

    // 3000ms triggers fade-out (200ms transition window) then onDismiss.
    act(() => {
      vi.advanceTimersByTime(1 + 250);
    });
    expect(onDismiss).toHaveBeenCalled();
  });

  it('honors custom duration (D-H-08 — 8s undo window)', () => {
    const onDismiss = vi.fn();
    render(
      <Toast
        id="x"
        message="Snoozed CVE-2024-1234 for 1h"
        duration={8000}
        onDismiss={onDismiss}
      />
    );

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(5000 + 250);
    });
    expect(onDismiss).toHaveBeenCalled();
  });

  it('renders an action button and fires its onClick (D-H-08)', () => {
    const actionFn = vi.fn();
    render(
      <Toast
        id="x"
        message="Snoozed CVE-2024-1234 for 1h"
        action={{ label: 'Undo', onClick: actionFn }}
        onDismiss={vi.fn()}
      />
    );

    const btn = screen.getByRole('button', { name: /undo/i });
    expect(btn).toBeInTheDocument();

    fireEvent.click(btn);
    expect(actionFn).toHaveBeenCalledTimes(1);
  });

  it('variant=success consumes the sunset success token (no raw Tailwind palette)', () => {
    const { container } = render(
      <Toast id="x" message="ok" variant="success" onDismiss={vi.fn()} />
    );
    const html = container.innerHTML;
    // Sunset token consumed (border-success / text-success / bg-success-soft).
    expect(html).toMatch(/(text-success|border-success|bg-success)/);
    // Raw Tailwind palette purged.
    expect(html).not.toMatch(
      /emerald-500\/40|emerald-400|red-500\/40|red-400|indigo-500\/40|indigo-400|bg-gray-900/
    );
  });

  it('ToastProvider passes duration + action through to Toast', () => {
    const actionFn = vi.fn();
    function Trigger() {
      const { toast } = useToast();
      return (
        <button
          onClick={() =>
            toast({
              message: 'Snoozed CVE-2024-1234 for 1h',
              duration: 8000,
              action: { label: 'Undo', onClick: actionFn },
            })
          }
        >
          fire
        </button>
      );
    }

    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: /fire/i }));
    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();
  });

  it('respects prefers-reduced-motion (motion-reduce token present)', () => {
    const { container } = render(
      <Toast id="x" message="hi" onDismiss={vi.fn()} />
    );
    // motion-reduce:* utility classes opt out of animation under
    // @media (prefers-reduced-motion: reduce). Asserting the class is present
    // is the contract — we don't rely on jsdom honoring the media query.
    expect(container.innerHTML).toMatch(/motion-reduce/);
  });

  it('has no axe violations with action present', async () => {
    // axe-core relies on real timers internally — opt out of the suite-wide fake timers.
    vi.useRealTimers();
    const { container } = render(
      <Toast
        id="x"
        message="Snoozed CVE-2024-1234 for 1h"
        action={{ label: 'Undo', onClick: vi.fn() }}
        onDismiss={vi.fn()}
      />
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
