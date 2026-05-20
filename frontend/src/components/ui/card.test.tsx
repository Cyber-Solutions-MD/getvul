import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { Card } from './card';

describe('<Card>', () => {
  it('renders children with default surface variant + md padding (D-P-01)', () => {
    render(<Card data-testid="card">content</Card>);
    const card = screen.getByTestId('card');
    expect(card).toHaveTextContent('content');
    // Default variant=surface consumes --color-surface + --color-border-subtle
    expect(card.className).toMatch(/bg-surface\b/);
    expect(card.className).toMatch(/border-border-subtle/);
    // Default padding=md
    expect(card.className).toMatch(/p-5/);
  });

  it("variant='elevated' applies bg-surface-2 and shadow-card", () => {
    render(
      <Card variant="elevated" data-testid="card">
        x
      </Card>
    );
    const card = screen.getByTestId('card');
    expect(card.className).toMatch(/bg-surface-2/);
    expect(card.className).toMatch(/shadow-card/);
  });

  it("variant='outline' applies transparent background and stronger border", () => {
    render(
      <Card variant="outline" data-testid="card">
        x
      </Card>
    );
    const card = screen.getByTestId('card');
    expect(card.className).toMatch(/bg-transparent/);
    expect(card.className).toMatch(/border-border\b/);
  });

  it("padding='sm' applies p-3; padding='lg' applies p-7", () => {
    const { rerender } = render(
      <Card padding="sm" data-testid="card">
        x
      </Card>
    );
    expect(screen.getByTestId('card').className).toMatch(/p-3/);
    rerender(
      <Card padding="lg" data-testid="card">
        x
      </Card>
    );
    expect(screen.getByTestId('card').className).toMatch(/p-7/);
  });

  it('Card.Header, Card.Body, Card.Footer render children without throwing', () => {
    render(
      <Card>
        <Card.Header>header</Card.Header>
        <Card.Body>body</Card.Body>
        <Card.Footer>footer</Card.Footer>
      </Card>
    );
    expect(screen.getByText('header')).toBeInTheDocument();
    expect(screen.getByText('body')).toBeInTheDocument();
    expect(screen.getByText('footer')).toBeInTheDocument();
  });

  it('forwards ref to underlying div', () => {
    let captured: HTMLDivElement | null = null;
    render(
      <Card
        ref={(el) => {
          captured = el;
        }}
      >
        x
      </Card>
    );
    expect(captured).toBeInstanceOf(HTMLDivElement);
  });

  it('merges consumer className via cn() (D-P-01)', () => {
    render(
      <Card className="custom-class" data-testid="card">
        x
      </Card>
    );
    expect(screen.getByTestId('card').className).toMatch(/custom-class/);
  });

  it('has no axe violations (D-Test-01)', async () => {
    const { container } = render(
      <Card>
        <Card.Header>Critical · open</Card.Header>
        <Card.Body>content</Card.Body>
        <Card.Footer>footer</Card.Footer>
      </Card>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
