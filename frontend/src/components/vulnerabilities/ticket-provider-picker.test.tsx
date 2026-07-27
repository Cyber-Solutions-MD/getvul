// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock the query hook — this component's four states are driven entirely
// by isLoading/isError/data, so we control them directly rather than
// standing up a QueryClientProvider + MSW server (D-14 unit-test contract).
vi.mock('@/lib/queries/use-ticketing-providers', () => ({
  useTicketingProviders: vi.fn(),
}));
import { useTicketingProviders } from '@/lib/queries/use-ticketing-providers';

import { TicketProviderPicker } from './ticket-provider-picker';

const useProvidersMock = vi.mocked(useTicketingProviders);

describe('<TicketProviderPicker> (D-14)', () => {
  const onChange = vi.fn();

  beforeEach(() => {
    onChange.mockReset();
  });

  it('loading: renders a skeleton, not an empty/error surface', () => {
    useProvidersMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useTicketingProviders>);

    render(<TicketProviderPicker value={null} onChange={onChange} />);

    expect(screen.getByTestId('provider-picker-skeleton')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
  });

  it('error: renders the error-state pattern (not a silent empty)', () => {
    useProvidersMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
    } as unknown as ReturnType<typeof useTicketingProviders>);

    render(<TicketProviderPicker value={null} onChange={onChange} />);

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
  });

  it('empty: renders EmptyState with a deep-link to the Connectors page', () => {
    useProvidersMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
    } as unknown as ReturnType<typeof useTicketingProviders>);

    render(<TicketProviderPicker value={null} onChange={onChange} />);

    expect(
      screen.getByText(/no ticketing provider configured yet/i),
    ).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /connectors/i });
    expect(link).toHaveAttribute('href', '/dashboard/connectors');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('populated: renders one option per configured provider, default-selects the first, and fires onChange on click', () => {
    useProvidersMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { provider: 'JIRA', enabled: true },
        { provider: 'ASANA', enabled: true },
      ],
    } as unknown as ReturnType<typeof useTicketingProviders>);

    render(<TicketProviderPicker value={null} onChange={onChange} />);

    const group = screen.getByRole('radiogroup');
    expect(group).toBeInTheDocument();
    const options = screen.getAllByRole('radio');
    expect(options).toHaveLength(2);

    // Default-select fires onChange once with the first configured provider.
    expect(onChange).toHaveBeenCalledWith('JIRA');

    fireEvent.click(screen.getByRole('radio', { name: /asana/i }));
    expect(onChange).toHaveBeenCalledWith('ASANA');
  });

  it('populated: only options for providers present in the response render (filtered server-side, D-15)', () => {
    useProvidersMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [{ provider: 'GITHUB', enabled: true }],
    } as unknown as ReturnType<typeof useTicketingProviders>);

    render(<TicketProviderPicker value="GITHUB" onChange={onChange} />);

    expect(screen.getAllByRole('radio')).toHaveLength(1);
    expect(screen.getByRole('radio', { name: /github/i })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    expect(screen.queryByRole('radio', { name: /jira/i })).not.toBeInTheDocument();
  });
});
