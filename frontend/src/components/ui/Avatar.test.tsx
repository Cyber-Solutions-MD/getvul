// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

// Plan 12-03 Task 2 creates this file. Import is the RED signal.
import { Avatar } from './Avatar';

describe('<Avatar> (owner card / topbar / directory)', () => {
  it('renders first+last initials uppercased per sketch (visual-language.md "2 chars")', () => {
    render(<Avatar name="alice carter" />);
    expect(screen.getByText('AC')).toBeInTheDocument();
  });

  it('single-word name falls back to one initial (avoids "AL" from "Alice")', () => {
    render(<Avatar name="Alice" />);
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('email with first.last local part produces two initials', () => {
    render(<Avatar email="bob.smith@example.com" />);
    expect(screen.getByText('BS')).toBeInTheDocument();
  });

  it('falls back to first letter of email local-part when there is no separator', () => {
    render(<Avatar email="bob@example.com" />);
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('renders ? placeholder when both name and email are missing', () => {
    render(<Avatar />);
    expect(screen.getByText('?')).toBeInTheDocument();
  });

  it('uses var(--gradient-sunset) as background (foundation.md token, no freehand hex)', () => {
    const { container } = render(<Avatar name="X" />);
    const span = container.querySelector('span');
    expect(span!.getAttribute('style')).toContain('var(--gradient-sunset)');
  });

  it('honors the size prop and exposes data-size for downstream styling hooks', () => {
    const { container } = render(<Avatar name="X" size={64} />);
    const span = container.querySelector('span');
    expect(span!.getAttribute('data-size')).toBe('64');
    expect(span!.getAttribute('style')).toContain('width: 64px');
  });

  it('does not render HTML from name prop (T-12-04 XSS guard)', () => {
    const { container } = render(<Avatar name="<img onerror=alert(1)>" />);
    // Core invariant: zero HTML elements escape from the name prop.
    expect(container.querySelector('img')).toBeNull();
    // The chip renders text only — initialsFor strips to leading characters
    // of the (whitespace-split) tokens. Exact char count depends on tokens
    // but it MUST be a plain text node, never markup.
    const span = container.querySelector('span')!;
    expect(span.children.length).toBe(0); // no element children → text only
    expect(span.textContent).toMatch(/^[^<>]*<[^<>]*$|^[^<>]+$/); // text node may include "<" char but no tag
  });
});
