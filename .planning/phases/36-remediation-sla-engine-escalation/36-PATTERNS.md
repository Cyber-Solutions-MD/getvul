# Phase 36: Remediation SLA Engine & Escalation - Pattern Map

**Mapped:** 2026-08-13
**Files analyzed:** 17 (7 new, 10 modified)
**Analogs found:** 17 / 17 (every new file has a strong in-repo analog — this phase reuses existing infrastructure almost entirely)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/vulnerabilities/sla_tier_service.py` (NEW) | service | transform + event-driven | `backend/app/vulnerabilities/sla_service.py` | exact (role) |
| `backend/app/notifications/escalation_channels.py` (NEW) | service | request-response (outbound HTTP/SMTP) | `backend/app/connectors/okta_sync.py` `_request_with_retry` + `backend/app/email.py` | role-match |
| `backend/app/vulnerabilities/models.py` (MODIFY — 2 new models) | model | CRUD (durable event rows) | `backend/alembic/versions/044_add_risk_backfill_job.py` (`RiskExposureBackfillJob`) | exact |
| `backend/alembic/versions/046_add_sla_escalation_events.py` (NEW) | migration | schema | `backend/alembic/versions/044_add_risk_backfill_job.py` | exact |
| `backend/alembic/versions/047_add_remediation_events.py` (NEW) | migration | schema | `backend/alembic/versions/044_add_risk_backfill_job.py` | exact |
| `backend/app/vulnerabilities/schemas.py` (MODIFY) | schema | request-response | existing fields in `VulnerabilityResponse`/`VulnerabilitySummary` | exact |
| `backend/app/connectors/scheduler.py` (MODIFY) | integration/loop | event-driven (60s tick) | in-file SLA block at `scheduler.py:314-328` | exact |
| `backend/app/notifications/alerts.py` (MODIFY — reconcile) | service | event-driven | in-file `_check_sla_breaches` + `_notification_exists` | exact |
| `backend/app/tenants/router.py` (MODIFY) | route | CRUD (settings) | in-file `/settings` GET+PATCH + `_safe_smtp` | exact |
| `backend/app/vulnerabilities/service.py` (MODIFY — new helper + call sites) | service | CRUD | in-file `update_vulnerability_status` | exact |
| `backend/app/ticketing/service.py` + `ticketing/daily_sync.py` (MODIFY — route through helper) | service | CRUD | `update_vulnerability_status` | role-match |
| MTTR-by-tier aggregate (in `sla_tier_service.py` or `service.py`) | service | batch/aggregate | `backend/app/vulnerabilities/trends.py:129-159` `get_mttr_trend` | role-match |
| `frontend/src/components/settings/sla-escalation-pane.tsx` (NEW) | component | CRUD (settings form) | `frontend/src/components/settings/notifications-pane.tsx` | exact |
| `frontend/src/components/settings/microcopy.ts` (MODIFY) | config | — | in-file `Category` union + `CATEGORY_LABELS` | exact |
| `frontend/src/components/settings/settings-sidebar-shell.tsx` (MODIFY) | component | — | in-file `ALL_CATEGORIES` + `ADMIN_ONLY` | exact |
| `frontend/src/components/tickets/sla-pill.tsx` (EXTEND) | component | request-response | itself (add optional server `state` prop) | exact |
| `frontend/src/components/settings/sla-escalation-pane.test.tsx` (NEW) | test | — | `saml-pane.test.tsx` / `ai-usage-pane.test.tsx` | role-match |

> Note: `notifications-pane.tsx` (the closest structural analog for the new pane) has **no** test file — mirror its markup/logic, but mirror `saml-pane.test.tsx` for the *test* structure (RESEARCH Wave-0 note, line 660).

---

## Pattern Assignments

### `backend/app/vulnerabilities/sla_tier_service.py` (NEW — service, transform + event-driven)

**Analog:** `backend/app/vulnerabilities/sla_service.py` (module shape, tenant-config lookup, scheduler-callable async functions) + `backend/app/assets/risk_score.py` (tier constants — import, never re-derive).

**Tier constants to import** (`risk_score.py:56-61` — do NOT hardcode `80/50/20`, the constant's own comment documents that it de-triplicated three prior copies):
```python
# RISK-06 (Phase 33): centralizes the >=80/>=50/>=20 tier boundaries
RISK_SCORE_TIER_CRITICAL = 80
RISK_SCORE_TIER_HIGH = 50
RISK_SCORE_TIER_MEDIUM = 20
```

**Tenant-config lookup pattern to mirror** (`sla_service.py:27-38` — copy the "custom-or-default" merge; the new tier policy extends `Tenant.sla_config` the same way `get_sla_days` reads `sla_config["days"]`):
```python
def get_sla_days(tenant: Tenant | None) -> dict[str, int]:
    if tenant and tenant.sla_config and tenant.sla_config.get("days"):
        custom = tenant.sla_config["days"]
        return {"CRITICAL": custom.get("CRITICAL", DEFAULT_SLA_DAYS["CRITICAL"]), ...}
    return dict(DEFAULT_SLA_DAYS)
