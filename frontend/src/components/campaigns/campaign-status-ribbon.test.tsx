/**
 * campaign-status-ribbon.test.tsx — TDD tests for CampaignStatusRibbon.
 *
 * Test 1: ACTIVE renders violet chrome.
 * Test 2: COMPLETE renders green (success) chrome.
 * Test 3: never applies a severity (red/orange/yellow) class, in either state.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CampaignStatusRibbon } from './campaign-status-ribbon';

describe('CampaignStatusRibbon', () => {
  it('renders violet chrome for ACTIVE', () => {
    render(<CampaignStatusRibbon status="ACTIVE" />);
    const pill = screen.getByText('Active').closest('[data-campaign-status]');
    expect(pill).not.toBeNull();
    expect(pill?.className).toContain('border-violet/40');
  });

  it('renders green (success) chrome for COMPLETE', () => {
    render(<CampaignStatusRibbon status="COMPLETE" />);
    const pill = screen.getByText('Complete').closest('[data-campaign-status]');
    expect(pill).not.toBeNull();
    expect(pill?.className).toContain('border-success/40');
  });

  it('never applies a severity class, in either state', () => {
    const { container: activeContainer } = render(<CampaignStatusRibbon status="ACTIVE" />);
    expect(activeContainer.innerHTML).not.toMatch(/severity-(critical|high|medium|low)/);

    const { container: completeContainer } = render(<CampaignStatusRibbon status="COMPLETE" />);
    expect(completeContainer.innerHTML).not.toMatch(/severity-(critical|high|medium|low)/);
  });
});
