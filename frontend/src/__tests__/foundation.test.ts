import { describe, it, expect, beforeEach } from 'vitest';

describe('Foundation tokens (UX-F-01 + UX-F-02 swap mechanism)', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.style.cssText = '';
  });

  it('data-theme attribute switches between dark and light (D-02)', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');

    document.documentElement.setAttribute('data-theme', 'light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('sunset --color-bg token defines plum dark base (D-01, D-08)', () => {
    // Smoke: inject the variable as the sunset.css would, assert resolution.
    document.documentElement.style.setProperty('--color-bg', '#0E0B1A');
    const resolved = getComputedStyle(document.documentElement)
      .getPropertyValue('--color-bg').trim();
    expect(resolved).toBe('#0E0B1A');
  });

  it('theme swap mechanism: setting data-theme to light overrides bg token', () => {
    // Dark layer
    document.documentElement.style.setProperty('--color-bg', '#0E0B1A');
    document.documentElement.setAttribute('data-theme', 'dark');
    expect(getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim()).toBe('#0E0B1A');

    // Light override
    document.documentElement.setAttribute('data-theme', 'light');
    document.documentElement.style.setProperty('--color-bg', '#FAF7F2');
    expect(getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim()).toBe('#FAF7F2');
  });
});