```
Keep `DEFAULT_SLA_DAYS` (`sla_service.py:18-24`) reachable as the **D-03 NULL-score fallback**; the new engine's default tier policy is a *separate* dict (critical 7 / high 30 / moderate 90). Per **D-12**, `tier_for_score` returns `None` below `RISK_SCORE_TIER_MEDIUM` → always `on_track`, no due date, no escalation. Per **D-12/Pitfall 5**, the fallback severity→tier map is an explicit tested lookup: `CRITICAL→critical, HIGH→high, MEDIUM/LOW/INFO→moderate`.

**Core state formula** (new code — RESEARCH Code Examples, lines 404-426; D-02 approaching % scales per tier automatically):
```python
def compute_sla_state(*, first_detected_at, tier_days, approaching_pct, now) -> tuple[datetime, str]:
    sla_due_at = first_detected_at + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))
    if now >= sla_due_at: return sla_due_at, "breached"
    if now >= approaching_at: return sla_due_at, "approaching"
    return sla_due_at, "on_track"
```

**Bulk-write mirror pattern** (`sla_service.py:86-101` — how `check_sla_breaches` writes `sla_breached`; the new engine writes `sla_due_at` + the `sla_breached` **derived mirror**, D-08):
```python
result = await db.execute(
    update(Vulnerability).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        Vulnerability.sla_due_at.isnot(None), Vulnerability.sla_due_at < now,
        Vulnerability.sla_breached.is_(False),
    ).values(sla_breached=True)
)
```

**Exactly-once escalation gate** (mirror `alerts.py:276-296` `_notification_exists`, but with **no time window** — D-07 is "ever fired for this exact transition+channel"):
```python
async def _escalation_already_fired(db, tenant_id, vuln_id, to_state, channel) -> bool:
    result = await db.execute(
        select(func.count(SlaEscalationEvent.id)).where(
            SlaEscalationEvent.tenant_id == tenant_id,
            SlaEscalationEvent.vulnerability_id == vuln_id,
            SlaEscalationEvent.to_state == to_state,
            SlaEscalationEvent.channel == channel,
        )
    )
    return result.scalar_one() > 0
```
Back it with the DB `UniqueConstraint(tenant_id, vulnerability_id, to_state, channel)` (see migration below) as a defense-in-depth backstop.

**MTTR-by-tier aggregate** (analog `trends.py:129-159` `get_mttr_trend` — group by tier instead of week; RESEARCH lines 549-557):
```python
select(RemediationEvent.tier_at_remediation,
       func.avg(RemediationEvent.duration_seconds).label("avg_seconds"),
       func.count().label("count")
).where(RemediationEvent.tenant_id == tenant_id).group_by(RemediationEvent.tier_at_remediation)
```
Do **not** touch the pre-existing flat MTTR queries at `service.py:571-579` / `dashboard.py:212-228` / `trends.py` (Pitfall 11 — out of scope).

---

### `backend/app/notifications/escalation_channels.py` (NEW — service, outbound request-response)

**Analog:** `backend/app/connectors/okta_sync.py` `_request_with_retry` (httpx retry shape) + `backend/app/email.py` `send_email` (email channel is already fully built — reuse, do not rebuild).

**httpx outbound + retry pattern** (`okta_sync.py:69-93` — the repo's existing hand-rolled retry convention; use `httpx.AsyncClient`, no vendor SDKs per D-04):
```python
async def _request_with_retry(client: httpx.AsyncClient, url, headers) -> httpx.Response:
    for attempt in range(1, RATE_LIMIT_MAX_RETRIES + 1):
        response = await client.get(url, headers=headers)
        if response.status_code != 429: return response
        wait = ... ; await asyncio.sleep(wait)
    return response
