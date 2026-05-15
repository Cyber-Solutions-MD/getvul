import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { Component, type ReactNode } from 'react';
import { ErrorBoundary } from './error-boundary';

// Test helper: a child that throws on demand.
function Bomb({ boom }: { boom: boolean }) {
  if (boom) throw new Error('boom-detonated');
  return <p>safe-children</p>;
}

// Suppress noisy console.error during the throw test — JSDOM logs the synthetic
// error to console even though we catch it.
let consoleSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
  consoleSpy.mockRestore();
});

describe('<ErrorBoundary>', () => {
  it('renders children when nothing throws (D-P-06)', () => {
    render(
      <ErrorBoundary fallback={() => <p>fallback-shown</p>}>
        <Bomb boom={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText('safe-children')).toBeInTheDocument();
    expect(screen.queryByText('fallback-shown')).not.toBeInTheDocument();
  });

  it('renders fallback(error, reset) when child throws (D-P-06 + Pattern 12)', () => {
    render(
      <ErrorBoundary
        fallback={(err, reset) => (
          <button data-testid="reset" onClick={reset}>
            {err.message}
          </button>
        )}
      >
        <Bomb boom />
      </ErrorBoundary>
    );
    const btn = screen.getByTestId('reset');
    expect(btn).toHaveTextContent('boom-detonated');
    expect(screen.queryByText('safe-children')).not.toBeInTheDocument();
  });

  it('reset clears the error and re-renders children when child is now safe', () => {
    // We can't easily change `boom` from outside the boundary mid-test without
    // a wrapper that owns state. Use a wrapper that switches a child after reset.
    class Switcher extends Component<{}, { phase: 'boom' | 'safe' }> {
      state = { phase: 'boom' as 'boom' | 'safe' };
      flip = () => this.setState({ phase: 'safe' });
      render(): ReactNode {
        return (
          <>
            <button
              data-testid="flip"
              onClick={this.flip}
            >
              flip
            </button>
            <ErrorBoundary
              fallback={(_err, reset) => (
                <button
                  data-testid="reset"
                  onClick={() => {
                    this.flip();
                    reset();
                  }}
                >
                  retry
                </button>
              )}
            >
              <Bomb boom={this.state.phase === 'boom'} />
            </ErrorBoundary>
          </>
        );
      }
    }
    render(<Switcher />);
    // Boundary should be in fallback initially
    expect(screen.getByTestId('reset')).toBeInTheDocument();
    // Click reset → flip switcher to safe + call reset() → boundary re-mounts children
    fireEvent.click(screen.getByTestId('reset'));
    expect(screen.getByText('safe-children')).toBeInTheDocument();
    expect(screen.queryByTestId('reset')).not.toBeInTheDocument();
  });

  it('has no axe violations on fallback render', async () => {
    const { container } = render(
      <ErrorBoundary
        fallback={(err) => (
          <div role="alert">
            <p>Something went wrong.</p>
            <p>{err.message}</p>
          </div>
        )}
      >
        <Bomb boom />
      </ErrorBoundary>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
