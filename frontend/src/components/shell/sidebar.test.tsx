import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { Sidebar } from './sidebar';

// Mock next/navigation usePathname per D-35
vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
}));

import { usePathname } from 'next/navigation';

describe('<Sidebar>', () => {
  beforeEach(() => {
    vi.mocked(usePathname).mockReset();
  });

  it('renders the D-36 verbatim item list with real hrefs', () => {
    vi.mocked(usePathname).mockReturnValue('/dashboard');
    render(<Sidebar />);

    expect(screen.getByRole('link', { name: /Dashboard/ })).toHaveAttribute('href', '/dashboard');
    expect(screen.getByRole('link', { name: /Vulnerabilities/ })).toHaveAttribute('href', '/dashboard/vulnerabilities');
    expect(screen.getByRole('link', { name: /Assets/ })).toHaveAttribute('href', '/dashboard/assets');
    expect(screen.getByRole('link', { name: /CSPM/ })).toHaveAttribute('href', '/dashboard/cspm');
    expect(screen.getByRole('link', { name: /Tickets/ })).toHaveAttribute('href', '/dashboard/tickets');
    // D-36 quirk: Connectors label maps to /dashboard/integrations
    expect(screen.getByRole('link', { name: /Connectors/ })).toHaveAttribute('href', '/dashboard/integrations');
    expect(screen.getByRole('link', { name: /^Users$/ })).toHaveAttribute('href', '/dashboard/users');
    expect(screen.getByRole('link', { name: /^Settings$/ })).toHaveAttribute('href', '/dashboard/settings');
  });

  it('marks /dashboard active only on exact match (D-35)', () => {
    vi.mocked(usePathname).mockReturnValue('/dashboard');
    render(<Sidebar />);
    const dashboard = screen.getByRole('link', { name: /Dashboard/ });
    expect(dashboard).toHaveAttribute('aria-current', 'page');
  });

  it('does NOT mark /dashboard active when on a nested route like /dashboard/vulnerabilities (D-35 exact-match)', () => {
    vi.mocked(usePathname).mockReturnValue('/dashboard/vulnerabilities');
    render(<Sidebar />);
    const dashboard = screen.getByRole('link', { name: /Dashboard/ });
    expect(dashboard).not.toHaveAttribute('aria-current', 'page');
    const vulns = screen.getByRole('link', { name: /Vulnerabilities/ });
    expect(vulns).toHaveAttribute('aria-current', 'page');
  });

  it('uses prefix matching for non-root items (e.g. /dashboard/vulnerabilities/CVE-123 lights up Vulnerabilities)', () => {
    vi.mocked(usePathname).mockReturnValue('/dashboard/vulnerabilities/CVE-2024-3094');
    render(<Sidebar />);
    expect(screen.getByRole('link', { name: /Vulnerabilities/ })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: /Dashboard/ })).not.toHaveAttribute('aria-current', 'page');
  });

  it('renders count placeholders as em-dash (D-35)', () => {
    vi.mocked(usePathname).mockReturnValue('/dashboard');
    const { container } = render(<Sidebar />);
    const dashes = container.querySelectorAll('span.tabular-nums');
    expect(dashes.length).toBeGreaterThan(0);
    dashes.forEach((el) => expect(el.textContent).toBe('—'));
  });

  it('brand mark wraps Link to /dashboard (D-40)', () => {
    vi.mocked(usePathname).mockReturnValue('/dashboard');
    render(<Sidebar />);
    // The brand is a link too — match by 'GetVul' label
    const brand = screen.getByText('GetVul').closest('a');
    expect(brand).toHaveAttribute('href', '/dashboard');
  });

  it('has no axe violations', async () => {
    vi.mocked(usePathname).mockReturnValue('/dashboard');
    const { container } = render(<Sidebar />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
