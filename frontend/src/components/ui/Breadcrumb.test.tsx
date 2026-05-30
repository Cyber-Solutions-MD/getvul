// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

// Plan 12-03 Task 2 creates this file. Import is the RED signal.
import { Breadcrumb, Crumb } from './Breadcrumb';

describe('<Breadcrumb> (UX-04-02 page header)', () => {
  it('renders <nav aria-label="Breadcrumb"> wrapping an <ol>', () => {
    const { container } = render(
      <Breadcrumb>
        <Crumb href="/assets">Assets</Crumb>
        <Crumb>prod-db-01</Crumb>
      </Breadcrumb>,
    );
    expect(
      screen.getByRole('navigation', { name: 'Breadcrumb' }),
    ).toBeInTheDocument();
    expect(container.querySelector('ol')).toBeTruthy();
  });

  it('renders linked crumb as anchor and last crumb as plain text with aria-current="page"', () => {
    render(
      <Breadcrumb>
        <Crumb href="/assets">Assets</Crumb>
        <Crumb>prod-db-01</Crumb>
      </Breadcrumb>,
    );
    const link = screen.getByRole('link', { name: 'Assets' });
    expect(link).toHaveAttribute('href', '/assets');
    expect(
      screen.getByText('prod-db-01').closest('[aria-current="page"]'),
    ).toBeTruthy();
  });

  it('inserts a chevron separator between crumbs (aria-hidden)', () => {
    const { container } = render(
      <Breadcrumb>
        <Crumb href="/assets">Assets</Crumb>
        <Crumb>x</Crumb>
      </Breadcrumb>,
    );
    const seps = container.querySelectorAll('[aria-hidden="true"]');
    // At least one is the chevron with content '›'.
    const chevron = Array.from(seps).find((s) => s.textContent === '›');
    expect(chevron).toBeTruthy();
  });
});
