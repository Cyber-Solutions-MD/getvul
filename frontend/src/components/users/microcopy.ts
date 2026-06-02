/**
 * microcopy.ts — copy strings for the users directory page (Plan 14-04).
 *
 * Follows copy-voice.md: sentence case, no "Please", no exclamation marks,
 * technical/direct, explains WHY in empty states.
 */

export const microcopy = {
  emptyState: {
    title: 'No people match these filters',
    body: 'No directory users match the active status, department, or source filters. Relax one filter and try again.',
    clearAll: 'Clear all filters',
    suggestion: 'Try broadening the department or source filter — or search by email.',
  },
  exportSelected: 'Export selected',
  exportGroups: 'Export groups',
  groupsEmpty: {
    title: 'No groups found',
    body: 'Connect Google Workspace or Azure Entra ID to sync groups.',
  },
  searchPlaceholder: 'Search name, email, department…',
  searchAriaLabel: 'Search people',
  directoryView: 'Directory',
  groupsView: 'Groups',
  selected: (n: number) => `${n} ${n === 1 ? 'person' : 'people'} selected`,
};
