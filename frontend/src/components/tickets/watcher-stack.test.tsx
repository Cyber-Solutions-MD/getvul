/**
 * WatcherStack tests — UX-05-05 / D-W-04
 * TDD RED: Tests written before implementation.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WatcherStack } from './watcher-stack';

const makeWatcher = (
  id: string,
  name: string,
  role: 'assignee' | 'reporter' | 'watcher' = 'watcher',
  createdAt = '2024-01-01T00:00:00Z',
) => ({ userId: id, displayName: name, role, createdAt });

describe('WatcherStack', () => {
  it('Test 1: renders first 3 Avatars + a +N overflow chip for 5 watchers', () => {
    const watchers = [
      makeWatcher('1', 'Alice Adams'),
      makeWatcher('2', 'Bob Brown'),
      makeWatcher('3', 'Carol Clark'),
      makeWatcher('4', 'Dave Davis'),
      makeWatcher('5', 'Eve Evans'),
    ];
    render(<WatcherStack watchers={watchers} />);
    // Should show 3 avatars (first 3 by role/sort order)
    const avatars = document.querySelectorAll('[data-size]');
    expect(avatars).toHaveLength(3);
    // Should have a +2 overflow chip
    expect(screen.getByRole('button', { name: /\+2/i })).toBeInTheDocument();
  });

  it('Test 2: assignee appears first regardless of order in input array', () => {
    const watchers = [
      makeWatcher('1', 'Zara Zelda', 'watcher', '2024-01-01T00:00:00Z'),
      makeWatcher('2', 'Alice Assignee', 'assignee', '2024-01-02T00:00:00Z'),
      makeWatcher('3', 'Bob Brown', 'watcher', '2024-01-03T00:00:00Z'),
    ];
    render(<WatcherStack watchers={watchers} />);
    // All 3 fit without overflow; assignee should be first in the DOM
    const avatars = Array.from(document.querySelectorAll('[data-size]'));
    // Assignee initials are "AA" (Alice Assignee)
    expect(avatars[0]).toHaveTextContent('AA');
  });

  it('Test 3: +N chip is keyboard-accessible and toggles a popover with all watchers', () => {
    const watchers = [
      makeWatcher('1', 'Alice Adams'),
      makeWatcher('2', 'Bob Brown'),
      makeWatcher('3', 'Carol Clark'),
      makeWatcher('4', 'Dave Davis'),
    ];
    render(<WatcherStack watchers={watchers} />);
    const chip = screen.getByRole('button', { name: /\+1/i });
    // Popover closed initially
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
    // Click chip → popover opens with all watchers listed
    fireEvent.click(chip);
    expect(screen.getByRole('list')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    // Pressing Esc should close the popover
    fireEvent.keyDown(chip, { key: 'Escape' });
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('Test 4: user appearing as both assignee and watcher is deduped (rendered once, strongest role)', () => {
    const watchers = [
      makeWatcher('user-1', 'Alice Adams', 'assignee'),
      makeWatcher('user-1', 'Alice Adams', 'watcher'), // duplicate userId, weaker role
      makeWatcher('user-2', 'Bob Brown', 'watcher'),
    ];
    render(<WatcherStack watchers={watchers} />);
    // Should only render 2 avatars (deduped), no overflow chip
    const avatars = document.querySelectorAll('[data-size]');
    expect(avatars).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /\+/i })).not.toBeInTheDocument();
  });
});
