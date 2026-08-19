# Phase 40: Proactive Alerting & Digests - Pattern Map

**Mapped:** 2026-08-19
**Files analyzed:** 13 (7 backend source + 1 migration + 4 frontend + tests)
**Analogs found:** 12 / 13 (only the wall-clock send-hour gate + HTML digest builder have no exact analog)

This phase is **wiring existing primitives**, not building new ones. Every reuse target named in 40-RESEARCH.md was verified in-session against the live codebase and the exact line numbers below are confirmed. The planner should treat these excerpts as the literal shape each new/modified file must mirror.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/notifications/alerts.py` (MODIFY: add `_check_new_kev_epss`) | service | event-driven | `_check_new_critical_vulns` (same file, alerts.py:46-97) | exact (sibling in same module) |
| `backend/app/notifications/digests.py` (NEW) | service | batch | `alerts.py` checks + `reports.py::run_due_reports` | role-match (assembled from two analogs) |
| `backend/app/connectors/scheduler.py` (MODIFY: digest dispatch block) | scheduler | event-driven | SLA-pass block scheduler.py:314-340 + alert block :369-379 | exact (extend same loop) |
| `backend/app/email.py` (MODIFY: add `html_body`) | utility | file-I/O (SMTP) | `send_email` (same file, email.py:17-93) | exact (extend in place) |
| `backend/app/tenants/models.py` (MODIFY: add `alerting_config` JSONB) | model | — | `sla_config`/`smtp_config`/`syslog_config` (models.py:39-41) | exact |
| `backend/app/tenants/router.py` (MODIFY: `alerting_config` PATCH branch + `AlertingConfigUpdate` + `_safe_alerting`) | controller/route | request-response / CRUD | `sla_config` branch (router.py:332-380) + `SlaConfigUpdate` (:104-124) | exact |
| Guard model `AlertingGuard` (NEW — in `notifications/models.py` or new) | model | — | `SlaEscalationEvent` (once-only `UniqueConstraint`) | role-match (different identity key) |
| `backend/alembic/versions/051_*.py` (NEW) | migration | — | `050_add_exceptions.py` (latest, +49 others) | exact |
| `frontend/.../settings/alerting-digests-pane.tsx` (NEW) | component | request-response | `sla-escalation-pane.tsx` | exact (clone) |
| `frontend/.../settings/settings-sidebar-shell.tsx` (MODIFY) | component | — | `ALL_CATEGORIES`/`ADMIN_ONLY` (shell:40-63) | exact |
| `frontend/.../settings/microcopy.ts` (MODIFY) | config | — | `Category` union + `CATEGORY_LABELS` (microcopy.ts:10-31) | exact |
| `frontend/.../settings/page.tsx` (MODIFY: `renderPane` case) | component/route | — | `case 'sla'` (page.tsx:134-135) | exact |
| `backend/tests/test_alerts_kev_epss.py` + `test_digests.py` (NEW) | test | — | (no `test_alerts.py` exists) — `sla-escalation-pane.test.tsx` for FE | partial |

---

## Pattern Assignments

### `backend/app/notifications/alerts.py` — ADD `_check_new_kev_epss` (D-03, D-04, D-05, D-06, D-20)

**Analog:** `_check_new_critical_vulns` (alerts.py:46-97) — same "select vulns → dedup → create_notification → email owners/admins" shape. The NEW check diverges only in (a) qualifier predicate (KEV/EPSS not severity+2h-window) and (b) dedup mechanism (durable guard table, NOT `_notification_exists`).

**Call-site (add ONE line, keep existing paths untouched) — alerts.py:28-34:**
```python
for tenant in tenants:
    alerts = 0
    alerts += await _check_new_critical_vulns(db, tenant)
    alerts += await _check_sla_breaches(db, tenant)      # no-op since Phase 36 — do not revive
    alerts += await _check_sync_failures(db, tenant)
    alerts += await _check_risk_score_changes(db, tenant)
    alerts += await _check_new_kev_epss(db, tenant)      # NEW (D-03)
    total_alerts += alerts
