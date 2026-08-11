import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OwnerCard } from './owner-card';
import type { AssetDetail } from '@/lib/queries/use-asset-detail';

// Stub ReassignCombobox so OwnerCard tests don't require QueryClient wiring.
vi.mock('./reassign-combobox', () => ({
  ReassignCombobox: ({ onDone }: { onDone: () => void }) => (
    <div data-testid="reassign-stub">
      <button onClick={onDone}>cancel</button>
    </div>
  ),
}));

const ASSET: AssetDetail = {
  id: 'a1',
  hostname: 'prod-db-01',
  os_name: null,
  os_version: null,
  device_category: null,
  risk_score: 50,
  seen_by_sources: [],
  assigned_user: 'alice@example.com',
  tags: [],
  sla_breach: 0,
  vuln_counts: { total: 0, critical: 0, high: 0, medium: 0, low: 0, exploitable: 0, kev: 0, sla_breach: 0 },
  directory_user: {
    email: 'alice@example.com',
    display_name: 'Alice Carter',
    department: 'Security',
    job_title: 'Engineer',
    avatar_url: null,
    groups: [],
    idp_source: 'okta',
    is_active: true,
    role: 'OWNER',
  },
  ip_addresses: [],
  mac_addresses: [],
  serial_number: null,
  model: null,
  managed_by: null,
  last_checkin_at: null,
  building: null,
  department: null,
  business_criticality: null,
  business_criticality_source: null,
  business_criticality_group_name: null,
  data_sensitivity: null,
  data_sensitivity_source: null,
  data_sensitivity_group_name: null,
  internet_facing: null,
  internet_facing_source: null,
  internet_facing_group_name: null,
};

describe('OwnerCard', () => {
  it('renders display_name + role + email + IdP pill when directory_user is present', () => {
    render(<OwnerCard asset={ASSET} />);
    expect(screen.getByTestId('owner-name').textContent).toBe('Alice Carter');
    expect(screen.getByText('OWNER')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    // IdP source 'okta' maps to display label 'Okta' (case-folded).
    expect(screen.getByTestId('idp-pill').textContent).toBe('Okta');
  });

  it('falls back to "Unassigned in directory" when directory_user is null but email exists (Pitfall 4)', () => {
    const a = { ...ASSET, directory_user: null };
    render(<OwnerCard asset={a} />);
    expect(screen.getByText('Unassigned in directory')).toBeInTheDocument();
    // IdP pill must be hidden when directory_user is null.
    expect(screen.queryByTestId('idp-pill')).toBeNull();
    // Email line still renders (analyst can copy it).
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    // Owner name falls back to the email (display name unknown).
    expect(screen.getByTestId('owner-name').textContent).toBe('alice@example.com');
  });

  it('renders "Unassigned" + "No owner set" when no email and no directory_user', () => {
    const a = { ...ASSET, directory_user: null, assigned_user: null };
    render(<OwnerCard asset={a} />);
    expect(screen.getByTestId('owner-name').textContent).toBe('Unassigned');
    expect(screen.getByText('No owner set')).toBeInTheDocument();
  });

  it('clicking Reassign flips card into edit mode', () => {
    render(<OwnerCard asset={ASSET} />);
    fireEvent.click(screen.getByTestId('owner-reassign-btn'));
    expect(screen.getByTestId('reassign-stub')).toBeInTheDocument();
    // Display chrome should be gone in edit mode.
    expect(screen.queryByTestId('owner-card')).toBeNull();
  });

  it('combobox onDone returns to display mode', () => {
    render(<OwnerCard asset={ASSET} />);
    fireEvent.click(screen.getByTestId('owner-reassign-btn'));
    fireEvent.click(screen.getByText('cancel'));
    expect(screen.queryByTestId('reassign-stub')).toBeNull();
    expect(screen.getByTestId('owner-card')).toBeInTheDocument();
  });

  it('IdP pill maps known sources through a hardcoded label table (T-12-04)', () => {
    // Unknown sources fall through as raw text — never innerHTML.
    const a = {
      ...ASSET,
      directory_user: { ...ASSET.directory_user!, idp_source: 'google' },
    };
    render(<OwnerCard asset={a} />);
    expect(screen.getByTestId('idp-pill').textContent).toBe('Google');
  });
});
