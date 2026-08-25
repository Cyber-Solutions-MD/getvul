import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FrameworkPostureStrip } from './framework-posture-strip';
import type { ControlStatus } from '@/lib/queries/use-compliance';

function control(overrides: Partial<ControlStatus>): ControlStatus {
  return {
    framework: 'soc2',
    control_id: 'CC7.1',
    title: 'Vulnerability detection & monitoring',
    metric_key: 'coverage_pct',
    value: null,
    status: 'not_measured',
    ...overrides,
  };
}

describe('FrameworkPostureStrip', () => {
  it('aggregates pass/partial/fail/not-measured counts per framework', () => {
    const controls: ControlStatus[] = [
      control({ framework: 'soc2', control_id: 'CC7.1', status: 'pass' }),
      control({ framework: 'soc2', control_id: 'CC7.2', status: 'fail' }),
      control({ framework: 'iso27001', control_id: 'A.8.8', status: 'partial' }),
      control({ framework: 'pci_dss', control_id: '6.3.1', status: 'not_measured' }),
    ];
    render(<FrameworkPostureStrip controls={controls} />);

    // SOC 2 has 1 pass out of 2 total controls -> aggregate shows worst-case
    // (fail present -> fail dot) with the "1/2" pass fraction.
    const soc2Pill = screen.getByTestId('framework-pill-soc2');
    expect(soc2Pill).toHaveTextContent('SOC 2');
    expect(soc2Pill).toHaveTextContent('1/2');

    expect(screen.getByTestId('framework-pill-iso27001')).toHaveTextContent('ISO 27001');
    expect(screen.getByTestId('framework-pill-pci_dss')).toHaveTextContent('PCI DSS');
    // NIST CSF has no controls in this dataset -> no pill rendered.
    expect(screen.queryByTestId('framework-pill-nist_csf')).not.toBeInTheDocument();
  });

  it('each pill links to /dashboard/compliance?framework=<fw>', () => {
    const controls: ControlStatus[] = [control({ framework: 'nist_csf', control_id: 'ID.RA-01', status: 'pass' })];
    render(<FrameworkPostureStrip controls={controls} />);
    const pill = screen.getByTestId('framework-pill-nist_csf');
    expect(pill).toHaveAttribute('href', '/dashboard/compliance?framework=nist_csf');
  });

  it('renders the hero-sized control-preview grid only in the hero variant', () => {
    const controls: ControlStatus[] = [
      control({ framework: 'soc2', control_id: 'CC7.1', status: 'pass' }),
      control({ framework: 'soc2', control_id: 'CC7.2', status: 'fail' }),
    ];
    const { rerender } = render(<FrameworkPostureStrip controls={controls} variant="compact" />);
    expect(screen.queryByTestId('framework-preview-control-soc2-CC7.1')).not.toBeInTheDocument();

    rerender(<FrameworkPostureStrip controls={controls} variant="hero" />);
    expect(screen.getByTestId('framework-preview-control-soc2-CC7.1')).toBeInTheDocument();
    expect(screen.getByTestId('framework-preview-control-soc2-CC7.2')).toBeInTheDocument();
  });

  it('a not_measured-only framework never renders as pass or fail (E8 honesty)', () => {
    const controls: ControlStatus[] = [control({ framework: 'pci_dss', control_id: '6.3.1', status: 'not_measured' })];
    render(<FrameworkPostureStrip controls={controls} />);
    const pill = screen.getByTestId('framework-pill-pci_dss');
    expect(pill).toHaveTextContent('0/1');
  });
});
