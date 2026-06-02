/**
 * CommentInput tests — D-C-04
 * TDD RED: Tests written before implementation.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CommentInput } from './comment-input';

describe('CommentInput', () => {
  it('Test 1: submits trimmed body via onSubmit; blank/whitespace is blocked', () => {
    const onSubmit = vi.fn();
    render(<CommentInput onSubmit={onSubmit} />);

    const textarea = screen.getByRole('textbox');
    const button = screen.getByRole('button', { name: /post note/i });

    // Empty textarea — button disabled
    expect(button).toBeDisabled();

    // Whitespace only — still disabled
    fireEvent.change(textarea, { target: { value: '   ' } });
    expect(button).toBeDisabled();

    // Real content — button enabled, submits trimmed text
    fireEvent.change(textarea, { target: { value: '  Hello team  ' } });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    expect(onSubmit).toHaveBeenCalledWith('Hello team');
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('Test 2: body > 10000 chars is blocked (maxLength enforced)', () => {
    const onSubmit = vi.fn();
    render(<CommentInput onSubmit={onSubmit} />);

    const textarea = screen.getByRole('textbox');
    // The textarea should have maxLength=10000
    expect(textarea).toHaveAttribute('maxLength', '10000');
  });
});
