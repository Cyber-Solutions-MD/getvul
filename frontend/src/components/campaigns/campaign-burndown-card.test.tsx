/**
 * campaign-burndown-card.test.tsx — TDD tests for CampaignBurndownCard.
 *
 * Test 1: wraps RiskRing (score=pct_remediated) — `role="img"` present with
 *         the RiskRing's own aria-label reflecting the score.
 * Test 2: renders "{pct}% remediated" + "{open} open · {in_progress} in
 *         progress · {done} done" + "Campaign MTTR: {duration}".
 * Test 3: MTTR renders "—" when mttrSeconds is null.
 * Test 4: zero-member campaign (0/0/0/0) renders "0% remediated" +
 *         "0 open · 0 in progress · 0 done" — never crashes (E6).
 * Test 5: never renders a severity-* class (status family only).
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CampaignBurndownCard, formatMttr } from './campaign-burndown-card';

describe('CampaignBurndownCard', () => {
  it('wraps RiskRing with score=pct_remediated', () => {
    render(
      <CampaignBurndownCard pctRemediated={42} open={3} inProgress={2} done={5} mttrSeconds={null} />,
    );
    const ring = screen.getByRole('img');
    expect(ring).toHaveAttribute('aria-label', expect.stringContaining('42'));
  });

  it('renders the pct/breakdown/MTTR copy verbatim', () => {
    render(
      <CampaignBurndownCard
        pctRemediated={50}
        open={3}
        inProgress={2}
        done={5}
        mttrSeconds={374400}
      />,
    );
    expect(screen.getByText('50% remediated')).toBeInTheDocument();
    expect(screen.getByText('3 open')).toBeInTheDocument();
    expect(screen.getByText('2 in progress')).toBeInTheDocument();
    expect(screen.getByText('5 done')).toBeInTheDocument();
    // 374400s = 4d 8h
    expect(screen.getByText('4d 8h')).toBeInTheDocument();
  });

  it('MTTR renders "—" when null', () => {
    render(<CampaignBurndownCard pctRemediated={10} open={1} inProgress={1} done={1} mttrSeconds={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('zero-member campaign shows 0% + "0 open · 0 in progress · 0 done", never crashes (E6)', () => {
    render(<CampaignBurndownCard pctRemediated={0} open={0} inProgress={0} done={0} mttrSeconds={null} />);
    expect(screen.getByText('0% remediated')).toBeInTheDocument();
    expect(screen.getByText('0 open')).toBeInTheDocument();
    expect(screen.getByText('0 in progress')).toBeInTheDocument();
    expect(screen.getByText('0 done')).toBeInTheDocument();
  });

  it('never renders a severity-* class (status family only)', () => {
    const { container } = render(
      <CampaignBurndownCard pctRemediated={75} open={1} inProgress={1} done={3} mttrSeconds={100000} />,
    );
    expect(container.innerHTML).not.toMatch(/severity-(critical|high|medium|low|info)/);
  });
});

describe('formatMttr', () => {
  it('formats seconds as "{d}d {h}h"', () => {
    expect(formatMttr(374400)).toBe('4d 8h'); // 4d 8h
    expect(formatMttr(3600)).toBe('0d 1h');
    expect(formatMttr(0)).toBe('0d 0h');
  });

  it('returns "—" for null', () => {
    expect(formatMttr(null)).toBe('—');
  });
});
