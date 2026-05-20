'use client';

import { useState, type ReactNode } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { makeQueryClient } from '@/lib/query-client';

// Lazy init per RESEARCH Pattern 1 / Pitfall 1 — NEVER instantiate the client
// at module scope. useState's lazy initializer runs exactly once per component
// tree, so the QueryClient survives React strict-mode double-mounts and HMR
// without leaking caches across trees or tests.
//
// Mounted at the root layout (above AuthProvider) so /login and (authed)/*
// share one cache. This is the precondition for `useAuth().logout()` to call
// useQueryClient().clear() (D-D-09) without throwing on /login.
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