```

**Qualifier query shape to mirror — alerts.py:51-61** (join Asset, tenant-scoped). The NEW check REPLACES the severity/first_detected predicate with `(Vulnerability.cisa_kev.is_(True)) OR (Vulnerability.epss_score >= threshold)` AND adds the D-20 exclusion (`~active_exception_subquery(tenant.id, now)` + `status NOT IN (...)`):
```python
select(Vulnerability, Asset)
    .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
    .where(
        Vulnerability.tenant_id == tenant.id,
        Vulnerability.severity == "CRITICAL",          # ← REPLACE with KEV/EPSS predicate
        Vulnerability.first_detected_at >= cutoff,      # ← REMOVE (transition guard replaces the window)
    )
```

**In-app twin + owner email — reuse VERBATIM (alerts.py:75-95):** `create_notification(db, tenant_id=…, title=…, message=…, severity="critical", category="new_kev_epss", resource_type="vulnerability", resource_id=…, details={…})` then `_email_owners_and_admins(db, tenant, title, message, "new_kev_epss")`. Note `category` is the NEW string `"new_kev_epss"` (distinct from `"new_critical_vuln"`), per D-03/D-21.

**Do NOT reuse `_notification_exists` (alerts.py:247-267) for dedup** — it is a time-windowed count, wrong for D-02/D-04 once-only-forever semantics. Use the guard-table subtraction instead (see Pattern: guard table).

**Owner-resolution + fallback (D-07/D-10):** use `_get_directory_user` (assets/router.py:81-114) — returns `None` when no email resolves. On `None`, fall through to `_email_owners_and_admins` (alerts.py:270-296, which selects `role IN ("OWNER","ADMIN")`). NOTE (A5): `_get_directory_user` currently lives in `assets/router.py` and returns a **dict** (`{"email", "display_name", …}`), not a User — a small extraction to a service module may be needed to import it cleanly into the notifications layer.

---

### `backend/app/notifications/digests.py` (NEW) — D-11..D-15, D-08/D-09

**Analog A (dispatch-loop shape):** `reports.py::run_due_reports` (reports.py:124-152) — the "select enabled rows → per-row due-gate → send-then-stamp → commit-if-any-sent" loop:
```python
now = datetime.now(UTC)
reports = (await db.execute(select(ScheduledReport).where(ScheduledReport.is_enabled.is_(True)))).scalars().all()
sent = 0
for report in reports:
    if not _is_due(report, now):
        continue
    try:
        await _send_report(db, report)
        report.last_sent_at = now
        report.last_send_status = "SUCCESS"
        sent += 1
    except Exception as e:
        report.last_send_status = "FAILED"
if sent > 0:
    await db.commit()
