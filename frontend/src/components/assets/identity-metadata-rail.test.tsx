// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { IdentityMetadataRail } from './identity-metadata-rail';
import type { AssetDetail } from '@/lib/queries/use-asset-detail';

const ASSET: AssetDetail = {
  id: 'a1',
  hostname: 'prod-db-01',
  os_name: 'Ubuntu',
  os_version: '22.04',
  device_category: 'SERVER',
  risk_score: 50,
  seen_by_sources: [],
  assigned_user: null,
  tags: [],
  sla_breach: 0,
  vuln_counts: {
    total: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    exploitable: 0,
    kev: 0,
    sla_breach: 0,
  },
  directory_user: null,
  ip_addresses: ['10.0.0.1', '10.0.0.2'],
  mac_addresses: ['00:11:22:33:44:55'],
  serial_number: 'SN1234',
  model: 'Dell PowerEdge',
  managed_by: 'JAMF',
  last_checkin_at: '2026-05-20T10:00:00Z',
  building: null,
  department: 'IT',
};

describe('IdentityMetadataRail', () => {
  it('renders hostname, IP, MAC, OS, serial, model, managed_by, last_checkin, department', () => {
    render(<IdentityMetadataRail asset={ASSET} />);
    expect(screen.getByText('prod-db-01')).toBeInTheDocument();
    expect(screen.getByText('10.0.0.1, 10.0.0.2')).toBeInTheDocument();
    expect(screen.getByText('00:11:22:33:44:55')).toBeInTheDocument();
    expect(screen.getByText('Ubuntu 22.04')).toBeInTheDocument();
    expect(screen.getByText('SN1234')).toBeInTheDocument();
    expect(screen.getByText('Dell PowerEdge')).toBeInTheDocument();
    expect(screen.getByText('JAMF')).toBeInTheDocument();
    expect(screen.getByText('IT')).toBeInTheDocument();
  });

  it('skips rows whose value is null/empty', () => {
    render(<IdentityMetadataRail asset={ASSET} />);
    // building is null → no "Building" label
    expect(screen.queryByText('Building')).toBeNull();
  });

  it('renders within an aria-labelled region', () => {
    render(<IdentityMetadataRail asset={ASSET} />);
    expect(screen.getByRole('region', { name: 'Host metadata' })).toBeInTheDocument();
  });

  it('handles empty ip_addresses / mac_addresses arrays without rendering empty rows', () => {
    const noNet: AssetDetail = {
      ...ASSET,
      ip_addresses: [],
      mac_addresses: null,
    };
    render(<IdentityMetadataRail asset={noNet} />);
    expect(screen.queryByText('IP')).toBeNull();
    expect(screen.queryByText('MAC')).toBeNull();
  });

  it('renders OS row even when only os_name is set (no os_version)', () => {
    const noVer: AssetDetail = { ...ASSET, os_version: null };
    render(<IdentityMetadataRail asset={noVer} />);
    expect(screen.getByText('Ubuntu')).toBeInTheDocument();
  });
});
