# Phase 9: `/login` + Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 09-login-foundation
**Areas discussed:** Token + theme plumbing, Primitive build strategy, Shell scaffold scope, Login content + modes

---

## Token + theme plumbing

### Q1 — Where does sunset.css live in the codebase?

| Option | Description | Selected |
|--------|-------------|----------|
| Vendor sunset.css as a file | Copy skill `sources/themes/sunset.css` to `frontend/src/styles/sunset.css` and `@import` from `globals.css`. | ✓ |
| Inline into globals.css | Paste sunset variables directly into `:root[data-theme="dark"]`. | |
| Generate via build step | Generate `globals.css` from a tokens.json. | |

### Q2 — How is the active theme set on the document?

| Option | Description | Selected |
|--------|-------------|----------|
| `data-theme` attribute (per spec) | Rewire `ThemeProvider` to set `data-theme="dark|light"` on `<html>`. | ✓ |
| Keep `.dark` / `.light` class | Current behaviour. | |
| Both — class + data-theme | Belt-and-braces. | |

### Q3 — How do Tailwind utilities consume sunset tokens?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend theme with `var()` colors | `theme.extend.colors` references `var(--color-*)`. | ✓ |
| Arbitrary values everywhere | `bg-[var(--color-pink)]` literal. | |
| Upgrade to Tailwind v4 | Native CSS-var theming. | |

### Q4 — What happens to existing v1 shadcn-style HSL vars?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep, redefine to sunset equivalents | v1 HSL names stay, point at sunset vars. | |
| Keep unchanged — sunset alongside | Both coexist. | |
| Delete + find-replace consumers now | Sweep entire frontend; delete HSL vars. | ✓ |

### Q5 — How far does the v1 HSL-var deletion sweep go?

| Option | Description | Selected |
|--------|-------------|----------|
| Full sweep — every frontend file | Touch all of `frontend/src/`. | ✓ |
| Phase 9 surface only + shim | Compat-shim block for v1 screens. | |
| Reverse — keep v1 vars | Sunset only on rebuilt screens. | |

### Q6 — Light theme scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Architecture only, dark looks right | Light block exists with credible mappings; only dark QA'd. | ✓ |
| Both themes polished now | Hand-tune light palette. | |
| Dark only, no light block | Skip `[data-theme="light"]`. | |

### Q7 — Font loading?

| Option | Description | Selected |
|--------|-------------|----------|
| `next/font/google` with CSS vars | `Inter({ variable: '--font-sans', display: 'swap' })` + JetBrains_Mono equivalent. | ✓ |
| `next/font/local` with vendored woff2 | Self-host. | |
| Plain `@font-face` | No next/font. | |

### Q8 — Token families shipped in phase 9?

| Option | Description | Selected |
|--------|-------------|----------|
| Full sunset.css ships now | All token families. | ✓ |
| Only what `/login` + shell consume | Strip; add later. | |
| Foundation now, severity/status later | Hybrid. | |

### Q9 — Tailwind extend scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Colors + spacing + radius + shadow + fontFamily | Standard utility set. | ✓ |
| Minimal — colors only | Arbitrary for everything else. | |
| Maximal — also transitionTimingFunction + transitionDuration | Full motion-utility fidelity. | |

### Q10 — Sunset gradient application?

| Option | Description | Selected |
|--------|-------------|----------|
| Tailwind utility classes (extended) | `backgroundImage` extend; `bg-gradient-sunset`. | ✓ |
| CSS utility classes in globals.css | `.gradient-sunset` / `.gradient-text`. | |
| Inline `style` prop | Local. | |

### Q11 — Severity / status / SLA / provider tokens as Tailwind utilities?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — extend `colors` with each | `bg-severity-critical` resolves. | ✓ |
| No — raw `var()` only | Used inside primitives only. | |
| Mixed — severity yes, others later | | |

### Q12 — Focus-visible style?

| Option | Description | Selected |
|--------|-------------|----------|
| 2px violet outline + 2px offset | Global `*:focus-visible`. | ✓ |
| Sunset-gradient ring | Cosmetically richer. | |
| Browser default | Don't touch outline. | |

### Q13 — `prefers-reduced-motion` implementation?

