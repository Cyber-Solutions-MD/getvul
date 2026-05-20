import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    // css:false skips Vite's CSS processing (no PostCSS, no @import resolution) so jsdom never sees
    // globals.css → @import './styles/sunset.css' chains. Tests therefore inject CSS variables via
    // document.documentElement.style for token assertions (see foundation.test.ts). End-to-end
    // CSS resolution from real globals.css is verified in Wave 5 via `npm run build` + manual cold-load.
    css: false,
  },
});
