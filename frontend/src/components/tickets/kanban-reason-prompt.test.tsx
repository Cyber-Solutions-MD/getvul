/**
 * KanbanReasonPrompt tests — UX-D-01-02 (D-DRAG-02)
 * TDD RED: written before the component exists (Wave 0). Mirrors
 * blocked-toggle.test.tsx's Save/Cancel/whitespace-coercion contract.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { KanbanReasonPrompt } from './kanban-reason-prompt';

describe('KanbanReasonPrompt', () => {
  it('typing a reason and clicking Save calls onSave with the trimmed reason', () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    render(
      <KanbanReasonPrompt ticketLabel="JIRA-123" onSave={onSave} onCancel={onCancel} />,
    );

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'the reason' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(onSave).toHaveBeenCalledWith('the reason');
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('clicking Cancel calls onCancel and does NOT call onSave', () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    render(
      <KanbanReasonPrompt ticketLabel="JIRA-123" onSave={onSave} onCancel={onCancel} />,
    );

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'some reason' } });
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('typing only whitespace then Save calls onSave(null)', () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    render(
      <KanbanReasonPrompt ticketLabel="JIRA-123" onSave={onSave} onCancel={onCancel} />,
    );

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(onSave).toHaveBeenCalledWith(null);
  });

  it('the input has maxLength={500}', () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    render(
      <KanbanReasonPrompt ticketLabel="JIRA-123" onSave={onSave} onCancel={onCancel} />,
    );

    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('maxLength', '500');
  });
});
