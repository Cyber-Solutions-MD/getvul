'use client';
/**
 * SettingsSidebarShell — D-SET-01 sidebar-of-categories layout shell.
 *
 * Layout: 220px sticky left nav + flex-1 right pane.
 * Active indicator: left gradient-strip (NOT a border-b tab indicator — Pitfall 1).
 *
 * RBAC gating (D-SET-05):
 *   - profile + api-tokens: always visible
 *   - workspace / saml / notifications / audit: require isAdmin (ADMIN or OWNER)
 *
 * Security note (T-14-04): this sidebar is a UX-layer access control only.
 * Backend routes enforce require_admin / require_owner independently. A VIEWER
 * who hand-crafts ?category=workspace still receives a 403 from the API; the
 * pane should render the PartialFailureBanner in that case.
 *
 * Mobile (<900px, D-SET-10): the shell stacks nav full-width above the pane.
 * The screen plan (14-05) wires the master-detail drill for mobile — this shell
 * only guarantees no horizontal-scroll at small viewports.
 */

import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';
import type { Category } from './microcopy';
import { CATEGORY_LABELS } from './microcopy';

// Re-export Category type for callers.
export type { Category };

type Props = {
  children: React.ReactNode;
  activeCategory: Category;
  onCategoryChange: (c: Category) => void;
};

/**
 * Ordered list of all categories. Gating is applied at render time based on role.
 * Profile always first; api-tokens always last.
 */
const ALL_CATEGORIES: Category[] = [
  'profile',
  'workspace',
  'saml',
  'notifications',
  'api-tokens',
  'audit',
];

/**
 * Admin-only categories (require isAdmin = OWNER | ADMIN).
 * Profile and api-tokens are always visible regardless of role.
 */
const ADMIN_ONLY: Set<Category> = new Set([
  'workspace',
  'saml',
  'notifications',
  'audit',
]);

export function SettingsSidebarShell({
  children,
  activeCategory,
  onCategoryChange,
}: Props) {
  const { user } = useAuth();

  // D-SET-05 RBAC gating — mirrors the isAdmin pattern from auth.tsx.
  const isAdmin =
    user?.role === 'OWNER' || user?.role === 'ADMIN';

  // visibleCategories preserves order; admin-only items are filtered out for non-admins.
  const visibleCategories = ALL_CATEGORIES.filter(
    (cat) => !ADMIN_ONLY.has(cat) || isAdmin,
  );

  return (
    // max-[900px]:flex-col: stack nav above pane on small viewports (D-SET-10).
    // The screen plan (14-05) wires the master-detail drill for mobile interactions.
    <div className="flex min-h-0 flex-1 max-[900px]:flex-col">
      {/* Left nav — 220px on desktop, full-width above pane on mobile */}
      <nav
        className="w-[220px] shrink-0 border-r border-border-subtle max-[900px]:w-full max-[900px]:border-r-0 max-[900px]:border-b"
        aria-label="Settings categories"
      >
        <ul className="flex flex-col gap-0.5 p-2">
          {visibleCategories.map((cat) => {
            const isActive = cat === activeCategory;
            return (
              <li key={cat}>
                {/* Each item is a <button> (not an anchor with a tab-indicator). Pitfall 1 guard. */}
                <button
                  type="button"
                  data-category={cat}
                  data-active={String(isActive)}
                  onClick={() => onCategoryChange(cat)}
                  className={cn(
                    // Base layout — relative so the gradient strip can be absolute-positioned.
                    'relative flex w-full items-center rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    // Text color: active → text-text, inactive → text-text-muted with hover
                    isActive
                      ? 'text-text'
                      : 'text-text-muted hover:text-text hover:bg-surface-2',
                  )}
                >
                  {/* Left gradient-strip active indicator — mirrors app-shell.md nav-item.active::before */}
                  {isActive && (
                    <span
                      className="absolute left-0 top-1 bottom-1 w-0.5 rounded-full"
                      style={{ background: 'var(--gradient-brand, var(--gradient-sunset, linear-gradient(135deg, #EC4899 0%, #A78BFA 50%, #F59E0B 100%)))' }}
                      aria-hidden="true"
                    />
                  )}
                  {/* Category label — sentence case per microcopy.ts */}
                  <span className="pl-2">{CATEGORY_LABELS[cat]}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Right pane — wraps the category content */}
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
