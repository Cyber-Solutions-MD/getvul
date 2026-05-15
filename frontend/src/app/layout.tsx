import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { ThemeProvider } from '@/lib/theme';
import { Providers } from './providers';

const fontSans = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

const fontMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

// Inline FOUC-prevention bootstrap (D-13).
// Runs synchronously in <head> before hydration, reading localStorage('getvul_theme')
// (the v1 key — preserved to keep existing user preferences) or prefers-color-scheme,
// and stamping data-theme on <html>. Wrapped in try/catch to defeat localStorage
// failures (private-mode Safari, disabled storage, etc.) by falling back to dark.
const THEME_BOOTSTRAP_SCRIPT = `(function(){
  try {
    var stored = localStorage.getItem('getvul_theme');
    var theme = stored || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();`;

export const metadata: Metadata = {
  title: 'GetVul',
  description: 'Unified Vulnerability Aggregation Platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      data-theme="dark"
      className={`${fontSans.variable} ${fontMono.variable}`}
    >
      <head>
        {/* FOUC bootstrap MUST be first child of <head> so it runs before any paint. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          {/* <Providers> mounts QueryClientProvider at the ROOT layout so /login
              and (authed)/* share one TanStack cache. Pre-Phase 10, the provider
              lived inside (authed)/layout.tsx; logout's qc.clear() (D-D-09)
              forced the hoist — AuthProvider must be a descendant of
              QueryClientProvider on every route. */}
          <Providers>
            <AuthProvider>{children}</AuthProvider>
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
