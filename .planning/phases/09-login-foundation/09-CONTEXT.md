# Phase 9: `/login` + Foundation - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the redesigned `/login` screen end-to-end against the validated sunset / Wiz-inspired design system, and the foundation it sits on:

1. **Sunset CSS variable token system** vendored at `frontend/src/styles/sunset.css` and consumed via Tailwind 3.4 extends
2. **Dark + light theme architecture** swapped via `data-theme` attribute on `<html>` (only dark visually QA'd in this phase)
3. **Persistent shell scaffold** (sidebar 220px + topbar with ⌘K chip + bell + help + user chip) rendered behind every authenticated route via a `(authed)/layout.tsx` route group, ready for Phase 10 to consume
4. **First primitive set:** Button, Input, SsoButton, GradientText (plus shadcn-vendored DropdownMenu for the user chip and Form primitives for `/login`)

The phase deliberately sweeps the v1 frontend (deletes v1 HSL CSS vars, deletes the root-level route duplicates, strips per-page container wrappers under `app/dashboard/`) so the foundation lands clean rather than carrying a shim across the next 6 phases. Existing v1 dashboard pages stay v1-colored visually until each subsequent phase rebuilds them — accepted visual debt for a clean foundation.

**In scope:**
- New `frontend/src/styles/sunset.css` (vendored from skill `sources/themes/sunset.css`)
- Wholesale rewrite of `frontend/src/app/globals.css` (no `!important` anywhere)
- Rewrite of `frontend/tailwind.config.ts` (theme.extend → sunset tokens)
- Rewire `frontend/src/lib/theme.tsx` → `data-theme` attribute + FOUC-prevention blocking script
- Font setup via `next/font/google` (Inter + JetBrains Mono with CSS-variable wiring)
- New route group `frontend/src/app/(authed)/layout.tsx` containing `<AppShell>`
- Move existing `app/dashboard/*` page files under `(authed)` (canonical paths stay `/dashboard/...`)
- Delete the duplicate root-level route directories: `app/assets/`, `app/integrations/`, `app/settings/`, `app/tickets/`, `app/vulnerabilities/`
- Strip per-page container wrappers from existing `dashboard/*/page.tsx` files so the new shell owns layout
- shadcn-vendored `Button`, `Input`, `Form*`, `DropdownMenu` primitives in `components/ui/`, sunset-themed
- Hand-built `SsoButton`, `GradientText` primitives in `components/ui/`
- New `/login` page: split-screen sunset (gradient-mesh left panel with sketch copy + hard-coded sample CVE rows; dark form panel right with SSO-primary + email/password fallback)
- Dev-only `/dev/primitives` route showing all primitive states
- Vitest + Testing Library smoke + axe-core a11y tests per primitive
- Route-guard middleware redirecting unauthed users to `/login?next=<path>`

**Out of scope (other phases / future):**
- Mobile hamburger / bottom-nav / sidebar collapse (Phase 15 — UX-07-01/02)
- Working ⌘K command palette (UX-D-* future or whichever phase needs it first)
- Bell-icon notification fetching (lands when notifications surface is rebuilt)
- Light-theme visual polish (UX-D-03)
- Phase 10+ shell consumers (dashboard hero, stat strip, breadcrumbs)
- Backend changes to `/auth/login` / `/auth/forgot-password` / `/auth/reset-password` / SSO endpoints
- New auth capabilities (MFA, remember-me, SSO-only enforcement, account recovery beyond existing forgot/reset)
- Self-serve registration (deliberately removed — admin-seeded model)
- Storybook playground (explicit out-of-scope in REQUIREMENTS-v2.md)
- Backend rate-limit / OIDC-state changes (Phase 1 already shipped; no further work)

</domain>

<decisions>
## Implementation Decisions

### Token + theme plumbing

- **D-01:** Vendor `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` into `frontend/src/styles/sunset.css` and `@import` it from the top of `globals.css`. Token file remains a single source of truth that survives future skill updates as a diffable file.
- **D-02:** Theme switches via `data-theme="dark"` / `data-theme="light"` on `<html>` (per UX-F-02 spec wording). Rewire `frontend/src/lib/theme.tsx` to set the attribute on `document.documentElement`. Remove the `.dark` / `.light` class pattern entirely.
- **D-03:** Stay on Tailwind 3.4. `tailwind.config.ts` `theme.extend` references CSS variables via `var(--color-*)` so utilities like `bg-pink` / `text-violet` / `rounded-lg` / `shadow-card` resolve to sunset tokens. No Tailwind v4 upgrade in this milestone.
- **D-04:** Delete every v1 HSL CSS variable (`--background`, `--foreground`, `--card`, `--card-foreground`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`) from `globals.css` and `tailwind.config.ts`. Sweep every file in `frontend/src/` and replace utilities like `bg-background` / `text-foreground` / `bg-card` / `text-card-foreground` / `border-border` with sunset-token utilities (`bg-bg` / `text-text` / `bg-surface` / `text-text-muted` / `border-border`). v1-styled screens visually shift but don't break.
- **D-05:** The v1 deletion sweep covers **every frontend/src/ file** in phase 9, not just `/login` + shell. This is a deliberate scope expansion vs the PROJECT.md "first slice extracts the minimal token set it needs" framing — the planner must size phase 9 accordingly. Rationale: carrying a class-name shim across 6 phases creates more drag than ripping the bandage now; v1-colored screens between phases is tolerable interim state.
- **D-06:** Ship light-theme **architecture only** (`:root[data-theme="light"]` block in `globals.css` with credible token mappings). Visual polish deferred per UX-D-03; only dark is QA'd in phase 9. Theme toggle works in both directions for testing.
- **D-07:** Load Inter (`--font-sans`) and JetBrains Mono (`--font-mono`) via `next/font/google` in `app/layout.tsx` with `display: 'swap'`. Apply both `variable` class names to `<html>`. Verifies UX-01-04 success criterion (Network panel shows no FOIT).
- **D-08:** Vendor the **full sunset.css** in phase 9 — every token family (surfaces, borders, text, sunset accents, severity, status, SLA, providers, spacing, radii, shadows, motion, gradients). Phases 10–14 only consume; no per-phase token additions.
- **D-09:** Tailwind `theme.extend` covers `colors`, `spacing`, `borderRadius`, `boxShadow`, `fontFamily`, and `backgroundImage` (for `bg-gradient-sunset` + `bg-gradient-mesh`). Motion eases + durations consumed via arbitrary values (`transition-[var(--motion-fast)]`) where needed.
- **D-10:** Severity / status / SLA / provider tokens get Tailwind utility names too — `bg-severity-critical`, `text-status-open`, `bg-sla-overdue`, `bg-provider-jira`. Land in phase 9 even though no phase-9 primitive consumes them; phases 11–13 reuse without extra Tailwind config work.
- **D-11:** Global focus-visible style applied via `*:focus-visible { outline: 2px solid var(--color-violet); outline-offset: 2px; }` in `globals.css`. Violet is the system-wide focus accent across all primitives.
- **D-12:** `prefers-reduced-motion: reduce` honored globally via a `@media` rule in `globals.css` that zeroes animation + transition durations universally. The single `!important` exception in the codebase — user-pref override beats Tailwind. Phase 15 (UX-07-04) only verifies; phase 9 implements.
- **D-13:** Inline synchronous theme-bootstrap script in `<head>` reads `localStorage.theme` (or `prefers-color-scheme`) and sets `data-theme` on `<html>` before hydration. Eliminates dark/light flash on cold load. Phase 15 (UX-07-05) verifies; phase 9 implements.
- **D-14:** Pink-tinted text selection (`::selection { background: var(--color-pink); color: var(--color-text-inverse); }`) and sunset-tinted scrollbar (`scrollbar-color: var(--color-border-strong) var(--color-bg)` + webkit fallback for chromium browsers) defined in `globals.css`.
- **D-15:** All animation keyframes (`pulse-urgency`, `gradient-drift`, `skeleton-shimmer`, `cta-shine-sweep`) defined upfront in phase 9 `globals.css` next to the token block. Phase 9 only consumes `gradient-drift` (mesh hero) but the others are available for phases 10+ without further `globals.css` churn.
- **D-16:** No Tailwind plugins. Skip `@tailwindcss/forms` and `@tailwindcss/typography`. Input primitive styled from scratch against sunset tokens.
- **D-17:** Replace the entire current `globals.css` wholesale. New file structure: Tailwind directives → `@import './styles/sunset.css'` → `:root[data-theme="dark"]` block → `:root[data-theme="light"]` block → `*:focus-visible` → `::selection` + scrollbar → `@media (prefers-reduced-motion: reduce)` → `@keyframes` definitions. Verifies UX-F-02 success criterion `grep -c '!important' frontend/src/app/globals.css` returns 0 (with the single intentional exception inside the reduced-motion media query).

### Primitive build strategy

- **D-18:** Run `npx shadcn@latest init` to write `components.json`, alias config, `lib/utils.ts` with `cn()` helper. Then run `npx shadcn@latest add button input dropdown-menu form` to seed those primitives. Customize the generated files against sunset tokens. SsoButton + GradientText hand-built in the same `components/ui/` directory following the same shadcn conventions.
- **D-19:** Variant API uses `class-variance-authority` (CVA) + `clsx` + `tailwind-merge` — what `shadcn add button` generates. Add `class-variance-authority`, `clsx`, `tailwind-merge` to deps if shadcn init doesn't.
- **D-20:** `cn()` helper lives at `frontend/src/lib/utils.ts` with `export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))` composition. Conflicting Tailwind classes resolve to the last one.
- **D-21:** Form library is `react-hook-form` + `zod` + `@hookform/resolvers` + shadcn `Form` / `FormField` / `FormItem` / `FormLabel` / `FormControl` / `FormMessage` compound components. Sets the convention for every phase that ships a form (phase 14 settings, phase 13 ticket comments, etc.).
- **D-22:** `<GradientText>` is a React component (counts as a primitive per UX-F-04). Polymorphic via `as` prop (or Radix Slot if simpler). Applies `background: var(--gradient-sunset); background-clip: text; -webkit-text-fill-color: transparent;` inline.
- **D-23:** Button polymorphism via `asChild` (Radix Slot, `@radix-ui/react-slot` ≈ 1KB). Enables `<Button asChild><Link href="…">…</Link></Button>` for mode-switch links + future nav buttons.
- **D-24:** Button loading API: `loading: boolean` prop swaps children for a 14px sunset-tinted inline SVG spinner + sets `aria-busy` + `disabled`. Optional `loadingText: string` swaps the visible label (`<Button loading loadingText="Signing in…">Sign in</Button>`). No separate Spinner primitive in phase 9 — it'll land when skeleton patterns ship in phase 11.
- **D-25:** Icons from `lucide-react` (already a dep). Button accepts `leftIcon` / `rightIcon` as `ReactNode` props. Button handles gap spacing internally. Auto-sized to `14px` for primary/secondary, `16px` for icon-only variant.
- **D-26:** `<SsoButton provider="google" | "microsoft" />` — single component owns the provider mark, label ("Continue with Google" / "Continue with Microsoft"), and accessible name. Extensible if Okta SAML is added later via `provider="okta"`. Click handler invokes existing `useAuth().loginSSO(provider)`.
- **D-27:** `<Input>` is a single primitive. When `type="password"`, it renders a built-in eye-toggle suffix button with `aria-pressed` and "Show password" / "Hide password" labels. Single primitive covers email + password + text + url + search input needs across the milestone.
- **D-28:** Error state on `<Input>`: when its wrapping `<FormItem>` has an error, the input flips to `border-danger` + sets `aria-invalid="true"`; `<FormMessage>` renders the field-level message below in `text-danger` `text-xs`. Separately, an `<ErrorAlert>` block at the top of the form panel renders auth-level errors (server 401, network failure, SSO failure) using `bg-danger-soft` + `border-danger` + danger icon + sentence-case copy. Verifies UX-01-05.
- **D-29:** File naming follows shadcn defaults: kebab-case, flat. `components/ui/button.tsx`, `components/ui/input.tsx`, `components/ui/sso-button.tsx`, `components/ui/gradient-text.tsx`, `components/ui/dropdown-menu.tsx`, `components/ui/form.tsx`. Future `shadcn add` commands land cleanly.
- **D-30:** Each primitive ships with a Vitest + Testing Library `.test.tsx` that renders every state (default, hover via class assertion, focus-visible via focus event, disabled, loading where applicable, error where applicable) and runs `axe-core` against the rendered output. Frontend CI already runs Vitest.
- **D-31:** `frontend/src/app/dev/primitives/page.tsx` renders every primitive in every state on one page for visual QA. Route gated by `process.env.NODE_ENV !== 'production'` (returns `notFound()` in prod build). Doubles as living documentation.
- **D-32:** `or with email` divider is a one-off in `/login` markup — not a `<Divider>` primitive in phase 9. Promote later if a second consumer appears.

### Shell scaffold scope

- **D-33:** Move every authenticated route into a `(authed)` route group: `frontend/src/app/(authed)/dashboard/...`. The route-group `layout.tsx` renders `<AppShell>` once, wrapping every child page. `/login` and the root `/` page stay outside the group; `/login` uses its own split-screen layout.
- **D-34:** Canonical authenticated paths are `/dashboard/...`. Delete the duplicate root-level route directories: `app/assets/`, `app/integrations/`, `app/settings/`, `app/tickets/`, `app/vulnerabilities/`. Resolves the existing v1 dual-routing ambiguity in one pass.
- **D-35:** Nav items render with real `next/link` `<Link>` `href`s. Active state computed in `AppShell` via `usePathname()` with prefix matching (`pathname === item.href || pathname.startsWith(item.href + '/')`); the `/dashboard` root item uses exact match to avoid lighting up for every nested route. Count chips (`1,247` in sketch) render as `—` placeholders in phase 9 — wired to real data when phase 10's data layer lands.
- **D-36:** Sidebar item list and lucide-react icon mapping (matches app-shell.md verbatim):
  - **Triage** section: Dashboard (`Home`) / Vulnerabilities (`Bug`) / Assets (`Server`) / CSPM (`Cloud`)
  - **Workflow** section: Tickets (`Ticket`) / Connectors (`Plug`, route `/dashboard/integrations` — keep that path; the v1 directory is named `integrations` even though the nav label is `Connectors`)
  - Unlabeled bottom: Users (`Users`) / Settings (`Settings`)
- **D-37:** Topbar functionality in phase 9 is **visual scaffold only** except the user chip. Search-as-input field + `⌘K` kbd chip render but click does nothing. Bell icon + help icon render but click does nothing. The `⌘K` command palette, real notification fetch, and help link target are deferred to whichever later phase needs them first.
- **D-38:** User chip reads `user.email` from `useAuth()` and derives 2-letter initials. Click opens a `DropdownMenu` (`shadcn add dropdown-menu`) with the user's email at the top, a `DropdownMenuRadioGroup` for `Theme: Dark` / `Theme: Light` (with check marks on the active option), and a `Sign out` action. Sign out invokes `useAuth().logout()` (already routes to `/login`). Theme toggle writes to `localStorage` + flips `data-theme` on `<html>` via the existing `ThemeProvider`.
- **D-39:** Strip per-page outer wrappers from existing `dashboard/*/page.tsx` files (e.g. `<div className="min-h-screen bg-gray-950 …">…</div>` containers) so the new shell owns layout chrome. Pages keep their v1 inner content + colors; only the outer-shell duplication is removed. Phase 10+ replace the inner content one screen at a time.
- **D-40:** Brand mark in sidebar wraps a `<Link href="/dashboard">`. Breadcrumbs deferred to phase 12 (first detail page); no breadcrumb primitive in phase 9.
- **D-41:** Mobile collapse handling in phase 9 is desktop-defensive only. Sidebar hides via `@media (max-width: 999px) { … }` so the layout doesn't horizontally scroll on mobile. No hamburger entry point + no bottom-nav — those land in phase 15 per UX-07-01/02. Phase 9 verifies that `/login` and the shell don't crash on 360px viewports, even if the authed shell isn't navigable there yet.

### Login content + modes

- **D-42:** Remove the self-serve `register` mode entirely from `/login`. Single-tenant-per-VM product model (install.sh seeds admin; new users come via admin + OIDC). Delete the `register` JSX branch and the `register` call site from `useAuth()` consumers in `/login`. Backend `/auth/register` route stays as-is (not in phase 9 scope to remove server-side).
- **D-43:** `/login` keeps its current `mode` state machine: `'login' | 'forgot' | 'reset'`. URL `/login?reset=TOKEN` deep-links into `reset` mode and pre-fills the token. SSO buttons + divider hide on `forgot` and `reset` modes (UX-01-04). Headings per mode: `Sign in` / `Reset your password` / `Set a new password`.
- **D-44:** Hard-code the product-peek vuln rows directly in the `/login` page JSX. Sample content: 3–4 rows of real public CVE references (xz-utils CVE-2024-3094, log4shell CVE-2021-44228, etc.) with severity color + asset hostname + CVSS score. Matches the 001-login-sunset sketch's visual fidelity without needing a data layer.
- **D-45:** Left-panel marketing copy ports **verbatim** from `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` (variant A — the winner). Tagline: `See your security posture without opening another tool.` (with `without opening another tool.` as the gradient-accent text). Sub-line: `One dashboard. Every scanner. Real ownership. Tickets out, fewer meetings.` Form panel subtitle: `Welcome back. Use your work account.`
- **D-46:** SSO button copy verbatim from sketch: `Continue with Google` / `Continue with Microsoft`. Sentence case. Matches Google's OAuth brand guidelines.
- **D-47:** Mode-switch links in `/login`:
  - Login mode: right-aligned `Forgot password?` link below the password input → switches to `forgot` mode (no route change)
  - Forgot mode: `Back to sign in` link below the email input → switches back to `login` mode
  - Reset mode: entered only via `?reset=TOKEN` deep link. No in-app mode-switch link to reach reset (token-gated).
- **D-48:** Inputs use `autoFocus` on the first field per mode (email in login + forgot; new password in reset) and proper `autoComplete` attrs: `email` for email fields, `current-password` for the login password, `new-password` for the reset new-password field. Token paste field uses `autoComplete="off"`.
- **D-49:** Login 401 surfaces a generic error: `Email or password is incorrect.` Pass through other 4xx backend messages (e.g. `Account locked`, `SSO required for this account`). Never differentiate `user not found` vs `wrong password` — anti-user-enumeration policy.
- **D-50:** Route-guard logic: when an unauthed user hits a protected route, `useAuth()` (or a route group `layout.tsx` server check) redirects to `/login?next=<encoded-original-path>`. On successful login, `/login` reads `searchParams.get('next')` and `router.replace(next ?? '/dashboard')`. SSO callback path inherits the same behavior via existing localStorage state handling in `useAuth().loginSSO`.
- **D-51:** SSO failure (e.g. `/auth/login/google` returns 5xx or network fails) renders in the same form-level `<ErrorAlert>` bar above SSO row: `Sign-in with Google is temporarily unavailable. Try email instead.` Replaces the current silent-catch behaviour in `useAuth().loginSSO`.
- **D-52:** Per-mode submit button copy (Button `children` + `loadingText`):
  - Login: `Sign in` / loading `Signing in…`
  - Forgot: `Send reset link` / loading `Sending…`
  - Reset: `Set new password` / loading `Updating…`
- **D-53:** Form validation runs on submit only (`mode: 'onSubmit'` in react-hook-form). Zod schemas: login = `{ email: z.string().email(), password: z.string().min(1) }`; forgot = `{ email: z.string().email() }`; reset = `{ token: z.string().min(1), newPassword: z.string().min(8) }`. Server response remains the source of truth for credential validity.

### Claude's Discretion

- Exact spacing of the sample-CVE rows on the left panel (pull from the sketch HTML for fidelity but adjust if cramped)
- Tailwind `colors` extend naming for severity / status / SLA tokens (e.g. `severity-critical` vs `severity.critical` — pick the convention that reads best with `bg-` / `text-` prefixes)
- Whether the FOUC-prevention script lives inline in `app/layout.tsx` or as a `<Script strategy="beforeInteractive">` component (whichever Next 15 supports cleanly)
- Test fixture layout — colocated `.test.tsx` next to each primitive vs. `__tests__/` subdirectory
- Whether `lib/auth.tsx` `loginSSO` error handling is updated in-place or a small wrapper component owns the error surface
- The specific CVE entries on the left panel (xz-utils / log4shell / spring4shell etc. — pick recognisable public CVEs that read credible at a glance)
- Whether the route-guard redirect lives in middleware (`middleware.ts`), the `(authed)/layout.tsx` server component, or in client-side `useAuth()` — pick the cleanest Next 15 App Router option
- Whether to ship a small `<EmailSentConfirmation>` view inside forgot mode after submit (current v1 has one) or just toast + reset the form

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design contract (mandatory reads)
- `.claude/skills/sketch-findings-getvul/SKILL.md` — Overall direction, palette, typography, layout patterns, voice
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — Color tokens, severity colors, typography scale, spacing, radii, shadows, motion, reduced-motion contract, anti-list (D-01..D-17 all derive from this)
- `.claude/skills/sketch-findings-getvul/references/app-shell.md` — Sidebar (220px, 3 sections, brand mark, gradient active strip, counts), topbar (search + ⌘K + bell + help + user chip), page-head conventions (D-33..D-41)
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — Split-screen login + authed shell layout decisions
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — Severity / SLA / status / provider tokens that ship in phase 9 even though no phase-9 primitive consumes them (D-10)
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — Loading / empty / error patterns (phase 9 only consumes the error-alert pattern for /login auth failures; the full library lands in phase 11)
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — Reference for hover lifts, focus-visible, gradient CTA behavior
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — Sentence case, no "Please", error specificity rules. Applies to every label, error, and tooltip in phase 9.

### Validated sketch (visual reference)
- `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` — Variant A is the winner. Marketing copy + sample CVE rows + form chrome lift verbatim from here (D-44, D-45, D-46).
- `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` — The token file vendored into `frontend/src/styles/sunset.css` in D-01.

### Project planning
- `.planning/PROJECT.md` — Stack constraints, anti-pattern guard ("no foundation-only phase"), single-tenant-per-VM model (justifies removing self-serve registration, D-42)
- `.planning/REQUIREMENTS-v2.md` — UX-01-01..05 (login requirements), UX-F-01..04 (foundation requirements embedded in phase 9), Out of Scope notes (`shadcn/ui as vendored seed` is locked; no Storybook; no real provider logos)
- `.planning/ROADMAP.md` §"Phase 9: `/login` + Foundation" — All 7 success criteria. Note: "no foundation-only phase" anti-pattern guard.
- `.planning/STATE.md` — Workflow note about v2-01 rolled-back attempt; phase numbering continuity (9–15)

### Code being modified / replaced (mandatory reads for planner)
- `frontend/src/app/layout.tsx` — Root layout. Rewire to load `next/font/google` Inter + JetBrains Mono with CSS-variable wiring; replace `className="dark"` with `data-theme="dark"` (set by bootstrap script); inline the FOUC-prevention `<script>`.
- `frontend/src/app/login/page.tsx` — Full rewrite against split-screen sunset; remove `register` mode (D-42); keep `useAuth()` integration intact.
- `frontend/src/app/globals.css` — Full rewrite per D-17. Verifies `grep -c '!important' frontend/src/app/globals.css` returns 0 except inside `@media (prefers-reduced-motion: reduce)`.
- `frontend/tailwind.config.ts` — Full rewrite of `theme.extend` per D-09 + D-10. No `colors.background = 'hsl(var(--background))'` pattern survives.
- `frontend/src/lib/theme.tsx` — Rewire to `data-theme` attribute (D-02). Existing API surface for `useTheme()` can stay; implementation changes.
- `frontend/src/lib/auth.tsx` — Largely unchanged. Update `loginSSO` to surface errors instead of silent catch (D-51); the route-guard `useEffect`/middleware honors `?next` (D-50).
- `frontend/src/app/dashboard/layout.tsx` — Existing dashboard layout file. Move/merge into `(authed)/layout.tsx` as the new shell owner.
- `frontend/src/app/dashboard/*/page.tsx` (every existing dashboard subroute) — Strip outer-shell wrappers per D-39.

### Code to delete in phase 9
- `frontend/src/app/assets/` (and any subroutes) — duplicate of `dashboard/assets`; canonical path is `/dashboard/assets` per D-34
- `frontend/src/app/integrations/` — duplicate of `dashboard/integrations`
- `frontend/src/app/settings/` — duplicate of `dashboard/settings`
- `frontend/src/app/tickets/` — duplicate of `dashboard/tickets`
- `frontend/src/app/vulnerabilities/` — duplicate of `dashboard/vulnerabilities`

### New files in phase 9 (planner enumerates concrete list)
- `frontend/src/styles/sunset.css` (vendored)
- `frontend/src/app/(authed)/layout.tsx` (shell consumer)
- `frontend/src/components/shell/AppShell.tsx`, `Sidebar.tsx`, `Topbar.tsx`, `UserChip.tsx` (or whatever component breakdown the planner picks)
- `frontend/src/components/ui/{button,input,form,dropdown-menu,sso-button,gradient-text}.tsx` (shadcn-vendored + hand-built)
- `frontend/src/components/ui/{button,input,sso-button,gradient-text}.test.tsx` (Vitest + RTL + axe per D-30)
- `frontend/src/lib/utils.ts` (`cn()` helper)
- `frontend/src/app/dev/primitives/page.tsx` (dev-only state matrix per D-31)
- `frontend/middleware.ts` (route-guard with `?next` per D-50) — if planner picks middleware over `(authed)/layout.tsx` server-side check
- `components.json` (shadcn config; written by `shadcn init`)

### Dependencies to add
- `class-variance-authority`
- `clsx`
- `tailwind-merge`
- `tailwindcss-animate` — only if shadcn init writes it as a default; otherwise skip per D-16
- `lucide-react` — already in deps per PROJECT.md, confirm version
- `@radix-ui/react-slot` (Button `asChild` per D-23)
- `@radix-ui/react-dropdown-menu` (user-chip menu per D-38)
- `@radix-ui/react-label` (shadcn Form internals)
- `react-hook-form`
- `@hookform/resolvers`
- `zod`
- `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `axe-core`, `vitest-axe` (or `jest-axe` equivalent) — if not already present in frontend dev deps
- (No `@tailwindcss/forms`, `@tailwindcss/typography`, Tremor / Chakra / MUI per D-16 + REQUIREMENTS-v2.md out-of-scope)

