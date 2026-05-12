# Copy & Voice

How the product speaks. Tone, sentence shape, formatting conventions, do's and don'ts. Cross-cutting from every sketch.

## Voice — short summary

**A peer, not a butler.** Direct, technical, friendly. Treats the analyst as a competent professional, not someone who needs hand-holding. Uses domain vocabulary without explanation (CVE, CVSS, CISA KEV, SLA, RCE, sshd, runc — all assumed known).

Reference points:
- **Like Linear, Vercel, GitHub** — short sentences, technical precision, occasional dry wit
- **Not like Mailchimp, Slack** — no exclamation marks, no "Hey there!", no emoji as decoration
- **Not like AWS Console** — no walls of unbroken text, no "Please refer to documentation"
- **Not like Wiz marketing** — no "transform your security posture" / "AI-powered" / vendor superlatives

## Tone matrix

| Situation | Tone |
|---|---|
| Normal screen content (titles, descriptions) | Plain, declarative |
| Empty state | Helpful, slightly playful ("Nothing matches all 5 filters. That's a tight net…") |
| Error state | Honest, specific (HTTP code shown; "Tenable connector is unreachable" not "Something went wrong") |
| Success / completion | Brief, no celebration ("✓ Signed in", "Ticket created") |
| Urgency | Direct, numeric, no panic ("3 critical CVEs need your eyes") |

## Headlines & titles

Sentence case, never title case. Trailing punctuation only when grammatically required.

✓ `Vulnerabilities` — page title
✓ `Welcome back` — login header
✗ `Welcome Back!` — wrong (title case + exclamation)
✗ `Welcome Back.` — wrong (period on a title)

### Dashboard hero

The headline is **always a number + what the analyst should do**:

✓ `3 critical CVEs need your eyes`
✗ `Dashboard` (boring)
✗ `Security Overview` (corporate)
✗ `Welcome to GetVul!` (no exclamation, no welcome)

### Login tagline

Sub-mark of the brand: positions the product, doesn't sell it.

✓ `See your security posture without opening another tool.`

Period at end is OK on a marketing-flavored statement. Span the closing phrase in the sunset gradient for emphasis.

## Microcopy

### Buttons

Verb phrases. Imperative. Never "Submit", never "Click here".

✓ `Sign in` · `Create one` · `Start triage` · `Open in Jira` · `Retry now` · `Snooze 24h`
✗ `Submit` · `OK` · `Click here` · `Save my filter`

CTAs frequently have an icon prefix (zap for triage, ticket-plus for ticket creation, check for completion).

### Form labels

Single nouns or noun phrases. Sentence case.

✓ `Email` · `Password` · `Full name` · `Reset token`
✗ `Your Email Address` · `Enter your password here`

### Placeholders

A realistic example, not a description:

✓ `you@company.com` · `Min 8 characters` · `Paste token from email` · `Ana Sokolova`
✗ `Enter your email address` · `Please enter password` · `Type your name`

### Helper text below inputs

Used only when truly necessary. One sentence.

✓ `Must include a number and an uppercase letter.`
✓ `We'll send a reset token to this address.`

### Error messages (form-level)

Specific, not generic. Tell the user what to do.

✓ `Incorrect email or password. Try again or use SSO.`
✓ `This email is already registered. Sign in instead.`
✗ `Authentication failed`
✗ `Error: Invalid credentials.`

## Empty state copy

Three sections:

1. **Headline** — what zero means in this context, often with the count of active filters
2. **Body** — explains WHY (the conjunction that produced zero)
3. **Lightbulb hint** — opportunity, not pity

Example:

> **Nothing matches all 5 filters**
>
> No vulnerabilities are simultaneously Critical or High *and* on CISA KEV *and* have an active exploit *and* from Tenable *and* contain "hyperion." That's a tight net — relax one or two and try again.
>
> 💡 This is a sharp query. Save it as "Hyperion KEV watch" — you'll be notified when anything matches.

## Error state copy

Specific. Actionable. Includes a request ID + HTTP code by default.

Example:

> **Tenable connector is unreachable**
>
> Last successful sync: 2h 14m ago · HTTP 503 Service Unavailable · Tried 3 times · Request ID `req_8f2a91c`

Buttons: `View trace` and `Retry now`. Never `OK` or `Dismiss`.

For partial-failure scenarios, always end with the partial-data caveat repeated at the bottom of the data:

> ⚠ Some results may be incomplete because Tenable hasn't responded since 2h 14m ago. [Retry Tenable] or [view connector logs].

## Activity timeline copy

```
{Actor} {verb} {ref}
{time}
```

✓ `Ana created ticket JIRA-2841 · 1h ago`
✓ `Qualys detected CVE-2024-3094 · 12m ago`
✓ `Diego commented: "Apt repos updated, rolling restart at 17:00 UTC" · 28m ago`
✓ `Jira status changed: Open → In progress · 28m ago`

Actor names are first-name-only for humans, full product names for systems (Qualys, Tenable, AWS Inspector, Jira).

## Sentence-level rules

- **One verb per sentence.** Hard cap.
- **Numbers in numerals, not words** (`3 critical`, never `three critical`)
- **Mono for anything that looks like a path/value** — CVE IDs, hostnames, durations, file paths, HTTP codes, request IDs
- **Em-dashes for compound clauses**, not commas, when the second clause modifies the first dramatically:
  - ✓ `Top one is on prod-db-01 — Postgres path, CVSS 9.8, exploited in the wild.`
- **No exclamation marks.** Ever. (Possible exception: a one-time celebratory toast for first-ticket-resolved, deferred.)
- **No "Please"** in UI copy. We're not begging.
- **No "Unable to" / "Cannot"** — say what happened. `Tenable connector is unreachable` not `Unable to reach Tenable`.

## Quantities and time

- `12m ago` not `12 minutes ago`
- `2h 14m ago` not `2 hours 14 minutes ago` or `~2 hours ago`
- `3d left` not `3 days left`
- `−2h SLA` for overdue items (the minus sign communicates "past due")
- Counts always numeric, never spelled out
- Big counts: `1,247` with thousands separator
- Percentages: `90%` (no space)

## "We" and "you"

- **"We"** — the system / GetVul, used sparingly: `We'll send a reset token…`
- **"You"** — addressing the analyst, used when describing actions: `3 critical CVEs need your eyes`
- Avoid "the user" — speak directly to them

## What NOT to say

- No "Welcome back, {name}!" — patronizing
- No "Loading…" alone — show what's loading and how much
- No "Something went wrong" — name what failed
- No "Are you sure?" without specifying what — `Mark JIRA-2841 as completed?` not `Are you sure?`
- No "Click here" — use the verb (`See all`, `View report`, `Open in Jira`)
- No "in order to" — use `to`
- No "utilize" — use `use`
- No "leverage" — use `use` or remove the word
- No "robust" — use a specific quality (`reliable`, `validated`, `tested`)

## Brand voice in the visual side of /login

The tagline + product peek + footer-strip together convey: "We're a tool, not a SaaS marketing site."

- Tagline: a *capability* statement, not a *value proposition*
- Product peek (the floating vuln rows): shows real CVEs with real assets, not lorem ipsum or made-up examples
- Footer strip: `SOC 2 Type II · Self-hosted or SaaS · v0.1` — credentials and version, no taglines

## Origin

Codified from sketch examples — copy lifted directly from 001 (tagline + form labels), 002 (urgency headline), 004 (empty + error states), 006 (timeline). Each line of copy in the sketches was treated as a real production candidate.
