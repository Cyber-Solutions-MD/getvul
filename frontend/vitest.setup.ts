import '@testing-library/jest-dom/vitest';
import 'vitest-axe/extend-expect';
import * as axeMatchers from 'vitest-axe/matchers';
import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

expect.extend(axeMatchers);

// Node 25/26 + jsdom collision: Node now exposes an experimental global
// `localStorage` that is `undefined` unless `--localstorage-file` is passed,
// and it shadows jsdom's implementation. Install a shared in-memory stub once
// here so every suite gets a working Storage without re-declaring it per file
// (the pattern auth.logout/api tests previously copy-pasted). Individual tests
// still call localStorage.clear() in beforeEach for isolation.
{
  const memStore: Record<string, string> = {};
  const memLocalStorage: Storage = {
    getItem: (k: string) => (k in memStore ? memStore[k] : null),
    setItem: (k: string, v: string) => {
      memStore[k] = String(v);
    },
    removeItem: (k: string) => {
      delete memStore[k];
    },
    clear: () => {
      for (const k of Object.keys(memStore)) delete memStore[k];
    },
    key: (i: number) => Object.keys(memStore)[i] ?? null,
    get length() {
      return Object.keys(memStore).length;
    },
  };
  Object.defineProperty(globalThis, 'localStorage', {
    value: memLocalStorage,
    writable: true,
    configurable: true,
  });
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'localStorage', {
      value: memLocalStorage,
      writable: true,
      configurable: true,
    });
  }
}

// jsdom doesn't implement matchMedia; usePrefersReducedMotion (consumed by
// TrendChart and any future a11y-aware components) calls it during effects.
// Default to "not matched" so animations stay enabled in tests; individual
// tests can vi.spyOn(window, 'matchMedia') to flip behavior.
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

afterEach(() => {
  cleanup();
});