### Backend — NOT modified in phase 9
- `backend/app/auth/router.py` (login, forgot-password, reset-password, OIDC endpoints) — frontend consumes as-is
- `backend/app/auth/password.py` — reset token plumbing unchanged
- `backend/app/auth/oidc.py` — SSO unchanged

### No external ADRs
This project does not maintain a formal `docs/decisions/` directory. The Implementation Decisions above (D-01..D-53) ARE the ADR for this phase. The sketch-findings-getvul skill is the design ADR.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`useAuth()` from `frontend/src/lib/auth.tsx`** — Provides `user`, `loading`, `login`, `register`, `loginSSO`, `logout`, `token`. New `/login` consumes verbatim except `register` (removed per D-42). Same hook backs the route-guard redirect (D-50) and the user-chip dropdown sign-out (D-38).
- **`useTheme()` from `frontend/src/lib/theme.tsx`** — API stays; implementation flips to `data-theme` attribute. Theme-toggle radio group in the user-chip dropdown consumes it.
- **`lucide-react`** — Already a project dep (per PROJECT.md). Provides `Home`, `Bug`, `Server`, `Cloud`, `Ticket`, `Plug`, `Users`, `Settings`, `Bell`, `Search`, `HelpCircle`, `LogOut`, `Eye`, `EyeOff`, `Check`, `ChevronDown` for phase 9.
- **`@/` import alias** — Already configured in `tsconfig.json`. Use throughout new files.

