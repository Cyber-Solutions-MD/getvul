/**
 * ActivityTimeline tests — D-C-01 / D-C-04
 * TDD RED: Tests written before implementation.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ActivityTimeline } from './activity-timeline';
import type { TimelineEntry } from './activity-timeline';

describe('ActivityTimeline', () => {
  it('Test 1: renders rows ascending by createdAt (oldest top), comments and sync events interleaved', () => {
    const entries: TimelineEntry[] = [
      {
        kind: 'sync',
        id: 's1',
        label: 'Jira status changed: Open → In progress',
        createdAt: '2024-06-01T12:00:00Z',
      },
      {
        kind: 'comment',
        id: 'c1',
        author: 'Ana',
        body: 'Starting investigation',
        createdAt: '2024-06-01T10:00:00Z', // earlier — should appear FIRST
      },
    ];
    render(<ActivityTimeline entries={entries} />);
    const rows = screen.getAllByRole('listitem');
    // First item should be the earlier comment
    expect(rows[0]).toHaveTextContent('Starting investigation');
    // Second item should be the sync event
    expect(rows[1]).toHaveTextContent('Jira status changed');
  });

  it('Test 2: rows are grouped under day headers (Today / Yesterday / MMM D)', () => {
    // Use a fixed past date so the test is deterministic
    const entries: TimelineEntry[] = [
      {
        kind: 'comment',
        id: 'c1',
        author: 'Ana',
        body: 'Old comment',
        createdAt: '2024-01-15T10:00:00Z',
      },
    ];
    render(<ActivityTimeline entries={entries} />);
    // Should render a day header (Jan 15 or similar, not "Today"/"Yesterday" for old dates)
    const headers = document.querySelectorAll('[data-day-header]');
    expect(headers.length).toBeGreaterThan(0);
  });

  it('Test 3: comment body renders as plain text (XSS-safe, whitespace-pre-wrap, no dangerouslySetInnerHTML)', () => {
    const entries: TimelineEntry[] = [
      {
        kind: 'comment',
        id: 'c1',
        author: 'Ana',
        body: '<script>alert("xss")</script>\nLine 2',
        createdAt: '2024-06-01T10:00:00Z',
      },
    ];
    const { container } = render(<ActivityTimeline entries={entries} />);
    // No actual <script> tag in the DOM — React text node escapes it
    expect(container.querySelector('script')).toBeNull();
    // The raw text is visible (escaped) and contains the string literally
    const bodyEl = container.querySelector('.whitespace-pre-wrap');
    expect(bodyEl).toBeTruthy();
    expect(bodyEl!.textContent).toContain('<script>');
  });
});
