/**
 * BlockedToggle tests — D-P-03 / D-P-02
 * TDD RED: Tests written before implementation.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BlockedToggle } from './blocked-toggle';

describe('BlockedToggle', () => {
  it('Test 1: not-blocked state renders "Mark blocked"; clicking opens inline reason editor', () => {
    const onToggle = vi.fn();
    render(<BlockedToggle blocked={false} blockedReason={null} onToggle={onToggle} />);

    // Should show Mark blocked button
    expect(screen.getByRole('button', { name: /mark blocked/i })).toBeInTheDocument();
    // No inline editor yet
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();

    // Click → inline editor appears
    fireEvent.click(screen.getByRole('button', { name: /mark blocked/i }));
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    // Save + Cancel buttons appear
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('Test 2: entering reason and saving calls onToggle({ blocked: true, blockedReason }); whitespace-only reason → null', () => {
    const onToggle = vi.fn();
    render(<BlockedToggle blocked={false} blockedReason={null} onToggle={onToggle} />);

    // Open editor
    fireEvent.click(screen.getByRole('button', { name: /mark blocked/i }));

    const input = screen.getByRole('textbox');

    // Whitespace-only reason → should coerce to null
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onToggle).toHaveBeenCalledWith({ blocked: true, blockedReason: null });
    onToggle.mockClear();

    // Reopen for real reason test (input still visible if component stays open,
    // but after save the parent would re-render with blocked=true — simulate fresh mount)
    const { rerender } = render(
      <BlockedToggle blocked={false} blockedReason={null} onToggle={onToggle} />,
    );
    fireEvent.click(screen.getAllByRole('button', { name: /mark blocked/i })[0]);
    const input2 = screen.getAllByRole('textbox')[0];
    fireEvent.change(input2, { target: { value: 'Waiting for vendor patch' } });
    // Verify maxLength=500 on the input
    expect(input2).toHaveAttribute('maxLength', '500');
    fireEvent.click(screen.getAllByRole('button', { name: /save/i })[0]);
    expect(onToggle).toHaveBeenCalledWith({
      blocked: true,
      blockedReason: 'Waiting for vendor patch',
    });
  });

  it('Test 3: blocked state renders "Unblock"; clicking calls onToggle({ blocked: false, blockedReason: null }) immediately', () => {
    const onToggle = vi.fn();
    render(
      <BlockedToggle blocked={true} blockedReason="Vendor patch pending" onToggle={onToggle} />,
    );

    // Should show Unblock (not "Mark blocked")
    expect(screen.getByRole('button', { name: /unblock/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /mark blocked/i })).not.toBeInTheDocument();
    // No inline editor
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();

    // Clicking Unblock calls onToggle immediately — no reason prompt
    fireEvent.click(screen.getByRole('button', { name: /unblock/i }));
    expect(onToggle).toHaveBeenCalledWith({ blocked: false, blockedReason: null });
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('Test 4: Cancel closes the inline editor without calling onToggle', () => {
    const onToggle = vi.fn();
    render(<BlockedToggle blocked={false} blockedReason={null} onToggle={onToggle} />);

    // Open editor
    fireEvent.click(screen.getByRole('button', { name: /mark blocked/i }));
    expect(screen.getByRole('textbox')).toBeInTheDocument();

    // Cancel → editor closes, onToggle not called
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(onToggle).not.toHaveBeenCalled();
  });
});
