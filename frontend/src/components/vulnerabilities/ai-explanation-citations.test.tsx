/**
 * ai-explanation-citations.test.tsx -- TDD RED-phase tests for
 * AiExplanationCitations AND AiExplanationSection (24-05 Task 2). Both
 * components' tests live in this single file per the plan's declared
 * files_modified list.
 *
 * AiExplanationCitations: pure render over a validated ExplainVulnResponse --
 * citation classes, uncited-text-stays-plain, no props/hooks to mock.
 *
 * AiExplanationSection: the 8 mutually-exclusive body states, driven by
 * useExplainCache + useExplainStream + useAuth (role) + useConnectorsList (the
 * key-configured signal) + usePrefersReducedMotion. All four hooks are mocked
 * so every state is directly, synchronously reachable without waiting on a
 * real query lifecycle.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import { AiExplanationCitations } from './ai-explanation-citations';
import type { ExplainVulnResponse } from '@/lib/ai/use-explain-stream';

// ─────────────────────────────────────────────────────────────────────────
// AiExplanationCitations
// ─────────────────────────────────────────────────────────────────────────

describe('AiExplanationCitations', () => {
  it('renders a scanner_verbatim citation inside a tinted, focusable span', () => {
    const data: ExplainVulnResponse = {
      summary: 'CVE-2024-9999 affects OpenSSL 3.0 on prod-db-01.',
      business_risk: 'Exploitation could expose customer data.',
      citations: [
        { text: 'CVE-2024-9999 affects OpenSSL 3.0', source: 'scanner_verbatim', source_field: 'cve_description' },
      ],
      grounded: true,
    };
    const { container } = render(<AiExplanationCitations data={data} />);
    const span = container.querySelector('span.bg-violet-soft');
    expect(span).not.toBeNull();
    expect(span).toHaveTextContent('CVE-2024-9999 affects OpenSSL 3.0');
    expect(span).toHaveAttribute('tabIndex', '0');
    expect(span?.className).toContain('cursor-help');
  });

  it('renders an ai_interpreted citation as plain prose followed by an AI superscript tag', () => {
    const data: ExplainVulnResponse = {
      summary: 'This finding is likely low-effort to exploit remotely.',
      business_risk: 'Business risk framing.',
      citations: [
        { text: 'likely low-effort to exploit remotely', source: 'ai_interpreted', source_field: null },
      ],
      grounded: true,
    };
    const { container } = render(<AiExplanationCitations data={data} />);
    const sup = screen.getByText('AI', { selector: 'sup' });
    expect(sup).toHaveAttribute('tabIndex', '0');
    expect(sup.className).toContain('uppercase');
    expect(container.textContent).toContain('likely low-effort to exploit remotely');
    // The cited prose itself is NOT wrapped in the violet-soft tint (that
    // treatment is reserved for scanner_verbatim only).
    expect(container.querySelector('.bg-violet-soft')).toBeNull();
  });

  it('renders uncited text as plain prose with no citation span', () => {
    const data: ExplainVulnResponse = {
      summary: 'Nothing in this sentence is cited.',
      business_risk: 'Nor is this one.',
      citations: [],
      grounded: true,
    };
    const { container } = render(<AiExplanationCitations data={data} />);
    expect(container.querySelector('.bg-violet-soft')).toBeNull();
    expect(container.querySelector('sup')).toBeNull();
    expect(container.textContent).toContain('Nothing in this sentence is cited.');
  });

  it('applies a staggered reveal animation class only when animateReveal is true', () => {
    const data: ExplainVulnResponse = {
      summary: 'Some summary text here.',
      business_risk: 'Some business risk text here.',
      citations: [],
      grounded: true,
    };
    const { container: staticContainer } = render(<AiExplanationCitations data={data} animateReveal={false} />);
    expect(staticContainer.querySelector('[style*="animation"]')).toBeNull();

    const { container: animatedContainer } = render(<AiExplanationCitations data={data} animateReveal />);
    expect(animatedContainer.querySelector('.motion-safe\\:animate-in')).not.toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────
// AiExplanationSection
// ─────────────────────────────────────────────────────────────────────────

const mockUseAuth = vi.fn();
vi.mock('@/lib/auth', () => ({ useAuth: () => mockUseAuth() }));

const mockUseExplainCache = vi.fn();
vi.mock('@/lib/queries/use-explain-cache', () => ({ useExplainCache: () => mockUseExplainCache() }));

const mockStart = vi.fn();
const mockUseExplainStream = vi.fn();
vi.mock('@/lib/ai/use-explain-stream', () => ({ useExplainStream: () => mockUseExplainStream() }));

const mockUseConnectorsList = vi.fn();
vi.mock('@/lib/queries/use-connectors-admin', () => ({ useConnectorsList: () => mockUseConnectorsList() }));

const mockReducedMotion = vi.fn();
vi.mock('@/hooks/use-prefers-reduced-motion', () => ({ usePrefersReducedMotion: () => mockReducedMotion() }));

// Static import -- vi.mock() calls above are hoisted by Vitest above every
// import statement in this file (including this one), so by the time
// ai-explanation-section.tsx (and its own imports of the 5 mocked modules)
// is evaluated, the mock registry is already populated.
import { AiExplanationSection } from './ai-explanation-section';

const VALIDATED_DATA: ExplainVulnResponse = {
  summary: 'Plain-English summary of the finding.',
  business_risk: 'Framed business risk.',
  citations: [],
  grounded: true,
};

function setDefaults(overrides?: {
  role?: string;
  cache?: unknown;
  stream?: unknown;
  connectors?: unknown;
  reducedMotion?: boolean;
}) {
  mockUseAuth.mockReturnValue({ user: { role: overrides?.role ?? 'ANALYST' } });
  mockUseExplainCache.mockReturnValue(
    overrides?.cache ?? { data: { cached: false }, isPending: false, isError: false },
  );
  mockUseExplainStream.mockReturnValue(
    overrides?.stream ?? { state: { phase: 'idle' }, start: mockStart },
  );
  mockUseConnectorsList.mockReturnValue(
    overrides?.connectors ?? {
      data: [{ connector_type: 'ANTHROPIC', is_enabled: true }],
      isPending: false,
      isError: false,
    },
  );
  mockReducedMotion.mockReturnValue(overrides?.reducedMotion ?? true);
}

describe('AiExplanationSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDefaults();
  });

  it('cache-miss + role=Viewer renders muted "No AI explanation generated yet." and no button', () => {
    setDefaults({ role: 'VIEWER' });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText('No AI explanation generated yet.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Explain this vuln' })).toBeNull();
  });

  it('cache-miss + role=Analyst renders the "Explain this vuln" button', () => {
    setDefaults({ role: 'ANALYST' });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByRole('button', { name: 'Explain this vuln' })).toBeInTheDocument();
  });

  it('no-key + role=Admin renders the "Configure AI" CTA', () => {
    setDefaults({ role: 'ADMIN', connectors: { data: [], isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText("AI isn't set up yet")).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Configure AI' })).toHaveAttribute('href', '/dashboard/connectors');
  });

  it('no-key + role=Analyst renders the "ask an admin" nudge with no CTA', () => {
    setDefaults({ role: 'ANALYST', connectors: { data: [], isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(
      screen.getByText("AI explanations aren't available yet — ask an admin to configure GetVul's AI connector."),
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Configure AI' })).toBeNull();
  });

  it('grounded=false (post-click error) renders the neutral insufficient-evidence card with no amber/red class', () => {
    setDefaults({ stream: { state: { phase: 'error', kind: 'grounded_false' }, start: mockStart } });
    const { container } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText('Not enough finding data to explain this reliably')).toBeInTheDocument();
    expect(container.querySelector('.bg-amber-soft')).toBeNull();
    expect(container.querySelector('[class*="danger"]')).toBeNull();
  });

  it('UI-SPEC backstop: a done payload flagged grounded=false routes to the insufficient-evidence card, never a citation render', () => {
    setDefaults({
      stream: {
        state: { phase: 'done', data: { ...VALIDATED_DATA, grounded: false } },
        start: mockStart,
      },
    });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText('Not enough finding data to explain this reliably')).toBeInTheDocument();
    expect(screen.queryByText(VALIDATED_DATA.summary)).toBeNull();
  });

  it('D-25: error kind=busy renders the amber "AI busy" card with a Try again button', () => {
    setDefaults({ stream: { state: { phase: 'error', kind: 'busy' }, start: mockStart } });
    const { container } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText('AI busy — try again in a moment')).toBeInTheDocument();
    expect(container.querySelector('.bg-amber-soft')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('unknown fallback: error kind=unknown renders the SAME amber provider-busy card, never a generic error card', () => {
    setDefaults({ stream: { state: { phase: 'error', kind: 'unknown' }, start: mockStart } });
    const { container } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText('AI busy — try again in a moment')).toBeInTheDocument();
    expect(container.querySelector('.bg-amber-soft')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('budget_exceeded renders an amber card (role-gated copy, Analyst gets no action)', () => {
    setDefaults({
      role: 'ANALYST',
      stream: { state: { phase: 'error', kind: 'budget_exceeded' }, start: mockStart },
    });
    const { container } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText('AI budget exceeded')).toBeInTheDocument();
    expect(container.querySelector('.bg-amber-soft')).not.toBeNull();
    expect(screen.queryByRole('link', { name: 'Raise the cap' })).toBeNull();
  });

  it('budget_exceeded for an Admin adds the "Raise the cap" link', () => {
    setDefaults({
      role: 'ADMIN',
      stream: { state: { phase: 'error', kind: 'budget_exceeded' }, start: mockStart },
    });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByRole('link', { name: 'Raise the cap' })).toHaveAttribute('href', '/dashboard/connectors');
  });

  it('under prefers-reduced-motion, a done state renders the full result immediately with no reveal animation', () => {
    setDefaults({
      reducedMotion: true,
      stream: { state: { phase: 'done', data: VALIDATED_DATA }, start: mockStart },
    });
    const { container } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText(VALIDATED_DATA.summary, { exact: false })).toBeInTheDocument();
    expect(container.querySelector('[style*="animation"]')).toBeNull();
  });

  it('without prefers-reduced-motion, a done state applies the token-by-token reveal animation (D-12)', () => {
    setDefaults({
      reducedMotion: false,
      stream: { state: { phase: 'done', data: VALIDATED_DATA }, start: mockStart },
    });
    const { container } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText(VALIDATED_DATA.summary, { exact: false })).toBeInTheDocument();
    expect(container.querySelector('.motion-safe\\:animate-in')).not.toBeNull();
  });

  it('a cache hit never shows the reveal animation, even without prefers-reduced-motion (D-09 vs D-12)', () => {
    setDefaults({
      reducedMotion: false,
      cache: { data: { cached: true, ...VALIDATED_DATA }, isPending: false, isError: false },
    });
    const { container } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText(VALIDATED_DATA.summary, { exact: false })).toBeInTheDocument();
    expect(container.querySelector('[style*="animation"]')).toBeNull();
  });

  it('never renders a red/--color-danger class anywhere, even across every state', () => {
    const states = [
      { phase: 'idle' },
      { phase: 'analyzing' },
      { phase: 'error', kind: 'busy' },
      { phase: 'error', kind: 'grounded_false' },
      { phase: 'error', kind: 'budget_exceeded' },
      { phase: 'done', data: VALIDATED_DATA },
    ];
    for (const state of states) {
      setDefaults({ stream: { state, start: mockStart } });
      const { container, unmount } = render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
      expect(container.querySelector('[class*="danger"]')).toBeNull();
      unmount();
    }
  });
});
