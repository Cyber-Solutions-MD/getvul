// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';

// Wave 1 (Plan 11-04) will create this file. Import is the RED signal.
import { EmptyState } from './empty-state';

describe('<EmptyState> (D-S-02 — compound component primitive + D-S-07 ARIA)', () => {
  it('root renders with role="status" + aria-live="polite" (D-S-07)', () => {
    render(
      <EmptyState>
        <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
        <EmptyState.Body>Try broadening severity or removing the date range.</EmptyState.Body>
      </EmptyState>
    );
    const root = screen.getByRole('status');
    expect(root).toBeInTheDocument();
    expect(root.getAttribute('aria-live')).toBe('polite');
  });

  it('<EmptyState.Title> renders as a heading (h2 or h3)', () => {
    render(
      <EmptyState>
        <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
      </EmptyState>
    );
    // role=heading picks up any h1..h6
    const heading = screen.getByRole('heading', {
      name: /Nothing matches all 5 filters/,
    });
    expect(heading.tagName.toLowerCase()).toMatch(/^h[23]$/);
  });

  it('<EmptyState.Body> renders body text inside a <p>', () => {
    const { container } = render(
      <EmptyState>
        <EmptyState.Body>Try broadening severity or removing the date range.</EmptyState.Body>
      </EmptyState>
    );
    const p = container.querySelector('p');
    expect(p).not.toBeNull();
    expect(p?.textContent).toMatch(/Try broadening severity/);
  });

  it('<EmptyState.Actions> renders an action group with flex layout', () => {
    const { container } = render(
      <EmptyState>
        <EmptyState.Actions>
          <button>Clear all</button>
          <button>Include Medium</button>
        </EmptyState.Actions>
      </EmptyState>
    );
    // The actions wrapper should be a flex container
    const wrappers = container.querySelectorAll('div');
    const hasFlex = Array.from(wrappers).some((d) => d.className.includes('flex'));
    expect(hasFlex).toBe(true);
  });

  it('<EmptyState.Suggestion> renders violet-accented hint chrome (bg-violet-soft + text-violet)', () => {
    const { container } = render(
      <EmptyState>
        <EmptyState.Suggestion>
          Tip: try broadening severity to Medium.
        </EmptyState.Suggestion>
      </EmptyState>
    );
    const suggestion = container.querySelector('[data-empty-suggestion]');
    expect(suggestion).not.toBeNull();
    expect((suggestion as HTMLElement).className).toMatch(/bg-violet-soft/);
    expect((suggestion as HTMLElement).className).toMatch(/text-violet/);
  });

  it('compound composition — all 5 sub-pieces produce a single accessible structure', () => {
    render(
      <EmptyState>
        <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
        <EmptyState.Body>Try broadening severity or removing the date range.</EmptyState.Body>
        <EmptyState.Actions>
          <button>Clear all</button>
          <button>Include Medium</button>
          <button>Search all sources</button>
        </EmptyState.Actions>
        <EmptyState.Suggestion>
          Tip: try broadening severity to Medium.
        </EmptyState.Suggestion>
      </EmptyState>
    );
    // One status region, one heading, one suggestion
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByRole('heading')).toBeInTheDocument();
    expect(screen.getAllByRole('button').length).toBe(3);
  });

  it('axe — no violations on the full filtered-zero variant', async () => {
    const { container } = render(
      <EmptyState>
        <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
        <EmptyState.Body>Try broadening severity or removing the date range.</EmptyState.Body>
        <EmptyState.Actions>
          <button>Clear all</button>
          <button>Include Medium</button>
          <button>Search all sources</button>
        </EmptyState.Actions>
        <EmptyState.Suggestion>
          Tip: try broadening severity to Medium.
        </EmptyState.Suggestion>
      </EmptyState>
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('optional Suggestion — omitting <EmptyState.Suggestion> still renders without errors', () => {
    expect(() =>
      render(
        <EmptyState>
          <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
          <EmptyState.Body>Try broadening severity or removing the date range.</EmptyState.Body>
        </EmptyState>
      )
    ).not.toThrow();
  });

  it('copy-voice — consumer-provided text renders verbatim (no Welcome / Please injected)', () => {
    const { container } = render(
      <EmptyState>
        <EmptyState.Title>Nothing matches all 5 filters</EmptyState.Title>
        <EmptyState.Body>Try broadening severity or removing the date range.</EmptyState.Body>
      </EmptyState>
    );
    expect(container.textContent).toContain('Nothing matches all 5 filters');
    expect(container.textContent).toContain('Try broadening severity or removing the date range.');
    expect(container.textContent).not.toMatch(/Welcome|Please/);
  });
});