| Option | Description | Selected |
|--------|-------------|----------|
| Global media query in globals.css | Universal `@media` rule. | ✓ |
| Per-component motion gating | `useReducedMotion()` per component. | |
| Defer to phase 15 | UX-07-04. | |

### Q14 — FOUC-prevention blocking script?

| Option | Description | Selected |
|--------|-------------|----------|
| Now — inline `<script>` in `<head>` | Read localStorage; set data-theme pre-hydration. | ✓ |
| Defer to phase 15 | UX-07-05. | |

### Q15 — Selection + scrollbar styling?

| Option | Description | Selected |
|--------|-------------|----------|
| Both styled to sunset | Pink `::selection` + sunset scrollbar. | ✓ |
| Selection only | Custom pink selection. | |
| Neither — platform defaults | | |

### Q16 — Where do animation keyframes live?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 9 globals.css — all upfront | All 4 keyframes defined once. | ✓ |
| Each phase adds the keyframes it consumes | Per-phase. | |

### Q17 — Tailwind plugins?

| Option | Description | Selected |
|--------|-------------|----------|
| None — ship plain Tailwind 3.4 | No forms/typography/animate plugins. | ✓ |
| Add `@tailwindcss/forms` | Form reset. | |
| Add `tailwindcss-animate` | Animation utilities. | |

### Q18 — Existing `!important` blocks in globals.css?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete the entire current globals.css | Wholesale rewrite. | ✓ |
| Strip `!important` lines only | Keep utility blocks. | |

---

## Primitive build strategy

### Q19 — shadcn/ui bootstrap?

| Option | Description | Selected |
|--------|-------------|----------|
| Run `shadcn init` + add `button` + `input` | Use the CLI; customize. | ✓ |
| Hand-build to shadcn API shape | Match contract; no CLI. | |
| All-custom — no shadcn surface | | |

### Q20 — Variant API?

| Option | Description | Selected |
|--------|-------------|----------|
| CVA + clsx (shadcn standard) | | ✓ |
| `tailwind-variants` | | |
| Plain string concat + helper | | |

### Q21 — Form library?

| Option | Description | Selected |
|--------|-------------|----------|
| `react-hook-form` + `zod` + shadcn `Form` | Compound `FormField`/`FormItem`/... | ✓ |
| Plain `useState` + manual validation | Current v1 pattern. | |
| Defer to phase 14 | | |

### Q22 — GradientText: component or utility class?

| Option | Description | Selected |
|--------|-------------|----------|
| React component | Polymorphic via `as` prop. | ✓ |
| CSS utility class only | `.gradient-text`. | |
| Both — component wrapping the class | | |

### Q23 — Button loading-state API?

| Option | Description | Selected |
|--------|-------------|----------|
| `loading` boolean + auto-spinner | + optional `loadingText`. | ✓ |
| Consumer renders the spinner | | |
| Separate `<LoadingButton>` primitive | | |

### Q24 — Icon library + how icons enter Button?

| Option | Description | Selected |
|--------|-------------|----------|
| lucide-react; `leftIcon` / `rightIcon` props | | ✓ |
| lucide-react; JSX children composition | `[&>svg]:` selectors. | |
| Inline SVG sprites | | |

### Q25 — SsoButton API?

| Option | Description | Selected |
|--------|-------------|----------|
| Single component, `provider` prop | `<SsoButton provider="google" />` | ✓ |
| Two named exports | `<GoogleSsoButton />` etc. | |
| Polymorphic with `mark` + `children` slot | | |

### Q26 — Password show/hide handling?

| Option | Description | Selected |
|--------|-------------|----------|
| Single `<Input type="password">` with built-in eye-toggle | | ✓ |
| Plain `<Input>`; consumer adds the toggle | | |
| Separate `<PasswordInput>` primitive | 5th primitive. | |

### Q27 — Error state UI?

| Option | Description | Selected |
|--------|-------------|----------|
| Input red border + inline FormMessage; form-level bar above SSO | Both field-level + form-level. | ✓ |
| Inline only | Field-level only. | |
| Form-level bar only | | |

### Q28 — Folder + filename convention?

