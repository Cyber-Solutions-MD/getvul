import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProviderMark } from './provider-mark';

describe('ProviderMark', () => {
  it('jira: references the jira gradient CSS variable (not raw hex)', () => {
    const { container } = render(<ProviderMark provider="jira" />);
    const el = container.firstChild as HTMLElement;
    // The background style must reference the CSS variable token, never inline hex
    expect(el.style.background).toContain('--gradient-provider-jira');
  });

  it('asana: references the asana gradient CSS variable', () => {
    const { container } = render(<ProviderMark provider="asana" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.background).toContain('--gradient-provider-asana');
  });

  it('github: references the github gradient CSS variable', () => {
    const { container } = render(<ProviderMark provider="github" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.background).toContain('--gradient-provider-github');
  });

  it('each provider produces a distinct gradient reference', () => {
    const { container: jiraContainer } = render(<ProviderMark provider="jira" />);
    const { container: asanaContainer } = render(<ProviderMark provider="asana" />);
    const { container: githubContainer } = render(<ProviderMark provider="github" />);

    const jiraBg = (jiraContainer.firstChild as HTMLElement).style.background;
    const asanaBg = (asanaContainer.firstChild as HTMLElement).style.background;
    const githubBg = (githubContainer.firstChild as HTMLElement).style.background;

    expect(jiraBg).not.toBe(asanaBg);
    expect(jiraBg).not.toBe(githubBg);
    expect(asanaBg).not.toBe(githubBg);
  });

  it('renders NO img element and NO logo asset reference', () => {
    const { container } = render(<ProviderMark provider="jira" />);
    expect(container.querySelectorAll('img')).toHaveLength(0);
    expect(container.innerHTML).not.toMatch(/\.svg|\.png|logo/i);
  });

  it('renders with aria-label for accessibility', () => {
    render(<ProviderMark provider="jira" />);
    expect(screen.getByLabelText('jira')).toBeDefined();
  });
});
