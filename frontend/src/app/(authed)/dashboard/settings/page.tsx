'use client';
/**
 * Settings page — UX-06-04 sidebar-of-categories layout.
 *
 * Replaces the v1 horizontal-tab implementation (4 tabs: general/auth/users/audit)
 * with a 6-category sidebar driven by <SettingsSidebarShell>.
 *
 * Category routing:
 *   - Driven by ?category= URL param via useUrlState (allow-list clamped, T-14-20).
 *   - Default: 'profile'.
 *   - 6 categories: profile / workspace / saml / notifications / api-tokens / audit.
 *
 * Unsaved-changes guard (D-SET-04 / WR-03):
 *   - Each editable pane reports its dirty state up via an onDirtyChange prop
 *     wired straight to useDirtyState.isDirty (no DOM polling / selector
 *     coupling — a SaveBar markup rename can no longer silently disable the
 *     guard, and there is no setTimeout(0) race).
 *   - Switching category while dirty opens ConfirmModal (UNSAVED_GUARD copy).
 *   - On confirm: navigate + clear dirty. On cancel: stay.
 *
 * Mobile (D-SET-10):
 *   - Relies on SettingsSidebarShell's stacked layout (<900px).
 *   - Back button visible in pane area on mobile to return to category list.
 *
 * RBAC: SettingsSidebarShell computes visibleCategories internally from
 *   useAuth(). The page only passes activeCategory + onCategoryChange.
 *
 * Security (T-14-16): sidebar gating is UX only. Backend 403 is authoritative.
 * Security (T-14-20): category value is clamped via useUrlState allow-list.
 *
 * No horizontal tab patterns anywhere in this file.
 * No gray-N / indigo-N raw palette utilities.
 *
 * Plan 14-05.
 */

import { useState, useRef, useCallback } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { SettingsSidebarShell, type Category } from '@/components/settings/settings-sidebar-shell';
import { ProfilePane } from '@/components/settings/profile-pane';
import { WorkspacePane } from '@/components/settings/workspace-pane';
import { SamlPane } from '@/components/settings/saml-pane';
import { NotificationsPane } from '@/components/settings/notifications-pane';
import { ApiTokensPane } from '@/components/settings/api-tokens-pane';
import { AuditLogPane } from '@/components/settings/audit-log-pane';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { UNSAVED_GUARD } from '@/components/settings/microcopy';
import { useUrlState } from '@/hooks/use-url-state';

// ── Category allow-list (T-14-20: clamp unknown values to 'profile') ──────────
const CATEGORY_ALLOW_LIST = [
  'profile',
  'workspace',
  'saml',
  'notifications',
  'api-tokens',
  'audit',
] as const satisfies readonly Category[];

// ── Component ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  useDocumentTitle('Settings');
  // URL-driven category (clamped via allow-list — T-14-20).
  const [activeCategory, setActiveCategory] = useUrlState<Category>(
    'category',
    CATEGORY_ALLOW_LIST,
    'profile',
  );

  // Unsaved-changes guard state (D-SET-04)
  // paneDirtyRef is a ref so handleCategoryChange always reads latest value
  // without needing to be recreated via useCallback. Panes report their dirty
  // state up through handleDirtyChange (WR-03) — no DOM polling.
  const paneDirtyRef = useRef(false);
  const [pendingCategory, setPendingCategory] = useState<Category | null>(null);
  const [guardOpen, setGuardOpen] = useState(false);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    paneDirtyRef.current = dirty;
  }, []);

  function handleCategoryChange(next: Category) {
    // Read from ref (sync) rather than state (potentially stale in closure)
    if (paneDirtyRef.current && next !== activeCategory) {
      // Open the unsaved-changes guard modal
      setPendingCategory(next);
      setGuardOpen(true);
    } else {
      setActiveCategory(next);
    }
  }

  function handleGuardConfirm() {
    // User confirmed discard — navigate and clear dirty state
    if (pendingCategory) {
      setActiveCategory(pendingCategory);
    }
    // The destination pane will re-report its own dirty state on mount.
    paneDirtyRef.current = false;
    setPendingCategory(null);
    setGuardOpen(false);
  }

  function handleGuardCancel() {
    setPendingCategory(null);
    setGuardOpen(false);
  }

  // Render the active pane.
  // Editable panes report their dirty state up via onDirtyChange (WR-03) so the
  // page-level guard can fire when the user tries to switch categories. No DOM
  // polling or SaveBar selector coupling.
  function renderPane() {
    switch (activeCategory) {
      case 'profile':
        return <ProfilePane />;
      case 'workspace':
        return <WorkspacePane onDirtyChange={handleDirtyChange} />;
      case 'saml':
        return <SamlPane onDirtyChange={handleDirtyChange} />;
      case 'notifications':
        return <NotificationsPane onDirtyChange={handleDirtyChange} />;
      case 'api-tokens':
        return <ApiTokensPane />;
      case 'audit':
        return <AuditLogPane />;
      default:
        return <ProfilePane />;
    }
  }

  return (
    <div>
      <SettingsSidebarShell
        activeCategory={activeCategory}
        onCategoryChange={handleCategoryChange}
      >
        {renderPane()}
      </SettingsSidebarShell>

      {/* Unsaved-changes guard (D-SET-04) */}
      <ConfirmModal
        open={guardOpen}
        title="Unsaved changes"
        message={UNSAVED_GUARD}
        confirmLabel="Discard"
        cancelLabel="Stay"
        variant="warning"
        onConfirm={handleGuardConfirm}
        onCancel={handleGuardCancel}
      />
    </div>
  );
}