```

**CRITICAL divergence — the due-gate must NOT copy `_is_due` (reports.py:155-166).** `_is_due` is a pure `elapsed_hours >= N` gate that drifts with process restarts and ignores the tenant's business hour. D-12 requires a NEW wall-clock gate: convert `now` into `Tenant.timezone` (models.py:37, default `"UTC"`), check `local_now.hour >= configured_send_hour` AND the last-sent marker is not within the current period. **Persist the last-sent marker** (per Pitfall 4 / A2 — a column on `Tenant` or a small row) rather than an in-memory `_last_digest_sent` dict, or restarts double-send.

**Section content readers (consume, never re-derive):**
- **due / breaching:** `resolve_state_for_vuln(vuln, policy, now, excepted_seconds=…)` (sla_tier_service.py:144) → returns `(sla_due_at, "on_track"|"approaching"|"breached")`. Filter sections on that state.
- **expiring-exceptions:** query `ExceptionRecord.expires_at` within the horizon (Phase 39; D-13 closes the deferred push).
- **exclusion on EVERY section (D-20):** `~active_exception_subquery(tenant.id, now)` (exceptions/service.py:50-91) + `status NOT IN ('SUPPRESSED','FALSE_POSITIVE')`. Do NOT re-derive — it is a 3-branch correlated EXISTS (finding / asset / asset-group scope).
- **top-N ordering (D-15):** order by risk via `RISK_SCORE_TIER_*` bands (assets/risk_score.py:56-61); cap per section + "and N more".

**HTML render:** call the extended `email.py::send_email(..., html_body=…)` (see below). **HTML-escape every finding-derived string** (CVE names, hostnames) — scanner text is untrusted (Security Domain: XSS in HTML email).

**Team digests (D-09):** post to the AssetGroup's shared Slack/Teams channel via `dispatch_channel` (see channel pattern below). A4: iterate only AssetGroups with content to avoid empty-post churn.

**Empty suppression (D-14):** if all sections empty for a recipient, send nothing.

---

### `backend/app/connectors/scheduler.py` — ADD digest dispatch block (D-12)

**Analog:** the SLA tier-engine block (scheduler.py:314-340) and the alert-check block (:369-379), both inside `_scheduler_loop`. Each is an **isolated `try/except` wrapping its own `async_session_factory()` session** so one failure never aborts the tick:
```python
# SLA pass block — scheduler.py:327-340 (the exact shape to mirror)
try:
    async with async_session_factory() as db:
        from app.tenants.models import Tenant as TenantModel
        from app.vulnerabilities.sla_tier_service import detect_and_escalate, run_sla_tier_pass
        tenants = (await db.execute(_sel(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
        for t in tenants:
            await run_sla_tier_pass(db, t)
            await detect_and_escalate(db, t)
        await db.commit()
except Exception as e:
    logger.error("sla_check_error", error=str(e))
```

**Where to slot in (D-12, planner discretion):** add a NEW isolated block for `_check_new_kev_epss` (or let it ride inside the existing `run_alert_checks` call at :369-379 since D-03 adds it there) and a SEPARATE block for digest dispatch. The 24h-gate idiom at :342-353 (`_last_ticket_sync`) shows the in-memory global-timestamp pattern — **but do NOT copy it for digests** (Pitfall 4: in-memory resets on restart → duplicate morning digests; use the persisted send-hour marker). Tick cadence is 60s (`await asyncio.sleep(60)`, :406); `run_alert_checks` is gated to every 5 min via `_loop_count % 5 == 0` (:371).

---

### `backend/app/email.py` — ADD `html_body` support (D-15)

**Analog:** `send_email` itself (email.py:17-93). Today it attaches ONE plain part — email.py:48-52:
```python
msg = MIMEMultipart()
msg["From"] = from_email
msg["To"] = ", ".join(to)
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain"))
```
**Change:** add an optional `html_body: str | None = None` param; when present, build `MIMEMultipart("alternative")` and attach BOTH `MIMEText(body, "plain")` and `MIMEText(html_body, "html")` so plain-text clients still render. Preserve the existing `{"ok": True}` / `{"ok": False, "error": …}` contract (email.py:83-93) — `send_email` **never raises**; all callers depend on that.

---

### `backend/app/tenants/models.py` — ADD `alerting_config` JSONB (D-18)

**Analog:** the JSONB config block (models.py:38-41):
```python
password_policy: Mapped[dict | None] = mapped_column(JSONB)
syslog_config: Mapped[dict | None] = mapped_column(JSONB)
smtp_config: Mapped[dict | None] = mapped_column(JSONB)
sla_config: Mapped[dict | None] = mapped_column(JSONB)
```
Add `alerting_config: Mapped[dict | None] = mapped_column(JSONB)` alongside. `Tenant.timezone` already exists (models.py:37, default `"UTC"`) — reuse it for the D-12 send-hour conversion; no new tz column.

---

### `backend/app/tenants/router.py` — ADD `alerting_config` PATCH branch + `AlertingConfigUpdate` + `_safe_alerting` (D-18, ALERT-03)

**Analog:** the `sla_config` branch (router.py:332-380) — validate → merge → assign → `flag_modified` → dedicated fail-closed `audit()`:
```python
if "sla_config" in body:
    from sqlalchemy.orm.attributes import flag_modified as _fm_sla
    new_sla = body["sla_config"] or {}
    try:
        SlaConfigUpdate.model_validate(new_sla)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    # … (secret merge — see below) …
    tenant.sla_config = new_sla
    _fm_sla(tenant, "sla_config")                        # ← MANDATORY on JSONB (Pitfall 5)
    await audit(db, user, "sla.policy_update", "tenant", str(tenant.id),
                { … secret-free summary … })
```

**Mirror as an `alerting_config` branch** with action `"alerting.config_update"`. The audit `details` must be **secret-free** (mirror :373-379 — only enablement/thresholds/cadence).

**Pydantic gate — clone `SlaConfigUpdate` (router.py:104-124):** it is validation-only (the handler persists the raw dict, not the model's serialization). Field-level bounds to mirror (Security Domain V5): `epss_threshold: float = Field(0.5, ge=0, le=1)`, `send_hour: int = Field(ge=0, le=23)`, `cadence: Literal["daily","weekly"]`, `kev_enabled: bool`. Use `@field_validator` for enums like `SlaConfigUpdate._valid_tier_floor` (:119-124).

**Secret handling (A1 — likely NONE needed):** D-19 says alerting REUSES Phase 36's channel credentials (`sla_config.channels`, Fernet-encrypted). So `alerting_config` should store routing/enablement/thresholds ONLY — **no raw secrets** — which sidesteps the `_SLA_SECRET_FIELDS` keep-stored-on-masked-write dance at router.py:341-358 and `_safe_sla` (router.py:127+). Confirm during planning; if alerting stores no secret, `_safe_alerting` masking is unnecessary and the branch is simpler than `sla_config`.

**RBAC (V4):** the whole `PATCH /settings` handler is `Depends(require_owner)` (router.py:284) — inherited free. GET is `require_admin` (asymmetric).

---

### Guard model `AlertingGuard` (NEW) + migration `051_*` (D-05, D-06)

**Analog:** `SlaEscalationEvent`'s once-only `UniqueConstraint` pattern (`uq_escalation_once`). Open Question 1 resolved: do NOT share `SlaEscalationEvent` — it keys on `vulnerability_id` (UUID) whereas ALERT-01 keys on `(cve_id, asset_id, trigger_type)`. New dedicated table:
- Columns: `tenant_id`, `cve_id`, `asset_id`, `trigger_type` (`"kev"|"epss"`), `fired_at` (cheap observability — discretion).
- `UniqueConstraint(tenant_id, cve_id, asset_id, trigger_type)`.

**Migration:** next number is **`051`** (latest is `050_add_exceptions.py`; 46-050 all present). One migration adds the guard table + the `alerting_config` column. Follow the 24+ existing Alembic files' structure.

**Subtraction / seed-silent logic (Pattern from RESEARCH.md:196-210):** per `(tenant, trigger_type)`: `qualifiers − guard = new_pairs`; if the guard is EMPTY for that slice (first run / newly-enabled / lowered threshold) → INSERT `new_pairs` WITHOUT firing (D-06); else fire on `new_pairs` then INSERT. Note `epss_score` is `Numeric(5,4)` → do the `>=` in SQL so Postgres coerces the Decimal-vs-float boundary (Pitfall 3).

---

### `frontend/.../settings/alerting-digests-pane.tsx` (NEW) — clone `sla-escalation-pane.tsx` (D-17)

**Analog:** `sla-escalation-pane.tsx` (structural clone). Required scaffolding (pane docstring, lines 5-8):
- Imports: `useAuth` (@/lib/auth), `useTenantSettings`/`useUpdateTenantSettings` (@/lib/queries/use-tenant-settings), `useDirtyState` (./use-dirty-state), `SaveBar` (./save-bar), `SkeletonTable`/`PartialFailureBanner`/`EmptyState` (@/components/states), `queryKeys` (sla-escalation-pane.tsx:48-54).
- `onDirtyChange?` prop + `useEffect(() => onDirtyChange?.(isDirty), [isDirty])` (:276-295).
- **RBAC:** `const isOwner = user?.role === 'OWNER';` then `disabled={!isOwner}` on every control (:284, :425 etc.) — asymmetric admin-view / owner-edit.
- Root test hook: `<div data-pane="alerting-digests" className="space-y-6 p-6">` (mirror :391 `data-pane="sla-escalation"`).
- Mandatory states: `PartialFailureBanner` on error, `SkeletonTable` on pending, `EmptyState` for empty channels (:392-467).

**Save handler shape (:328-384):** build a plain config object then `await updateSettings.mutateAsync({ alerting_config: { … } }); reset();`:
```python
await updateSettings.mutateAsync({
  sla_config: { tier_policy, approaching_pct, tier_floor, channels, routing },  # ← mirror as alerting_config
});
reset();
```
Since alerting reuses Phase 36 credentials (D-19), the pane likely does NOT re-collect webhook secrets → skip the `*Touched`/`*WasConfigured`/`SLA_SECRET_MASK` mask dance (:79-86, :340-372). Config = KEV toggle, EPSS threshold, cadence + send-hour + timezone, per-type channel routing, per-owner/per-team enablement.

**Test:** clone `sla-escalation-pane.test.tsx` → `alerting-digests-pane.test.tsx` (render / save / RBAC owner-gate / empty-state).

---

### `frontend/.../settings/settings-sidebar-shell.tsx` + `microcopy.ts` + `page.tsx` — register the pane

**`microcopy.ts` (:10-31):** add `'alerting'` to the `Category` union and a `CATEGORY_LABELS['alerting'] = 'Alerting & Digests'` entry (sentence case, per copy-voice.md — no "Please"/exclamation).

**`settings-sidebar-shell.tsx` (:40-63):** add `'alerting'` to `ALL_CATEGORIES` array AND to the `ADMIN_ONLY` Set (admin/owner-gated, D-17).

**`page.tsx` (:118-135):** add `case 'alerting': return <AlertingDigestsPane onDirtyChange={handleDirtyChange} />;` to `renderPane()`, plus the import (mirror :47 `import { SlaEscalationPane }`).

---

## Shared Patterns

### Fail-isolated channel dispatch (ALERT-01 push + team digests — D-07/D-09/D-19)
**Source:** `escalation_channels.py::dispatch_channel` (:272-298) — never raises, always returns `{"ok": bool, "error": str|None}`; SSRF-guarded (`_validate_webhook_url` :69-94, https-only + blocks private/loopback/metadata), `follow_redirects=False` (:196), 429-retry (`_post_json_with_retry` :174-187).
**Apply to:** `digests.py` team posts + the ALERT-01 channel push.
```python
outcome = await dispatch_channel(channel, config, context)   # never raises
if not outcome["ok"]:
    logger.error("alert_channel_failed", channel=channel, error=outcome["error"])
    # record + continue — never let one channel stall the tick
```
Build `config` via `_build_channel_config(sla_config, channel, tenant)` (sla_tier_service.py:328-344) so alerting reuses Phase 36's Fernet-decrypted **shared** credentials (D-19) — it decrypts slack/teams `url`, pagerduty `routing_key`, and merges `sla_config.channels.email.to` + `tenant.smtp_config`.

### Scheduler-originated audit (no CurrentUser) — Pattern 3
**Source:** `sla_tier_service.py::_audit_escalation_fire` (:347-388). The shared `audit(db, None, …)` writes `tenant_id=uuid.UUID(int=0)` (nil tenant) when `user is None` — WRONG for a tenant-scoped scheduler row.
**Apply to:** any scheduler-side alert/digest audit. Construct `AuditLog` directly with a real `tenant_id` + `user_email="system:scheduler"`:
```python
db.add(AuditLog(tenant_id=tenant.id, user_id=None, user_email="system:scheduler",
                action="alert.fire", resource_type="vulnerability", resource_id=…,
                details={…}, ip_address=None, created_at=datetime.now(UTC)))
```

### Fail-closed config audit (ALERT-03 config save — D-18)
**Source:** `audit.py:28-33` — `audit(...)` then `db.commit()`; if the audit row can't write, the commit short-circuits and the mutation fails closed. This one DOES have a real `CurrentUser`:
```python
await audit(db, user, "alerting.config_update", "tenant", str(tenant.id), {…secret-free…})
# … await db.commit() at end of handler
```

### `flag_modified` on every JSONB write (Pitfall 5)
**Source:** router.py:311, 316, 361, 386, 396 — every JSONB save calls `flag_modified(tenant, "<col>")` or the save is a silent no-op. Apply to the `alerting_config` assignment.

---

## No Analog Found

| File / Concern | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Wall-clock send-hour gate (in `digests.py`) | service (helper) | — | No existing "past target hour in tenant tz AND not sent this period" gate — both `reports.py::_is_due` (:155-166) and `_last_ticket_sync` (scheduler.py:342-353) are pure elapsed-hours gates. MUST be built new (D-12). |
| Multi-section HTML digest body | utility (render) | — | `escalation_channels._build_summary_text` (:102-110) is single-finding SLA-shaped, not a multi-section digest. Build a digest-specific HTML renderer (A3); reuse `email.py` only for transport. |

---

## Metadata

**Analog search scope:** `backend/app/notifications/`, `backend/app/connectors/`, `backend/app/tenants/`, `backend/app/vulnerabilities/`, `backend/app/exceptions/`, `backend/app/assets/`, `backend/app/reports.py`, `backend/app/email.py`, `backend/app/audit.py`, `backend/alembic/versions/`, `frontend/src/components/settings/`, `frontend/src/app/(authed)/dashboard/settings/`.
**Files scanned:** 15 (all read in-session; line numbers verified against live tree).
**Pattern extraction date:** 2026-08-19
