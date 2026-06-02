/**
 * TDD RED — compliance-framework-strip.tsx
 * Plan 14-03, Task 1.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

// ── Test 5: ComplianceFrameworkStrip ─────────────────────────────────────────
describe('ComplianceFrameworkStrip', () => {
  const frameworks = [
    { name: 'CIS AWS', total_controls: 100, passed: 80, failed: 15, suppressed: 5, pass_rate: 80 },
    { name: 'SOC 2', total_controls: 60, passed: 54, failed: 4, suppressed: 2, pass_rate: 90 },
  ];

  it('renders one cell per framework with its pass_rate as a percentage', async () => {
    const { ComplianceFrameworkStrip } = await import('./compliance-framework-strip');
    render(<ComplianceFrameworkStrip frameworks={frameworks} />);

    expect(screen.getByText('CIS AWS')).toBeTruthy();
    expect(screen.getByText('SOC 2')).toBeTruthy();
    // pass_rate as percentage
    expect(screen.getByText('80%')).toBeTruthy();
    expect(screen.getByText('90%')).toBeTruthy();

    // data-framework-strip attribute
    expect(document.querySelector('[data-framework-strip]')).toBeTruthy();
  });

  it('renders an empty strip when no frameworks provided', async () => {
    const { ComplianceFrameworkStrip } = await import('./compliance-framework-strip');
    const { container } = render(<ComplianceFrameworkStrip frameworks={[]} />);
    expect(container.querySelector('[data-framework-strip]')).toBeTruthy();
  });
});
