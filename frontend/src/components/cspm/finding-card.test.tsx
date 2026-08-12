/**
 * TDD RED — finding-card.tsx, cspm-status-pill.tsx
 * Plan 14-03, Task 1.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

// ── Test 3: CspmStatusPill ────────────────────────────────────────────────────
describe('CspmStatusPill', () => {
  it('renders OPEN with violet class', async () => {
    const { CspmStatusPill } = await import('./cspm-status-pill');
    const { container } = render(<CspmStatusPill status="OPEN" />);
    const pill = container.querySelector('[data-cspm-status="OPEN"]');
    expect(pill).toBeTruthy();
    expect(pill?.className).toContain('violet');
  });

  it('renders REMEDIATED with severity-low class', async () => {
    const { CspmStatusPill } = await import('./cspm-status-pill');
    const { container } = render(<CspmStatusPill status="REMEDIATED" />);
    const pill = container.querySelector('[data-cspm-status="REMEDIATED"]');
    expect(pill).toBeTruthy();
    expect(pill?.className).toContain('severity-low');
  });

  it('renders SUPPRESSED with text-muted class', async () => {
    const { CspmStatusPill } = await import('./cspm-status-pill');
    const { container } = render(<CspmStatusPill status="SUPPRESSED" />);
    const pill = container.querySelector('[data-cspm-status="SUPPRESSED"]');
    expect(pill).toBeTruthy();
    // Suppressed uses text-muted (gray)
    expect(pill?.className).toContain('text-muted');
  });

  it('does NOT contain ticket status strings Completed or Blocked', async () => {
    const { CspmStatusPill } = await import('./cspm-status-pill');
    // Render all CSPM statuses
    const statuses = ['OPEN', 'IN_PROGRESS', 'REMEDIATED', 'SUPPRESSED', 'FALSE_POSITIVE'];
    for (const status of statuses) {
      const { container } = render(<CspmStatusPill status={status} />);
      expect(container.textContent).not.toContain('Completed');
      expect(container.textContent).not.toContain('Blocked');
    }
  });
});

// ── Test 4: FindingCard ───────────────────────────────────────────────────────
describe('FindingCard', () => {
  const mockFinding = {
    id: 'f1',
    rule_id: 'R1',
    rule_name: 'S3 bucket public access',
    category: 'STORAGE',
    severity: 'HIGH',
    source: 'WIZ',
    status: 'OPEN',
    resource_id: 'arn:aws:s3:::my-bucket',
    resource_name: 'my-bucket',
    resource_type: 'AWS::S3::Bucket',
    cloud_provider: 'AWS',
    first_detected_at: '2026-01-01T00:00:00Z',
    last_seen_at: '2026-06-01T00:00:00Z',
  };

  it('renders cloud provider mark, severity glyph, resource_id mono, title, and CspmStatusPill', async () => {
    const { FindingCard } = await import('./finding-card');
    render(
      <FindingCard
        finding={mockFinding}
        selected={false}
        onSelect={vi.fn()}
        onOpen={vi.fn()}
      />,
    );

    // resource_id in mono font
    expect(screen.getByText(/arn:aws:s3:::my-bucket/)).toBeTruthy();

    // title
    expect(screen.getByText('S3 bucket public access')).toBeTruthy();

    // severity glyph ▲ for HIGH
    expect(screen.getByText('▲')).toBeTruthy();

    // CspmStatusPill renders (data-cspm-status attribute)
    expect(document.querySelector('[data-cspm-status="OPEN"]')).toBeTruthy();

    // data-finding-card attribute
    expect(document.querySelector('[data-finding-card]')).toBeTruthy();
  });

  // Phase 35 SRC-01/05 — shared SourceBadgeGroup on CSPM finding cards.
  it('renders SourceBadgeGroup: single neutral mark when sources is a 1-tool group', async () => {
    const { FindingCard } = await import('./finding-card');
    const { container } = render(
      <FindingCard
        finding={{ ...mockFinding, sources: ['WIZ'], sources_count: 1 }}
        selected={false}
        onSelect={vi.fn()}
        onOpen={vi.fn()}
      />,
    );
    expect(container.querySelector('[data-source-badge-group="single"]')).toBeTruthy();
    expect(container.textContent).not.toContain('confirmed');
  });

  it('renders SourceBadgeGroup: multi-source corroborated group + "N sources" label', async () => {
    const { FindingCard } = await import('./finding-card');
    const { container } = render(
      <FindingCard
        finding={{ ...mockFinding, sources: ['WIZ', 'DEFENDER'], sources_count: 2 }}
        selected={false}
        onSelect={vi.fn()}
        onOpen={vi.fn()}
      />,
    );
    expect(container.querySelector('[data-source-badge-group="multi"]')).toBeTruthy();
    expect(screen.getByText('2 sources')).toBeTruthy();
  });

  it('falls back to [finding.source] when sources is absent (pre-Plan-04 shape)', async () => {
    const { FindingCard } = await import('./finding-card');
    const { container } = render(
      <FindingCard finding={mockFinding} selected={false} onSelect={vi.fn()} onOpen={vi.fn()} />,
    );
    expect(container.querySelector('[data-source-badge-group="single"]')).toBeTruthy();
  });
});
