# Phase 36 — External API Coverage Matrix

**Decided:** 2026-08-13 · **Enforced at seal time** (API-integrating phase cannot seal without a decided matrix).

This phase integrates four outbound escalation channels via webhooks/API-key + SMTP (D-04 — no OAuth apps).
Every capability below is either INTEGRATE (built this phase) or OPT-OUT (with a one-line reason).

Single-header table (one `| capability | decision | reason |` header for the whole matrix); the `##` provider lines are prose section markers, not repeated headers.

| capability | decision | reason |
|------------|----------|--------|

## Slack (Incoming Webhook)

| POST message (`text` + `blocks`) on approaching/breach | INTEGRATE | Core SLA-03 escalation delivery |
| Rich block formatting (`blocks[]`) | INTEGRATE | Finding/CVE/host/tier context per RESEARCH payload shape |
| OAuth Slack app (chat.postMessage, scopes, bot token) | OPT-OUT | D-04 — webhook-only, no OAuth apps this phase |
| Threading / reply-in-thread / message update on resolve | OPT-OUT | D-13-analogue — no un-fire/resolve path this phase; alerts are fire-and-forget |
| User `@mention` / channel routing beyond the fixed channel | OPT-OUT | Incoming webhooks post to one fixed channel by design; richer routing deferred to Phase 40 (digests) |

## Microsoft Teams (Workflows webhook — NOT classic connector, D-15)

| POST message to a Workflows `webhook.office.com` URL on approaching/breach | INTEGRATE | Core SLA-03; `{"text": ...}` payload; classic connector retired (D-15 / Pitfall 7) |
| Adaptive Card envelope (`attachments[].contentType=adaptive`) | INTEGRATE | Best-effort — Workflows supports Adaptive/MessageCard; simple `text` is the guaranteed-render fallback |
| Classic Office 365 "Incoming Webhook" connector (MessageCard) | OPT-OUT | D-15 — retired by Microsoft (`outlook.office.com`), new connectors blocked; admin copy targets Workflows |
| OAuth Teams app / Graph API posting | OPT-OUT | D-04 — webhook-only |
| Rate-limit backoff on 429 (4 req/s per webhook) | INTEGRATE | Reuse `okta_sync.py::_request_with_retry` 429 shape (Pitfall 7 rate limit) |

## PagerDuty (Events API v2)

| `event_action=trigger` with stable `dedup_key` on approaching/breach | INTEGRATE | Core SLA-03; `dedup_key=getvul:{vuln_id}:{to_state}` mirrors local once-only gate |
| `payload.severity` enum (critical/error/warning/info) + `custom_details` | INTEGRATE | Required trigger fields per RESEARCH-cited contract |
| `event_action=resolve` on remediation / un-breach | OPT-OUT | **D-13** — not needed yet; incidents require manual resolution; documented in admin pane copy + `escalation_channels.py` comment |
| `event_action=acknowledge` | OPT-OUT | D-13-analogue — no ack lifecycle this phase |
| OAuth / REST API incident management (list/close via API) | OPT-OUT | D-04 — Events API integration-key only, no OAuth app |

## Email (SMTP — existing `app/email.py`)

| Send escalation email via existing `send_email(smtp_config=...)` | INTEGRATE | Reuse fully-built SMTP path (Don't Hand-Roll) — zero new integration |
| TLS/STARTTLS/attachments | INTEGRATE | Inherited — already handled by `email.py`; no new code |
| Retroactive Fernet re-encryption of pre-existing `smtp_config.password` | OPT-OUT | D-14 — out of scope; only NEW channel secrets are Fernet-encrypted |

**All OPT-OUTs carry a reason. Matrix decided.**