```
> Adapt to `.post(url, json=payload)`. Per **Pitfall 10 (SSRF)**: enforce `https://` scheme, block private/loopback/metadata targets, and construct the client with `httpx.AsyncClient(follow_redirects=False)`. Per **Pattern 1** (scheduler isolation): a channel POST failure must be caught, audited, and recorded on the escalation-event row (`delivery_status="failed"`, `error_message=...`) — it must NOT block the transition record or other tenants.

**Email channel — reuse verbatim** (`email.py:17-26` — already handles TLS/STARTTLS; the email channel is `send_email(smtp_config=tenant.smtp_config, to=[...], subject=..., body=...)`):
```python
def send_email(*, smtp_config: dict, to: list[str], subject: str, body: str, ...) -> dict:
    """Returns {"ok": True} or {"ok": False, "error": "..."}."""
```

**Channel payload shapes:** Slack `{"text":..., "blocks":[...]}` (RESEARCH 486-498); Teams **Workflows** `webhook.office.com` `{"text": "..."}` — NOT the retired classic connector, D-15 / Pitfall 7 (RESEARCH 500-518); PagerDuty Events API v2 POST `https://events.pagerduty.com/v2/enqueue` with `routing_key`/`event_action="trigger"`/`dedup_key=f"getvul:{vuln_id}:{to_state}"` (RESEARCH 521-540). Per **D-13**: PagerDuty fires on approaching/breach only — no `resolve` this phase; document the manual-resolution limitation in code + admin pane.

**Test convention:** monkeypatch the local sender function, do NOT hit real endpoints or add `respx` (RESEARCH 625; mirror `test_scheduler_enrichment_refresh.py`).

---

### `backend/app/vulnerabilities/models.py` (MODIFY — add `SlaEscalationEvent` + `RemediationEvent`)

**Analog:** `RiskExposureBackfillJob` (defined via migration `044_add_risk_backfill_job.py`) — mirror its column shape, `tenant_id` FK `ondelete="CASCADE"`, `created_at`/`updated_at` `server_default=now()`, and its use of a `UniqueConstraint` as both identity key and correctness guard (`uq_risk_backfill_job_tenant`).

Both new tables MUST carry `tenant_id` FK + index and every query filters by it (cross-tenant isolation, RESEARCH Security Domain line 699). `remediation_events` columns: `tenant_id`, `vulnerability_id`, `tier_at_remediation` (String), `duration_seconds` (Integer), `first_detected_at`, `remediated_at`, `created_at`.

---

### `backend/alembic/versions/046_add_sla_escalation_events.py` (NEW — migration)

**Analog:** `044_add_risk_backfill_job.py` (read in full). Copy: module docstring style, `revision`/`down_revision` string format (≤32 chars), `op.create_table` with `postgresql.UUID(as_uuid=True)` PK, `sa.ForeignKey("tenants.id", ondelete="CASCADE")`, `server_default=sa.text("now()")` timestamps, `sa.UniqueConstraint(...)`, and `op.create_index("ix_..._tenant_id", ...)`. `down_revision = "045_add_seen_by_sources_gin"` (current head per RESEARCH line 104). Exact table shape given in RESEARCH lines 458-481 (includes `delivery_status`/`error_message` for the failed-POST audit trail).

