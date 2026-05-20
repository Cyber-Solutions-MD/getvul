import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  usePathname: () => '/dashboard',
}));

// Mock useAuth + useTheme used by UserChip
vi.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: { email: 'igor@parity.io', id: '1' },
    logout: vi.fn(),
  }),
}));
vi.mock('@/lib/theme', () => ({
  useTheme: () => ({ theme: 'dark', setTheme: vi.fn() }),
}));

import { AppShell } from './app-shell';

describe('<AppShell>', () => {
  it('renders sidebar + topbar + children (UX-F-03)', () => {
    render(<AppShell><div data-testid="content">Page content</div></AppShell>);

    // Sidebar (matched by nav landmark or brand)
    expect(screen.getByRole('navigation', { name: /Primary navigation/i })).toBeInTheDocument();
    // Topbar — search input
    expect(screen.getByLabelText('Search')).toBeInTheDocument();
    // Children
    expect(screen.getByTestId('content')).toHaveTextContent('Page content');
  });

  it('topbar search is readOnly (D-37 visual scaffold only)', () => {
    render(<AppShell>x</AppShell>);
    const search = screen.getByLabelText('Search') as HTMLInputElement;
    expect(search.readOnly).toBe(true);
  });

  it('user chip is rendered with email-derived initials', () => {
    render(<AppShell>x</AppShell>);
    // 'igor@parity.io' -> 'IG' (no '.' / '_' in local part, slice 2)
    expect(screen.getByText('IG')).toBeInTheDocument();
  });

  it('has no axe violations on the rendered shell', async () => {
    const { container } = render(<AppShell><div>x</div></AppShell>);
    expect(await axe(container)).toHaveNoViolations();
  });
});
