import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import type { DirectoryUser } from './use-asset-detail';

// Phase 12 D-A-02 — combobox source for the Reassign owner flow (UX-04-04).
//
// RESEARCH §2: hits /users/directory NOT /users.
//   /users is a device-rollup view keyed by lowercased email string.
//   /users/directory is the canonical User table — the assignable set.
//
// T-12-14: /users/directory already restricts to the caller's tenant in
// backend/app/users/router.py (~line 267). No frontend mitigation needed.
//
// T-12-15: per-keystroke spam is mitigated downstream in Plan 12-07's
// combobox via debounce — this hook is intentionally not debounced. The
// enabled-gate at >=2 chars trims the obvious zero-value calls (full
// directory dump on first focus, single-letter scans).
export type AssignableUsersResponse = {
  users: DirectoryUser[];
  total: number;
  page: number;
  page_size: number;
};

export function useAssignableUsers(search: string) {
  return useQuery({
    queryKey: queryKeys.assignableUsers.search(search),
    queryFn: ({ signal }) => {
      const sp = new URLSearchParams();
      sp.set('status', 'active');
      if (search) sp.set('search', search);
      sp.set('page_size', '25');
      return api<AssignableUsersResponse>(
        `/api/v1/users/directory?${sp.toString()}`,
        { signal }
      );
    },
    // W9 — only fetch once the user starts typing (>=2 chars). Avoids
    // loading the full directory on combobox first focus. Debouncing of
    // the search term itself lives in the combobox component.
    enabled: search.trim().length >= 2,
    staleTime: 30_000,
    retry: 1,
  });
}
