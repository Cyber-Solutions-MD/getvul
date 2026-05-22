import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// D-F-04 — saved filters are READ-ONLY in Phase 11. Save / rename / delete
// UX is deferred until a user actually asks for it. The chip bar renders the
// violet `★ Today's triage` pill only when at least one saved filter exists.
export type SavedFilter = {
  id: string;
  name: string;
  filter_type: string;
  filters: Record<string, unknown>; // raw blob; consumer maps to canonical Phase 11 filter shape
  created_at: string;
};

export function useSavedFilters() {
  return useQuery({
    queryKey: queryKeys.savedFilters.list(),
    queryFn: ({ signal }) =>
      api<SavedFilter[]>(
        '/api/v1/vulnerabilities/saved-filters?filter_type=vulnerability',
        { signal }
      ),
    staleTime: 300_000, // 5 min — saved filters change rarely
    retry: 1,
  });
}
