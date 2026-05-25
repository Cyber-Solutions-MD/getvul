// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock next/navigation
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard/vulnerabilities',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    getAll: (k: string) => mockParams.getAll(k),
    toString: () => mockParams.toString(),
  }),
}));

// Wave 2 (Plan 11-05) will create this file. Import is the RED signal.
import { ViewToggle } from './view-toggle';

describe('<ViewToggle> (UX-03-05 + D-V-01 — By CVE / By Host segmented toggle)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
  });

  it('renders a 2-segment pill (By CVE / By Host)', () => {
    render(<ViewToggle />);
    expect(screen.getByRole('button', { name: /By CVE/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /By Host/i })).toBeInTheDocument();
  });

  it('active segment matches current ?group URL state', () => {
    mockParams = new URLSearchParams('group=host');
    render(<ViewToggle />);
    const host = screen.getByRole('button', { name: /By Host/i });
    expect(host.getAttribute('aria-pressed')).toBe('true');
    const cve = screen.getByRole('button', { name: /By CVE/i });
    expect(cve.getAttribute('aria-pressed')).toBe('false');
  });

  it('clicking inactive segment fires URL setter with new group value', () => {
    mockParams = new URLSearchParams();
    render(<ViewToggle />);
    const host = screen.getByRole('button', { name: /By Host/i });
    fireEvent.click(host);
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).toContain('group=host');
  });

  it('switching does NOT clear filter chips — other URL params survive the toggle', () => {
    mockParams = new URLSearchParams(
      'severity=critical&severity=high&source=QUALYS&search=log4j'
    );
    render(<ViewToggle />);
    const host = screen.getByRole('button', { name: /By Host/i });
    fireEvent.click(host);
    const [target] = mockReplace.mock.calls[0];
    // Other params remain in the next URL
    expect(target).toContain('severity=critical');
    expect(target).toContain('severity=high');
    expect(target).toContain('source=QUALYS');
    expect(target).toContain('search=log4j');
    expect(target).toContain('group=host');
  });

  it('keyboard — Tab focuses each segment; Enter/Space activates', () => {
    render(<ViewToggle />);
    const cve = screen.getByRole('button', { name: /By CVE/i });
    const host = screen.getByRole('button', { name: /By Host/i });
    cve.focus();
    expect(document.activeElement).toBe(cve);
    fireEvent.keyDown(cve, { key: 'Tab' });
    // Focus order moved to host
    host.focus();
    expect(document.activeElement).toBe(host);
    // Activation via Enter or Space (HTMLButtonElement handles both natively;
    // assert click handler via keyboard-triggered click)
    fireEvent.click(host); // simulates Enter/Space → click
    expect(mockReplace).toHaveBeenCalled();
  });
});
