import { describe, it, expect } from 'vitest';

// Plan 12-03 Task 2 creates this file. Import is the RED signal.
import { osFamily } from './os-family';

describe('osFamily() — client-side OS family derivation (locked_decisions item 6)', () => {
  it.each([
    ['Ubuntu 22.04 LTS', 'linux'],
    ['Debian 12', 'linux'],
    ['CentOS Stream 9', 'linux'],
    ['Red Hat Enterprise Linux 9', 'linux'],
    ['Fedora 39', 'linux'],
    ['Windows 11 Pro', 'windows'],
    ['Windows Server 2022', 'windows'],
    ['macOS Ventura 13.0', 'macos'],
    ['Mac OS X 10.15', 'macos'],
    ['Cisco IOS XE', 'other'],
    ['FreeBSD 14', 'other'],
    ['', 'other'],
  ] as const)('osFamily(%p) === %p', (input, expected) => {
    expect(osFamily(input)).toBe(expected);
  });

  it('returns other for null', () => {
    expect(osFamily(null)).toBe('other');
  });

  it('returns other for undefined', () => {
    expect(osFamily(undefined)).toBe('other');
  });

  it('is case-insensitive', () => {
    expect(osFamily('WINDOWS 11')).toBe('windows');
    expect(osFamily('UBUNTU 22.04')).toBe('linux');
    expect(osFamily('MACOS Sequoia')).toBe('macos');
  });
});
