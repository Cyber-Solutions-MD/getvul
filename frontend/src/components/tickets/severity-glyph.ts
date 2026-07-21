/**
 * severity-glyph.ts — shared severity glyph + tint-class maps.
 *
 * Extracted from tickets-table.tsx (Phase 18, 18-02) so the list table and
 * the kanban card share a single source (Pitfall parity with sla-pill.tsx's
 * single-threshold pattern). Pure module — no React, no side effects.
 *
 * Values verbatim from visual-language.md (three-axis severity encoding).
 */

// Severity glyph map from visual-language.md
export const SEVERITY_GLYPH: Record<string, string> = {
  critical: '■',
  high: '▲',
  medium: '◆',
  low: '○',
  info: '□',
};

// Severity tint classes from sunset tokens
export const SEVERITY_CLASS: Record<string, string> = {
  critical: 'text-[var(--color-severity-critical-on-soft)]',
  high: 'text-[var(--color-severity-high-on-soft)]',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-severity-info',
};
