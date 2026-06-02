# Phase 14: Remaining Screens — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 14-remaining-screens
**Areas discussed:** Connector card identity, Settings categories reality, Users screen scope, CSPM finding interaction, Settings save model, Connector credential editing, CSPM bulk + finding cards, Settings RBAC gating, Connectors grouping, Audit-log category UX, Profile self-edit scope, Connector health surfacing, Connector delete/disable safety, SAML/OIDC toggle UX, CSPM trends chart, Plan sequencing, Notifications pane structure, Settings mobile, Connector deep-links

---

## Connector card identity

| Option | Description | Selected |
|--------|-------------|----------|
| Gradient tokens for all 14 | Brand-tinted `--gradient-provider-*` per provider; ProviderMark reads var() | ✓ |
| Category-colored marks | 4 category gradients + letter glyph | |
| Neutral glyph fallback | 3 brand gradients + neutral tiles for the rest | |

**User's choice:** Gradient tokens for all 14 → D-CONN-01

| Option | Description | Selected |
|--------|-------------|----------|
| Functional, unstyled-wizard | Add/edit/test/sync/delete stay wired; deferred wizard = polish only | ✓ |
| Modal shell, links out | Thin add entry point, rebuilt edit/test/sync/delete | |
| Non-functional placeholder | No create capability this phase | |

**User's choice:** Functional, unstyled-wizard → D-CONN-02

---

## Settings categories reality

| Option | Description | Selected |
|--------|-------------|----------|
| Coming-soon placeholder | Keep API-tokens category, EmptyState, no backend | ✓ |
| Drop the category | Ship 5 categories | |
| Verify backend deeper first | Research before deciding | |

**User's choice:** Coming-soon placeholder → D-SET-02

| Option | Description | Selected |
|--------|-------------|----------|
| Workspace category | Login-account/RBAC mgmt under Workspace; /users stays directory | ✓ |
| Lives on /dashboard/users | Account mgmt on the users screen | |
| Keep a Users settings category | 7th category mirroring v1 | |

**User's choice:** Workspace category → D-SET-03

---

## Users screen scope

| Option | Description | Selected |
|--------|-------------|----------|
| Directory stays, accounts in Settings | /users = people directory; accounts in Settings>Workspace | ✓ |
| Users = accounts, drop dir from Settings | /users = login-accounts admin (reverses Area-2) | |
| Both on /users (two tabs) | Accounts + Directory tabs on /users | |

**User's choice:** Directory stays, accounts in Settings → D-USR-01

| Option | Description | Selected |
|--------|-------------|----------|
| Export-only bulk bar | Selection + Export CSV only | ✓ |
| No bulk bar on directory | Read/drill surface only | |
| Bulk bar on Settings accounts | RBAC bulk on the accounts list | |

**User's choice:** Export-only bulk bar → D-USR-02

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Groups, rebuild it | Directory + Groups segmented toggle | ✓ |
| Directory only, defer Groups | Drop Groups for now | |

**User's choice:** Keep Groups, rebuild it → D-USR-03

---

## CSPM finding interaction

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse generalized DrillPanel | idKey='finding' content slot | ✓ |
| CSPM-specific side panel | Dedicated panel chrome | |
| Route to detail page | /cspm/[id] two-column route | |

**User's choice:** Reuse generalized DrillPanel → D-CSPM-01

| Option | Description | Selected |
|--------|-------------|----------|
| Cloud segmented control + frameworks rail | Segmented control + frameworks strip + cards | ✓ |
| Cloud as a chip-bar axis | Cloud folded into ChipBar | |
| Frameworks-first sidebar | Two-column frameworks rail left | |

**User's choice:** Cloud segmented control + frameworks rail → D-CSPM-02

---

## Settings save model

| Option | Description | Selected |
|--------|-------------|----------|
| Per-category sticky save bar | Dirty-state + unsaved guard | ✓ |
| Autosave on blur | Field-level autosave | |
| Single page-level save | One save for whole screen | |

**User's choice:** Per-category sticky save bar → D-SET-04

---

## Connector credential editing

| Option | Description | Selected |
|--------|-------------|----------|
| Masked + sentinel passthrough | Untouched fields send sentinel; mirrors SMTP contract | ✓ |
| Always re-enter on edit | Re-enter all secrets | |
| Edit metadata only, separate rotate | Split secret rotation | |

**User's choice:** Masked + sentinel passthrough → D-CONN-04

---

## CSPM bulk + finding cards

| Option | Description | Selected |
|--------|-------------|----------|
| Bulk resolve/ignore + rich cards | BulkActionBar + full finding cards | ✓ |
| Bulk status only, compact cards | Leaner cards | |
| No bulk, per-row status in drill | Single-finding status only | |

