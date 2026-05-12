# Phase 9: `/login` + Foundation - Research

**Researched:** 2026-05-12
**Domain:** Next.js 15 App Router redesign — `/login` vertical slice + sunset design-system foundation (tokens, theme, shell, primitives) on an existing React 19 + Tailwind 3.4 codebase
**Confidence:** HIGH (codebase, decisions, design contract, and library versions all directly inspected)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Token + theme plumbing**

- **D-01** Vendor `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` into `frontend/src/styles/sunset.css` and `@import` it from the top of `globals.css`. Token file remains a single source of truth that survives future skill updates as a diffable file.
- **D-02** Theme switches via `data-theme="dark"` / `data-theme="light"` on `<html>` (per UX-F-02 spec wording). Rewire `frontend/src/lib/theme.tsx` to set the attribute on `document.documentElement`. Remove the `.dark` / `.light` class pattern entirely.
- **D-03** Stay on Tailwind 3.4. `tailwind.config.ts` `theme.extend` references CSS variables via `var(--color-*)` so utilities like `bg-pink` / `text-violet` / `rounded-lg` / `shadow-card` resolve to sunset tokens. No Tailwind v4 upgrade in this milestone.
- **D-04** Delete every v1 HSL CSS variable from `globals.css` and `tailwind.config.ts`. Sweep every file in `frontend/src/` and replace utilities like `bg-background` / `text-foreground` / `bg-card` / `text-card-foreground` / `border-border` with sunset-token utilities.
- **D-05** The v1 deletion sweep covers **every frontend/src/ file** in phase 9, not just `/login` + shell. Planner must size accordingly.
- **D-06** Ship light-theme **architecture only**. Visual polish deferred. Theme toggle works in both directions for testing.
- **D-07** Load Inter (`--font-sans`) and JetBrains Mono (`--font-mono`) via `next/font/google` in `app/layout.tsx` with `display: 'swap'`. Apply both `variable` class names to `<html>`.
- **D-08** Vendor the **full sunset.css** in phase 9 — every token family. Phases 10–14 only consume.
- **D-09** Tailwind `theme.extend` covers `colors`, `spacing`, `borderRadius`, `boxShadow`, `fontFamily`, and `backgroundImage`. Motion eases + durations consumed via arbitrary values.
- **D-10** Severity / status / SLA / provider tokens get Tailwind utility names too (`bg-severity-critical`, `text-status-open`, `bg-sla-overdue`, `bg-provider-jira`). Land in phase 9.
- **D-11** Global focus-visible: `*:focus-visible { outline: 2px solid var(--color-violet); outline-offset: 2px; }` in `globals.css`.
- **D-12** `prefers-reduced-motion: reduce` honored globally via `@media` rule. The single `!important` exception in the codebase — user-pref override beats Tailwind.
- **D-13** Inline synchronous theme-bootstrap script in `<head>` reads `localStorage.theme` (or `prefers-color-scheme`) and sets `data-theme` on `<html>` before hydration.
- **D-14** Pink-tinted text selection + sunset-tinted scrollbar in `globals.css`.
- **D-15** All animation keyframes (`pulse-urgency`, `gradient-drift`, `skeleton-shimmer`, `cta-shine-sweep`) defined upfront in phase 9 `globals.css`.
- **D-16** No Tailwind plugins. Skip `@tailwindcss/forms` and `@tailwindcss/typography`. Input primitive styled from scratch.
- **D-17** Replace entire current `globals.css` wholesale. New file structure: Tailwind directives → `@import './styles/sunset.css'` → `:root[data-theme="dark"]` block → `:root[data-theme="light"]` block → `*:focus-visible` → `::selection` + scrollbar → `@media (prefers-reduced-motion: reduce)` → `@keyframes` definitions.

**Primitive build strategy**

- **D-18** Run `npx shadcn@latest init` then `npx shadcn@latest add button input dropdown-menu form`. Customize generated files against sunset tokens. SsoButton + GradientText hand-built in the same `components/ui/` directory.
- **D-19** Variant API: CVA + `clsx` + `tailwind-merge` (what shadcn generates). `clsx` and `tailwind-merge` are already deps; add `class-variance-authority`.
- **D-20** `cn()` helper at `frontend/src/lib/utils.ts`: `export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))`.
- **D-21** Form library: `react-hook-form` + `zod` + `@hookform/resolvers` + shadcn Form compound components.
- **D-22** `<GradientText>` is a primitive. Polymorphic via `as` prop (or Radix Slot). Applies `background: var(--gradient-sunset); background-clip: text; -webkit-text-fill-color: transparent;` inline.
- **D-23** Button polymorphism via `asChild` (`@radix-ui/react-slot`).
- **D-24** Button `loading` prop swaps children for a 14px sunset-tinted inline SVG spinner + `aria-busy` + `disabled`. Optional `loadingText`. No separate Spinner primitive yet.
- **D-25** Icons from `lucide-react`. Button accepts `leftIcon` / `rightIcon` as `ReactNode`.
- **D-26** `<SsoButton provider="google" | "microsoft" />`. Click invokes existing `useAuth().loginSSO(provider)`.
- **D-27** `<Input>` is a single primitive. When `type="password"`, renders built-in eye-toggle suffix button with `aria-pressed` + "Show password" / "Hide password" labels.
- **D-28** Field-level error flips input to `border-danger` + `aria-invalid="true"`; `<FormMessage>` renders in `text-danger`. Form-level `<ErrorAlert>` uses `bg-danger-soft` + `border-danger`.
- **D-29** File naming follows shadcn defaults: kebab-case, flat (`button.tsx`, `input.tsx`, `sso-button.tsx`, `gradient-text.tsx`).
- **D-30** Each primitive ships with Vitest + Testing Library `.test.tsx` covering every state + `axe-core` against the rendered output.
- **D-31** `frontend/src/app/dev/primitives/page.tsx` renders every primitive state. Gated by `process.env.NODE_ENV !== 'production'`.
- **D-32** `or with email` divider is a one-off in `/login` markup — not a primitive.

**Shell scaffold scope**

- **D-33** Move every authenticated route into a `(authed)` route group. Route-group `layout.tsx` renders `<AppShell>` once. `/login` and `/` stay outside.
- **D-34** Canonical authenticated paths are `/dashboard/...`. Delete duplicate root-level route directories.
- **D-35** Nav items render with real `next/link` `<Link>` hrefs. Active state via `usePathname()` with prefix matching (`/dashboard` root item uses exact match). Counts render as `—` placeholders.
- **D-36** Sidebar item list (verbatim): **Triage** = Dashboard (`Home`) / Vulnerabilities (`Bug`) / Assets (`Server`) / CSPM (`Cloud`); **Workflow** = Tickets (`Ticket`) / Connectors (`Plug`, route `/dashboard/integrations`); **Unlabeled** = Users (`Users`) / Settings (`Settings`).
- **D-37** Topbar functionality is visual scaffold only except the user chip. Search + ⌘K + bell + help render but don't act.
- **D-38** User chip reads `user.email`, derives 2-letter initials. Click opens `DropdownMenu` with email at top, `DropdownMenuRadioGroup` for Theme (Dark/Light), and Sign out.
- **D-39** Strip per-page outer wrappers from existing `dashboard/*/page.tsx` files. Pages keep v1 inner content + colors.
- **D-40** Brand mark wraps `<Link href="/dashboard">`. Breadcrumbs deferred.
- **D-41** Mobile collapse is desktop-defensive only: sidebar hides via `@media (max-width: 999px)`. No hamburger, no bottom-nav. Verify `/login` + shell don't crash at 360px.

**Login content + modes**

- **D-42** Remove `register` mode entirely from `/login`. Backend `/auth/register` stays.
- **D-43** `/login` mode state machine: `'login' | 'forgot' | 'reset'`. URL `/login?reset=TOKEN` deep-links into `reset` mode. SSO + divider hide on `forgot` and `reset`. Headings: `Sign in` / `Reset your password` / `Set a new password`.
- **D-44** Hard-code product-peek vuln rows directly in `/login` JSX. Use real public KEV CVEs.
- **D-45** Left-panel marketing copy ports **verbatim** from the variant-A sketch. Tagline: `See your security posture without opening another tool.` (with `without opening another tool.` as gradient-accent text). Sub-line: `One dashboard. Every scanner. Real ownership. Tickets out, fewer meetings.` Form panel subtitle: `Welcome back. Use your work account.`
- **D-46** SSO button copy: `Continue with Google` / `Continue with Microsoft`.
- **D-47** Mode-switch links: Login → `Forgot password?` link right-aligned below password input; Forgot → `Back to sign in` below email; Reset → entered only via `?reset=TOKEN` (no in-app link).
- **D-48** First field of each mode uses `autoFocus`. `autoComplete`: `email`, `current-password`, `new-password`, `off` for token field.
- **D-49** Login 401 surfaces generic `Email or password is incorrect.` Pass through other 4xx backend messages. Never differentiate user-not-found vs wrong-password.
- **D-50** Route-guard: unauthed user hitting protected route → redirect to `/login?next=<encoded-original-path>`. On successful login, `/login` reads `searchParams.get('next')` and `router.replace(next ?? '/dashboard')`.
- **D-51** SSO failure renders in same form-level `<ErrorAlert>`: `Sign-in with Google is temporarily unavailable. Try email instead.`
- **D-52** Per-mode submit copy: Login `Sign in` / `Signing in…`; Forgot `Send reset link` / `Sending…`; Reset `Set new password` / `Updating…`.
- **D-53** Form validation on submit only (`mode: 'onSubmit'`). Zod schemas: login `{ email: z.string().email(), password: z.string().min(1) }`; forgot `{ email: z.string().email() }`; reset `{ token: z.string().min(1), newPassword: z.string().min(8) }`.

### Claude's Discretion