| Option | Description | Selected |
|--------|-------------|----------|
| shadcn default — kebab-case flat | `components/ui/button.tsx` etc. | ✓ |
| PascalCase flat | `Button.tsx` etc. | |
| Per-component folder | | |

### Q29 — Tests for the 4 primitives?

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest + Testing Library smoke + axe-core a11y | Per primitive. | ✓ |
| Playwright snapshot tests | | |
| Manual QA only | Defer automation to phase 15. | |

### Q30 — Preview surface (no Storybook)?

| Option | Description | Selected |
|--------|-------------|----------|
| Dev-only `/dev/primitives` route | Gated by NODE_ENV. | ✓ |
| No preview surface | | |
| Markdown gallery in repo docs | | |

### Q31 — `cn()` helper composition?

| Option | Description | Selected |
|--------|-------------|----------|
| clsx + tailwind-merge (shadcn default) | `twMerge(clsx(...))`. | ✓ |
| clsx only | | |

### Q32 — Spinner — primitive or inline in Button?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline SVG inside Button | Promote to `<Spinner>` later. | ✓ |
| 5th primitive `<Spinner>` | Now. | |

### Q33 — `asChild` polymorphism?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — Button supports `asChild` | `@radix-ui/react-slot`. | ✓ |
| No | Always `<button>`. | |

### Q34 — `or with email` divider?

| Option | Description | Selected |
|--------|-------------|----------|
| One-off in `/login` markup | | ✓ |
| Ship `<Divider>` as a 5th primitive | | |

---

## Shell scaffold scope

### Q35 — Where does the shell live?

| Option | Description | Selected |
|--------|-------------|----------|
| Route group `(authed)/layout.tsx` | All authed routes moved into the group. | ✓ |
| Per-route layout files | | |
| Single root layout, conditional | | |

### Q36 — Nav items — real wiring vs stubs?

| Option | Description | Selected |
|--------|-------------|----------|
| Real `<Link>`s + active state via `usePathname()`; counts as `—` placeholder | | ✓ |
| Real wiring + real counts now | | |
| Inert placeholders | | |

### Q37 — Topbar functionality?

| Option | Description | Selected |
|--------|-------------|----------|
| Visual scaffold only — nothing functional | ⌘K + bell + help inert; user chip wired separately (Q39). | ✓ |
| User chip wired to logout + theme toggle | | |
| Full ⌘K palette + bell wiring | | |

### Q38 — Mobile collapse?

| Option | Description | Selected |
|--------|-------------|----------|
| Desktop-only with `min-width: 1000px` CSS guard | No hamburger yet. | ✓ |
| Ship hamburger + drawer now | | |
| Desktop-only; no mobile CSS handling | | |

### Q39 — User chip interactivity?

| Option | Description | Selected |
|--------|-------------|----------|
| Real user data + dropdown (logout + theme toggle) | `shadcn add dropdown-menu`. | ✓ |
| Real user data + sign-out icon button only | | |
| Fully inert chip | | |

### Q40 — Active-route matching?

| Option | Description | Selected |
|--------|-------------|----------|
| Prefix match | `pathname.startsWith(item.href)`. | ✓ |
| Exact match | | |
| Custom per-item matcher | | |

### Q41 — Existing v1 dashboard pages inside new shell?

| Option | Description | Selected |
|--------|-------------|----------|
| Strip per-page wrappers; shell owns container | | ✓ |
| Keep v1 wrappers — nested containers | | |
| Hide behind feature flag | | |

### Q42 — Brand mark + breadcrumb scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Brand → `/dashboard`; breadcrumbs deferred to phases 12+ | | ✓ |
| Brand → `/dashboard`; ship breadcrumb primitive now | | |
| Brand inert; breadcrumbs deferred | | |

### Q43 — Canonical route paths?

| Option | Description | Selected |
|--------|-------------|----------|
| Canonicalize on `/dashboard/...`; delete root-level duplicates | | ✓ |
| Canonicalize on root paths; delete `/dashboard/*` duplicates | | |
| Investigate first | | |

### Q44 — Lucide icon mapping?

| Option | Description | Selected |
|--------|-------------|----------|
| Match sketch literally (Home / Bug / Server / Cloud / Ticket / Plug / Users / Settings) | | ✓ |
| Pick alternates | | |

