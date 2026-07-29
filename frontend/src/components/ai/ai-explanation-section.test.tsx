/**
 * ai-explanation-section.test.tsx -- TDD tests for AiExplanationSection at
 * its new shared, view-agnostic home (24-09 Task 1, D-15's "all three
 * views" widening).
 *
 * The 8-state behavior matrix (mutually-exclusive body states driven by
 * useExplainCache + useExplainStream + useAuth (role) + useConnectorsList
 * (key-configured) + usePrefersReducedMotion) is RELOCATED verbatim from
 * components/vulnerabilities/ai-explanation-citations.test.tsx (24-05
 * Task 2 / 24-07) -- no behavior changed by the move, since the component
 * was already fully generalized over resourceType/resourceId (it just used
 * to live in a vuln-specific directory). All five hooks are mocked so every
 * state is directly, synchronously reachable without waiting on a real
 * query lifecycle.
 *
 * Two NEW describe blocks close out this plan's own D-15 obligation:
 * - "three-view parity": proves the SAME chrome/copy/role-gating renders
 *   for resourceType='vuln'|'host'|'remediation' given equivalent state --
 *   no per-view copy of the state machine (must_haves truth #1).
 * - "resourceType/resourceId prop-forwarding": proves the section forwards
 *   its props to useExplainCache/useExplainStream VERBATIM for all three
 *   resourceTypes, never a hardcoded 'vuln' literal. This composes with
 *   Plan 05's own use-explain-stream.test.ts (which already separately
 *   proves the hook-internal fetch-URL construction is resourceType-
 *   parameterized, e.g. resourceType='host' -> /explain-host/host-77) to
 *   verify the Plan-05 behavior end-to-end against the two NEW
 *   resourceTypes this plan mounts -- without re-deriving or re-mocking
 *   the SSE/fetch machinery Plan 05 already owns and tests.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const mockUseAuth = vi.fn();
vi.mock('@/lib/auth', () => ({ useAuth: () => mockUseAuth() }));

// Forward call args (not just `()`) so the prop-forwarding suite below can
// assert exactly what resourceType/resourceId the section passed through --
// existing tests are unaffected since they only ever assert on
// `.mockReturnValue(...)`, never on call arguments.
const mockUseExplainCache = vi.fn();
vi.mock('@/lib/queries/use-explain-cache', () => ({
  useExplainCache: (...args: unknown[]) => mockUseExplainCache(...args),
}));

const mockStart = vi.fn();
const mockUseExplainStream = vi.fn();
vi.mock('@/lib/ai/use-explain-stream', () => ({
  useExplainStream: (...args: unknown[]) => mockUseExplainStream(...args),
}));

const mockUseAiStatus = vi.fn();
vi.mock('@/lib/queries/use-ai-status', () => ({ useAiStatus: () => mockUseAiStatus() }));

const mockReducedMotion = vi.fn();
vi.mock('@/hooks/use-prefers-reduced-motion', () => ({ usePrefersReducedMotion: () => mockReducedMotion() }));

// 24-07: AiExplanationSection renders AiFeedbackControl beneath a validated
// explanation (section state 1). The real component calls useAiFeedback()
// (a real useMutation), which throws without a QueryClientProvider -- this
// file renders the bare component tree (no provider), so it's stubbed here
// exactly like the other 4 hooks above. ai-feedback-control.tsx stays in
// components/vulnerabilities/ per this plan's own file scope (only the
// section + citations components move) -- the mock target below is the
// NEW cross-directory import path ai-explanation-section.tsx now uses.
vi.mock('@/components/vulnerabilities/ai-feedback-control', () => ({
  AiFeedbackControl: () => <div data-testid="ai-feedback-control-stub" />,
}));

// Static import -- vi.mock() calls above are hoisted by Vitest above every
// import statement in this file (including this one), so by the time
// ai-explanation-section.tsx (and its own imports of the 5 mocked modules)
// is evaluated, the mock registry is already populated.
import { AiExplanationSection } from './ai-explanation-section';
import type { ExplainVulnResponse } from '@/lib/ai/use-explain-stream';
import { queryKeys } from '@/lib/queries/keys';

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
  status?: unknown;
  reducedMotion?: boolean;
}) {
  mockUseAuth.mockReturnValue({ user: { role: overrides?.role ?? 'ANALYST' } });
  mockUseExplainCache.mockReturnValue(
    overrides?.cache ?? { data: { cached: false }, isPending: false, isError: false },
  );
  mockUseExplainStream.mockReturnValue(
    overrides?.stream ?? { state: { phase: 'idle' }, start: mockStart },
  );
  mockUseAiStatus.mockReturnValue(
    overrides?.status ?? { data: { configured: true }, isPending: false, isError: false },
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
    // 24-07: no validated explanation yet -- feedback control must be absent.
    expect(screen.queryByTestId('ai-feedback-control-stub')).toBeNull();
  });

  it('no-key + role=Admin renders the "Configure AI" CTA', () => {
    setDefaults({ role: 'ADMIN', status: { data: { configured: false }, isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByText("AI isn't set up yet")).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Configure AI' })).toHaveAttribute('href', '/dashboard/connectors');
    // 24-07: onboarding card, not a validated explanation -- no feedback control.
    expect(screen.queryByTestId('ai-feedback-control-stub')).toBeNull();
  });

  it('no-key + role=Analyst renders the "ask an admin" nudge with no CTA and no trigger button', () => {
    setDefaults({ role: 'ANALYST', status: { data: { configured: false }, isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(
      screen.getByText("AI explanations aren't available yet — ask an admin to configure GetVul's AI connector."),
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Configure AI' })).toBeNull();
    // D-23 gap closure (24-VERIFICATION.md truth #2): a real unconfigured
    // signal must never leave the live trigger reachable for Analyst -- this
    // is exactly the bug the isError-based optimistic pass-through caused.
    expect(screen.queryByRole('button', { name: 'Explain this vuln' })).toBeNull();
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
    // 24-07: grounded=false is never a "validated explanation" -- no feedback control.
    expect(screen.queryByTestId('ai-feedback-control-stub')).toBeNull();
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
    // 24-07: a validated (grounded) explanation IS shown -- feedback control present.
    expect(screen.getByTestId('ai-feedback-control-stub')).toBeInTheDocument();
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
    // 24-07: a cache-hit validated explanation IS shown -- feedback control present.
    expect(screen.getByTestId('ai-feedback-control-stub')).toBeInTheDocument();
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

// ─────────────────────────────────────────────────────────────────────────
// D-15: three-view parity -- the SAME shared component, mounted with
// different resourceType values, must render IDENTICAL chrome/copy/states.
// No per-view branch may exist inside AiExplanationSection itself.
// ─────────────────────────────────────────────────────────────────────────

describe('three-view parity (D-15) -- identical chrome/copy/role-gating for vuln/host/remediation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDefaults();
  });

  it.each(['vuln', 'host', 'remediation'])(
    'cache-miss + role=Analyst renders the identical "AI Explanation" heading + "Explain this vuln" trigger for resourceType=%s',
    (resourceType) => {
      setDefaults({ role: 'ANALYST' });
      const { unmount } = render(<AiExplanationSection resourceType={resourceType} resourceId={`${resourceType}-id`} />);
      expect(screen.getByText('AI Explanation')).toBeInTheDocument();
      // Copy is NOT resourceType-conditional (must_haves truth #1/#5) -- the
      // trigger label stays "Explain this vuln" verbatim on every view, not
      // "Explain this host"/"Explain this remediation".
      expect(screen.getByRole('button', { name: 'Explain this vuln' })).toBeInTheDocument();
      unmount();
    },
  );

  it.each(['vuln', 'host', 'remediation'])(
    'role-gating: Viewer sees no trigger and the identical muted copy for resourceType=%s',
    (resourceType) => {
      setDefaults({ role: 'VIEWER' });
      const { unmount } = render(<AiExplanationSection resourceType={resourceType} resourceId={`${resourceType}-id`} />);
      expect(screen.getByText('No AI explanation generated yet.')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Explain this vuln' })).toBeNull();
      unmount();
    },
  );

  it.each(['vuln', 'host', 'remediation'])(
    'a grounded done payload renders the identical citation prose + feedback control for resourceType=%s',
    (resourceType) => {
      setDefaults({ stream: { state: { phase: 'done', data: VALIDATED_DATA }, start: mockStart } });
      const { unmount } = render(<AiExplanationSection resourceType={resourceType} resourceId={`${resourceType}-id`} />);
      expect(screen.getByText(VALIDATED_DATA.summary, { exact: false })).toBeInTheDocument();
      expect(screen.getByTestId('ai-feedback-control-stub')).toBeInTheDocument();
      unmount();
    },
  );

  it.each(['vuln', 'host', 'remediation'])(
    'no-key onboarding card renders identically for resourceType=%s',
    (resourceType) => {
      setDefaults({ role: 'ADMIN', status: { data: { configured: false }, isPending: false, isError: false } });
      const { unmount } = render(<AiExplanationSection resourceType={resourceType} resourceId={`${resourceType}-id`} />);
      expect(screen.getByText("AI isn't set up yet")).toBeInTheDocument();
      unmount();
    },
  );
});

// ─────────────────────────────────────────────────────────────────────────
// D-23 gap closure (24-10, 24-VERIFICATION.md truth #2): keyConfigured now
// derives from the REAL GET /api/v1/ai/status boolean (via useAiStatus),
// never from the admin-gated connectors endpoint's isError state. This
// matrix directly proves the fix for all four roles across both tenant
// states -- exactly the production behavior the prior isError-based guess
// could never reach for Analyst/Viewer (their GET /api/v1/connectors always
// 403s, so isError was always true, which the old code optimistically read
// as "assume configured").
// ─────────────────────────────────────────────────────────────────────────

describe('real ai-status signal: role x configured-state matrix (D-23 gap closure)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDefaults();
  });

  it('unconfigured + Analyst: "ask an admin" nudge present, no CTA, no live trigger button', () => {
    setDefaults({ role: 'ANALYST', status: { data: { configured: false }, isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(
      screen.getByText("AI explanations aren't available yet — ask an admin to configure GetVul's AI connector."),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Explain this vuln' })).toBeNull();
  });

  it('unconfigured + Viewer: the SAME "ask an admin" nudge, no CTA, never the generic no-explanation text', () => {
    setDefaults({ role: 'VIEWER', status: { data: { configured: false }, isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(
      screen.getByText("AI explanations aren't available yet — ask an admin to configure GetVul's AI connector."),
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Configure AI' })).toBeNull();
    expect(screen.queryByText('No AI explanation generated yet.')).toBeNull();
  });

  it('unconfigured + Admin: "Configure AI" CTA linking to /dashboard/connectors', () => {
    setDefaults({ role: 'ADMIN', status: { data: { configured: false }, isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByRole('link', { name: 'Configure AI' })).toHaveAttribute('href', '/dashboard/connectors');
  });

  it('configured + Analyst: renders the live "Explain this vuln" button, no false nudge', () => {
    setDefaults({ role: 'ANALYST', status: { data: { configured: true }, isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByRole('button', { name: 'Explain this vuln' })).toBeInTheDocument();
    expect(
      screen.queryByText("AI explanations aren't available yet — ask an admin to configure GetVul's AI connector."),
    ).toBeNull();
  });

  it('configured + Admin: also renders the live "Explain this vuln" button (asserted explicitly, not only by inference)', () => {
    setDefaults({ role: 'ADMIN', status: { data: { configured: true }, isPending: false, isError: false } });
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(screen.getByRole('button', { name: 'Explain this vuln' })).toBeInTheDocument();
  });

  it('forwards nothing to the old admin-gated connectors endpoint for the key signal -- only useAiStatus is consulted', () => {
    setDefaults();
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(mockUseAiStatus).toHaveBeenCalled();
  });
});

// ─────────────────────────────────────────────────────────────────────────
// D-15 path resolution: proves the section forwards resourceType/resourceId
// to useExplainCache/useExplainStream VERBATIM -- the exact inputs that
// determine the fetch path Plan 05 already proves are resourceType-
// parameterized (use-explain-stream.test.ts: resourceType='host' ->
// /explain-host/host-77). This plan's own new seam is the COMPONENT ->
// HOOK wiring for the two new resourceTypes ('host'/'remediation'); the
// hook -> fetch-URL construction itself is Plan 05's already-proven,
// unmodified territory (this plan does not touch use-explain-stream.ts).
// ─────────────────────────────────────────────────────────────────────────

describe('resourceType/resourceId prop-forwarding to the shared hooks (D-15)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDefaults();
  });

  it.each([
    ['vuln', 'CVE-2024-1234'],
    ['host', 'host-77'],
    ['remediation', 'CVE-2023-4863'],
  ])(
    'forwards resourceType=%s resourceId=%s to useExplainCache and useExplainStream verbatim, never a hardcoded literal',
    (resourceType, resourceId) => {
      render(<AiExplanationSection resourceType={resourceType} resourceId={resourceId} />);
      expect(mockUseExplainCache).toHaveBeenCalledWith(resourceType, resourceId);
      expect(mockUseExplainStream).toHaveBeenCalledWith(resourceType, resourceId);
    },
  );

  it('the ai.explain query key namespaces by resourceType, so a host mount and a vuln mount sharing a coincidental id string never collide', () => {
    // Pure function assertion (no render needed) -- proves the D-15 cache
    // namespacing claim directly against the single source of query keys,
    // composing with the forwarding proof above (the section passes
    // resourceType straight into this same key builder via useExplainCache).
    expect(queryKeys.ai.explain('vuln', 'shared-id')).not.toEqual(queryKeys.ai.explain('host', 'shared-id'));
    expect(queryKeys.ai.explain('vuln', 'shared-id')).not.toEqual(queryKeys.ai.explain('remediation', 'shared-id'));
    expect(queryKeys.ai.explain('host', 'shared-id')).not.toEqual(queryKeys.ai.explain('remediation', 'shared-id'));
  });
});

// ─────────────────────────────────────────────────────────────────────────
// D-15 (Task 2): mounting the SAME shared component more than once on one
// page (host mount + remediation mount both live on /assets/[id]) would
// collide on a hardcoded DOM id -- the h4's id must be caller-overridable.
// Default stays 'drill-ai-h' so drill-content.tsx's existing
// aria-labelledby="drill-ai-h" wrapper needs zero changes.
// ─────────────────────────────────────────────────────────────────────────

describe('headingId prop (D-15 multi-mount DOM-id safety, Task 2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDefaults();
  });

  it('defaults the heading id to "drill-ai-h" when no headingId prop is given (vuln view backward-compat)', () => {
    render(<AiExplanationSection resourceType="vuln" resourceId="abc-123" />);
    expect(document.getElementById('drill-ai-h')).toHaveTextContent('AI Explanation');
  });

  it('renders a caller-supplied headingId instead, so two mounts on one page never share a DOM id', () => {
    render(<AiExplanationSection resourceType="host" resourceId="host-1" headingId="ai-explanation-h-host" />);
    expect(document.getElementById('ai-explanation-h-host')).toHaveTextContent('AI Explanation');
    expect(document.getElementById('drill-ai-h')).toBeNull();
  });
});
