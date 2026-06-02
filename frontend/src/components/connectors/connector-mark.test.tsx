/**
 * connector-mark.test.tsx — TDD RED-phase tests for ConnectorMark.
 *
 * Test 1: Each of the 14 providers renders a span with correct aria-label
 *         and a non-empty background style.
 * Test 2: An unknown provider string renders no gradient (literal-lookup
 *         injection guard — T-14-01 / T-13-14 mitigation).
 * Test 3: globals.css contains all 12 new --gradient-provider-* token names.
 */
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { ConnectorMark } from './connector-mark';
import type { ConnectorProvider } from './types';

const ALL_PROVIDERS: ConnectorProvider[] = [
  'crowdstrike',
  'nessus',
  'defender',
  'wiz',
  'qualys',
  'rapid7',
  'google_workspace',
  'azure_entra_id',
  'okta',
  'jamf',
  'intune',
  'humaans',
  'jira',
  'asana',
  'github',
];

const NEW_TOKENS = [
  '--gradient-provider-crowdstrike',
  '--gradient-provider-nessus',
  '--gradient-provider-defender',
  '--gradient-provider-wiz',
  '--gradient-provider-qualys',
  '--gradient-provider-rapid7',
  '--gradient-provider-google_workspace',
  '--gradient-provider-azure_entra_id',
  '--gradient-provider-okta',
  '--gradient-provider-jamf',
  '--gradient-provider-intune',
  '--gradient-provider-humaans',
];

describe('ConnectorMark', () => {
  it('Test 1: all 14 providers render a span with correct aria-label and non-empty background style', () => {
    for (const provider of ALL_PROVIDERS) {
      const { container, unmount } = render(<ConnectorMark provider={provider} />);
      const span = container.querySelector('span');
      expect(span, `span should exist for provider "${provider}"`).not.toBeNull();
      expect(span!.getAttribute('aria-label')).toBe(provider);
      const bg = span!.style.background || span!.style.backgroundImage || '';
      expect(bg, `background should be non-empty for "${provider}"`).not.toBe('');
      unmount();
    }
  });

  it('Test 2: unknown provider falls through to undefined — no gradient rendered (injection guard)', () => {
    const { container } = render(
      // Cast to exercise the injection guard for an unknown connector type
      <ConnectorMark provider={'evilcorp' as ConnectorProvider} />,
    );
    const span = container.querySelector('span');
    expect(span).not.toBeNull();
    // background must be empty — literal lookup returns undefined, no CSS var injected
    const bg = span!.style.background || span!.style.backgroundImage || '';
    expect(bg).toBe('');
  });

  it('Test 3: globals.css contains all 12 new --gradient-provider-* token names', () => {
    const cssPath = resolve(__dirname, '../../app/globals.css');
    const css = readFileSync(cssPath, 'utf-8');
    for (const token of NEW_TOKENS) {
      expect(css, `"${token}" should be present in globals.css`).toContain(token);
    }
  });
});
