// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

// Plan 12-03 Task 2 creates this file. Import is the RED signal.
import { Avatar } from './Avatar';

describe('<Avatar> (owner card / topbar / directory)', () => {
  it('renders first letter of name uppercased', () => {
    render(<Avatar name="alice carter" />);
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('falls back to first letter of email local-part when name is empty', () => {
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
    expect(container.querySelector('img')).toBeNull();
    // First char of the string is '<' — uppercased '<' === '<'. Text, not HTML.
    expect(container.querySelector('span')!.textContent).toBe('<');
  });
});
