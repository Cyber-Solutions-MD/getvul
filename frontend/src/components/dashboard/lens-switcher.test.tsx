import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LensSwitcher } from './lens-switcher';

describe('LensSwitcher', () => {
  it('renders 4 segments with aria-pressed, single row (E1)', () => {
    render(<LensSwitcher lens="analyst" onLensChange={vi.fn()} />);
    const group = screen.getByRole('group', { name: 'Dashboard lens' });
    expect(group).toHaveClass('flex-nowrap');

    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(4);
    expect(screen.getByRole('button', { name: 'Analyst' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'IT-ops' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Compliance' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Leadership' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('active segment gets the pink ChipBar chrome', () => {
    render(<LensSwitcher lens="leadership" onLensChange={vi.fn()} />);
    const activeButton = screen.getByRole('button', { name: 'Leadership' });
    expect(activeButton.className).toContain('bg-pink-soft');
    const inactiveButton = screen.getByRole('button', { name: 'Analyst' });
    expect(inactiveButton.className).toContain('text-text-muted');
  });

  it('calls onLensChange with the clicked lens id', async () => {
    const user = userEvent.setup();
    const onLensChange = vi.fn();
    render(<LensSwitcher lens="analyst" onLensChange={onLensChange} />);
    await user.click(screen.getByRole('button', { name: 'Compliance' }));
    expect(onLensChange).toHaveBeenCalledWith('compliance');
  });

  it('lens availability does not depend on any role prop (T-43-13 — no role prop exists)', () => {
    // The component signature itself has no `role` prop — every segment
    // renders unconditionally regardless of who's logged in.
    render(<LensSwitcher lens="analyst" onLensChange={vi.fn()} />);
    expect(screen.getAllByRole('button')).toHaveLength(4);
  });
});
