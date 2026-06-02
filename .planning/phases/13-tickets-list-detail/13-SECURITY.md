---
phase: 13
slug: tickets-list-detail
status: verified
threats_open: 0
asvs_level: 2
created: 2026-06-02
---

# Phase 13 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verified by gsd-security-auditor against the live codebase (33/34 closed on first pass;
> T-13-09 closed after adding `extra="forbid"` to the request schemas in commit 32bad5c).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Browser → FastAPI | Authenticated analyst session calling ticket list/detail/mutation routes | ticket filters, comment bodies, blocked reasons, watch toggles (per-tenant) |
| FastAPI → Postgres | Tenant-scoped reads/writes of tickets, comments, watchers | ticket/comment/watcher rows, all carrying `tenant_id` |
| FastAPI → Provider APIs (Jira/GitHub) | Outbound connector stubs (auth + create + read-back) | provider credentials (decrypted in-memory), issue payloads |
| URL params → React | Chip filters and `?ticket=`/`?cve=` drill keys reflected into client state | filter axis values, ticket/cve identifiers |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-13-01 | Tampering | comment body / blocked_reason | mitigate | `schemas.py:164,183` Field min/max length + `@field_validator` strip; stored plain text | closed |
| T-13-02 | Info Disclosure | 027 backfill UPDATE | accept | `027_*.py:39-47` joins tenant-owned `tickets.vulnerability_id = vulnerabilities.id`; no cross-tenant path | closed |
| T-13-03 | Tampering | TicketWatcher composite PK | mitigate | `models.py:143` / `028_*.py:41` `PrimaryKeyConstraint(ticket_id,user_id)` idempotency | closed |
| T-13-04 | Info Disclosure | provider tokens in logs | mitigate | `jira_client.py` / `github_client.py` structlog emits status/url/error only — never token | closed |
| T-13-05 | Info Disclosure | provider tokens at rest | transfer | `router.py:60,73` tokens via `get_decrypted_credentials` (existing `credentials_secret_arn` infra) | closed |
| T-13-06 | SSRF | Jira base_url (user domain) | accept | Admin-CLI config only in P13, no user-input surface; domain allow-list deferred to P14 | closed |
| T-13-07 | DoS (rate limit) | outbound 429 | mitigate | `jira_client.py:128-132` / `github_client.py:96-100` single Retry-After sleep+retry-once, no loop | closed |
| T-13-08 | Info Disclosure / Elevation | cross-tenant ticket/comment via crafted {id} | mitigate | `router.py:451-460` `_resolve_group` tenant filter → 404; called on every route (480,523,567,605,636,679) | closed |
| T-13-09 | Tampering | mass assignment on blocked/comment | mitigate | Explicit field assignment (`router.py:526-529,570-577`, no `**model_dump()`) **+ `model_config={"extra":"forbid"}` on CommentCreate/BlockedUpdate** (commit 32bad5c) → 422 on extras; regression test `test_post_comment_extra_field_422` | closed |
| T-13-10 | Repudiation | audit loss on mutation | mitigate | `router.py:533,580,615,646` `audit()` BEFORE `db.commit()`, fail-closed, no suppressing except | closed |
| T-13-11 | Tampering / Stored XSS | comment body, blocked_reason | mitigate | Backend validates+bounds; `models.py:128` Text plain; `activity-timeline.tsx:111` React text node | closed |
| T-13-12 | Input validation | malformed path id | mitigate | `router.py` all `ticket_id: uuid.UUID` → 422 not 500 | closed |
| T-13-13 | Tampering | watcher row duplication | mitigate | `router.py:607-612` `on_conflict_do_nothing(ticket_id,user_id)` | closed |
| T-13-14 | Tampering / XSS | externalStatus / provider strings | mitigate | `provider-mark.tsx:17-21` / `status-pill.tsx:27-44` literal lookup, unknown → neutral default | closed |
| T-13-15 | Info Disclosure | presentational components | accept | No secrets; components receive already-authorized display data | closed |
| T-13-16 | Tampering | "Open in provider" anchor | mitigate | `ticket-drill-content.tsx:218-222` `rel="noopener noreferrer"`; backend-controlled URL | closed |
| T-13-17 | Tampering | crafted ?ticket= param | mitigate | `page.tsx:139-142` uuid-keyed find; drill renders only on matching row; no var/class from raw param | closed |
| T-13-18 | DoS / regression | drill chrome refactor | mitigate | Additive-only props + vuln-preserving defaults; unmodified vuln drill tests = regression gate | closed |
| T-13-19 | Tampering / Stored XSS | comment body + watcher name in timeline/stack | mitigate | `activity-timeline.tsx:111` / `watcher-stack.tsx:107-111` React text nodes; no dangerouslySetInnerHTML | closed |
| T-13-20 | Tampering | oversize comment/reason | mitigate | `comment-input.tsx:20` maxLength 10000 / `blocked-toggle.tsx:39` maxLength 500 mirror backend | closed |
| T-13-21 | Input validation | whitespace-only comment/reason | mitigate | `comment-input.tsx:31-32` trim+disable; `blocked-toggle.tsx:64` coerces to null | closed |
| T-13-22 | Tampering | reflected XSS via chip URL params | mitigate | `tickets-chip-bar.tsx:21-24` hardcoded allowLists; `use-url-state-list.ts:28,38` clamp read+write | closed |
| T-13-23 | Tampering | mass assignment on mark-blocked | mitigate | `use-mark-blocked.ts:43` sends only `{blocked, blocked_reason}` | closed |
| T-13-24 | Info Disclosure | error message leakage | accept | `page.tsx:278-281` full err.message → PartialFailureBanner visual truncation; backend scrubs server-side | closed |
| T-13-25 | Access control | ticket data tenant scope | mitigate | `service.py:684` `tenant_id` base filter; `_resolve_group` enforces on detail/mutation | closed |
| T-13-26 | Tampering | mass assignment on add-comment / watch | mitigate | `use-ticket-comments.ts:63-66` sends only `{body}`; `use-ticket-watch.ts:39-41` method-only, no body | closed |
| T-13-27 | Tampering / Stored XSS | comment body + description on detail page | mitigate | `[id]/page.tsx:303-304` + `activity-timeline.tsx:111` React text nodes; zero dangerouslySetInnerHTML | closed |
| T-13-28 | Info Disclosure | cross-tenant detail via crafted id | accept | Backend `_resolve_group` → 404; `[id]/page.tsx:183-201` not-found state | closed |
| T-13-29 | Info Disclosure | error leakage on detail load | accept | Same control as T-13-24 (PartialFailureBanner visual truncation) | closed |
| T-13-30 | Repudiation | optimistic-rollback integrity | mitigate | `use-ticket-comments.ts:70-95` / `use-ticket-watch.ts:43-89` onMutate snapshot + onError restore; backend audit authoritative | closed |
| T-13-31 | Tampering | reflected XSS via rules chip params | mitigate | `rules/page.tsx:32-33,138` hardcoded allowList; `use-url-state-list.ts` clamps | closed |
| T-13-32 | Tampering / Stored XSS | rule name / conditions rendered | mitigate | `rules/page.tsx:103-108` React text children; no dangerouslySetInnerHTML | closed |
| T-13-33 | Access control | rules surface authz | accept | Read-only `GET /tickets/rules` (`router.py:1015` `get_current_user`); authz inherited, no new surface | closed |
| T-13-34 | Info Disclosure | error leakage on rules load | accept | Same control as T-13-24 (PartialFailureBanner visual truncation) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-13-01 | T-13-02 | Migration 027 backfill joins only tenant-owned rows (`tickets.vulnerability_id = vulnerabilities.id`); no cross-tenant leakage path. Migration runs as superuser by design. | igorchemencedji | 2026-06-02 |
| AR-13-02 | T-13-06 | Jira `base_url` is admin-CLI configured in P13 — no user-facing input surface exists yet. **P14 connector UI MUST add a domain allow-list before exposing this to users.** | igorchemencedji | 2026-06-02 |
| AR-13-03 | T-13-15 | Phase 13 presentational primitives receive only already-authorized display data; no secrets in scope. | igorchemencedji | 2026-06-02 |
| AR-13-04 | T-13-24, T-13-29, T-13-34 | Frontend passes full `err.message` to PartialFailureBanner, which truncates visually; backend already scrubs sensitive details server-side before the API layer. | igorchemencedji | 2026-06-02 |
| AR-13-05 | T-13-28 | Cross-tenant ticket detail is blocked backend-side by `_resolve_group` (404 on foreign id); the frontend only renders the authorized payload it receives. | igorchemencedji | 2026-06-02 |
| AR-13-06 | T-13-33 | `/tickets/rules` is a read-only reuse of the existing `GET /tickets/rules` route; authz + tenant scoping inherited from the established backend route. No new attack surface. | igorchemencedji | 2026-06-02 |

*Accepted risks do not resurface in future audit runs.*

> **Carry-forward to Phase 14:** AR-13-02 — the Jira `base_url` SSRF mitigation (domain allow-list) is deferred and becomes a hard requirement when the P14 connector UI exposes provider config to users.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-02 | 34 | 33 | 1 | gsd-security-auditor (ASVS L2) |
| 2026-06-02 | 34 | 34 | 0 | orchestrator (after T-13-09 `extra=forbid` fix, commit 32bad5c) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-02
