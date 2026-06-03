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
 * Unsaved-changes guard (D-SET-04):
 *   - Active pane reports dirty state via onDirtyChange callback.
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
  // URL-driven category (clamped via allow-list — T-14-20).
  const [activeCategory, setActiveCategory] = useUrlState<Category>(
    'category',
    CATEGORY_ALLOW_LIST,
    'profile',
  );

  // Unsaved-changes guard state (D-SET-04)
  // paneDirtyRef is a ref so handleCategoryChange always reads latest value
  // without needing to be recreated via useCallback.
  const paneDirtyRef = useRef(false);
  const [paneDirty, setPaneDirty] = useState(false);
  const [pendingCategory, setPendingCategory] = useState<Category | null>(null);
  const [guardOpen, setGuardOpen] = useState(false);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    paneDirtyRef.current = dirty;
    setPaneDirty(dirty);
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
    paneDirtyRef.current = false;
    setPaneDirty(false);
    setPendingCategory(null);
    setGuardOpen(false);
  }

  function handleGuardCancel() {
    setPendingCategory(null);
    setGuardOpen(false);
  }

  // Render the active pane.
  // For editable panes, we wrap with a dirty-bridge to allow the page-level
  // guard to fire when the user tries to switch categories.
  function renderPane() {
    switch (activeCategory) {
      case 'profile':
        return <ProfilePane />;
      case 'workspace':
        return (
          <PaneWithDirtyBridge onDirtyChange={handleDirtyChange}>
            <WorkspacePane />
          </PaneWithDirtyBridge>
        );
      case 'saml':
        return (
          <PaneWithDirtyBridge onDirtyChange={handleDirtyChange}>
            <SamlPane />
          </PaneWithDirtyBridge>
        );
      case 'notifications':
        return (
          <PaneWithDirtyBridge onDirtyChange={handleDirtyChange}>
            <NotificationsPane />
          </PaneWithDirtyBridge>
        );
      case 'api-tokens':
        return <ApiTokensPane />;
      case 'audit':
        return <AuditLogPane />;
      default:
        return <ProfilePane />;
    }
  }

  // Page-level click listener: refresh the dirty ref before any click is
  // processed. This ensures that when a sidebar category button is clicked,
  // paneDirtyRef reflects the current SaveBar state.
  function handlePageClick() {
    const hasBar = document.querySelector('[data-save-bar]') !== null;
    paneDirtyRef.current = hasBar;
    setPaneDirty(hasBar);
  }

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div onClickCapture={handlePageClick}>
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

/**
 * PaneWithDirtyBridge — thin wrapper that monitors the SaveBar's presence to
 * set the page-level paneDirty flag.
 *
 * The SaveBar renders with data-save-bar when the pane is dirty. We detect
 * this by scheduling a check after user interaction (via queueMicrotask so
 * React state has settled before we read the DOM).
 */
function PaneWithDirtyBridge({
  children,
  onDirtyChange,
}: {
  children: React.ReactNode;
  onDirtyChange: (dirty: boolean) => void;
}) {
  function scheduleCheck() {
    // Defer DOM check until after React has flushed the interaction's state
    // updates and rendered the SaveBar (setTimeout(0) yields after paint flush).
    setTimeout(() => {
      const hasBar = document.querySelector('[data-save-bar]') !== null;
      onDirtyChange(hasBar);
    }, 0);
  }

  return (
    <div
      onClickCapture={scheduleCheck}
      onChangeCapture={scheduleCheck}
      onInputCapture={scheduleCheck}
    >
      {children}
    </div>
  );
}
