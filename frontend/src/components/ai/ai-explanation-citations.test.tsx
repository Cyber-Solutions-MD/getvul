/**
 * ai-explanation-citations.test.tsx -- pure-render tests for
 * AiExplanationCitations, relocated verbatim from
 * components/vulnerabilities/ai-explanation-citations.test.tsx (24-05 Task 2)
 * as part of 24-09 Task 1's move to the shared, view-agnostic
 * components/ai/ directory (D-15). No behavior change from the move --
 * AiExplanationCitations never had any vuln-specific logic; it renders any
 * validated ExplainVulnResponse-shaped payload regardless of which
 * resourceType produced it.
 *
 * (The sibling AiExplanationSection tests now live in their own
 * ai-explanation-section.test.tsx in this same directory -- split out of
 * this file's former combined test suite so the two components' test files
 * mirror the two components' own file split.)
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { AiExplanationCitations } from './ai-explanation-citations';
import type { ExplainVulnResponse } from '@/lib/ai/use-explain-stream';

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
