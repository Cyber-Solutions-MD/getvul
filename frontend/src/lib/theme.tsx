'use client';

import { createContext, useCallback, useContext, useState } from 'react';

type Theme = 'dark' | 'light';

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'dark',
  setTheme: () => {},
  toggle: () => {},
});

// Read the data-theme attribute the layout bootstrap script set pre-hydration.
// SSR has no document, so default to "dark" (matches layout.tsx's default attr).
function readInitialTheme(): Theme {
  if (typeof document === 'undefined') return 'dark';
  const attr = document.documentElement.getAttribute('data-theme');
  return attr === 'light' ? 'light' : 'dark';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // No mounted gate — D-02 + Pitfall 4. The bootstrap script in <head> has
  // already set data-theme synchronously before this provider hydrates, so
  // there is no theme flash to hide. Children render unconditionally.
  const [theme, setThemeState] = useState<Theme>(readInitialTheme);

  const setTheme = useCallback((next: Theme) => {
    document.documentElement.setAttribute('data-theme', next);
    try {
      localStorage.setItem('getvul_theme', next);
    } catch {
      // Storage unavailable (private-mode Safari, disabled storage). State
      // still flips for this session — preference just won't persist.
    }
    setThemeState(next);
  }, []);

  const toggle = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  }, [theme, setTheme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
