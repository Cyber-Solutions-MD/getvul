/**
 * ai-feedback-control.test.tsx -- TDD RED-phase tests for AiFeedbackControl
 * (24-07 Task 2). `use-ai-feedback.ts` is mocked entirely (mirroring
 * ai-explanation-citations.test.tsx's convention of mocking every hook
 * AiExplanationSection calls) so the mutation's success/failure path is
 * driven synchronously via the per-call `mutate(vars, { onError })`
 * callback, with no QueryClientProvider needed.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const mockMutate = vi.fn();
vi.mock('@/lib/queries/use-ai-feedback', () => ({
  useAiFeedback: () => ({ mutate: mockMutate }),
}));

import { AiFeedbackControl } from './ai-feedback-control';

describe('AiFeedbackControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "Was this explanation accurate?" with thumbs + an optional note field', () => {
    render(<AiFeedbackControl resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText('Was this explanation accurate?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Accurate' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Not accurate' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('What was off? (optional)')).toBeInTheDocument();
  });

  it('clicking a thumb optimistically marks it active and fires the mutation', () => {
    render(<AiFeedbackControl resourceType="vuln" resourceId="abc-123" />);
    const upButton = screen.getByRole('button', { name: 'Accurate' });

    expect(upButton).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(upButton);

    expect(upButton).toHaveAttribute('aria-pressed', 'true');
    expect(mockMutate).toHaveBeenCalledTimes(1);
    expect(mockMutate).toHaveBeenCalledWith(
      { verdict: 'up', note: null },
      expect.objectContaining({ onError: expect.any(Function) }),
    );
  });

  it('silent revert: a mutation failure reverts the thumb to its prior state with NO error toast/card rendered', () => {
    mockMutate.mockImplementation((_vars: unknown, opts?: { onError?: (e: Error) => void }) => {
      opts?.onError?.(new Error('network error'));
    });
    render(<AiFeedbackControl resourceType="vuln" resourceId="abc-123" />);
    const upButton = screen.getByRole('button', { name: 'Accurate' });

    fireEvent.click(upButton);

    expect(upButton).toHaveAttribute('aria-pressed', 'false');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByText(/could not|failed|error/i)).toBeNull();
  });

  it('a thumb without a note submits successfully (note optional)', () => {
    render(<AiFeedbackControl resourceType="vuln" resourceId="abc-123" />);
    fireEvent.click(screen.getByRole('button', { name: 'Not accurate' }));

    expect(mockMutate).toHaveBeenCalledWith({ verdict: 'down', note: null }, expect.any(Object));
  });

  it('a thumb WITH a typed note submits the trimmed note alongside the verdict', () => {
    render(<AiFeedbackControl resourceType="vuln" resourceId="abc-123" />);
    const note = screen.getByPlaceholderText('What was off? (optional)');
    fireEvent.change(note, { target: { value: '  off on CVSS  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Accurate' }));

    expect(mockMutate).toHaveBeenCalledWith({ verdict: 'up', note: 'off on CVSS' }, expect.any(Object));
  });

  it('caps the note field at 500 chars with no char-count warning element', () => {
    render(<AiFeedbackControl resourceType="vuln" resourceId="abc-123" />);
    const textarea = screen.getByLabelText('Feedback note');
    expect(textarea).toHaveAttribute('maxLength', '500');
    // Unlike CommentInput's 9500-char precedent -- UI-SPEC: no warning UI here.
    expect(screen.queryByText(/characters? (left|remaining)/i)).toBeNull();
  });
});