- Exact spacing of sample-CVE rows on left panel
- Tailwind colors-extend naming convention (e.g. `severity-critical` vs `severity.critical`) — pick what reads best with `bg-` / `text-` prefixes
- Whether FOUC-prevention script lives inline in `app/layout.tsx` or as `<Script strategy="beforeInteractive">`
- Test fixture layout — colocated `.test.tsx` vs `__tests__/` subdirectory
- Whether `lib/auth.tsx` `loginSSO` error handling is updated in-place or via a small wrapper component
- Specific CVE entries on left panel
- Whether route-guard redirect lives in middleware, `(authed)/layout.tsx` server component, or client-side `useAuth()`
- Whether to ship a small `<EmailSentConfirmation>` view inside forgot mode after submit

### Deferred Ideas (OUT OF SCOPE)

- Working ⌘K command palette
- Bell-icon notification badge + dropdown
- Mobile hamburger + bottom-nav
- Light-theme visual polish
- Breadcrumb primitive
- Spinner primitive
- Divider primitive
- Page-transition motion
- SSO-only enforcement / MFA / remember-me / account lockout UX
- Backend `_reset_tokens` in-memory dict refactor
- Self-serve registration UI (removed; backend endpoint kept)
- Storybook playground
- Settings page sidebar-of-categories pattern (Phase 14)
- Keeping `frontend/src/app/dashboard/layout.tsx` (merge into `(authed)/layout.tsx`)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-01-01 | `/login` split-screen layout, gradient mesh left, clean form right, 360/768/1280 tested | Sketch source at `sources/001-login-sunset/index.html` variant A; layout pattern in `page-layouts.md` §1 |
| UX-01-02 | SSO buttons primary, email/password secondary, `or with email` divider | Sketch markup + `interaction-patterns.md`; SsoButton primitive spec D-26 |
| UX-01-03 | Gradient CTA pill is sole fancy element; loading shows `Signing in…` | `visual-language.md` CTA section; Button `loading` API D-24 |
| UX-01-04 | Forgot/reset modes inherit chrome; SSO hides in those modes | D-43 + D-47 state-machine spec |
| UX-01-05 | Error states use `bg-danger-soft` + `border-danger` | Sketch `.error-bar` CSS at line 59–63; D-28 ErrorAlert spec |
| UX-F-01 | CSS-variable token system; Inter+JetBrains Mono via `next/font` with swap | `sunset.css` vendored verbatim; `next/font` CSS-variable wiring documented below |
| UX-F-02 | `:root[data-theme="dark"]` / `[data-theme="light"]` swap. Zero `!important` | D-17 globals.css rewrite spec; the single `!important` exception is inside reduced-motion `@media` block |
| UX-F-03 | Persistent shell — 220px sidebar with gradient brand mark + active strip; topbar with ⌘K + bell + help + avatar chip | `app-shell.md` (full reference); shell component breakdown documented below |
| UX-F-04 | First primitive set: Button, Input, SsoButton, GradientText (all states) | shadcn-vendored Button + Input; hand-built SsoButton + GradientText; D-30 covers all states + tests |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

These are non-negotiable rules from the project root CLAUDE.md. Any plan that violates them must be revised.

| # | Constraint | Source | Implication for Phase 9 |
|---|-----------|--------|------------------------|
| C1 | Read `sketch-findings-getvul` skill FIRST before writing UI code | CLAUDE.md "Sketch findings" | Planner must reference skill `references/*.md` files; do not re-derive design |
| C2 | If a UI decision conflicts with skill references, references win | CLAUDE.md routing | Resolve conflicts in favor of skill, flag if discovered |
| C3 | Don't substitute fonts (Inter + JetBrains Mono locked) | CLAUDE.md "What NOT to do" | `next/font/google` loads these two exact families |
| C4 | Don't pick hex colors freehand — use CSS variables from `foundation.md` | CLAUDE.md "What NOT to do" | Tailwind extend resolves to `var(--color-*)`; no inline `#xxxxxx` |
| C5 | Don't ship a screen without empty/loading/error states | CLAUDE.md "What NOT to do" | `/login` has form-level error (D-28); loading via Button `loading` state (D-24). No empty state needed (auth has no "no data" surface). Phase 11 lands full list-state patterns. |
| C6 | Don't use Tailwind admin-template patterns | CLAUDE.md "What NOT to do" | Avoid generic admin chrome — match sketch fidelity |
| C7 | Don't compose generic SaaS copy ("Welcome!", "Please...", "Click here") | CLAUDE.md "What NOT to do" + `copy-voice.md` | All copy ports from sketch + voice rules: sentence case, no exclamation, no "please", specific errors |
| C8 | Frontend = Next 15 App Router + React 19 + TS 5.5 + Tailwind 3.4 | CLAUDE.md "Codebase conventions" | Do NOT upgrade to Tailwind v4 (D-03 lock); use `next/font` not `@font-face` |

## Summary

Phase 9 is a **simultaneous-rewrite** vertical slice: replace v1's gray-800/HSL-variable frontend with a sunset CSS-variable design system **and** ship `/login` against the validated split-screen sketch in a single phase. The scope spans seven concerns at once — token vendoring, theme switch refactor, Tailwind reconfig, font wiring, route-group restructure, primitive seeding (shadcn init + 4 custom primitives), and a full `/login` rewrite — plus a sweeping deletion of v1 utility class usage across every file in `frontend/src/`. The technical stack is well-trodden and reduces to ten implementation lanes the planner should treat as parallel tracks.

The two highest-risk lanes are: (1) the v1 deletion sweep — ~708 occurrences of legacy utility classes (`bg-background`, `bg-card`, `bg-gray-{800,900,950}`, `text-gray-{300,400,500}`, `border-gray-{700,800}`, etc.) need replacement; missing any will leave that pixel orphaned against deleted CSS variables, and visual debt is explicitly accepted (D-39) so the planner must be precise about *which* utilities get migrated to sunset tokens vs left v1-tinted for later phases to inherit; and (2) the route-group migration `app/dashboard/...` → `app/(authed)/dashboard/...` plus deletion of 5 root-level duplicate route directories — this needs `git mv` to preserve blame and an atomic commit so the working tree never has both routes coexisting.

Everything else is mechanical: shadcn init writes a known set of files [VERIFIED via shadcn docs]; `next/font/google` CSS-variable wiring is one-liner pattern [VERIFIED via Next docs]; `data-theme` attribute switching is a standard FOUC-prevention pattern with a documented inline-script approach [VERIFIED via Next dark-mode discussions]; Vitest + React Testing Library + vitest-axe is a known setup for Next 15 + React 19 [VERIFIED via Next testing docs].

**Primary recommendation:** Structure the plan as a Wave 0 foundation (token vendoring, globals.css rewrite, Tailwind reconfig, font wiring, theme bootstrap, test infrastructure) → Wave 1 primitive seeding (shadcn init + 4 primitives + dev/primitives route + tests) → Wave 2 v1 sweep + route-group migration → Wave 3 shell scaffold + `(authed)` layout → Wave 4 `/login` rewrite + route-guard → Wave 5 verification (grep `!important`, font cold-paint check, 360/1280 viewport pass, axe sweep, primitive tests green). Waves 0 and 1 are mostly serial (later waves need their outputs); Wave 2 can run in parallel with Wave 1 after globals.css lands; Waves 3 and 4 share the new primitives so they should run sequentially.

## Standard Stack

### Core (already in deps — verified)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | ^15.5.13 | App Router framework | Project pinned; latest 15.x is 15.5.18 [VERIFIED: npm view next@15] — minor upgrade optional, not required |
| react / react-dom | ^19.0.0 | UI runtime | Project pinned; required for Next 15 |
| typescript | ^5.5.0 | Type system | Project pinned |
| tailwindcss | ^3.4.0 | Utility CSS | D-03 locks 3.4 (no v4 upgrade); current 3.4.x line still maintained [VERIFIED: npm view tailwindcss@3] |
| clsx | ^2.1.0 | Conditional className composition | Already present; needed by `cn()` helper |
| tailwind-merge | ^2.3.0 | Tailwind class conflict resolution | Already present; needed by `cn()` helper |
| lucide-react | ^0.383.0 | Icon set | Already present; latest is 0.553.0 [VERIFIED: npm view lucide-react] — upgrade not required, current covers needed icons (Home, Bug, Server, Cloud, Ticket, Plug, Users, Settings, Bell, Search, HelpCircle, LogOut, Eye, EyeOff, Check, ChevronDown, AlertTriangle) |

### To install (verified versions as of 2026-05-12)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| class-variance-authority | ^0.7.1 | Variant API for primitives | [VERIFIED: npm view class-variance-authority] — current 0.7.1; shadcn-generated Button imports this |
| @radix-ui/react-slot | ^1.2.4 | `asChild` polymorphism on Button | [VERIFIED: npm view] — D-23 requires |
| @radix-ui/react-dropdown-menu | ^2.1.16 | User-chip dropdown | [VERIFIED: npm view] — D-38 requires |
| @radix-ui/react-label | latest | shadcn Form internals | Pulled in transitively by `shadcn add form` |
| react-hook-form | ^7.75.0 | Form state machine | [VERIFIED: npm view react-hook-form] — D-21 requires |
| zod | ^4.4.3 | Schema validation | [VERIFIED: npm view zod] — D-21, D-53 require; v4 is current major. Verify resolver compatibility (some `@hookform/resolvers` versions pin to zod v3 — see Pitfalls) |
| @hookform/resolvers | ^5.2.2 | RHF ↔ zod bridge | [VERIFIED: npm view @hookform/resolvers] — v5 supports zod v4 [CITED: hookform changelog] |