`047_add_remediation_events.py` chains off 046 (or combine both into one migration — **Claude's Discretion**, CONTEXT D / line 50).

---

### `backend/app/vulnerabilities/schemas.py` (MODIFY — foundational, Pitfall 3)

**Analog:** the existing optional fields already on these two models (`risk_exposure_score: int | None = None` at `schemas.py:67`).

Add `sla_state: str | None = None` + `sla_due_at: datetime | None = None` to **both** `VulnerabilityResponse` (schemas.py:27-71) and `VulnerabilitySummary` (schemas.py:74-98). FastAPI's `response_model` drops any attribute not declared on the model — the frontend `vuln-table.tsx` `slaBand()` renders `—` today because these fields are never returned (RESEARCH lines 330-334). Treat this as a **first, blocking sub-task** — D-11 depends on it. Both use `model_config = {"from_attributes": True}`.

---

### `backend/app/connectors/scheduler.py` (MODIFY — extend the tick block, don't add a scheduler)

**Analog:** the existing SLA block **in this file at `scheduler.py:314-328`** (read in full). The new tier-engine pass + transition/escalation fire replaces or wraps this block. Follow the exact isolation shape (**Pattern 1**): own `async with async_session_factory() as db:`, own `try/except Exception as e: logger.error(...)`, `await db.commit()` at the end.
```python
# scheduler.py:314-328 — the block to extend
try:
    async with async_session_factory() as db:
        tenants = (await db.execute(_sel(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
        for t in tenants:
            await backfill_sla_due_dates(db, t.id)
            await check_sla_breaches(db, t.id)   # ← reconcile vs new engine (D-08)
        await db.commit()
except Exception as e:
    logger.error("sla_check_error", error=str(e))
```
**Pitfall 2:** after changing `Vulnerability.sla_due_at`, call `recompute_ticket_sla` for every affected `external_ticket_url` (pattern below) or ticket-side `SlaPill` goes stale. Do NOT register a new scheduler (single-process asyncio constraint, RESEARCH line 67).

**Ticket-SLA resync pattern** (`ticketing/service.py:72-115` `recompute_ticket_sla`; call after `db.flush()`, before `db.commit()`):
```python
await db.flush()  # new sla_due_at values must be visible to the MIN aggregate
# for every affected external_ticket_url:
await recompute_ticket_sla(db, ticket_url, tenant_id)
```
Start with "recompute all groups" (matches admin-endpoint precedent `vulnerabilities/router.py:237-257`); optimize to only-changed-groups only if measured (**Discretion**, Open Question #5).

---

### `backend/app/notifications/alerts.py` (MODIFY — reconcile `_check_sla_breaches`, D-08 / Pitfall 1)

**Analog:** the function itself (`alerts.py:100-143`). It currently fires an in-app `category="sla_breach"` notification on a flat 24h lookahead. Retire it or gate it to a no-op so a single breach yields exactly ONE signal (the new engine's own in-app twin), never two. The new engine's in-app twin uses a **distinct** `category="sla_escalation"` (RESEARCH line 449) so tests can assert no `sla_breach`+`sla_escalation` pair lands for the same `resource_id`.

---

### `backend/app/tenants/router.py` (MODIFY — extend `/settings`, mask channel secrets)

**Analog:** in-file `_safe_smtp` (router.py:140-147) + the `smtp_config` PATCH branch (router.py:214-222) + the `sla_config` PATCH branch (router.py:202-206). RBAC is asymmetric and MUST be preserved: `GET /settings` → `require_admin` (router.py:108), `PATCH /settings` → `require_owner` (router.py:154).

**Mask-on-read** (extend `_safe_smtp` shape to the new channel secrets — Pattern 4 / D-14):
```python
def _safe_smtp(cfg):           # router.py:140-147 — the template
    safe = dict(cfg)
    if safe.get("password"): safe["password"] = "••••••••"
    return safe
```

**Keep-stored-on-masked-write** (router.py:219-221 — the "if masked, keep existing" trick to extend to Slack/Teams webhook URLs + PagerDuty routing key):
```python
if new_smtp and new_smtp.get("password") == "••••••••" and tenant.smtp_config:
    new_smtp["password"] = tenant.smtp_config.get("password", "")
```

**JSONB write + flag_modified** (router.py:202-206 — extend `sla_config` to hold tier days, approaching %, tier floor, per-transition routing, channel secrets):
```python
tenant.sla_config = body["sla_config"]
_fm_sla(tenant, "sla_config")   # flag_modified — required for JSONB in-place mutation
```

**Per D-14:** Fernet-encrypt the channel secrets at rest via `app/encryption.py` `encrypt_value`/`decrypt_value` (see Shared Patterns) — this goes *beyond* the existing plaintext `smtp_config.password` precedent (Pitfall 9). Every settings mutation goes through `audit()` (router.py:224+ already does this for the existing fields).

---

### `backend/app/vulnerabilities/service.py` + `ticketing/service.py` + `ticketing/daily_sync.py` (MODIFY — centralize remediation, D-09 / Pitfall 6)

**Analog:** `update_vulnerability_status` (service.py:325-338) — the canonical status+timestamp write:
```python
values: dict = {"status": new_status, "updated_at": now}
if new_status == "REMEDIATED":
    values["remediated_at"] = now
```
Introduce ONE helper `mark_vulnerability_remediated(db, vuln)` that sets status + `remediated_at` AND writes the `RemediationEvent` row (freezing tier-at-remediation via the same `tier_for_score` used by the engine), then route all **six** call sites through it (RESEARCH Pitfall 6 lists exact lines): `service.py:332`, `service.py:349`, `ticketing/service.py:1177-1179`, `ticketing/service.py:1326-1327`, `ticketing/daily_sync.py:243-245/:327-328/:417-418`. Missing any one silently drops MTTR data for that path.

---

### `frontend/src/components/settings/sla-escalation-pane.tsx` (NEW — component)

**Analog:** `notifications-pane.tsx` (read in full — mirror structure exactly).

**Full pattern to copy:**
- `useTenantSettings()` + `useUpdateTenantSettings()` (notifications-pane.tsx:126-127)
- `useDirtyState<T>()` with `values`/`setField`/`isDirty`/`reset` (notifications-pane.tsx:129-132; hook at `use-dirty-state.ts:34`)
- `onDirtyChange` prop reporting up (notifications-pane.tsx:120-137)
- Seed-from-settings via `useEffect(...[settings])` + `reset({...})` (notifications-pane.tsx:141-149)
- **Secret touched-flag** for webhook URLs / PagerDuty key — copy the `passwordTouched` pattern verbatim (notifications-pane.tsx:44-58, 168-175): seed field EMPTY, placeholder `'••••••••'` (`SMTP_PASSWORD_PLACEHOLDER`, line 75), include in PATCH body only when touched (D-14 mask-on-read twin)
- Mandatory states: `<SkeletonTable>` loading + `<PartialFailureBanner>` error + `<EmptyState>` (notifications-pane.tsx:32-34, 205-219) — CLAUDE.md "no screen without empty/loading/error states"
- Single `<SaveBar isDirty isSaving onSave onDiscard>` at bottom (notifications-pane.tsx:438-443; component `save-bar.tsx:29`)
- `data-pane="sla-escalation"` test hook (notifications-pane.tsx:204)
- Design tokens only — `border-border-subtle bg-surface`, `text-text`/`text-text-muted`, `bg-violet`, no raw hex (CLAUDE.md + foundation.md)
- Teams setup copy must describe the **Workflows** flow, not the retired connector (D-15)

---

### `frontend/src/components/settings/microcopy.ts` + `settings-sidebar-shell.tsx` (MODIFY)

**Analog:** in-file. Add `'sla'` to the `Category` union (microcopy.ts:10-17) and `CATEGORY_LABELS` (microcopy.ts:20-28, e.g. `sla: 'SLA & Escalation'`, sentence case). Add `'sla'` to both `ALL_CATEGORIES` (shell:40-48) and `ADMIN_ONLY` (shell:54-60 — admin/owner-gated per D-10). RBAC gate `isAdmin = role === 'OWNER' || role === 'ADMIN'` already applied at shell:70-76.

---

### `frontend/src/components/tickets/sla-pill.tsx` (EXTEND — D-11)

**Analog:** itself (read in full). It computes tier **client-side** from `dueAt`. For findings, add an **optional** `state?: 'on_track' | 'approaching' | 'breached'` prop: when present, render the server-computed 3-state directly (map to the existing `TIER_CONFIG` color classes: breached→`overdue`/severity-critical, approaching→`soon`/severity-high, on_track→`ok`/severity-low); when absent, keep the existing `computeTier(dueAt)` path so ticket call sites are untouched (RESEARCH State-of-the-Art line 567 — do NOT touch `tickets-table.tsx`/`kanban-card.tsx`/`ticket-drill-content.tsx`). Never re-derive the tier formula client-side (Anti-Pattern, RESEARCH line 298). Existing test file `sla-pill.test.tsx` gets the new `state`-prop path added.

---

## Shared Patterns

### Audit (every escalation fire + every SLA policy change — D-07, fail-closed)
**Source:** `backend/app/audit.py:143-171`
**Apply to:** `sla_tier_service.py` (each escalation fire), `tenants/router.py` (policy changes)
```python
await audit(db, user_or_none, "sla.escalation_fire", "vulnerability", str(vuln_id),
            {"channel": "slack", "from_state": "on_track", "to_state": "breached"})
```
`audit()` is fail-closed: it raises on failure so the enclosing `db.commit()` is skipped and the whole transaction rolls back. The scheduler tick has **no CurrentUser** — pass `user=None` (audit.py:174 writes `tenant_id=uuid.UUID(int=0)` for a None user). For a system actor, follow the `user_email="system:cli"` precedent used by `encryption.py:264` (`rotate_credentials` writes `AuditLog` directly with `user_email="system:cli"`); a `"system:scheduler"` string is the consistent choice here.

### In-app notification twin (D-08 breach signal)
**Source:** `backend/app/notifications/service.py:19-61` `create_notification`
**Apply to:** `sla_tier_service.py` breach path
```python
await create_notification(db, tenant_id=tenant.id, title=..., message=...,
    severity="critical", category="sla_escalation",  # NEW category ≠ legacy "sla_breach"
    resource_type="vulnerability", resource_id=cve_id_or_uuid, details={...})
```
Supports broadcast (`user_id=None`) + optional email fan-out. The distinct `category` is what lets D-08 reconciliation be tested.

### Fernet secret encryption at rest (D-14 channel secrets)
**Source:** `backend/app/encryption.py:24-33` (`encrypt_value`/`decrypt_value`) + usage precedent `backend/app/connectors/service.py:84,119,152-158`
**Apply to:** `tenants/router.py` PATCH branch for channel secrets
```python
# WRITE (connectors/service.py:84 — the pattern for a dict of secrets):
encrypted = json.dumps({k: encrypt_value(v) for k, v in secrets.items()})
# READ (connectors/service.py:157-158):
return {k: decrypt_value(v) for k, v in json.loads(encrypted).items()}
```
`_get_fernet()` reads `settings.encryption_key`. Combine with mask-on-read so the browser never sees plaintext (D-14). Does NOT retroactively re-encrypt `smtp_config.password` (out of scope).

### Tenant JSONB config extension
**Source:** `backend/app/tenants/models.py:39-41` (`syslog_config`/`smtp_config`/`sla_config` all `Mapped[dict | None] = mapped_column(JSONB)`)
**Apply to:** tier policy + approaching % + tier floor + channel routing + channel secrets all extend the existing `Tenant.sla_config` JSONB — no new column. Always call `flag_modified(tenant, "sla_config")` after in-place mutation (router.py:203-206).

### Check-before-insert exactly-once gate
**Source:** `backend/app/notifications/alerts.py:276-296` `_notification_exists`
**Apply to:** the escalation-event once-only gate (see `sla_tier_service.py` above) — same query shape, no time window, backed by a `UniqueConstraint`.

### Scheduler-tick isolation (Pattern 1)
**Source:** `backend/app/connectors/scheduler.py:314-328` (and every sibling block 290-355)
**Apply to:** the new tier-engine + escalation pass — own session, own try/except, own commit; a channel POST failure or a bad tenant must not stall other tenants or sibling tasks.

## No Analog Found

None. Every new file in this phase has a strong in-repo analog — this is a "reuse existing infrastructure" phase (audit, notifications, JSONB config, secret masking, httpx client, Fernet encryption, tier constants, migration shape, settings-pane pattern all already exist). The genuinely new *code* (not pattern) is: the tier + elapsed-% state formula, the two event tables, the per-channel payload builders, and the pane markup — all covered by the assignments above.

## Metadata

**Analog search scope:** `backend/app/vulnerabilities/`, `backend/app/notifications/`, `backend/app/connectors/`, `backend/app/tenants/`, `backend/app/ticketing/`, `backend/app/{audit,email,encryption}.py`, `backend/alembic/versions/`, `frontend/src/components/settings/`, `frontend/src/components/tickets/`
**Files read for excerpts:** 18 (13 backend, 5 frontend)
**Pattern extraction date:** 2026-08-13
