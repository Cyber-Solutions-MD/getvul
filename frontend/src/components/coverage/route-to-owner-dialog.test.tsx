import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RouteToOwnerDialog } from './route-to-owner-dialog';

describe('RouteToOwnerDialog', () => {
  const onOpenChange = vi.fn();
  const onConfirm = vi.fn();

  beforeEach(() => {
    onOpenChange.mockReset();
    onConfirm.mockReset();
  });

  it('resolved branch renders the D-07 title/body + "Notify owner" confirm label', () => {
    render(
      <RouteToOwnerDialog
        open
        onOpenChange={onOpenChange}
        hostname="prod-db-01"
        ownerResolved
        ownerName="Jane Doe"
        onConfirm={onConfirm}
        isPending={false}
      />,
    );
    expect(screen.getByText('Notify Jane about this device?')).toBeInTheDocument();
    expect(
      screen.getByText(
        "prod-db-01 is in your inventory but no scanner covers it. We'll email Jane to onboard it — this doesn't create a ticket or a finding.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Notify owner' })).toBeInTheDocument();
  });

  it('unresolvable branch (D-09) renders "No owner found for this device" + "Notify admins" confirm label', () => {
    render(
      <RouteToOwnerDialog
        open
        onOpenChange={onOpenChange}
        hostname="prod-db-01"
        ownerResolved={false}
        onConfirm={onConfirm}
        isPending={false}
      />,
    );
    expect(screen.getByText('No owner found for this device')).toBeInTheDocument();
    expect(
      screen.getByText(
        "We couldn't resolve an owner from your directory. We'll notify your admins and the configured alert channel instead so this isn't silently dropped.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Notify admins' })).toBeInTheDocument();
  });

  it('shows the disabled "Notifying…" pending state on the confirm button while isPending', () => {
    render(
      <RouteToOwnerDialog
        open
        onOpenChange={onOpenChange}
        hostname="prod-db-01"
        ownerResolved={false}
        onConfirm={onConfirm}
        isPending
      />,
    );
    const confirmBtn = screen.getByRole('button', { name: 'Notifying…' });
    expect(confirmBtn).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Notify admins' })).toBeNull();
  });

  it('never renders null (closed) chrome and returns nothing when closed', () => {
    render(
      <RouteToOwnerDialog
        open={false}
        onOpenChange={onOpenChange}
        hostname="prod-db-01"
        ownerResolved={false}
        onConfirm={onConfirm}
        isPending={false}
      />,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('the confirm button never carries the pink bg-gradient-sunset CTA class', () => {
    render(
      <RouteToOwnerDialog
        open
        onOpenChange={onOpenChange}
        hostname="prod-db-01"
        ownerResolved={false}
        onConfirm={onConfirm}
        isPending={false}
      />,
    );
    const confirmBtn = screen.getByRole('button', { name: 'Notify admins' });
    expect(confirmBtn.className).not.toContain('bg-gradient-sunset');
    // Violet focus ring is the required accent (UI-SPEC Color) instead.
    expect(confirmBtn.className).toContain('focus-visible:outline-violet');
  });
});
