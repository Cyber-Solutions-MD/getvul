// @vitest-environment jsdom
/**
 * result-table.test.tsx -- TDD RED-phase tests for ResultTable (44-03 Task 3).
 *
 * ResultTable is a THIN entity-dispatch wrapper (D-08): it must never
 * introduce a second table/row pattern. The three EXISTING list-row
 * primitives (VulnTable/AssetsTable/TicketsTable) are mocked here so this
 * test asserts the DISPATCH decision itself (which primitive renders for
 * which entity, and with which rows) without coupling to those primitives'
 * own internal rendering (already covered by their own test suites).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@/components/vulnerabilities/vuln-table', () => ({
  VulnTable: (props: { rows: unknown[] }) => (
    <div data-testid="vuln-table" data-rows={props.rows.length} />
  ),
}));
vi.mock('@/components/assets/assets-table', () => ({
  AssetsTable: (props: { rows: unknown[] }) => (
    <div data-testid="assets-table" data-rows={props.rows.length} />
  ),
}));
vi.mock('@/components/tickets/tickets-table', () => ({
  TicketsTable: (props: { rows: unknown[] }) => (
    <div data-testid="tickets-table" data-rows={props.rows.length} />
  ),
}));

import { ResultTable } from './result-table';

describe('<ResultTable> (D-08 entity-dispatch thin wrapper)', () => {
  it('dispatches to VulnTable for entity="vulnerabilities" -- never a bespoke second table', () => {
    render(
      <ResultTable
        entity="vulnerabilities"
        rows={[{ id: 'v1' }, { id: 'v2' }, { id: 'v3' }]}
        total={47}
        onRowOpen={vi.fn()}
      />,
    );

    expect(screen.getByTestId('vuln-table')).toHaveAttribute('data-rows', '3');
    expect(screen.queryByTestId('assets-table')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tickets-table')).not.toBeInTheDocument();
  });

  it('dispatches to AssetsTable for entity="assets"', () => {
    render(<ResultTable entity="assets" rows={[{ id: 'a1' }]} total={1} onRowOpen={vi.fn()} />);

    expect(screen.getByTestId('assets-table')).toHaveAttribute('data-rows', '1');
    expect(screen.queryByTestId('vuln-table')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tickets-table')).not.toBeInTheDocument();
  });

  it('dispatches to TicketsTable for entity="tickets"', () => {
    render(<ResultTable entity="tickets" rows={[{ id: 't1' }]} total={1} onRowOpen={vi.fn()} />);

    expect(screen.getByTestId('tickets-table')).toHaveAttribute('data-rows', '1');
    expect(screen.queryByTestId('vuln-table')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assets-table')).not.toBeInTheDocument();
  });

  it('renders the "{topN} of {total} total" caption in mono numerals (D-07)', () => {
    render(
      <ResultTable
        entity="vulnerabilities"
        rows={[{ id: 'v1' }, { id: 'v2' }]}
        total={47}
        onRowOpen={vi.fn()}
      />,
    );

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('47')).toBeInTheDocument();
    expect(screen.getByText(/total$/)).toBeInTheDocument();
  });

  it('renders the zero-rows slot (no table) when rows is empty', () => {
    render(
      <ResultTable
        entity="vulnerabilities"
        rows={[]}
        total={0}
        onRowOpen={vi.fn()}
        emptyState={<div data-testid="empty-slot">Nothing matches that</div>}
      />,
    );

    expect(screen.getByTestId('empty-slot')).toBeInTheDocument();
    expect(screen.queryByTestId('vuln-table')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assets-table')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tickets-table')).not.toBeInTheDocument();
  });
});
