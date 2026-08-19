/**
 * settings-sidebar-shell.test.tsx — TDD RED phase tests for SettingsSidebarShell.
 *
 * Behaviors verified:
 * 1. VIEWER role: sidebar renders exactly 'Profile' and 'API tokens' (no admin-only categories)
 * 2. ADMIN role: all 9 categories render (28-04 added 'ai'; Phase 36 added 'sla';
 *    Phase 40 (D-17) added the admin-only 'alerting' category)
 * 3. Clicking a category calls onCategoryChange with that category key
 * 4. Active category uses left gradient-strip indicator (data-active="true"), NOT a bottom border
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SettingsSidebarShell } from './settings-sidebar-shell';

// Mock useAuth — needed since the component reads role internally.
const mockUseAuth = vi.fn();
vi.mock('@/lib/auth', () => ({
  useAuth: () => mockUseAuth(),
}));

describe('SettingsSidebarShell', () => {
  it('Test 1: VIEWER role renders only Profile and API tokens', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });

    const { container } = render(
      <SettingsSidebarShell activeCategory="profile" onCategoryChange={vi.fn()}>
        <div>pane content</div>
      </SettingsSidebarShell>,
    );

    const nav = container.querySelector('nav');
    expect(nav).not.toBeNull();

    const buttons = nav!.querySelectorAll('button[data-category]');
    expect(buttons.length).toBe(2);
    const labels = Array.from(buttons).map((b) => b.textContent?.trim());
    expect(labels).toContain('Profile');
    expect(labels).toContain('API tokens');

    // Admin-only categories must not appear
    expect(labels).not.toContain('Workspace');
    expect(labels).not.toContain('SAML & OIDC');
    expect(labels).not.toContain('Notifications');
    expect(labels).not.toContain('Audit log');
  });

  it('Test 2: ADMIN role renders all 9 categories', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });

    const { container } = render(
      <SettingsSidebarShell activeCategory="profile" onCategoryChange={vi.fn()}>
        <div>pane content</div>
      </SettingsSidebarShell>,
    );

    const nav = container.querySelector('nav');
    const buttons = nav!.querySelectorAll('button[data-category]');
    expect(buttons.length).toBe(9);

    const labels = Array.from(buttons).map((b) => b.textContent?.trim());
    expect(labels).toContain('Profile');
    expect(labels).toContain('Workspace');
    expect(labels).toContain('SAML & OIDC');
    expect(labels).toContain('Notifications');
    expect(labels).toContain('API tokens');
    expect(labels).toContain('Audit log');
    expect(labels).toContain('AI usage & settings');
    expect(labels).toContain('SLA & Escalation');
    // Phase 40 (D-17): new admin-only category added by this plan.
    expect(labels).toContain('Alerting & Digests');
  });

  it('Test 2b: OWNER role renders all 9 categories (isAdmin includes OWNER)', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'OWNER' } });

    const { container } = render(
      <SettingsSidebarShell activeCategory="profile" onCategoryChange={vi.fn()}>
        <div>pane content</div>
      </SettingsSidebarShell>,
    );

    const nav = container.querySelector('nav');
    const buttons = nav!.querySelectorAll('button[data-category]');
    expect(buttons.length).toBe(9);
  });

  it('Test 3: clicking a category calls onCategoryChange with that category key', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    const onCategoryChange = vi.fn();

    const { container } = render(
      <SettingsSidebarShell activeCategory="profile" onCategoryChange={onCategoryChange}>
        <div>pane content</div>
      </SettingsSidebarShell>,
    );

    const nav = container.querySelector('nav');
    const workspaceButton = nav!.querySelector('button[data-category="workspace"]');
    expect(workspaceButton).not.toBeNull();

    fireEvent.click(workspaceButton!);
    expect(onCategoryChange).toHaveBeenCalledWith('workspace');
  });

  it('Test 4: active category uses data-active="true" gradient-strip, NOT bottom border', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });

    const { container } = render(
      <SettingsSidebarShell activeCategory="workspace" onCategoryChange={vi.fn()}>
        <div>pane content</div>
      </SettingsSidebarShell>,
    );

    const nav = container.querySelector('nav');

    // Active item has data-active="true"
    const activeButton = nav!.querySelector('button[data-active="true"]');
    expect(activeButton).not.toBeNull();
    expect(activeButton!.getAttribute('data-category')).toBe('workspace');

    // Inactive items have data-active="false"
    const inactiveButtons = nav!.querySelectorAll('button[data-active="false"]');
    expect(inactiveButtons.length).toBe(8);

    // No border-b, border-b-2, or role="tab" anywhere in the nav
    const outerHtml = nav!.outerHTML;
    expect(outerHtml).not.toContain('border-b-2');
    expect(outerHtml).not.toContain('role="tab"');
  });

  it('Test 5: children render in the right pane (not inside nav)', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });

    render(
      <SettingsSidebarShell activeCategory="profile" onCategoryChange={vi.fn()}>
        <div data-testid="pane-child">Child content</div>
      </SettingsSidebarShell>,
    );

    const child = screen.getByTestId('pane-child');
    expect(child).toBeDefined();
    expect(child.textContent).toBe('Child content');
  });
});
