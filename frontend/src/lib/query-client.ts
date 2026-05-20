import { QueryClient } from '@tanstack/react-query';

// Factory rather than module-level singleton — RESEARCH Pattern 1 / Pitfall 1.
// Mounted via `useState(() => makeQueryClient())` in src/app/providers.tsx so
// each component tree owns one QueryClient instance that survives strict-mode
// double-mounts and HMR without leaking caches across tests or trees.
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000, // D-D-06 base — per-query overrides allowed
        retry: 0, // D-D-07 default — useStats overrides to 1
        refetchOnWindowFocus: true, // D-D-12 cross-tab sync via focus
        refetchOnReconnect: true,
      },
      mutations: { retry: 0 },
    },
  });
}
