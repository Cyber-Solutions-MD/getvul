/**
 * Avatar — sunset-gradient circle with initials.
 *
 * Consumers: owner card (12-07), topbar user chip, directory pages.
 * Background uses var(--gradient-sunset) per foundation.md; no freehand hex.
 *
 * T-12-04 (XSS via Avatar.name): mitigate. The computed `initial` is rendered
 * as a TEXT child of the span, never via dangerouslySetInnerHTML. React
 * escapes text content by default; the test passes `<img onerror=...>` as
 * the name and asserts no <img> element appears in the DOM.
 */
import { cn } from '@/lib/utils';

function initialsFor(name?: string, email?: string): string {
  // WR-09: 2-char initials per sketch-findings-getvul/references/visual-language.md
  // ("Initials inside (2 chars)" — examples 'AS', 'JK'). Multi-word names use
  // first letter of first + last word; single-word names fall back to the
  // first letter only so the chip doesn't show a partial second char.
  const trimmedName = (name ?? '').trim();
  if (trimmedName) {
    const parts = trimmedName.split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0][0].toUpperCase();
  }
  const local = (email ?? '').split('@')[0]?.trim();
  if (local) {
    // Email local parts are commonly first.last → take both halves.
    const segs = local.split(/[._-]/);
    if (segs.length >= 2 && segs[0] && segs[1]) {
      return (segs[0][0] + segs[1][0]).toUpperCase();
    }
    return local[0].toUpperCase();
  }
  return '?';
}

export type AvatarProps = {
  name?: string;
  email?: string;
  size?: number; // default 40 (sketch 005 owner card size)
  className?: string;
};

export function Avatar({ name, email, size = 40, className }: AvatarProps) {
  const initial = initialsFor(name, email);
  const fontSize = Math.round(size * 0.42);
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-text-inverse',
        className,
      )}
      style={{
        width: size,
        height: size,
        background: 'var(--gradient-sunset)',
        fontSize,
        lineHeight: 1,
      }}
      data-size={size}
      aria-hidden={name || email ? undefined : 'true'}
    >
      {/* T-12-04 mitigation — text node only, never innerHTML. */}
      {initial}
    </span>
  );
}
