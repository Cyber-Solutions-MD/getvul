/**
 * microcopy.ts — peer-voice copy strings for the /tickets detail surface.
 *
 * Rules (copy-voice.md):
 * - Peer voice — sentence case, direct, technical. No generic SaaS copy.
 * - Buttons use verb phrases (imperative). No exclamation marks.
 */

export const microcopy = {
  // WatcherStack
  watchersEmpty: "No one's watching this yet.",

  // CommentInput
  commentPlaceholder: 'Add a note for the team…',

  // BlockedToggle
  blockedPrompt: "What's blocking this?",
  markBlocked: 'Mark blocked',
  unblock: 'Unblock',
  blockedSave: 'Save',
  blockedCancel: 'Cancel',

  // TicketAssetCard
  openFull: 'Open full detail',
  viewAsset: 'View asset →',
  multipleHosts: 'Multiple hosts',

  // CommentInput submit
  postNote: 'Post note',

  // CommentInput char-count helper
  charLimitWarning: (remaining: number) => `${remaining} characters left`,
} as const;
