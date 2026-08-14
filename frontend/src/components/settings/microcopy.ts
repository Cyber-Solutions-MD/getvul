/**
 * microcopy.ts — copy strings for the /dashboard/settings surface.
 *
 * Rules (copy-voice.md):
 * - Peer voice: direct, technical, sentence case.
 * - Buttons use verb phrases (imperative). No exclamation marks. No "Please".
 * - No "Are you sure?" — name the action instead.
 */

export type Category =
  | 'profile'
  | 'workspace'
  | 'saml'
  | 'notifications'
  | 'api-tokens'
  | 'audit'
  | 'ai'
  | 'sla';

/** Sidebar category labels — sentence case per copy-voice.md. */
export const CATEGORY_LABELS: Record<Category, string> = {
  profile: 'Profile',
  workspace: 'Workspace',
  saml: 'SAML & OIDC',
  notifications: 'Notifications',
  'api-tokens': 'API tokens',
  audit: 'Audit log',
  ai: 'AI usage & settings',
  // Phase 36 (D-10): risk-tier SLA policy + escalation-channel admin pane.
  sla: 'SLA & Escalation',
} as const;

/**
 * Unsaved-changes navigation guard copy.
 * Per copy-voice.md: no "Are you sure?", names the action directly.
 */
export const UNSAVED_GUARD =
  'You have unsaved changes. Discard them and switch?' as const;

/** SaveBar copy strings. */
export const SAVE_BAR = {
  unsavedNote: 'Unsaved changes',
  save: 'Save changes',
  discard: 'Discard',
  saving: 'Saving…',
} as const;
