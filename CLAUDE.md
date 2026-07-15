# GetVul — Project Instructions for Claude

## What this project is

GetVul is a vulnerability triage platform: a vuln-triage analyst opens one dashboard, sees the same CVE-on-host correlated across multiple scanners (Tenable, Qualys, Rapid7, AWS Inspector), identifies the asset's owner via IdP/MDM/HR, and ships a Jira/Asana ticket — without ever opening a scanner console.

## Active work

- **v2.2 Deferred UI Features** — 🚧 IN PROGRESS (opened 2026-07-15). Phases 16–19: light-theme completion, page transitions (View Transitions API), Tickets kanban (@dnd-kit), add-connector wizard. See `.planning/milestones/v2.2-ROADMAP.md`. Next: `/gsd-plan-phase 16`.
- **v1.0 Production Readiness** — ✅ SHIPPED (Phases 1–8, 2026-07-14). Backend hardening.
- **v2.0 UI/UX Redesign** — ✅ SHIPPED (Phases 9–15, 2026-06-30). Every authed screen on the sunset design system.
- **v2.1 Polish & Tech Debt** — ✅ SHIPPED (BL-01..05, 2026-07-15). Backlog cleanup; all phase VALIDATION.md now Nyquist-compliant.

See `.planning/ROADMAP.md` + `.planning/MILESTONES.md` for full history.

## Skills

### Sketch findings (auto-load when building UI)

When implementing any frontend code on this project — components, screens, primitives, design tokens, state handling, copy — **first read** the `sketch-findings-getvul` skill at `.claude/skills/sketch-findings-getvul/`. It captures 43 validated design decisions from the v2.0 redesign sketches (palette, typography, layouts, severity / status / SLA visual language, state patterns, copy voice).

Specifically:
- `references/foundation.md` — color tokens, typography, spacing, motion
- `references/app-shell.md` — sidebar + topbar persistent chrome
- `references/page-layouts.md` — hero / list / detail patterns
- `references/state-patterns.md` — loading / empty / error (mandatory in production)
- `references/visual-language.md` — severity / status / SLA / providers / CTA
- `references/interaction-patterns.md` — drill-down panel / chip bar / bulk bar / timeline
- `references/copy-voice.md` — tone and microcopy rules

If a UI decision conflicts with these references, the references win. If a reference appears incomplete for an edge case, follow the spirit (see "what NOT to do" sections in each reference) and flag the gap rather than inventing.

## Codebase conventions

- Frontend: Next.js 15 App Router + React 19 + TypeScript 5.5 + Tailwind 3.4 (v2.0 will rewire Tailwind to consume CSS variables from `sketch-findings-getvul`'s `foundation.md`).
- Backend: FastAPI + Postgres + Redis (Phase 1 of v1.0 moved state from in-process dicts to Redis).
- Deployment: Docker Compose with nginx in front of `frontend` and `backend` services.
- Auth: OIDC (Google + Microsoft/Azure) + email/password. Session state in Redis.

## What NOT to do

- Don't substitute fonts (Inter + JetBrains Mono are locked per design system)
- Don't pick hex colors freehand — use the CSS variables from `foundation.md`
- Don't ship a screen without empty/loading/error states (it was the v1 audit's top pain point)
- Don't use Tailwind admin-template patterns (the redesign explicitly avoids that energy)
- Don't compose generic SaaS copy ("Welcome!", "Please...", "Click here") — see `copy-voice.md`