**User's choice:** Bulk resolve/ignore + rich cards → D-CSPM-03

---

## Settings RBAC gating

| Option | Description | Selected |
|--------|-------------|----------|
| Hide categories below your role | Sidebar lists only accessible categories | ✓ |
| Show all, disabled with explainer | Locked panes with role explainer | |
| Show all, 403 empty-state on click | Clickable into a 403 wall | |

**User's choice:** Hide categories below your role → D-SET-05

---

## Connectors grouping

| Option | Description | Selected |
|--------|-------------|----------|
| Category-sectioned grid | v1 category sections retained | ✓ |
| Flat grid + category chip-filter | One grid + chip filter | |
| Category sections + chip-filter | Both | |

**User's choice:** Category-sectioned grid → D-CONN-03

---

## Profile self-edit scope

| Option | Description | Selected |
|--------|-------------|----------|
| Identity view + password change | /auth/me read + /change-password | ✓ |
| Add client-side theme/prefs | + local-only preferences | |
| Push for display-name editing | Needs backend (out of scope) | |

**User's choice:** Identity view + password change → D-SET-06

---

## Audit-log category UX

| Option | Description | Selected |
|--------|-------------|----------|
| Filtered + paginated log table | action/resource_type/actor filters + pagination | ✓ |
| Paginated table, search-only | Single search box | |
| Recent-events feed | Compact feed + load more | |

**User's choice:** Filtered + paginated log table → D-SET-09

---

## Connector health surfacing

| Option | Description | Selected |
|--------|-------------|----------|
| Status pill (4 states) + reuse strip | ok/failed/never/running + PerSourceStatusStrip | ✓ |
| Status pill only | No live strip | |
| Minimal text status | Plain text | |

**User's choice:** Status pill (4 states) + reuse strip → D-CONN-05

---

## Connector delete/disable safety

| Option | Description | Selected |
|--------|-------------|----------|
| Disable toggle + guarded delete | is_enabled toggle + ConfirmModal delete (Owner/Admin) | ✓ |
| Delete-only, strong confirm | No disable toggle | |
| Disable-only, no delete | No delete this phase | |

**User's choice:** Disable toggle + guarded delete → D-CONN-06

---

## SAML/OIDC toggle UX

| Option | Description | Selected |
|--------|-------------|----------|
| Provider-first, gated enforce toggle | Picker first; enforce disabled until IdP set | ✓ |
| Free toggle, handle 400 | Always show toggle, surface errors | |
| Wizard-style step gate | Two-step configure→enforce | |

**User's choice:** Provider-first, gated enforce toggle → D-SET-07

---

## CSPM trends chart

| Option | Description | Selected |
|--------|-------------|----------|
| Defer trends per UX-D-05 | Cards + frameworks + drill, no chart | ✓ |
| Include a simple trend strip | One lightweight recharts viz | |
| Compliance pass-rate summary only | Static stat/ring, no time-series | |

**User's choice:** Defer trends per UX-D-05 → D-CSPM-04

---

## Plan sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| Foundation-first, then 4 screens | Wave 0 shared tokens/primitives, then parallelizable screens | ✓ |
| Per-screen vertical slices | Tokens land with first screen needing them | |
| Leave entirely to planner | No preference captured | |

**User's choice:** Foundation-first, then 4 screens → D-SEQ-01

---

## Notifications pane structure

| Option | Description | Selected |
|--------|-------------|----------|
| Three labeled sub-sections | SMTP / Syslog / Alerts cards in one pane | ✓ |
| Sub-tabs within the pane | Nested tabs (avoided) | |
| Split into separate categories | Promote to own categories | |

**User's choice:** Three labeled sub-sections → D-SET-08

---

## Settings mobile

| Option | Description | Selected |
|--------|-------------|----------|
| Category list → pane drill | Master-detail drill with back affordance | ✓ |
| Top select dropdown | Category select above pane | |
| Defer to Phase 15 | Desktop only | |

**User's choice:** Category list → pane drill → D-SET-10

---

## Connector deep-links

| Option | Description | Selected |
|--------|-------------|----------|
| Category empty-states + honor inbound deep-links | Per-category EmptyState + ?provider= handling | ✓ |
| Empty-states only, no deep-link handling | Ignore inbound query | |
| Global empty-state only | Single page-level empty | |

**User's choice:** Category empty-states + honor inbound deep-links → D-CONN-07

---

## Claude's Discretion

- Exact primitive APIs/file placement; complementary connector chip-filter; alert-category field shape; skeleton/shimmer specifics.

## Deferred Ideas

- Full connector onboarding wizard (UX-D-02); API token issuance; CSPM trend charts (UX-D-05); self-serve display-name editing; formal mobile/a11y/perf audit (Phase 15).
