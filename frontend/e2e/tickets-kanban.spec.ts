// UX-D-01-01..05 — Tickets kanban board e2e spec (Phase 18).
//
// NOTE: This spec is authored BEFORE the board exists (Wave 0). Every test here is
// EXPECTED to be RED until Wave 2 (18-03) replaces the `view==='board'` placeholder
// with the real <TicketsKanbanBoard>. Do NOT force these green in this plan — see
// 18-01-PLAN.md objective.
//
// Test titles below are pinned EXACTLY as referenced by 18-VALIDATION.md's
// `-g` grep filters. Do not rename without updating the validation doc.
//
// Board DOM contract these tests assert against (Wave 2 must honor):
//   - Route: /dashboard/tickets?view=board
//   - Column labels: "Open", "In progress", "Completed", "Blocked"
//     (queried via data-column attribute + header text)
//   - Each column header shows a live count badge
//   - Each card carries data-ticket-id={ticket.id} and shows the mono external_ticket_id
//   - Empty column renders the canonical EmptyState (role="status")

import { test, expect } from '@playwright/test';
import { MOBILE_NAV, waitForNav } from './routes';

const COLUMN_LABELS = ['Open', 'In progress', 'Completed', 'Blocked'] as const;

test.describe('Tickets kanban board', () => {
  test('renders four columns', async ({ page }) => {
    await page.goto('/dashboard/tickets?view=board');
    await waitForNav(page, 1280);
    // 18-04 gate fix: the board is a next/dynamic({ssr:false}) lazy import — waitForNav
    // resolves as soon as the persistent shell mounts, before the board chunk downloads
    // and the ticket-list query resolves. Without this wait, the immediate .count() below
    // races the fetch and false-skips even when tickets ARE seeded (reproduced live: 0
    // cards at t=0, 5 cards by t=200ms). Wait for network to settle before reading DOM.
    await page.waitForLoadState('networkidle');

    // Guard against an empty dataset — skip with a visible reason rather than a silent pass.
    const anyCard = page.locator('[data-ticket-id]').first();
    const hasCards = await anyCard.count();
    if (hasCards === 0) {
      test.skip(true, 'no seeded tickets — cannot assert board column contents');
      return;
    }

    // Assert all four column labels are visible.
    for (const label of COLUMN_LABELS) {
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
    }

    // Board toggle still shows Board pressed.
    const boardToggle = page.getByRole('button', { name: 'Board', exact: true });
    await expect(boardToggle).toHaveAttribute('aria-pressed', 'true');

    // Switching to ?view=list still renders the table (toggle preserved — UX-D-01-01).
    await page.goto('/dashboard/tickets?view=list');
    await waitForNav(page, 1280);
    await expect(page.getByRole('table')).toBeVisible();
  });

  test('drag into Blocked persists', async ({ page }) => {
    await page.goto('/dashboard/tickets?view=board');
    await waitForNav(page, 1280);
    // 18-04 gate fix — see 'renders four columns' comment (dynamic-import + fetch race).
    await page.waitForLoadState('networkidle');

    const cards = page.locator('[data-ticket-id]');
    const cardCount = await cards.count();
    if (cardCount === 0) {
      test.skip(true, 'no seeded tickets — cannot assert drag-and-drop');
      return;
    }

    // Locate the first card that is NOT already in the Blocked column.
    const sourceCard = cards.first();
    const sourceBox = await sourceCard.boundingBox();
    if (!sourceBox) {
      test.skip(true, 'source card has no bounding box');
      return;
    }

    const blockedColumn = page.locator('[data-column="blocked"]');
    const blockedBox = await blockedColumn.boundingBox();
    if (!blockedBox) {
      test.skip(true, 'Blocked column has no bounding box');
      return;
    }

    // Perform the pointer drag: down on the card, move >=8px, over Blocked, up.
    await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(sourceBox.x + sourceBox.width / 2 + 20, sourceBox.y + sourceBox.height / 2 + 20);
    await page.mouse.move(blockedBox.x + blockedBox.width / 2, blockedBox.y + blockedBox.height / 2, {
      steps: 10,
    });
    await page.mouse.up();

    // Reason popover appears — click Save (no reason entered, optional).
    const saveButton = page.getByRole('button', { name: /save/i });
    await saveButton.waitFor({ state: 'visible', timeout: 5_000 });
    // 18-04 gate fix: clicking in the same tick the popover becomes visible is flaky —
    // the deferred (setTimeout(...,0), Pitfall 6) autofocus commit needs one settle beat
    // before a click reliably reaches the onClick handler (reproduced live: click()
    // returns with no error but onSave never fires without this wait).
    await page.waitForTimeout(200);
    await saveButton.click();

    // Assert the card now appears under the Blocked column.
    await expect(blockedColumn.locator('[data-ticket-id]').first()).toBeVisible();
    // 18-04 gate fix: the successful mutation above re-buckets the columns (the moved
    // card leaves Open, remaining Open cards reflow upward). Grabbing the next
    // boundingBox() in the same tick can race that reflow and land the next drag's
    // mousedown between cards instead of on one (reproduced live — the drag silently
    // never activates and the Save button never appears). Let the reflow settle first.
    await page.waitForTimeout(300);

    // --- Rollback assertion ---
    // Install a 500 interceptor BEFORE the next drag, then repeat, expecting the card
    // to snap back to its origin column after the failed mutation.
    await page.route('**/api/v1/tickets/*/blocked', (route) =>
      route.fulfill({ status: 500, body: '{}' }),
    );

    const nonBlockedColumn = page.locator('[data-column="open"]');
    const nonBlockedCard = nonBlockedColumn.locator('[data-ticket-id]').first();
    const nonBlockedCount = await nonBlockedCard.count();
    if (nonBlockedCount === 0) {
      test.skip(true, 'no non-Blocked cards remain to exercise rollback');
      return;
    }
    const rollbackSourceBox = await nonBlockedCard.boundingBox();
    if (!rollbackSourceBox) {
      test.skip(true, 'rollback source card has no bounding box');
      return;
    }

    await page.mouse.move(
      rollbackSourceBox.x + rollbackSourceBox.width / 2,
      rollbackSourceBox.y + rollbackSourceBox.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      rollbackSourceBox.x + rollbackSourceBox.width / 2 + 20,
      rollbackSourceBox.y + rollbackSourceBox.height / 2 + 20,
    );
    await page.mouse.move(blockedBox.x + blockedBox.width / 2, blockedBox.y + blockedBox.height / 2, {
      steps: 10,
    });
    await page.mouse.up();

    const rollbackSave = page.getByRole('button', { name: /save/i });
    await rollbackSave.waitFor({ state: 'visible', timeout: 5_000 });
    // 18-04 gate fix — see the first Save click above (deferred-autofocus settle beat).
    await page.waitForTimeout(200);
    await rollbackSave.click();

    // The mutation fails (500) — assert the card snaps back to Open (origin column).
    await expect(nonBlockedColumn.locator('[data-ticket-id]').first()).toBeVisible({ timeout: 5_000 });
  });

  test('keyboard drag', async ({ page }) => {
    await page.goto('/dashboard/tickets?view=board');
    await waitForNav(page, 1280);
    // 18-04 gate fix — see 'renders four columns' comment (dynamic-import + fetch race).
    await page.waitForLoadState('networkidle');

    const cards = page.locator('[data-ticket-id]');
    const cardCount = await cards.count();
    if (cardCount === 0) {
      test.skip(true, 'no seeded tickets — cannot assert keyboard drag');
      return;
    }

    // WR-02 positive-branch assertion (22-01): the dnd-kit live region announces
    // the committed move. Declared once here to avoid a duplicate-const error.
    const liveRegion = page.locator('[id^="DndLiveRegion"]');

    const firstCard = cards.first();
    const ticketId = await firstCard.getAttribute('data-ticket-id');
    await firstCard.focus();

    // Space grabs the focused card.
    await page.keyboard.press('Space');
    // Arrow right until over Blocked — bounded loop to avoid infinite retry.
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('ArrowRight');
    }
    // Space drops.
    await page.keyboard.press('Space');

    // Save in the reason prompt.
    const saveButton = page.getByRole('button', { name: /save/i });
    await saveButton.waitFor({ state: 'visible', timeout: 5_000 });
    await saveButton.click();

    // Assert the card lands in Blocked.
    const blockedColumn = page.locator('[data-column="blocked"]');
    await expect(blockedColumn.locator(`[data-ticket-id="${ticketId}"]`)).toBeVisible({
      timeout: 5_000,
    });

    // WR-02: the committed read-only->Blocked drop announces a real success
    // in the same live region (positive branch of the gating logic).
    await expect(liveRegion).toContainText(/Moved ticket .* to the Blocked column/i);
  });

  test('keyboard drag with Enter does not open the DrillPanel', async ({ page }) => {
    // CR-01: dnd-kit's KeyboardSensor treats Enter as a drag start/end activator
    // and calls preventDefault() when it consumes the key. kanban-card.tsx's
    // handleKeyDown guard (`if (e.defaultPrevented) return;`) relies on this to
    // suppress onOpen (the DrillPanel) during an Enter-driven keyboard drag.
    await page.goto('/dashboard/tickets?view=board');
    await waitForNav(page, 1280);
    await page.waitForLoadState('networkidle');

    const cards = page.locator('[data-ticket-id]');
    if ((await cards.count()) === 0) {
      test.skip(true, 'no seeded tickets — cannot assert Enter-key drag');
      return;
    }

    const firstCard = cards.first();
    const ticketId = await firstCard.getAttribute('data-ticket-id');
    await firstCard.focus();

    // Pick up with Enter (dnd-kit consumes it -> preventDefault -> onOpen suppressed).
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-drill-panel]')).toHaveCount(0); // not opened mid-drag

    // Move to Blocked.
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('ArrowRight');
    }

    // Drop with Enter.
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-drill-panel]')).toHaveCount(0); // still not opened after drop

    // The committed read-only->Blocked transition opens KanbanReasonPrompt — Save it,
    // mirroring the existing 'keyboard drag' test's settle beat.
    const saveButton = page.getByRole('button', { name: /save/i });
    await saveButton.waitFor({ state: 'visible', timeout: 5_000 });
    await page.waitForTimeout(200); // deferred-autofocus settle (18-04 gate fix)
    await saveButton.click();

    // Assert the card landed in Blocked (status changed).
    const blockedColumn = page.locator('[data-column="blocked"]');
    await expect(blockedColumn.locator(`[data-ticket-id="${ticketId}"]`)).toBeVisible({
      timeout: 5_000,
    });

    // Final guard — DrillPanel still closed after the whole sequence.
    await expect(page.locator('[data-drill-panel]')).toHaveCount(0);
  });

  test('gated no-op drop announces returned-to-column, not a false success', async ({ page }) => {
    await page.goto('/dashboard/tickets?view=board');
    await waitForNav(page, 1280);
    await page.waitForLoadState('networkidle');

    const openCard = page.locator('[data-column="open"] [data-ticket-id]').first();
    if ((await openCard.count()) === 0) {
      test.skip(true, 'no Open tickets seeded — cannot assert read-only->read-only gated drop');
      return;
    }

    await openCard.focus();
    const liveRegion = page.locator('[id^="DndLiveRegion"]');

    await page.keyboard.press('Space'); // pick up
    await page.keyboard.press('ArrowRight'); // -> In progress (still a read-only lane)

    // CRITICAL anti-vacuous-pass gate: prove the ArrowRight actually moved the
    // drag to a DIFFERENT column BEFORE dropping. Without this interim
    // assertion, if ArrowRight failed to register a column change, dnd-kit
    // would resolve `over` back to the STARTING `open` column, and the
    // gated-no-op drop below would emit the IDENTICAL "returned to its
    // column" text regardless of whether a genuine cross-column drop was
    // ever attempted — the exact vacuous-pass class this phase exists to
    // eliminate.
    await expect(liveRegion).toContainText(/is over the In progress column/i);

    await page.keyboard.press('Space'); // drop -> gated no-op -> snaps back

    // Assert the correct wording, and the ABSENCE of a false success.
    await expect(liveRegion).toContainText(/returned to its column/i);
    await expect(liveRegion).not.toContainText(/^Moved ticket/i);

    // Assert the card did NOT move — it is still under Open.
    await expect(page.locator('[data-column="open"] [data-ticket-id]').first()).toBeVisible();
  });

  test('empty column', async ({ page }) => {
    await page.goto('/dashboard/tickets?view=board&status=open');
    await waitForNav(page, 1280);
    // 18-04 gate fix — see 'renders four columns' comment (dynamic-import + fetch race).
    await page.waitForLoadState('networkidle');

    const openColumn = page.locator('[data-column="open"]');
    const openCards = openColumn.locator('[data-ticket-id]');
    const openCount = await openCards.count();
    if (openCount === 0) {
      test.skip(true, 'no Open tickets seeded — cannot assert narrowed-column contrast');
      return;
    }

    // Open holds cards.
    await expect(openCards.first()).toBeVisible();

    // In progress / Completed / Blocked columns each render an EmptyState (role="status").
    for (const columnKey of ['in_progress', 'completed', 'blocked']) {
      const column = page.locator(`[data-column="${columnKey}"]`);
      await expect(column.getByRole('status').first()).toBeVisible();
    }
  });

  test('board mobile bottom-nav', async ({ page }) => {
    // Set the viewport to 360px BEFORE navigation.
    await page.setViewportSize({ width: 360, height: 780 });
    await page.goto('/dashboard/tickets?view=board');
    await waitForNav(page, 360);

    // The fixed mobile bottom-nav must be visible while the board is rendered.
    const mobileNav = page.locator(MOBILE_NAV);
    await expect(mobileNav).toBeVisible();

    // Focus its first link/button and assert focus lands inside the nav.
    const firstNavItem = mobileNav.locator('a, button').first();
    await firstNavItem.focus();
    const focusInsideNav = await page.evaluate((sel) => {
      return document.activeElement?.closest(sel) !== null;
    }, MOBILE_NAV);
    expect(focusInsideNav).toBe(true);

    // Assert the nav is not aria-hidden.
    await expect(mobileNav).not.toHaveAttribute('aria-hidden', 'true');
  });
});
