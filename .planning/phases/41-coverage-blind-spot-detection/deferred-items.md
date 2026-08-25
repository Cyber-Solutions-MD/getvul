# Phase 41 — Deferred Items

Out-of-scope discoveries logged during execution, per the executor's scope-boundary
rule (pre-existing issues unrelated to the current task's changes are logged, not fixed).

## 41-01

- **Pre-existing frontend lint error (not introduced by 41-01):**
  `frontend/src/components/exceptions/approver-combobox.tsx:176` —
  `jsx-a11y/click-events-have-key-events` ("Visible, non-interactive elements with
  click handlers must have at least one keyboard listener"). Introduced in Phase 39
  (commit `8757fdd`, `feat(39-07): approver-combobox + grant/revoke mutation hooks +
  drill microcopy`), untouched by any 41-01 file. Causes `npm run lint` to exit 1
  tenant-repo-wide even though every 41-01 file (`coverage/page.tsx`,
  `coverage/microcopy.ts`, `use-blind-spot-assets.ts`, `keys.ts`, `nav-items.ts`,
  `e2e/routes.ts`) is lint-clean in isolation (verified: none appear in the lint
  output). Routed to a frontend a11y backlog item — not fixed here.