### Established Patterns
- **`"use client";` directive top of every interactive page** — `/login`, dashboard pages, and shell components all need it. App Router defaults to server components.
- **`router.replace()` after auth state change** — Existing pattern in `useAuth()` and the v1 login page. New login + route-guard inherit it.
- **Tailwind utility-first composition** — Existing v1 code uses Tailwind classes throughout; phase 9 stays utility-first but against new tokens.
- **`process.env.NEXT_PUBLIC_*` env-var convention** — If route-guard needs env-aware behaviour, follow existing pattern.

### Integration Points
- **`app/layout.tsx`** — Root for everything. Phase 9 rewires `<html>` className → CSS-variable wiring + data-theme bootstrap. `<AuthProvider>` + `<ThemeProvider>` stay; only their implementations and the `<html>` props change.
- **Route group `(authed)`** — New layer between root layout and dashboard pages. The route-group folder name is wrapped in parens so it doesn't appear in URLs (`/dashboard/...` paths unchanged).
- **Middleware vs server layout for route guard** — Next 15 App Router supports both. Middleware (`middleware.ts`) runs on every request and can redirect with `?next=` cheaply; server-side check in `(authed)/layout.tsx` is simpler but doesn't catch unauthed access before SSR. Pick whichever the planner finds cleanest (Claude's discretion).
- **Backend SSO callback URLs** — Existing backend `/auth/callback/{provider}` redirects back to frontend after OIDC. No phase-9 changes to this contract; SSO error UX (D-51) wraps existing `useAuth().loginSSO`.

