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

type Props = {
  children: ReactNode;
  fallback: (error: Error, reset: () => void) => ReactNode;
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
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error)
      return this.props.fallback(this.state.error, this.reset);
    return this.props.children;
  }
}
