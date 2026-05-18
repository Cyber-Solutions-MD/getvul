'use client';
import { Component, type ReactNode } from 'react';

// D-P-06 + Pattern 12: React 19 class ErrorBoundary primitive. Used per-section
// in /dashboard so a single failing section degrades gracefully instead of
// blanking the whole page.
//
// T-10-18: componentDidCatch logs only in NODE_ENV !== 'production'. The
// fallback render-prop receives only the Error object — it's the consumer's
// responsibility to render a sanitized message (Plan 05 displays "<error code> ·
// Request ID" per copy-voice.md, not the raw stack).

// WR-11: monitoring hook. In production the boundary catches, the fallback
// renders, and the original error was vanishing silently — for a remediation
// dashboard, a silent UI crash that gives an analyst wrong info is a real
// risk. Consumers pass `onError` (and optionally `boundaryName`) to plug in
// Sentry / Rollbar / structured logging. T-10-18 (no PII in logs) is still
// the consumer's responsibility — this hook just carries the Error object
// to wherever monitoring lives.
export type ErrorBoundaryReporter = (
  error: Error,
  context: { boundaryName?: string; info: unknown }
) => void;

type Props = {
  children: ReactNode;
  fallback: (error: Error, reset: () => void) => ReactNode;
  /** Optional human-readable name forwarded to onError for filtering in monitoring. */
  boundaryName?: string;
  /** Optional reporter wired to Sentry/Rollbar/etc. by the application root. */
  onError?: ErrorBoundaryReporter;
};
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary]', error, info);
    }
    // WR-11: forward to monitoring if a reporter is wired. Wrapped in
    // try/catch so a faulty reporter cannot itself trigger an unhandled
    // exception inside componentDidCatch (React would then bubble the
    // boundary failure further up the tree).
    if (this.props.onError) {
      try {
        this.props.onError(error, {
          boundaryName: this.props.boundaryName,
          info,
        });
      } catch {
        // Swallow — a broken reporter must not break the boundary itself.
      }
    }
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error)
      return this.props.fallback(this.state.error, this.reset);
    return this.props.children;
  }
}