### Frontend file inventory (snapshot at phase start)
- `frontend/src/app/`
  - `assets/` — duplicate of `dashboard/assets`, **DELETE in phase 9**
  - `dashboard/` — canonical authed surface; **move into `(authed)/dashboard/`**
    - `layout.tsx` (existing, merge into `(authed)/layout.tsx`)
    - `page.tsx`, `assets/`, `connectors/`, `cspm/`, `settings/`, `tickets/`, `users/`, `vulnerabilities/` (existing pages, strip outer wrappers)
  - `integrations/`, `settings/`, `tickets/`, `vulnerabilities/` — **DELETE in phase 9** (duplicates)
  - `login/page.tsx` — **rewrite in phase 9**
  - `globals.css` — **rewrite in phase 9**
  - `layout.tsx` — **rewire** (fonts, data-theme bootstrap)
  - `page.tsx` (root) — likely a redirect to `/dashboard` or `/login`; verify and preserve
- `frontend/src/components/`
  - `dashboard/`, `layout/`, `tickets/`, `vulnerabilities/`, `ui/` — existing; ui/ may already contain v1 primitives that need replacing or removing
- `frontend/src/lib/`
  - `auth.tsx`, `theme.tsx` — modified per code-context above

</code_context>

<specifics>
## Specific Ideas

