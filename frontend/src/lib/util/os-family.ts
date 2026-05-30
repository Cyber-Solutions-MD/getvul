/**
 * osFamily — client-side OS family derivation (locked_decisions item 6).
 *
 * MUST stay in lockstep with backend OS_FAMILY_PATTERNS in app/assets/router.py
 * (Plan 12-01 Task 2). Any change here requires a matching backend change.
 *
 * Patterns (case-insensitive substring match):
 *   linux   → 'linux' OR 'ubuntu' OR 'debian' OR 'centos' OR 'rhel' OR 'fedora'
 *   windows → 'windows'
 *   macos   → 'macos' OR 'mac os'
 *   other   → anything else (and null / undefined / empty input)
 *
 * Note: 'rhel' is the short token for "Red Hat Enterprise Linux"; the test
 * for "Red Hat Enterprise Linux 9" passes via the 'linux' token, while a
 * bare "rhel" string still matches via the 'rhel' token.
 */
export type OsFamily = 'linux' | 'windows' | 'macos' | 'other';

const LINUX_TOKENS = [
  'linux',
  'ubuntu',
  'debian',
  'centos',
  'rhel',
  'fedora',
];
const WINDOWS_TOKENS = ['windows'];
const MACOS_TOKENS = ['macos', 'mac os'];

export function osFamily(osName: string | null | undefined): OsFamily {
  if (!osName) return 'other';
  const lower = osName.toLowerCase();
  if (LINUX_TOKENS.some((t) => lower.includes(t))) return 'linux';
  if (WINDOWS_TOKENS.some((t) => lower.includes(t))) return 'windows';
  if (MACOS_TOKENS.some((t) => lower.includes(t))) return 'macos';
  return 'other';
}
