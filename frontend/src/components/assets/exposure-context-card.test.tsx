import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ExposureContextCard } from './exposure-context-card';
import type { AssetDetail } from '@/lib/queries/use-asset-detail';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));

const toastFn = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: toastFn }),
}));

const mockUseAuth = vi.fn();
vi.mock('@/lib/auth', () => ({
  useAuth: () => mockUseAuth(),
}));

import { api } from '@/lib/api';
const apiMock = vi.mocked(api);

const ASSET: AssetDetail = {
  id: 'a1',
  hostname: 'prod-db-01',
  os_name: null,
  os_version: null,
  device_category: null,
  risk_score: 50,
  seen_by_sources: [],
  assigned_user: null,
  tags: [],
  sla_breach: 0,
  vuln_counts: { total: 0, critical: 0, high: 0, medium: 0, low: 0, exploitable: 0, kev: 0, sla_breach: 0 },
  directory_user: null,
  ip_addresses: [],
  mac_addresses: [],
  serial_number: null,
  model: null,
  managed_by: null,
  last_checkin_at: null,
  building: null,
  department: null,
  business_criticality: 'HIGH',
  business_criticality_source: 'AUTO',
  business_criticality_group_name: null,
  data_sensitivity: 'CONFIDENTIAL',
  data_sensitivity_source: 'ASSET_OVERRIDE',
  data_sensitivity_group_name: null,
  internet_facing: true,
  internet_facing_source: 'GROUP_OVERRIDE',
  internet_facing_group_name: 'Prod Tier',
};

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

describe('ExposureContextCard', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('renders all 3 fields with values + source badges', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });
    render(<ExposureContextCard asset={ASSET} />, { wrapper: wrap() });

    expect(screen.getByTestId('exposure-row-business_criticality')).toHaveTextContent('High');
    expect(screen.getByTestId('exposure-row-data_sensitivity')).toHaveTextContent('Confidential');
    expect(screen.getByTestId('exposure-row-internet_facing')).toHaveTextContent('Yes');

    const badges = screen.getAllByTestId('exposure-source-badge');
    expect(badges[0].textContent).toBe('auto');
    expect(badges[1].textContent).toBe('manually set');
    // GROUP_OVERRIDE renders "group: {name}" per 32-05-PLAN truths.
    expect(badges[2].textContent).toBe('group: Prod Tier');
  });

  it('admin sees an edit affordance on every row; non-admin sees none', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    const { rerender } = render(<ExposureContextCard asset={ASSET} />, { wrapper: wrap() });
    expect(screen.getByTestId('exposure-edit-btn-business_criticality')).toBeInTheDocument();
    expect(screen.getByTestId('exposure-edit-btn-data_sensitivity')).toBeInTheDocument();
    expect(screen.getByTestId('exposure-edit-btn-internet_facing')).toBeInTheDocument();

    mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
    rerender(<ExposureContextCard asset={ASSET} />);
    expect(screen.queryByTestId('exposure-edit-btn-business_criticality')).toBeNull();
    expect(screen.queryByTestId('exposure-edit-btn-data_sensitivity')).toBeNull();
    expect(screen.queryByTestId('exposure-edit-btn-internet_facing')).toBeNull();
  });

  it('non-admin (VIEWER) also sees no edit affordance', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });
    render(<ExposureContextCard asset={ASSET} />, { wrapper: wrap() });
    expect(screen.queryByTestId('exposure-edit-btn-business_criticality')).toBeNull();
  });

  it('admin can flip a select field into edit mode, change the value, and Save calls the mutation', async () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    apiMock.mockResolvedValue({ ...ASSET, business_criticality: 'CRITICAL', business_criticality_source: 'ASSET_OVERRIDE' });

    render(<ExposureContextCard asset={ASSET} />, { wrapper: wrap() });
    fireEvent.click(screen.getByTestId('exposure-edit-btn-business_criticality'));

    const select = screen.getByLabelText('Business criticality value') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'CRITICAL' } });
    fireEvent.click(screen.getByTestId('exposure-save-business_criticality'));

    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith(
        '/api/v1/assets/a1/exposure-context',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ field: 'business_criticality', value: 'CRITICAL' }),
        }),
      ),
    );
    // Edit mode closes on success.
    await waitFor(() =>
      expect(screen.queryByTestId('exposure-edit-row-business_criticality')).toBeNull(),
    );
  });

  it('admin can toggle internet_facing to No and Save sends value "false"', async () => {
    mockUseAuth.mockReturnValue({ user: { role: 'OWNER' } });
    apiMock.mockResolvedValue({ ...ASSET, internet_facing: false, internet_facing_source: 'ASSET_OVERRIDE' });

    render(<ExposureContextCard asset={ASSET} />, { wrapper: wrap() });
    fireEvent.click(screen.getByTestId('exposure-edit-btn-internet_facing'));
    fireEvent.click(screen.getByText('No'));
    fireEvent.click(screen.getByTestId('exposure-save-internet_facing'));

    await waitFor(() =>
      expect(apiMock).toHaveBeenCalledWith(
        '/api/v1/assets/a1/exposure-context',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ field: 'internet_facing', value: 'false' }),
        }),
      ),
    );
  });

  it('Cancel exits edit mode without calling the mutation', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    render(<ExposureContextCard asset={ASSET} />, { wrapper: wrap() });
    fireEvent.click(screen.getByTestId('exposure-edit-btn-data_sensitivity'));
    expect(screen.getByTestId('exposure-edit-row-data_sensitivity')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByTestId('exposure-edit-row-data_sensitivity')).toBeNull();
    expect(apiMock).not.toHaveBeenCalled();
  });

  it('renders "—" for a null value', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });
    const a = { ...ASSET, business_criticality: null, business_criticality_source: null };
    render(<ExposureContextCard asset={a} />, { wrapper: wrap() });
    expect(screen.getByTestId('exposure-row-business_criticality')).toHaveTextContent('—');
  });
});