### Test infrastructure (devDependencies)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| vitest | ^4.1.6 | Test runner | [VERIFIED: npm view vitest] — latest line; React 19 compatible per Next testing docs [CITED: nextjs.org/docs/app/guides/testing/vitest] |
| @vitejs/plugin-react | latest | React JSX support in Vitest | [CITED: Next 15 Vitest setup guide] |
| vite-tsconfig-paths | latest | `@/*` alias resolution in tests | [CITED: same] |
| jsdom | ^16.3.2 | DOM environment for Vitest | [VERIFIED: npm view jsdom] |
| @testing-library/react | ^10.0.0 | Component query/render | [VERIFIED: npm view @testing-library/react] — latest |
| @testing-library/jest-dom | latest | DOM matchers | Standard |
| @testing-library/user-event | latest | User-event simulation (focus, click, type) | Required for focus-visible assertions |
| vitest-axe | ^0.1.0 | axe-core matcher for Vitest | [VERIFIED: npm view vitest-axe] — Vitest-native fork of jest-axe [CITED: github.com/chaance/vitest-axe]. **Use `jsdom`, not `happy-dom`** — vitest-axe has a known Happy DOM incompatibility with `Node.prototype.isConnected` [CITED: vitest-axe search results] |

### Installation order

```bash
# 1. shadcn init (writes components.json + lib/utils.ts + installs CVA/clsx/tailwind-merge/lucide-react if missing)
# Note: project is on Tailwind 3 — pin to shadcn@2.3.0 [CITED: shadcn docs "For Tailwind v3, use shadcn@2.3.0"]
cd frontend && npx shadcn@2.3.0 init

# 2. shadcn add primitives
npx shadcn@2.3.0 add button input form dropdown-menu

# 3. Form deps
npm i react-hook-form@^7.75.0 zod@^4.4.3 @hookform/resolvers@^5.2.2

# 4. Test infra
npm i -D vitest @vitejs/plugin-react vite-tsconfig-paths jsdom \
         @testing-library/react @testing-library/jest-dom @testing-library/user-event \
         vitest-axe
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff | Rejected because |
|------------|-----------|----------|-----|
| shadcn vendoring | Headless UI / Ariakit | Smaller install footprint | D-18 + REQUIREMENTS-v2.md "Out of Scope" lock shadcn |
| react-hook-form | Tanstack Form / Conform | Modern alternatives | D-21 locks RHF; ecosystem familiarity wins |
| vitest-axe | jest-axe (with vitest interop) | Jest-derived API | vitest-axe is Vitest-native; no environment friction |
| `next-themes` package | Bespoke ThemeProvider | Drop-in dark/light/system | Existing `useTheme()` consumer surface in `lib/theme.tsx`; D-02 is rewire-not-replace; pulling next-themes adds a dep for a 30-line job |
| `@tailwindcss/forms` | — | Better default inputs | D-16 explicitly forbids; Input primitive styled from scratch |
| Tailwind v4 | — | Native `@theme` directive | D-03 explicitly defers to next milestone |

### Version verification

Verified 2026-05-12 against npm registry. Versions above are current as of research date. Re-check before installing if execution slips beyond ~30 days.

## Architecture Patterns

### Recommended File Layout (post-Phase 9)

```
frontend/
├── components.json                                    # shadcn config (D-18)
├── middleware.ts                                       # IF planner picks middleware for route guard (D-50)
├── tailwind.config.ts                                  # full rewrite (D-09, D-10)
├── vitest.config.mts                                   # new
├── vitest.setup.ts                                     # new (RTL setup, axe matcher install)
└── src/
    ├── styles/
    │   └── sunset.css                                  # vendored from skill (D-01)
    ├── lib/
    │   ├── utils.ts                                    # cn() helper (D-20)
    │   ├── auth.tsx                                    # existing; minor updates per D-50, D-51
    │   ├── theme.tsx                                   # rewired to data-theme (D-02)
    │   ├── api.ts, fetch.ts                            # unchanged
    │   └── validation/                                 # new — zod schemas
    │       └── auth.ts                                 # login/forgot/reset schemas (D-53)
    ├── components/
    │   ├── ui/                                         # shadcn-vendored + hand-built (flat, kebab-case per D-29)
    │   │   ├── button.tsx                              # shadcn-generated, customized to sunset tokens
    │   │   ├── button.test.tsx                         # (D-30)
    │   │   ├── input.tsx                               # shadcn-generated, customized + password eye-toggle (D-27)
    │   │   ├── input.test.tsx
    │   │   ├── form.tsx                                # shadcn-generated (Form/FormField/FormItem/FormLabel/FormControl/FormMessage)
    │   │   ├── dropdown-menu.tsx                       # shadcn-generated
    │   │   ├── sso-button.tsx                          # hand-built (D-26)
    │   │   ├── sso-button.test.tsx
    │   │   ├── gradient-text.tsx                       # hand-built (D-22)
    │   │   └── gradient-text.test.tsx
    │   └── shell/                                      # new — persistent app chrome
    │       ├── app-shell.tsx                           # grid container; renders Sidebar + Topbar + main
    │       ├── sidebar.tsx                             # 220px nav; brand mark + sections + items (D-36)
    │       ├── topbar.tsx                              # search + bell + help + user chip (D-37)
    │       └── user-chip.tsx                           # avatar + DropdownMenu with Theme radio + Sign out (D-38)
    └── app/
        ├── layout.tsx                                  # rewire: next/font, FOUC script, data-theme stays as html attribute
        ├── globals.css                                 # full rewrite (D-17)
        ├── page.tsx                                    # existing root; verify it redirects to /dashboard or /login
        ├── login/page.tsx                              # full rewrite (D-43..D-53)
        ├── dev/primitives/page.tsx                     # state matrix (D-31)
        └── (authed)/                                    # NEW route group (D-33)
            ├── layout.tsx                               # renders <AppShell>{children}</AppShell>
            └── dashboard/                               # git-mv'd from app/dashboard/
                ├── page.tsx                             # outer wrapper stripped (D-39)
                ├── assets/[id]/page.tsx                 # outer wrapper stripped
                ├── connectors/, cspm/, settings/, tickets/, users/, vulnerabilities/  # all wrappers stripped
                └── ...
```

### Pattern 1: `next/font/google` with CSS Variables

```tsx
// frontend/src/app/layout.tsx
// Source: https://nextjs.org/docs/app/api-reference/components/font [CITED]
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const fontSans = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',            // UX-01-04 success criterion (no FOIT)
  adjustFontFallback: true,   // reduces CLS (default true)
});

const fontMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
  adjustFontFallback: true,
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      // data-theme is set by the inline bootstrap script BEFORE hydration (D-13).
      // Do NOT set it server-side — that would force a single theme on first paint
      // for users whose localStorage preference differs. Use suppressHydrationWarning
      // so React doesn't complain about the attribute appearing post-script.
      suppressHydrationWarning
      className={`${fontSans.variable} ${fontMono.variable}`}
    >
      <head>
        {/* Theme bootstrap — inline, synchronous, runs before paint (D-13). See Pattern 4. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

**Why `variable` not `className`:** the variable approach exposes the font as `var(--font-sans)` for use in Tailwind/CSS, instead of forcing one font family at the root. This lets the sunset.css token file already declare `--font-sans: 'Inter', …` (with system fallbacks) and `next/font` injects the same variable name — Inter wins, fallbacks still work if the swap window expires.

**Verification for UX-01-04:** Open DevTools → Network → Filter by font. Look for two woff2 requests, both with `display: swap` headers (Next.js applies this to the `@font-face` rule it generates). On cold load, body text should render in fallback within < 50ms, then swap to Inter when loaded — no FOIT (Flash of Invisible Text).

### Pattern 2: Tailwind `theme.extend` bridging to CSS variables

```ts
// frontend/tailwind.config.ts (full rewrite per D-09, D-10)
import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        // Surfaces
        bg:           'var(--color-bg)',
        'bg-darker':  'var(--color-bg-darker)',
        surface:      'var(--color-surface)',
        'surface-2':  'var(--color-surface-2)',
        // Borders
        border:           'var(--color-border)',
        'border-subtle':  'var(--color-border-subtle)',
        'border-strong':  'var(--color-border-strong)',
        // Text
        text:           'var(--color-text)',
        'text-muted':   'var(--color-text-muted)',
        'text-faint':   'var(--color-text-faint)',
        'text-inverse': 'var(--color-text-inverse)',
        // Sunset accents (allow `bg-pink`, `text-violet`, etc.)
        pink:        'var(--color-pink)',
        'pink-soft': 'var(--color-pink-soft)',
        violet:        'var(--color-violet)',
        'violet-soft': 'var(--color-violet-soft)',
        amber:        'var(--color-amber)',
        'amber-soft': 'var(--color-amber-soft)',
        // Semantic states
        danger:       'var(--color-danger)',
        'danger-soft':'var(--color-danger-soft)',
        success:       'var(--color-success)',
        'success-soft':'var(--color-success-soft)',
        warning: 'var(--color-warning)',
        info:    'var(--color-info)',
        // Severity (D-10)
        'severity-critical': 'var(--color-severity-critical)',
        'severity-high':     'var(--color-severity-high)',
        'severity-medium':   'var(--color-severity-medium)',
        'severity-low':      'var(--color-severity-low)',
        'severity-info':     'var(--color-severity-info)',
        // Status (D-10) — even though no Phase 9 component consumes, ship for Phase 13
        'status-open':        'var(--color-violet)',
        'status-inprogress':  'var(--color-amber)',
        'status-completed':   'var(--color-success)',
        'status-blocked':     'var(--color-danger)',
        // SLA tiers (D-10)
        'sla-overdue':  'var(--color-severity-critical)',
        'sla-soon':     'var(--color-severity-high)',
        'sla-ok':       'var(--color-success)',
        // Providers (D-10)
        'provider-jira':   '#5C9CFF',  // hard-coded; not in sunset.css since they're brand-adjacent
        'provider-asana':  '#FF8AA0',
        'provider-github': 'var(--color-violet)',
      },
      backgroundImage: {
        'gradient-sunset':    'var(--gradient-sunset)',
        'gradient-sunset-vertical': 'var(--gradient-sunset-vertical)',
        'gradient-mesh':      'var(--gradient-mesh)',
        'gradient-orb':       'var(--gradient-orb)',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
      borderRadius: {
        sm:    'var(--radius-sm)',
        md:    'var(--radius-md)',
        lg:    'var(--radius-lg)',
        xl:    'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
      },
      boxShadow: {
        card:     'var(--shadow-card)',
        elevated: 'var(--shadow-elevated)',
        'glow-pink':   'var(--glow-pink)',
        'glow-violet': 'var(--glow-violet)',
        'glow-amber':  'var(--glow-amber)',
        'glow-cta':    'var(--glow-cta)',
      },
      spacing: {
        // 4px scale already matches Tailwind defaults; only add the sunset.css extras if needed
        // Default Tailwind: 1=4px, 2=8px, 3=12px, 4=16px, 5=20px, 6=24px, 8=32px, 10=40px, 12=48px, 16=64px, 20=80px, 24=96px
        // sunset.css uses the same scale → no override needed
      },
    },
  },
  plugins: [],  // D-16: no @tailwindcss/forms, no @tailwindcss/typography
};

export default config;
```

**Naming choice for severity/status/SLA/provider (Claude's Discretion territory):**
Recommend kebab in `bg-` / `text-` consumers (`bg-severity-critical`, `text-sla-overdue`) — keeps utilities flat and reads naturally. Avoid nested object form (`severity.critical`) — that style requires arbitrary `bg-[var(--color-severity-critical)]` references downstream.

### Pattern 3: globals.css structure (D-17)

```css
/* Source: D-17 spec; verifies grep -c '!important' returns 0 */

@tailwind base;
@tailwind components;
@tailwind utilities;

@import './styles/sunset.css';

:root[data-theme="dark"] {
  /* Sunset tokens — already imported above; this block can re-declare overrides
     if the same vars need different values per theme.
     Per current sunset.css, the :root block IS the dark theme. To make swapping
     work, either:
       (a) move the :root block to :root[data-theme="dark"] when vendoring, OR
       (b) keep :root as the base and add :root[data-theme="light"] to override
     Recommendation: (b) — vendor sunset.css unchanged, then add a `[data-theme="light"]`
     override block below. This preserves diff-ability with the upstream skill file. */
}

:root[data-theme="light"] {
  /* Architecture only (D-06). Credible mappings for token swap, no visual polish required. */
  --color-bg:            #FAF7F2;  /* warm off-white */
  --color-bg-darker:     #F2EDE5;
  --color-surface:       #FFFFFF;
  --color-surface-2:     #F7F2EA;
  --color-border:        #E5DDD0;
  --color-border-subtle: #EFE9DF;
  --color-border-strong: #D4C9B5;
  --color-text:          #1A1430;
  --color-text-muted:    #5C5474;
  --color-text-faint:    #8A8298;
  --color-text-inverse:  #F0E8FF;
  /* Sunset accents stay vibrant in light theme — same hex */
  /* Semantic states stay the same */
  /* Severity stays the same */
  color-scheme: light;
}

:root[data-theme="dark"] {
  color-scheme: dark;
}

*:focus-visible {
  outline: 2px solid var(--color-violet);
  outline-offset: 2px;
}

::selection {
  background: var(--color-pink);
  color: var(--color-text-inverse);
}

html { scrollbar-color: var(--color-border-strong) var(--color-bg); }
::-webkit-scrollbar { width: 12px; height: 12px; }
::-webkit-scrollbar-track { background: var(--color-bg); }
::-webkit-scrollbar-thumb { background: var(--color-border-strong); border-radius: 6px; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;     /* THE ONE !important — D-12 documented */
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

@keyframes pulse-urgency { /* phase 9 ships definition; consumed by phase 10 dashboard hero */
  0%, 100% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0.6); }
  50%      { box-shadow: 0 0 0 8px rgba(248, 113, 113, 0); }
}
@keyframes gradient-drift {
  0%, 100% { transform: scale(1) translate(0, 0); }
  50%      { transform: scale(1.1) translate(-2%, 1%); }
}
@keyframes skeleton-shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -200% 0; }
}
@keyframes cta-shine-sweep {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
```

**Critical:** the `!important` exception inside `@media (prefers-reduced-motion: reduce)` is a documented and accepted exception per D-12. The `grep -c '!important' frontend/src/app/globals.css` check (UX-F-02 success criterion §2) returns a number > 0 if the reduced-motion block is present — see Pitfall §1 for the correct verification recipe.

### Pattern 4: Theme bootstrap inline script (D-13)

```js
// Source: aggregated from Next.js dark-mode discussion threads [CITED: github.com/vercel/next.js/discussions/53063]
// Inline in app/layout.tsx <head> via dangerouslySetInnerHTML.
// Synchronous, runs before paint, sets data-theme on <html> from localStorage or prefers-color-scheme.

const THEME_BOOTSTRAP_SCRIPT = `
(function(){
  try {
    var stored = localStorage.getItem('getvul_theme');
    var theme = stored || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;
```

Notes:
- **Use the existing `getvul_theme` localStorage key** — `lib/theme.tsx` already reads/writes this key in v1; do not introduce a new key
- The script does NOT use the literal `theme` key — the v1 code uses `getvul_theme` (verified in `lib/theme.tsx:17`). Keeping the same key avoids invalidating user preferences on first load post-deploy
- `suppressHydrationWarning` on `<html>` is required because the attribute is set client-side before React hydrates; without it React will warn about the mismatch
- For CSP: this requires `'unsafe-inline'` for `script-src` OR a `nonce` (see Security Domain below)

### Pattern 5: Route guard — middleware vs (authed)/layout.tsx

Three options for D-50; recommendation = **middleware** for the `?next=` redirect. Rationale:

| Option | Pros | Cons |
|--------|------|------|
| **Middleware (`middleware.ts`)** | Runs before SSR; cheapest redirect; survives JS-disabled clients | Cannot read in-memory token from `useAuth()` — must read from `localStorage`-mirroring cookie. Project currently stores tokens in `localStorage` only (see `lib/auth.tsx:48`). |
| Server component check in `(authed)/layout.tsx` | Centralized; can read cookies | Same cookie problem — Next 15 server components cannot read localStorage. Requires moving access token to httpOnly cookie. |
| Client-side `useAuth()` redirect | Works with current localStorage model; already exists in `auth.tsx:73–75` | Renders the protected route briefly before redirecting; loses the `?next=` URL preservation idiomatically; visible flash |

**Recommended pick (Claude's Discretion per CONTEXT):**

Stay with **client-side redirect in `useAuth()`** + extend it to encode `?next=`. Reason: changing token storage from localStorage to httpOnly cookie is a backend-touching change (D-OUT-OF-SCOPE — phase 9 must not modify backend, and the cookie set must come from the backend). Adding `?next=` on the client redirect path is a 5-line change to the existing `useEffect` at `lib/auth.tsx:72–76`:

```tsx
// lib/auth.tsx (modified)
useEffect(() => {
  if (!loading && !user && pathname && isProtectedPath(pathname)) {
    const next = encodeURIComponent(pathname + (searchParams ? '?' + searchParams.toString() : ''));
    router.replace(`/login?next=${next}`);
  }
}, [loading, user, pathname, router, searchParams]);

function isProtectedPath(p: string): boolean {
  return p.startsWith('/dashboard');
}
```

And on the `/login` page, after success:
```tsx
const next = searchParams.get('next');
const decoded = next ? decodeURIComponent(next) : '/dashboard';
// Validate next is same-origin path (D-50, security; see Security Domain below)
const safeDest = (decoded.startsWith('/') && !decoded.startsWith('//')) ? decoded : '/dashboard';
router.replace(safeDest);
```

If the project later moves tokens to httpOnly cookies (out of scope for phase 9, possibly v2.1+ backend hardening), the planner can swap to middleware then.

**Alternative — non-blocking middleware skeleton:** the planner MAY also add a `middleware.ts` that handles redirects when *only* legacy non-(authed) URLs are visited (e.g., redirect `/assets` → `/dashboard/assets` for old bookmarks). That's a route-cleanup task, not auth gating.

### Pattern 6: shadcn primitive customization to sunset tokens

```tsx
// components/ui/button.tsx — POST shadcn-generation customization
// Source: shadcn docs theming pattern + D-19, D-20, D-23
import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  // base
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-all ' +
  'disabled:pointer-events-none disabled:opacity-50 ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
  {
    variants: {
      variant: {
        cta:       'bg-gradient-sunset text-white shadow-glow-cta hover:-translate-y-px hover:shadow-elevated',
        secondary: 'bg-surface border border-border-subtle text-text hover:bg-surface-2 hover:border-border',
        ghost:     'text-text-muted hover:text-text hover:bg-surface-2',
        icon:      'h-[34px] w-[34px] rounded-md bg-surface border border-border-subtle text-text-muted hover:text-text hover:border-border',
      },
      size: {
        sm:  'px-3 py-1.5 text-xs',
        md:  'px-4 py-2 text-sm',
        lg:  'px-[18px] py-[10px] text-sm',
      },
    },
    defaultVariants: { variant: 'secondary', size: 'md' },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  loadingText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading, loadingText, leftIcon, rightIcon, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading ? (
          <>
            <Loader2 className="h-[14px] w-[14px] animate-spin" aria-hidden />
            {loadingText ?? children}
          </>
        ) : (
          <>
            {leftIcon}
            {children}
            {rightIcon}
          </>
        )}
      </Comp>
    );
  }
);
Button.displayName = 'Button';
```

The Slot/`asChild` pattern (D-23) enables `<Button asChild><Link href="/dashboard">Go</Link></Button>` — the Link receives all Button styling but stays a real anchor for nav.

### Pattern 7: react-hook-form + zod + shadcn Form

```tsx
// components/ui/form.tsx is shadcn-generated; consume as documented.
// Source: shadcn Form docs + D-21, D-53
'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

// lib/validation/auth.ts
export const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

// /login form usage
const form = useForm<z.infer<typeof loginSchema>>({
  resolver: zodResolver(loginSchema),
  mode: 'onSubmit',  // D-53
  defaultValues: { email: '', password: '' },
});

<Form {...form}>
  <form onSubmit={form.handleSubmit(onSubmit)}>
    <FormField
      control={form.control}
      name="email"
      render={({ field }) => (
        <FormItem>
          <FormLabel>Email</FormLabel>
          <FormControl>
            <Input type="email" placeholder="you@company.com" autoFocus autoComplete="email" {...field} />
          </FormControl>
          <FormMessage />  {/* field-level error per D-28 */}
        </FormItem>
      )}
    />
    {/* password field similar */}
    {authError && <ErrorAlert>{authError}</ErrorAlert>}  {/* form-level error */}
    <Button type="submit" variant="cta" size="lg" loading={form.formState.isSubmitting} loadingText="Signing in…">
      Sign in
    </Button>
  </form>
</Form>
```

**ErrorAlert** is a small one-off component (NOT a primitive) used for form-level auth errors per D-28:
```tsx
function ErrorAlert({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-md border border-danger bg-danger-soft px-3 py-2 text-sm text-danger">
      {children}
    </div>
  );
}
```

### Anti-Patterns to Avoid

- **Don't use `next-themes`** — D-02 mandates a rewire of existing `lib/theme.tsx`, not a library swap. Adding `next-themes` is +1 dep for a 30-line job.
- **Don't store the theme in a cookie** — D-13 + existing v1 use localStorage. Cookie storage requires server-side reads and middleware changes that aren't in scope.
- **Don't hardcode hex colors anywhere** in TSX. Every color flows through Tailwind utilities → CSS variables. CLAUDE.md "What NOT to do" enforces this.
- **Don't run `shadcn init` more than once** — re-running can overwrite customized files. See Pitfall §3.
- **Don't keep the v1 `.dark` / `.light` class fallback after the rewire** — D-02 says remove entirely; partial migration leaves dead CSS and confusing dual paths.
- **Don't ship a Spinner primitive** — D-24 explicitly inlines the spinner in Button; promote later when needed.
- **Don't use `next/dynamic` to lazy-load the shell** — it's persistent; loading it dynamically would flash the page chrome.
- **Don't use `position: fixed` on the topbar** — `app-shell.md` "What NOT to do" §2 forbids this; topbar scrolls with content.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Class composition + Tailwind conflict resolution | Custom `cn()` | `clsx + tailwind-merge` | Already deps; handles `cn('px-3', cond && 'px-5')` correctly |
| Variant API for primitives | Bespoke `variant` prop dispatcher | `class-variance-authority` (CVA) | What shadcn writes; type-safe variants |
| Form state | `useState` per field + manual validation | `react-hook-form` + `zod` + `@hookform/resolvers` | Validation, error surface, isSubmitting all unified |
| Polymorphic Button | Conditional `<a>`/`<button>` JSX | `@radix-ui/react-slot` (`asChild`) | Used by shadcn Button; <1KB; correct semantic + a11y |
| Dropdown menu | Custom abs-pos menu | `@radix-ui/react-dropdown-menu` (via shadcn) | Focus trap, ESC handling, ARIA, animations |
| Form primitive composition | Custom `<FormField>` / `<FormMessage>` | shadcn `add form` | Wires RHF context → field error surface |
| Accessibility testing | Manual focus assertion + ARIA grep | `vitest-axe` (`expect(container).toHaveNoViolations()`) | Catches role/label/contrast issues across all primitives at once |
| Loading text + spinner UX | Bespoke loading prop on each button | CVA + `loading` API in Button | One pattern, all consumers (D-24) |
| `cn()` for Tailwind merging | Manual concat with conditions | `cn(...inputs) = twMerge(clsx(inputs))` | Resolves conflicting utilities (`px-3 px-5` → `px-5`) |
| Inline FOUC-prevention | Component-level mounted gating | Synchronous inline script in `<head>` | Mounted-gate causes blank screen (current v1 behavior at `theme.tsx:34` returns null while !mounted — flashes blank!) |

**Key insight:** the existing v1 `theme.tsx` `if (!mounted) return null;` pattern (line 34) **causes a blank-screen flash on every cold load** because the entire AuthProvider tree is gated on theme mount. The inline-script pattern (D-13) eliminates both this AND the dark-flash. Removing the `mounted` gate is part of the theme.tsx rewire.

## Runtime State Inventory

> Phase 9 includes a major refactor (route group migration + v1 deletion sweep). Runtime state audit:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | `localStorage.getvul_token`, `localStorage.getvul_refresh`, `localStorage.getvul_sso_state`, `localStorage.getvul_theme` — all keep their keys; only theme.tsx implementation changes (from class toggling to attribute setting) | No data migration. Existing user sessions + theme preferences survive |
| **Live service config** | None — no external service has the phase-9 strings hardcoded. Backend `/auth/login` / `/auth/forgot-password` / `/auth/reset-password` / `/auth/login/{provider}` endpoints unchanged | None |
| **OS-registered state** | None — frontend has no OS-level registrations | None |
| **Secrets/env vars** | `NEXT_PUBLIC_API_URL` unchanged. No new env vars introduced | None |
| **Build artifacts** | `next` `.next/` cache: must invalidate after Tailwind config rewrite. `package-lock.json` will see ~15 new packages | Run `rm -rf frontend/.next && npm install` after dep additions; commit `package-lock.json` |
| **URL routes** | `/assets`, `/integrations`, `/settings`, `/tickets`, `/vulnerabilities` — these are deleted by D-34. **Any external bookmarks or links to these will 404 after this phase.** | Decision needed (Claude's discretion): add `middleware.ts` redirects from each deleted root to the `/dashboard/*` canonical path? Or accept the 404 since the product is single-tenant-per-VM and bookmarks are intra-org? Recommend the redirect — it's 6 lines and protects power users with sidebar-pinned tabs |

**Verified via grep:** `frontend/src/` has ~708 occurrences of legacy v1 utility classes (`bg-background`, `bg-card`, `bg-gray-{8,9}00`, `bg-gray-950`, `text-foreground`, `text-card-foreground`, `text-gray-{3,4,5}00`, `border-border`, `border-gray-{7,8}00`). D-05 mandates sweeping every file. The planner should size this as its own wave; per-file find-replace per token family is the cleanest approach.

## Common Pitfalls

### Pitfall 1: The `grep -c '!important'` success criterion misreads the reduced-motion block

**What goes wrong:** UX-F-02 §2 says `grep -c '!important' frontend/src/app/globals.css` must return 0. D-12 says the `@media (prefers-reduced-motion: reduce)` block contains 4 `!important` declarations. Naive grep returns 4, not 0 — verification fails.

**Why it happens:** the success-criterion language is shorthand for "no `!important` outside the documented reduced-motion exception."

**How to avoid:** the planner must encode the verification as:
```bash
# Total !important count
COUNT=$(grep -c '!important' frontend/src/app/globals.css)

# Count INSIDE the reduced-motion block (the documented exception)
EXEMPT=$(awk '/prefers-reduced-motion/,/^}/' frontend/src/app/globals.css | grep -c '!important')

# Effective non-exempt count must be 0
test "$((COUNT - EXEMPT))" -eq 0
```
Or alternatively: `grep -v '/\*' frontend/src/app/globals.css | awk '/^@media \(prefers-reduced-motion/,/^}$/{next} 1' | grep -c '!important'`. Document the verification command in the task explicitly so verify-work doesn't fail on the legitimate exception.

**Warning signs:** the success criterion text "returns 0" is taken literally by tooling.

### Pitfall 2: `next/font` CSS variables don't render in dev mode

**What goes wrong:** font CSS variables sometimes fail to inject in `next dev` due to a known Next 15 issue, especially after hot-reload of `layout.tsx`. Body text falls back to system font; tests pass; production build is fine.

**Why it happens:** [CITED: github.com/vercel/next.js/discussions/59500] — module-level font declarations occasionally lose their variable class on fast-refresh.

**How to avoid:** verify cold-paint by hard-reloading (Cmd+Shift+R) in DevTools with Network → Disable Cache. Run `next build && next start` for production verification. Don't trust dev-server output alone for UX-01-04.

**Warning signs:** body text looks slightly wider than expected; computed style on `<html>` shows `--font-sans` is empty.

### Pitfall 3: Running `shadcn init` twice clobbers customizations

**What goes wrong:** if `shadcn init` is run a second time (e.g., by a different task or after a `git stash`), it overwrites `components.json`, `lib/utils.ts`, and potentially `globals.css` with shadcn defaults — losing all sunset-token customizations.

**Why it happens:** the init command is idempotent on intent but destructive on output.

**How to avoid:** init exactly once in the foundation wave. Subsequent primitive additions use `shadcn add <name>`, which only writes new files (and prompts before overwriting existing ones). Document this in the plan: "shadcn init runs ONCE in task X; subsequent tasks use `shadcn add`."

**Warning signs:** `git diff components/ui/button.tsx` shows the file revert to defaults; `globals.css` shows shadcn's HSL token block reappear.

### Pitfall 4: `suppressHydrationWarning` mismatch on `<html>`

**What goes wrong:** without `suppressHydrationWarning` on `<html>`, React 19 throws a hydration error because the bootstrap script set `data-theme` post-script (before hydration) but the SSR markup had no attribute.

**Why it happens:** Next.js SSR renders `<html lang="en">` with no `data-theme`. Bootstrap script adds it. React hydrates and notices the diff.

**How to avoid:** `<html suppressHydrationWarning data-theme="dark">` — set a default attribute SSR-side AND suppress the warning. The script will override the default on client with the user's actual preference. Net behavior: cold-load users with `light` preference see a single-frame dark-then-light swap; users with `dark` preference (or no preference + dark prefers-color-scheme) see no flash.

**Warning signs:** console error "Hydration failed because the initial UI does not match what was rendered on the server."

### Pitfall 5: zod v4 + @hookform/resolvers compatibility

**What goes wrong:** zod v4 (current major) requires `@hookform/resolvers` v5+. Older v3 resolvers throw at form submit when used with zod v4 schemas.

**Why it happens:** zod v4 changed internal API for parsing; older resolver versions can't read the new shape.

**How to avoid:** pin `zod@^4.4.3` AND `@hookform/resolvers@^5.2.2` together in package.json. Cross-check with `npm ls zod @hookform/resolvers` after install. If a transitive dep pulls zod v3, use npm `overrides` to force v4.

**Warning signs:** `TypeError: cannot read property '_parse' of undefined` on form submit.

### Pitfall 6: vitest-axe + happy-dom incompatibility

**What goes wrong:** if Vitest config uses `environment: 'happy-dom'` instead of `'jsdom'`, axe-core fails silently — `toHaveNoViolations()` always passes regardless of accessibility issues.

**Why it happens:** [CITED: vitest-axe socket.dev / search results] — happy-dom's `Node.prototype.isConnected` implementation differs; axe relies on it.

**How to avoid:** `vitest.config.mts` MUST set `test.environment = 'jsdom'`. Don't switch to happy-dom for "speed" reasons.

**Warning signs:** all axe tests passing on day one, even on buttons with no accessible name — the matcher is no-oping.

### Pitfall 7: Route-group `git mv` not preserving blame

**What goes wrong:** moving `app/dashboard/*` to `app/(authed)/dashboard/*` via `cp -r + rm -rf` loses git blame history. Files appear as new in `git log --follow`.

**Why it happens:** git's rename detection requires high path-similarity; large file restructures need explicit `git mv`.

**How to avoid:** for each subroute file, `git mv app/dashboard/X app/(authed)/dashboard/X`. Commit the moves in a SINGLE commit, separate from any content changes (no string-strip on the same commit as the move — strip in a follow-up commit). The parens in `(authed)` need shell escaping or quoting: `git mv 'app/dashboard/page.tsx' 'app/(authed)/dashboard/page.tsx'`.

**Warning signs:** `git log --follow frontend/src/app/(authed)/dashboard/page.tsx` shows fewer commits than the original; per-line blame attributes everything to the mover.

### Pitfall 8: `useSearchParams()` requires Suspense boundary in Next 15

**What goes wrong:** `/login?next=/dashboard/vulnerabilities` — calling `useSearchParams()` in the login page client component without a Suspense boundary causes build errors / "deopts to client-side rendering" warnings.

**Why it happens:** Next 15 requires `useSearchParams()` to be wrapped in `<Suspense>` for static prerendering compatibility.

**How to avoid:** wrap the form-side component in `<Suspense fallback={<LoginFormSkeleton />}>`, or accept that `/login` becomes dynamic (acceptable — auth is never cached).

**Warning signs:** `next build` warning: "useSearchParams should be wrapped in a suspense boundary at page \"/login\"."

### Pitfall 9: User-enumeration leak via error copy on `forgot` mode

**What goes wrong:** D-49 covers login mode (always-generic 401). But the forgot-password form's success/error handling can leak: if the backend returns "email not found" specifically, surfacing that lets an attacker enumerate registered emails.

**Why it happens:** v1 code at `login/page.tsx:106` does `data.detail || "Failed to send reset email"` — passes backend errors through. If backend distinguishes "email exists" vs "email doesn't exist," the UI surfaces that.

**How to avoid:** always show generic success copy on forgot — `If that email is registered, a reset token is on its way.` Backend may or may not have actually sent the email. This is the OWASP ASVS V2 / NIST 800-63 standard. The planner should verify the backend response shape; if backend already returns generic, no change needed.

**Warning signs:** different error texts for valid vs invalid emails in DevTools Network panel.

### Pitfall 10: Open redirect via `?next=` URL parameter

**What goes wrong:** `/login?next=//evil.com` — without validation, after successful login the user is redirected to the attacker's site. Classic open-redirect vulnerability.

**Why it happens:** naive `router.replace(next)` accepts any URL.

**How to avoid:** validate `next` is a same-origin relative path before redirecting:
```ts
const next = searchParams.get('next');
const decoded = next ? decodeURIComponent(next) : '/dashboard';
const safe = (decoded.startsWith('/') && !decoded.startsWith('//') && !decoded.startsWith('/\\'))
  ? decoded
  : '/dashboard';
router.replace(safe);
```
Plus: HTML-encode the `?next` value if it ever renders in markup (it shouldn't, but defense-in-depth).

**Warning signs:** `?next=https://...` redirects out of the app post-login.

### Pitfall 11: `data-theme` attribute on `<html>` SSR rendering with no value

**What goes wrong:** Tailwind utilities that resolve to `var(--color-bg)` etc. resolve to the empty string (or the fallback color) for the first frame between SSR HTML arriving and the bootstrap script running. Result: a sub-100ms flash of unstyled colors on slow clients.

**Why it happens:** CSS variables defined inside `:root[data-theme="dark"]` only apply when the attribute matches. With no attribute set yet, the variables are undefined.

**How to avoid:** SSR `<html data-theme="dark">` as the default — covers the period before the bootstrap script runs. Bootstrap script then overrides to user's actual preference. With `suppressHydrationWarning`, the React/DOM diff is silenced. The remaining "flash" for light-preference users on cold load is ≤1 frame and accepted.

**Warning signs:** dark plum body color absent on the first frame, replaced by browser default white. Visible especially on slow Network throttling.

### Pitfall 12: `prefers-reduced-motion` global `!important` rule disables motion on hover even on click feedback

**What goes wrong:** D-12's blanket rule zeroes `animation-duration` and `transition-duration` for ALL elements. This is correct for big animations but also kills click-feedback transitions (e.g., button :active state's transform).

**Why it happens:** the rule is universal; user-agent feedback animations get caught.

**How to avoid:** accepted tradeoff per D-12 — reduced-motion is a strong user signal that they want zero motion. The phase-15 UX-07-04 verification explicitly tests this. No fix needed.

**Warning signs:** UX-07-04 reviewer reports buttons "feel dead" in reduced-motion. Document this as expected behavior.

## Code Examples

### Sunset gradient text (GradientText primitive, D-22)

```tsx
// components/ui/gradient-text.tsx
import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';

interface GradientTextProps extends React.HTMLAttributes<HTMLElement> {
  asChild?: boolean;
}

export const GradientText = React.forwardRef<HTMLElement, GradientTextProps>(
  ({ asChild = false, className, style, children, ...props }, ref) => {
    const Comp: any = asChild ? Slot : 'span';
    return (
      <Comp
        ref={ref}
        className={className}
        style={{
          background: 'var(--gradient-sunset)',
          backgroundClip: 'text',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          color: 'transparent',
          ...style,
        }}
        {...props}
      >
        {children}
      </Comp>
    );
  }
);
GradientText.displayName = 'GradientText';
```

Usage in `/login` tagline (UX-01-01 success criterion §1):
```tsx
<h1 className="text-5xl font-extrabold leading-tight tracking-tighter">
  See your security posture <GradientText>without opening another tool.</GradientText>
</h1>
```

### SsoButton primitive (D-26)

```tsx
// components/ui/sso-button.tsx
import * as React from 'react';
import { cn } from '@/lib/utils';
import { GoogleIcon, MicrosoftIcon } from './sso-icons';  // inline SVGs from existing v1 code

type Provider = 'google' | 'microsoft';

const PROVIDER_LABEL: Record<Provider, string> = {
  google: 'Continue with Google',
  microsoft: 'Continue with Microsoft',
};

const PROVIDER_ICON: Record<Provider, React.ComponentType> = {
  google: GoogleIcon,
  microsoft: MicrosoftIcon,
};

interface SsoButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  provider: Provider;
}

export const SsoButton = React.forwardRef<HTMLButtonElement, SsoButtonProps>(
  ({ provider, className, ...props }, ref) => {
    const Icon = PROVIDER_ICON[provider];
    const label = PROVIDER_LABEL[provider];
    return (
      <button
        ref={ref}
        type="button"
        className={cn(
          'flex w-full items-center justify-center gap-2.5 rounded-md',
          'border border-border bg-surface-2 px-4 py-2.5 text-sm font-medium text-text',
          'transition-all hover:-translate-y-px hover:border-border-strong hover:bg-surface',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
          'disabled:pointer-events-none disabled:opacity-50',
          className
        )}
        aria-label={label}
        {...props}
      >
        <Icon />
        <span>{label}</span>
      </button>
    );
  }
);
SsoButton.displayName = 'SsoButton';
```

Note: the existing v1 page has the Google + Microsoft SVG inline at `login/page.tsx:75-82`. Lift those into a small `components/ui/sso-icons.tsx` file or keep them inline in `sso-button.tsx`. The Microsoft v1 code uses `loginSSO("azure")` — the backend route is `azure` but the user-facing label is `Microsoft`. Keep that internal naming: `provider="microsoft"` on the prop, `loginSSO('azure')` on the call site (or unify by mapping inside the component if cleaner — Claude's discretion).

### Vitest config (test infra setup)

```ts
// frontend/vitest.config.mts
// Source: nextjs.org/docs/app/guides/testing/vitest [CITED]
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',   // NOT happy-dom — see Pitfall 6
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    css: false,             // skip CSS parsing in tests
  },
});
```

```ts
// frontend/vitest.setup.ts
import '@testing-library/jest-dom/vitest';
import * as axeMatchers from 'vitest-axe/matchers';
import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

expect.extend(axeMatchers);

afterEach(() => {
  cleanup();
});
```

### Primitive smoke test pattern (D-30)

```tsx
// components/ui/button.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { Button } from './button';

describe('<Button>', () => {
  it('renders default state', () => {
    render(<Button>Sign in</Button>);
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('shows loading state with aria-busy and disables the button', () => {
    render(<Button loading loadingText="Signing in…">Sign in</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toBeDisabled();
    expect(btn).toHaveTextContent('Signing in…');
  });

  it('honors disabled prop', () => {
    render(<Button disabled>Click</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('shows focus-visible ring on keyboard focus', async () => {
    render(<Button>Sign in</Button>);
    await userEvent.tab();
    const btn = screen.getByRole('button');
    expect(btn).toHaveFocus();
    // focus-visible utility class application — assert via class presence
    expect(btn.className).toMatch(/focus-visible:ring-violet/);
  });

  it('renders asChild as polymorphic anchor', () => {
    render(<Button asChild><a href="/dashboard">Go</a></Button>);
    expect(screen.getByRole('link', { name: 'Go' })).toHaveAttribute('href', '/dashboard');
  });

  it('has no accessibility violations across variants', async () => {
    const { container } = render(
      <>
        <Button variant="cta">Start triage</Button>
        <Button variant="secondary">Snooze 1h</Button>
        <Button variant="ghost">View trace</Button>
        <Button variant="icon" aria-label="Notifications">🔔</Button>
        <Button loading loadingText="Signing in…">Sign in</Button>
        <Button disabled>Disabled</Button>
      </>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
```

## State of the Art

| Old (v1) | Current (phase 9) | Why Changed |
|----------|------|-------------|
| `.dark` class on `<html>` | `data-theme="dark"` attribute | UX-F-02 spec; data-attributes are the modern accepted pattern (works with CSS `[data-theme="dark"]` selector, doesn't clash with utility classes) |
| HSL CSS variables (`--background: 224 71% 4%`) | Hex CSS variables (`--color-bg: #0E0B1A`) | Sunset tokens are direct hex; HSL was a shadcn-v1 holdover, no functional benefit |
| `className="dark"` server-side | `data-theme` set by inline script before paint | Eliminates mounted-gate blank flash; supports `prefers-color-scheme` on first visit |
| Hand-rolled SSO buttons inline in `/login/page.tsx` | `<SsoButton provider="google">` primitive | Reusable in future SAML / Okta additions; testable |
| `useState` + manual `setError` | `useForm()` + `zodResolver()` + `<FormMessage>` | Field-level validation, isSubmitting unified; no manual error state management |
| `<input className="…long-tailwind…">` inline | `<Input>` primitive with built-in eye-toggle on `type="password"` | Single chrome surface; accessibility handled once |
| Outer wrapper div per dashboard page (`<div className="min-h-screen bg-gray-950 …">`) | Shell owns layout via `(authed)/layout.tsx` | DRY; one place to evolve chrome |
| `frontend/src/components/layout/{Sidebar,Header}.tsx` | `frontend/src/components/shell/{app-shell,sidebar,topbar,user-chip}.tsx` | New shell, kebab-case + flat per shadcn convention; old `layout/` directory deleted |
| Self-serve register UI | Admin-seeded model (no register branch) | Single-tenant-per-VM product (D-42) |

**Deprecated/outdated:**
- v1 `useTheme()` `mounted` gate that returns null — causes blank flash, replaced by inline bootstrap script
- `useAuth()` route-guard at `lib/auth.tsx:73` that hard-codes `/login` — extended to encode `?next=`
- `lib/auth.tsx` `loginSSO` silent catch at line 164 — surfaces error via `<ErrorAlert>` per D-51

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Backend `/auth/forgot-password` returns a generic response that doesn't differentiate "email registered" vs "not registered" | Pitfall 9 | If backend leaks enumeration, the planner must add a UI-side generic-success wrapper. Verify by checking `backend/app/auth/router.py` response shape — this is in repo, plannable. |
| A2 | The `frontend/src/app/page.tsx` root route exists and redirects to `/dashboard` or `/login` | File Layout | If `/` is its own page, the planner must verify it survives the rewrite. Quick check during planning: `cat frontend/src/app/page.tsx` |
| A3 | `next/font` produces CSS-variable wiring that works against both `:root[data-theme="dark"]` and `[data-theme="light"]` | Pattern 1 | Low risk — Next's `--font-*` declaration lives on `<html>` via the className mechanism, independent of theme attribute. Verified by docs but not in this codebase yet. |
| A4 | The 4-digit count of v1 utility classes (~708 matches across `frontend/src/`) covers all sweep targets | Runtime State Inventory | If grep missed a pattern (e.g., `bg-zinc-900` style variations), the sweep will leave stragglers. Mitigation: the planner should write its own grep at task-creation time and document the full pattern list. |
| A5 | shadcn-generated `Form.tsx` from `shadcn@2.3.0 add form` works against react-hook-form v7.75 + zod v4 | Pattern 7 | shadcn Form internals call `useFormContext` from RHF v7 API surface; v7.75 is stable. Risk = LOW. |
| A6 | The `getvul_theme` localStorage key in current v1 is the canonical key | Pattern 4 | Verified by reading `lib/theme.tsx:17` — confirmed. No risk. |
| A7 | Project's CI does not currently run frontend tests (no `test` script in package.json) | Validation Architecture | Verified — `frontend/package.json` has no test script. Wave 0 adds it. No risk. |
| A8 | `vitest@4` supports React 19 testing without compatibility shims | Standard Stack | Per Next.js Vitest setup docs [CITED], this is supported. There's a known Storybook+Vitest+Next 15 conflict but it doesn't affect direct Vitest usage. Risk LOW. |
| A9 | Existing dashboard layout `frontend/src/app/dashboard/layout.tsx` is the only layout file in the dashboard tree | File Layout | Verified by reading the file. Nested route segments don't override (none exist). No risk. |
| A10 | Adding redirect middleware for deleted root routes (`/assets` → `/dashboard/assets`) is desired by the user | Runtime State Inventory | Claude's discretion territory — flagged for planner decision, not assumed. |

## Open Questions

1. **Backend `/auth/forgot-password` response shape**
   - What we know: v1 surfaces `data.detail || "Failed to send reset email"` (login/page.tsx:106)
   - What's unclear: whether backend returns different messages for valid vs invalid emails (user enumeration risk per Pitfall 9)
   - Recommendation: planner reads `backend/app/auth/router.py` forgot-password handler in plan-phase; if it differentiates, add UI-side generic-success wrapper. Don't change backend.

2. **Should `middleware.ts` exist at all in phase 9?**
   - What we know: route guard goes in `lib/auth.tsx` (recommended Pattern 5); deleted route directories cause 404s
   - What's unclear: whether to add a minimal `middleware.ts` for legacy URL redirects (`/assets` → `/dashboard/assets`)
   - Recommendation: include in plan as a small task — 10 lines, addresses bookmark continuity, no auth coupling

3. **Light-theme color values**
   - What we know: D-06 says architecture only; visual polish deferred
   - What's unclear: the specific hex values for light-theme tokens — `foundation.md` doesn't define them; sunset.css doesn't either
   - Recommendation: use the credible warm-off-white mapping in Pattern 3 (Architecture Patterns) as a starting point; flag that light theme is not visually QA'd (per D-06) and may be revisited in UX-D-03

4. **CSP for inline FOUC-prevention script**
   - What we know: D-13 mandates an inline script; this requires `'unsafe-inline'` in `script-src` or a `nonce`
   - What's unclear: does nginx (or the backend's CSP middleware, per PROD-04-01 — deferred) currently set `Content-Security-Policy`?
   - Recommendation: planner checks current CSP. If absent (likely — PROD-04-01 is deferred), no immediate issue. Document that when CSP is added in v1.1, the bootstrap script needs a nonce.

5. **Form-level error placement on `/login`**
   - What we know: D-28 puts `<ErrorAlert>` at the top of the form panel
   - What's unclear: whether the alert displaces other form content (causing reflow) or floats above (no reflow)
   - Recommendation: use spec-fidelity — sketch HTML places it INSIDE the form, displacing content downward. Reflow is acceptable.

6. **`/dev/primitives` route visibility in production builds**
   - What we know: D-31 says `process.env.NODE_ENV !== 'production'` gate, returns `notFound()` in prod
   - What's unclear: whether the route should be excluded from the route manifest entirely (via `generateStaticParams` returning `[]`) or just respond 404
   - Recommendation: just respond `notFound()` — simpler, no manifest tricks. The route file ships in the prod bundle but the handler short-circuits.

## Environment Availability

> Phase 9 is code-only — no new external runtime dependencies.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Build + dev server | ✓ (assumed; project runs) | ≥ 18 (Next 15 req) | — |
| npm | Package install | ✓ | (any 9+) | — |
| Backend at `NEXT_PUBLIC_API_URL` | Login form submit (UX-01 §5) | ✓ (existing v1 talks to it) | Phase 1 of v1.0 shipped | — |
| Backend `/auth/login`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/login/{google,azure}` | All login flows | ✓ (existing endpoints, no changes) | — | — |

**No missing dependencies.** All work is within the existing frontend container.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1 + @testing-library/react 10 + vitest-axe 0.1 (all to be installed in Wave 0) |
| Config file | `frontend/vitest.config.mts` (NEW — does not exist) |
| Setup file | `frontend/vitest.setup.ts` (NEW) |
| Quick run command | `cd frontend && npm test -- --run` (single pass, no watch) |
| Watch command | `cd frontend && npm test` |
| Full suite command | `cd frontend && npm test -- --run && npm run lint && npm run build` |

### Phase Requirements → Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-01-01 | `/login` renders split-screen at 1280px with mesh + form panel | manual smoke + screenshot | `npm run dev` → open `localhost:3000/login` at 1280px viewport | ❌ Manual (Wave 5) |
| UX-01-01 (mobile) | `/login` collapses to vertical stack at 360px | manual smoke | DevTools device toolbar → iPhone SE 360px | ❌ Manual (Wave 5) |
| UX-01-02 | SSO buttons render above email form with divider | unit (DOM order) | `vitest src/app/login/page.test.tsx` (NEW) | ❌ Wave 0 / Wave 4 |
| UX-01-03 | Gradient CTA shows loading text on submit | unit (Button.test.tsx already covers `loading`+`loadingText`) | `vitest src/components/ui/button.test.tsx` | ❌ Wave 1 |
| UX-01-04 | `forgot`/`reset` modes hide SSO | unit (login.test) | `vitest src/app/login/page.test.tsx` — mode switch assertion | ❌ Wave 4 |
| UX-01-04 (font swap) | Inter + JetBrains Mono load with `display: swap` (no FOIT) | manual + automated grep | `grep -E "display.*swap" .next/static/css/*.css` after `npm run build` (Next inlines this in the generated CSS) | ❌ Wave 0 / Wave 5 |
| UX-01-05 | Form-level errors use `bg-danger-soft` + `border-danger` | unit (login.test) | `vitest …login/page.test.tsx` — assert ErrorAlert class names | ❌ Wave 4 |
| UX-F-01 | Sunset CSS variables resolve on `/login` | smoke (DOM check) | `vitest …` — render LoginPage, assert `getComputedStyle(document.body).getPropertyValue('--color-bg')` returns `#0E0B1A` | ❌ Wave 0 |
| UX-F-02 | `grep -c '!important' globals.css` returns 0 (modulo reduced-motion) | grep | `awk '/prefers-reduced-motion/,/^}/' frontend/src/app/globals.css \| grep -c '!important' \| xargs -I {} test $((`grep -c '!important' frontend/src/app/globals.css` - {})) -eq 0` (see Pitfall 1) | ❌ Wave 0 / Wave 5 |
| UX-F-02 (theme swap) | Setting `data-theme="light"` flips body bg | unit | `vitest` — toggle attr, assert different computed `--color-bg` | ❌ Wave 0 |
| UX-F-03 | Shell renders sidebar + topbar | unit (shell.test) | `vitest src/components/shell/app-shell.test.tsx` (NEW, optional — D-30 only requires primitive tests, but shell is core UX-F-03 surface) | ❌ Wave 3 |
| UX-F-03 (active nav) | Active nav item matches pathname prefix | unit | mock `usePathname`, assert active class | ❌ Wave 3 |
| UX-F-04 | Button has all states (default / hover / focus-visible / disabled / loading / error) with no axe violations | unit + axe | `vitest src/components/ui/button.test.tsx` | ❌ Wave 1 |
| UX-F-04 | Input has all states + password eye-toggle | unit + axe | `vitest src/components/ui/input.test.tsx` | ❌ Wave 1 |
| UX-F-04 | SsoButton renders both providers + a11y | unit + axe | `vitest src/components/ui/sso-button.test.tsx` | ❌ Wave 1 |
| UX-F-04 | GradientText applies gradient styles | unit | `vitest src/components/ui/gradient-text.test.tsx` | ❌ Wave 1 |
| Submit against `/auth/login` (UX-01 §5 in roadmap) | Login form submits and routes to `/dashboard` | manual smoke | `npm run dev` + valid credentials | ❌ Manual (Wave 5) |
| Phase 9 success criterion §6 (shell behind protected routes) | `/dashboard` renders inside `(authed)` shell after login | manual smoke | login → land on `/dashboard`, observe sidebar | ❌ Manual (Wave 5) |
| `?next=` preservation | `/login?next=/dashboard/vulnerabilities` → after login, lands at `/dashboard/vulnerabilities` | manual smoke | open URL when unauthed → log in → verify landing | ❌ Manual (Wave 5) |
| Open-redirect mitigation | `/login?next=//evil.com` → after login, lands at `/dashboard` (not evil.com) | unit | `vitest …login/page.test.tsx` — assert sanitization function | ❌ Wave 4 |

### Sampling Rate
- **Per task commit:** `cd frontend && npm test -- --run --reporter=dot` (quick — primitives only ≈ 30s)
- **Per wave merge:** `npm test -- --run && npm run lint && npm run build` (full — includes Next build for FOUC + bundle-size sanity, ≈ 90s)
- **Phase gate (verify-work):** Full suite green + manual smoke checklist for the items marked "Manual" above

### Wave 0 Gaps
- [ ] `frontend/vitest.config.mts` — Vitest entry config (NEW)
- [ ] `frontend/vitest.setup.ts` — RTL + axe matcher install (NEW)
- [ ] `package.json` `test` script — `"test": "vitest"` (NEW; doesn't exist)
- [ ] Framework + companion install: `npm i -D vitest @vitejs/plugin-react vite-tsconfig-paths jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event vitest-axe`
- [ ] Smoke test fixture or example test: ensure CI gets at least one passing test before primitives land
- [ ] CI integration: re-running `npm test` in `.github/workflows/ci.yml` (NOTE: per STATE.md, CI gating is PROD-02 — deferred. Adding a `test` script that humans can run locally is sufficient for phase 9; full CI wiring waits.)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (UI surface only; backend unchanged) | Generic 401 copy (D-49); generic forgot-password success (Pitfall 9); no user enumeration |
| V3 Session Management | no (backend owns; phase 9 doesn't touch session storage) | — |
| V4 Access Control | partial — route guard for protected paths (D-50) | Client-side redirect + same-origin `?next` validation (Pattern 5; Pitfall 10) |
| V5 Input Validation | yes — all 3 forms | zod schemas (D-53); RHF resolver; HTML5 input types (`type=email`, `type=password`) |
| V6 Cryptography | no | — |
| V8 Data Protection | partial — autocomplete attrs | `autocomplete="current-password"` / `new-password` (D-48); browsers offer password manager integration |
| V14 Configuration | partial — CSP friction | Inline FOUC script requires `'unsafe-inline'` or nonce; document for future CSP rollout (Open Question 4) |

### Known Threat Patterns for `/login` + Foundation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **Open redirect via `?next=`** | Tampering | Same-origin validation: `decoded.startsWith('/') && !decoded.startsWith('//')` (Pitfall 10) |
| **User enumeration via login error** | Information Disclosure | D-49: generic `Email or password is incorrect.` Don't differentiate cases. |
| **User enumeration via forgot-password response** | Information Disclosure | Pitfall 9: always show `If that email is registered, a reset token is on its way.` regardless of backend response |
| **Password autofill leak (cross-form)** | Information Disclosure | Per-mode `autoComplete` (D-48): `email` / `current-password` / `new-password` / `off` |
| **CSRF on auth POST** | Tampering | Backend already handles (existing). No frontend changes. Same-origin POST is standard browser behavior. |
| **XSS via reflected `?next`** | Tampering / Injection | NEVER render `?next` value as HTML; only use it as a redirect target via `router.replace()` |
| **FOUC inline script bypassing CSP** | Configuration weakness | Acceptable for current state (no CSP in nginx — verify). When CSP lands (PROD-04-01, deferred), add nonce |
| **Token in localStorage (XSS-readable)** | Tampering | Inherent to existing v1; not addressed in phase 9 (backend cookie migration is OOS) |
| **Reduced-motion attack surface** | None | Honoring `prefers-reduced-motion` is purely defensive — no exploit vector |
| **Password visibility toggle leaking on shared screens** | Information Disclosure | Eye-toggle button has `aria-pressed` so screen-reader users know state; visible state is user-initiated |

**Security posture for phase 9 in one sentence:** the phase is auth-adjacent but doesn't change the auth contract — it adds two UI-side defenses (generic-error copy + same-origin redirect validation) and inherits the existing backend's session model.

## Sources

### Primary (HIGH confidence)
- `.claude/skills/sketch-findings-getvul/SKILL.md` — design contract overview
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — token system spec
- `.claude/skills/sketch-findings-getvul/references/app-shell.md` — sidebar + topbar spec
- `.claude/skills/sketch-findings-getvul/references/page-layouts.md` — split-screen + shell layout
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — error-alert pattern for /login (the consumed slice)
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — CTA, severity, status, input, chip specs
- `.claude/skills/sketch-findings-getvul/references/copy-voice.md` — copy rules for all UI text
- `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` — token file to vendor
- `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` — variant-A visual reference of last resort
- `.planning/phases/09-login-foundation/09-CONTEXT.md` — 53 locked decisions
- `.planning/REQUIREMENTS-v2.md` — UX-01 / UX-F requirement bodies
- `.planning/ROADMAP.md` Phase 9 — 7 success criteria
- Existing `frontend/src/app/{layout.tsx,login/page.tsx,globals.css,dashboard/layout.tsx}` — directly read for migration shape
- Existing `frontend/src/lib/{auth.tsx,theme.tsx}` — directly read for API surface preservation
- Existing `frontend/package.json` — verified deps + scripts
- Existing `frontend/tailwind.config.ts` — verified v1 config shape
- Next.js docs — `nextjs.org/docs/app/api-reference/components/font` (next/font), `nextjs.org/docs/app/guides/testing/vitest` (Vitest setup)
- shadcn docs — `ui.shadcn.com/docs/installation/next`, `ui.shadcn.com/docs/components-json`
- vitest-axe — `github.com/chaance/vitest-axe`, `npmjs.com/package/vitest-axe`
- npm registry (via `npm view`) — verified versions for next, react, tailwindcss, lucide-react, react-hook-form, zod, @hookform/resolvers, class-variance-authority, @radix-ui/react-slot, @radix-ui/react-dropdown-menu, vitest, @testing-library/react, jsdom, jest-axe, vitest-axe

### Secondary (MEDIUM confidence)
- Next.js dark-mode discussions — `github.com/vercel/next.js/discussions/53063` (FOUC patterns), `github.com/vercel/next.js/discussions/59500` (font-variable hot-reload bug)
- WorkOS auth guide 2026 — pattern for `?redirect=` middleware redirects
- Authgear Next.js JWT guide — query-parameter preservation
- shadcn theming docs — CSS-variable override patterns

### Tertiary (LOW confidence — verify before relying)
- The exact light-theme color palette is bespoke (no skill source); used credible warm-off-white values in Pattern 3. Confidence LOW. Flag for visual review in Phase 9 verify-work or defer entirely per D-06.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dep verified against npm registry 2026-05-12; versions current
- Architecture patterns: HIGH — sketch + skill reference is canonical for design; Next 15 patterns verified against official docs
- Pitfalls: HIGH — derived from direct codebase inspection (708 utility-class occurrences confirmed, theme.tsx mounted-gate confirmed, login/page.tsx structure confirmed) and verified library quirks (zod v4 resolver pinning, vitest-axe jsdom requirement)
- Code examples: HIGH — based on verified API surfaces; the Button component pattern derives directly from shadcn's generated output
- Security domain: HIGH — threats mapped to documented OWASP patterns; mitigations match D-49 and Pattern 5 (Pitfall 10) recommendations
- Validation architecture: HIGH — test infrastructure is greenfield (no `test` script exists); commands documented are runnable

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (~30 days; package versions current as of research date but the JS ecosystem moves fast)
