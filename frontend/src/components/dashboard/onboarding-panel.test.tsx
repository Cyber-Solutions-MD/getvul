import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { OnboardingPanel } from './onboarding-panel';

describe('<OnboardingPanel>', () => {
  it('no_scanners renders title + body + Connect a scanner CTA linking to /dashboard/connectors (D-O-02)', () => {
    render(<OnboardingPanel state="no_scanners" />);
    expect(screen.getByText('No scanners connected yet')).toBeInTheDocument();
    expect(
      screen.getByText('Connect a scanner so we can start aggregating findings.')
    ).toBeInTheDocument();
    const cta = screen.getByRole('link', { name: 'Connect a scanner' });
    expect(cta.getAttribute('href')).toBe('/dashboard/connectors');
  });

  it('no_data_yet renders title + body + Refresh button (D-O-03)', () => {
    render(<OnboardingPanel state="no_data_yet" />);
    expect(screen.getByText('Your first sync is in progress')).toBeInTheDocument();
    expect(
      screen.getByText('Findings will appear as soon as the sync completes.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument();
  });

  it('no_data_yet renders Last sync attempted timestamp when lastSyncAt provided', () => {
    render(
      <OnboardingPanel state="no_data_yet" lastSyncAt="2026-05-15T08:00:00Z" />
    );
    expect(screen.getByText(/Last sync attempted:/)).toBeInTheDocument();
  });

  it('has no axe violations (no_scanners)', async () => {
    const { container } = render(<OnboardingPanel state="no_scanners" />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no axe violations (no_data_yet)', async () => {
    const { container } = render(<OnboardingPanel state="no_data_yet" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