- The 001-login-sunset sketch's variant A is the winner. **Reproduce visually**, don't deviate stylistically. The sketch HTML at `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` is the visual reference of last resort.
- The "without opening another tool." accent text on the hero tagline uses the sunset gradient via `<GradientText>` (or the `gradient-text` utility). Verifies the GradientText primitive in the most visible context immediately.
- Sample peek-row CVEs should read credible to a security analyst: use real public KEVs (CVE-2024-3094 xz-utils, CVE-2021-44228 log4shell, CVE-2022-22965 spring4shell, CVE-2023-23397 outlook-ntlm-leak — pick whichever feel right). The hostname column shows mono lowercase fake hostnames like `prod-db-01`, `auth-api-02`.
- Reduced-motion handling: the gradient-mesh drift (`@keyframes gradient-drift` at 24s) is the loudest motion on `/login`; the global media-query rule kills it for `prefers-reduced-motion: reduce` users automatically — no per-component opt-out needed in phase 9.
- The user-chip dropdown is the **only** affordance in the new shell that has real interactivity in phase 9. Everything else is decorative. This is intentional — phase 9 establishes the shape; phases 10–14 fill in behaviors.
- The `(authed)` route group rename is a meaningful refactor — git mv every existing `app/dashboard/...` file under `app/(authed)/dashboard/...`. Plan it as a single atomic commit so blame stays clean.
- "Connectors" in the sidebar maps to the existing `/dashboard/integrations` route — keep the URL path (rename costs more than it saves), but the nav label reads "Connectors" per the sketch.