### Q45 — Theme toggle UX in dropdown?

| Option | Description | Selected |
|--------|-------------|----------|
| Two menu items with check marks (DropdownMenuRadioGroup) | | ✓ |
| Single toggle row with switch | Needs Switch primitive. | |
| No toggle until phase 15 | | |

---

## Login content + modes

### Q46 — Self-serve registration?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove — admin-seeded users only | | ✓ |
| Keep behind env flag | | |
| Keep visible (current v1) | | |

### Q47 — Forgot/reset — modes or routes?

| Option | Description | Selected |
|--------|-------------|----------|
| In-form modes (current pattern) | State machine + `?reset=TOKEN` deep link. | ✓ |
| Separate routes | `/forgot-password` + `/reset-password` pages. | |
| Modes for forgot; route for reset | Asymmetric. | |

### Q48 — Product-peek vuln rows source?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-coded sample in the page component | Real public CVEs. | ✓ |
| Static JSON fixture in `lib/marketing-peek.ts` | | |
| Drop the peek rows | | |

### Q49 — Left-panel marketing copy?

| Option | Description | Selected |
|--------|-------------|----------|
| Verbatim from the 001-login-sunset sketch | | ✓ |
| Draft new copy tuned to the product | | |
| Minimal — brand name + single tagline | | |

### Q50 — SSO button copy?

| Option | Description | Selected |
|--------|-------------|----------|
| `Continue with Google` / `Continue with Microsoft` | Verbatim sketch. | ✓ |
| `Sign in with Google` / `Sign in with Microsoft` | | |
| Provider name only | | |

### Q51 — Mode-switch links + headings?

| Option | Description | Selected |
|--------|-------------|----------|
| Login: `Forgot password?` below password; Forgot: `Back to sign in`; Reset: deep-link only | | ✓ |
| Forgot link in form footer only | | |
| Mode tabs at the top of the form | | |

### Q52 — autoFocus + autocomplete?

| Option | Description | Selected |
|--------|-------------|----------|
| `autoFocus` on email + `autoComplete="email|current-password|new-password"` | | ✓ |
| Autocomplete only, no autoFocus | | |
| Neither | | |

### Q53 — Error message for failed login (401)?

| Option | Description | Selected |
|--------|-------------|----------|
| Generic — `Email or password is incorrect` | Anti-enumeration. | ✓ |
| Pass through backend message | | |
| Differentiate `user not found` vs `wrong password` | | |

### Q54 — Redirect-after-login?

| Option | Description | Selected |
|--------|-------------|----------|
| Honor `?next=/path` if present, default `/dashboard` | | ✓ |
| Always `/dashboard` | | |

### Q55 — SSO failure UX?

| Option | Description | Selected |
|--------|-------------|----------|
| Surface in the form-level error bar | | ✓ |
| Inline next to the failed button | | |
| Silent (current v1) | | |

### Q56 — Per-mode submit button copy?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-mode action verbs (`Sign in` / `Send reset link` / `Set new password`) | | ✓ |
| Generic `Continue` everywhere | | |

### Q57 — Form validation timing?

| Option | Description | Selected |
|--------|-------------|----------|
| Submit-time only, server is source of truth | `mode: 'onSubmit'`. | ✓ |
| Live (`onChange`) | | |
| On blur | | |

---

## Claude's Discretion

Captured in CONTEXT.md `<decisions>` § "Claude's Discretion" — areas where the user explicitly deferred to Claude:
- Exact spacing of sample-CVE rows on the left panel
- Tailwind colors-extend naming convention for severity / status / SLA tokens
- FOUC-prevention script location (inline `<script>` vs `<Script strategy="beforeInteractive">`)
- Test fixture colocation (.test.tsx next to primitives vs `__tests__/`)
- Whether `lib/auth.tsx` `loginSSO` error handling is updated in-place or via a wrapper
- Specific CVE entries on the left panel (xz-utils / log4shell / spring4shell etc.)
- Route-guard implementation (`middleware.ts` vs server-component check in `(authed)/layout.tsx`)
- Whether to ship a small `<EmailSentConfirmation>` view inside forgot mode

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section — surfaced during discussion but explicitly out-of-phase-9 scope.