</specifics>

<deferred>
## Deferred Ideas

- **Working ⌘K command palette** — Topbar shows the kbd chip but no modal opens. Lands when first phase needs global search. Likely phase 11 (vulnerabilities) or a dedicated palette phase.
- **Bell-icon notification badge + dropdown** — Wire to existing `/api/v1/notifications` when notifications surface is rebuilt (phase 14 catch-all).
- **Mobile hamburger + bottom-nav** — Phase 15 (UX-07-01/02). Phase 9 keeps the layout from horizontal-scrolling on mobile but doesn't make it navigable.
- **Light-theme visual polish** — Architecture only in phase 9; full polish deferred per UX-D-03.
- **Breadcrumb primitive** — Deferred to phase 12 (first detail page).
- **Spinner primitive** — Phase 9 inlines a spinner inside Button. Promote to `<Spinner>` when phase 11's skeleton + loading states need it across screens.
- **Divider primitive** — One-off in `/login` markup. Promote when a second consumer appears.
- **Page-transition motion** — UX-D-06. Not in this milestone.
- **SSO-only enforcement / MFA / remember-me / account lockout UX** — Not currently in product scope; would be a future milestone.
- **`_reset_tokens` in-memory dict in backend** — Same anti-pattern as PROD-01-01 (in-process state); should move to Redis. Out of scope for v2.0 UI/UX milestone; add to backlog for v1.1+ backend hardening.
- **Self-serve registration UI** — Removed per D-42. Backend `/auth/register` endpoint stays (not removing server-side in phase 9).
- **Storybook playground** — Explicit out-of-scope per REQUIREMENTS-v2.md. `/dev/primitives` route covers the visual-QA need without the dep.
- **Settings page sidebar-of-categories pattern** — Phase 14 (UX-06-04). Phase 9 strips the v1 settings page wrapper but doesn't redesign the page itself.
- **Removing `frontend/src/app/dashboard/layout.tsx`** — Merge into `(authed)/layout.tsx` rather than keeping two layers.

</deferred>

---

*Phase: 09-login-foundation*
*Context gathered: 2026-05-12*
