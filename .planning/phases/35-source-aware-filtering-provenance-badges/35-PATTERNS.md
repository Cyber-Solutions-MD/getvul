# Phase 35: Source-Aware Filtering & Provenance Badges - Pattern Map

**Mapped:** 2026-08-12
**Files analyzed:** 15 (backend: 7 modify/extend, 1 new test harness, 3 new test files; frontend: 1 new component + 1 new test, 3 modify)
**Analogs found:** 15 / 15 (all have at least a role-match analog; CSPM grouping and SourceBadgeGroup visual are flagged MEDIUM — genuinely new mechanisms per RESEARCH.md)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/vulnerabilities/service.py` (`_apply_filters`, `list_vulnerabilities`) | service | CRUD (read, filter) | itself, pre-existing `_apply_filters` (`service.py:34-67`) + `risk_exposure_service.py:320-345` (batching) | exact (filter shape) / role-match (batching) |
| `backend/app/vulnerabilities/schemas.py` (`VulnerabilityFilter`, `VulnerabilitySummary`) | config/schema | transform | itself — `order: Literal["asc","desc"]` (`schemas.py:134`) is the exact shape precedent for `source_mode` | exact |
| `backend/app/assets/router.py` (`list_assets` filter block) | route+service (filter inline in router) | CRUD (read, filter) | itself — the buggy loop (`router.py:154-159`); OR-fix precedent = `os_family`'s `or_(*[...])` pattern in the SAME file (`router.py:172-186`, not yet read in full but same file, same function) | exact (bug to fix) / role-match (OR-fix precedent already lives in this file) |
| `backend/app/ticketing/rule_engine.py` (`_find_matching_assets` scanner block) | service (rule engine) | CRUD (read, filter) | identical bug, `router.py:154-159` | exact (same bug, flagged out-of-scope but same fix) |
| `backend/app/cspm/service.py` (`_apply_filters`, new grouping query) | service | CRUD (read) + new aggregate/transform | itself (`service.py:28-51`, OR-only, same shape as pre-Phase-35 Vulnerabilities) for the filter; `risk_exposure_service.py:320-345` for the NEW batched-GROUP-BY shape (no CSPM-native precedent exists) | role-match (filter) / no analog, synthesize (grouping — MEDIUM confidence per RESEARCH.md) |
| `backend/app/cspm/schemas.py` (`MisconfigFilter`, `MisconfigSummary`) | config/schema | transform | `vulnerabilities/schemas.py` `VulnerabilityFilter`/`VulnerabilitySummary` (`schemas.py:74-138`) — CSPM's `MisconfigFilter` (`cspm/schemas.py:60-67`) is missing the `max_length` cap Vulnerabilities already has | role-match |
| `backend/app/ticketing/service.py` (`list_tickets` provenance resolution) | service | CRUD (read) + batch-aggregate | itself — the WR-05 batched-detail-aggregate precedent (`service.py:849-901`, `details_by_url` dict keyed by `external_ticket_url`) | exact (batching shape) — extend with a second batched dict for `(cve_id, asset_id) -> sources` |
| `backend/app/ticketing/schemas.py` (`TicketResponse`, `TicketSummary`) | config/schema | transform | itself (`schemas.py:13-47`) — already joins `cve_id`/`severity`/`hostname` off the single linked vuln; add `sources`/`sources_count` alongside those | exact |
| `backend/tests/test_query_count_assertions.py` (NEW harness) | test (infra) | N/A | NO existing analog — `tests/conftest.py`'s `db_session` fixture (`conftest.py:157-213`, uses `app.db.session.async_session_factory`) is the closest fixture to hook a `before_cursor_execute` listener onto; `app.db.session.engine.sync_engine` is the attach point | no analog — new infra, build from `conftest.py`'s engine/session fixture shape |
| `backend/tests/test_asset_source_filter.py` (NEW) | test | integration | `backend/tests/test_vuln_source_filter.py` (full file, 77 lines) — same `_seed()` helper + `client`/`db_session`/`tenant_a` fixture shape | exact |
| `backend/tests/test_cspm_source_filter.py` (NEW) | test | integration | `backend/tests/test_vuln_source_filter.py` (seed+assert shape) + `backend/tests/test_risk_exposure_service.py::test_compute_uses_correlation_sources_count` (lines ~369-395, for seeding a correlation-shaped multi-source fixture) | role-match |
| `backend/tests/test_ticket_source_provenance.py` (NEW) | test | integration | `backend/tests/test_risk_exposure_service.py::test_compute_uses_correlation_sources_count` (seeds `VulnerabilityCorrelation` directly) + `test_asset_groups.py::test_group_list_and_detail_include_member_count` (lines 152-179, N+1-avoidance assertion phrasing precedent) | role-match |
| `frontend/src/components/vulnerabilities/source-badge-group.tsx` (NEW) | component | transform (presentational) | `frontend/src/components/tickets/provider-mark.tsx` (full file, 54 lines) for the mark; `visual-language.md:41-47` (`.sev-pill`) + `:143-150` (`.sla-pill.ok`, green `--color-success` tint) for the pill chrome | no exact analog (new component), strong compositional analog |
| `frontend/src/components/vulnerabilities/source-badge-group.test.tsx` (NEW) | test | N/A | `frontend/src/components/tickets/provider-mark.test.tsx` (full file) — CSS-variable-reference assertions (`el.style.background).toContain('--gradient-provider-...')`), no-raw-`<img>` assertion | exact |
| `frontend/src/components/vulnerabilities/chip-bar.tsx` (AND toggle + `SOURCES` fix) | component | transform | itself (`chip-bar.tsx:26` stale list; `chip-bar.tsx:69-74` `sourceAxis` shape) + `ChipBar.tsx:134-157` (chip-button `aria-pressed` shape, reused for the AND toggle) + `use-url-state.ts` (singular `?order=` sibling hook) | exact |
| `frontend/src/components/assets/assets-chip-bar.tsx` (scanner/enrichment split + `SOURCES` fix) | component | transform | itself (`assets-chip-bar.tsx:22` stale list, `:69-75` single `source` axis to be split into two axes) | exact |

## Pattern Assignments

### `backend/app/vulnerabilities/service.py` — `_apply_filters` + `list_vulnerabilities` (service, CRUD)

**Analog:** itself (existing filter to replace) + `risk_exposure_service.py:320-345` (batching to extend)

**Current filter to REPLACE** (`service.py:40-41`):
```python
if filters.source:
    query = query.where(Vulnerability.source.in_(filters.source))
```
This is per-row OR on the wrong column (`Vulnerability.source`, not the correlation ARRAY). Must become the `source_mode` branch (RESEARCH.md Pattern 2, `tuple_(cve_id, asset_id).in_(corr_subq)` for AND, `or_(corr_subq_match, Vulnerability.source.in_(...))` for OR-with-single-source-fallback).

**Imports to extend** (`service.py:9,15-16`):
```python
from sqlalchemy import Select, asc, case, desc, func, nulls_last, or_, select, update
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation
```
`VulnerabilityCorrelation` is already imported — no new import needed for the filter branch. `tuple_` needs adding: `from sqlalchemy import tuple_`.

**Batching pattern to extend, verbatim structure** (`risk_exposure_service.py:320-345`):
```python
corr_rows = (
    await db.execute(
        select(
            VulnerabilityCorrelation.cve_id,
            VulnerabilityCorrelation.asset_id,
            VulnerabilityCorrelation.sources_count,
        ).where(VulnerabilityCorrelation.tenant_id == tenant_id)
    )
).all()
corr_by_key = {(row.cve_id, row.asset_id): row.sources_count for row in corr_rows}
...
sources_count = corr_by_key.get((vuln.cve_id, vuln.asset_id), 1)
```
**What differs:** that precedent is a tenant-WIDE bulk-select (acceptable for a background job run once per sync). For `list_vulnerabilities` (interactive, paginated), scope the second query to only the CURRENT PAGE's `(cve_id, asset_id)` keys via `tuple_(...).in_(keys)` — NOT a tenant-wide select on every page load (RESEARCH.md §3). Also extend the selected columns to carry `sources` (the array itself), not just `sources_count`, since `SourceBadgeGroup` needs the actual source list.

**Facet-group precedent already in this file** (`service.py:31`):
```python
_ALLOWED_FACET_GROUPS: frozenset[str] = frozenset({"severity", "source", "status"})
```
Mirror this frozenset-allow-list style for any new `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` constants (see Assets section) — same file already establishes the "hardcoded frozenset, not a raw string" convention.

---

### `backend/app/vulnerabilities/schemas.py` — `VulnerabilityFilter` + `VulnerabilitySummary` (schema, transform)

**Analog:** itself — `order` field is the exact shape precedent for `source_mode`

**Precedent field to mirror** (`schemas.py:131-134`):
```python
# Phase 11 / T-11-01: sort direction. Defaults to "desc" so the existing
# severity / triage sorts (which today are inherently desc) keep the same
# shape when callers don't pass `order=`.
order: Literal["asc", "desc"] = "desc"
```
**New field, same shape:**
```python
source_mode: Literal["or", "and"] = "or"
```
This is a `Literal[...]` field, not a raw `str` — FastAPI/Pydantic rejects unrecognized values with a 422 automatically (RESEARCH.md V5 Input Validation note), no manual allow-list check needed at this layer.

**`VulnerabilitySummary` (`schemas.py:74-90`) currently has NO source/correlation field at all** — this is the literal SRC-01 gap. Add:
```python
sources: list[str] = Field(default_factory=list)
sources_count: int = 1
```
Defaulting `sources_count=1` (not `0` or `None`) mirrors the existing `corr_by_key.get((...), 1)` fallback convention already used in `risk_exposure_service.py:352` — "no correlation row" = "single source," never "unknown" (RESEARCH.md §2 critical gap).

**`max_length` cap precedent** (`schemas.py:99-104`, already applies to `source`):
```python
severity: list[str] | None = Field(None, max_length=10)
source: list[str] | None = Field(None, max_length=10)
```
Carry this same cap convention over to CSPM's `MisconfigFilter.source` (currently uncapped, `cspm/schemas.py:62`).

---

### `backend/app/assets/router.py` — `list_assets` scanner filter (route+inline-service, CRUD)

**Analog:** itself (bug to fix)

**Current buggy AND-loop** (`router.py:154-159`):
```python
if scanner:
    # Filter by seen_by_sources containing the scanner
    # seen_by_sources is a JSONB array like ["CROWDSTRIKE", "NESSUS"]
    scanners = [s.strip().upper() for s in scanner.split(",") if s.strip()]
    for s in scanners:
        query = query.where(Asset.seen_by_sources.contains([s]))
```
Each `.where()` call ANDs — this is the SRC-03 bug. Must become `or_(*[Asset.seen_by_sources.contains([s]) for s in scanners])` for OR-default, gated behind a new `source_mode`/`scanner_mode` param; keep the chained-AND shape only for the explicit AND-toggle path (it already computes true AND correctly — the bug is only that it's the unconditional default).

**The OR-fix pattern already exists in the SAME FILE** (`router.py:172-186`, `os_family` handling) — this is the closest in-repo analog for "how to `or_()` a list of `.contains()`-style clauses" once you fix the scanner loop:
```python
if os_family:
    from sqlalchemy import and_, not_, or_
    requested = {f.strip().lower() for f in os_family.split(",") if f.strip()}
    valid = requested & ({"other"} | OS_FAMILY_PATTERNS.keys())
    ors = []
    known = valid & OS_FAMILY_PATTERNS.keys()
```
Note the import-inline style (`from sqlalchemy import and_, not_, or_` mid-function) is this file's existing convention — mirror it rather than adding a new top-level import if consistency with this file matters more than the top-of-file style in `vulnerabilities/service.py` (which imports `or_` at module level, `service.py:9`). Either is acceptable; prefer module-level per RESEARCH.md's overall SQLAlchemy-only-no-raw-SQL convention, but this file's own established idiom is inline.

**Scanner/enrichment partition — new constants, no existing analog, mirror this file's `_ALLOWED_FACET_GROUPS`-style frozenset** (`vulnerabilities/service.py:31`) and `VulnSource` enum (`vulnerabilities/models.py:32-38`):
```python
SCANNER_SOURCES = frozenset(s.value for s in VulnSource)  # CROWDSTRIKE/NESSUS/DEFENDER/WIZ/QUALYS/RAPID7
ENRICHMENT_SOURCES = frozenset({"JAMF", "HUMAANS", "INTUNE"})
```
**What differs from the vuln-schema field:** Assets' scanner param today is a raw comma-separated query string (`scanner: str = Query("", ...)`, `router.py:129`), not a `list[str]` Pydantic field like `VulnerabilityFilter.source` — the existing `[s.strip().upper() for s in scanner.split(",") if s.strip()]` parse-and-clamp shape (`router.py:157`) should stay (matches this router's convention throughout, e.g. `device_category` at `router.py:150-153`), just validated against `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` instead of passed straight into `.contains()`.

**Do NOT model on** `backend/app/enrich_assets.py:130-141` (dead `__main__`-only script that overwrites `seen_by_sources` as a dict, not a list — RESEARCH.md §4 landmine). Confirmed dead: zero references from `connectors/scheduler.py`.

---

### `backend/app/ticketing/rule_engine.py` — `_find_matching_assets` scanner block (service, CRUD)

**Analog:** identical bug in `assets/router.py:154-159`

**Current** (`rule_engine.py:69-73`):
```python
# Scanner filter (from "scanner" or "source" conditions)
scanners = conditions.get("scanner") or conditions.get("source")
if scanners and isinstance(scanners, list):
    for s in scanners:
        query = query.where(Asset.seen_by_sources.contains([s]))
```
Same AND-loop bug, same fix shape. RESEARCH.md's Open Question #1 flags this as adjacent-but-technically-out-of-scope (ticket-automation-RULE asset matching, not ticket-provenance-display) — note it for the planner but do not silently skip; it is the exact 2-line fix the Assets router needs, in the same PR-adjacent surface.

---

### `backend/app/cspm/service.py` — `_apply_filters` + new grouping (service, CRUD + new aggregate)

**Analog:** itself for the OR filter (`service.py:28-51`, identical pre-Phase-35-Vulnerabilities shape); `risk_exposure_service.py:320-345` for the NEW batched-GROUP-BY shape (genuinely new mechanism, MEDIUM confidence per RESEARCH.md)

**Current OR-only filter** (`service.py:32-33`):
```python
if filters.source:
    query = query.where(Misconfiguration.source.in_(filters.source))
```
Keep as OR-default (correct already); the NEW work is the AND-mode grouping query, which has NO existing analog anywhere under `app/cspm/` (verified: no "correlation"/"corrobora" string anywhere in the module).

**Grouping key already exists as a schema constraint** (`cspm/models.py:47-48`):
```python
__table_args__ = (UniqueConstraint("tenant_id", "rule_id", "resource_id", "source", name="uq_misconfig_dedup"),)
```
This IS the GROUP BY key (`tenant_id, rule_id, resource_id`) — no migration needed for the computed-GROUP-BY approach (CONTEXT.md locked decision, [RESOLVED A2]).

**Read-time GROUP BY pattern — synthesize from Pattern 1's batching shape, page-scoped** (per RESEARCH.md Pitfall 2, this needs its OWN 2-query batching discipline, same shape as Vulnerabilities):
```python
# Pattern: fetch page rows first, collect (rule_id, resource_id) keys present
# on THIS page only, then ONE grouped aggregate query scoped to those keys.
page_keys = {(r.rule_id, r.resource_id) for r in page_rows}
group_q = (
    select(
        Misconfiguration.rule_id,
        Misconfiguration.resource_id,
        func.array_agg(func.distinct(Misconfiguration.source)).label("sources"),
        func.count(func.distinct(Misconfiguration.source)).label("sources_count"),
    )
    .where(
        Misconfiguration.tenant_id == tenant_id,
        tuple_(Misconfiguration.rule_id, Misconfiguration.resource_id).in_(page_keys),
    )
    .group_by(Misconfiguration.rule_id, Misconfiguration.resource_id)
)
```
**What differs:** No table/GIN index precedent exists for this (it's computed at read time, not a persisted+indexed ARRAY like `VulnerabilityCorrelation.sources`). AND-mode = "same (rule_id, resource_id) group's `sources_count >= len(selected)` AND all selected present in `sources`" — must NOT collapse to `Misconfiguration.source.in_(filters.source)` (the exact anti-pattern SRC-05 names, RESEARCH.md Anti-Patterns).

---

### `backend/app/cspm/schemas.py` — `MisconfigFilter` (schema, transform)

**Analog:** `vulnerabilities/schemas.py` `VulnerabilityFilter` (`schemas.py:96-138`)

**Current, uncapped** (`cspm/schemas.py:60-67`):
```python
class MisconfigFilter(BaseModel):
    severity: list[str] | None = None
    source: list[str] | None = None
    status: list[str] | None = None
    category: list[str] | None = None
    cloud_provider: str | None = None
    resource_type: str | None = None
    search: str | None = None
```
**What to copy:** add `source_mode: Literal["or", "and"] = "or"` (same shape as the Vulnerabilities field) and `max_length=10` caps on the list fields to align with `VulnerabilityFilter`'s existing convention (`schemas.py:103-105`) — currently CSPM lacks this DoS-bound cap entirely.

---

### `backend/app/ticketing/service.py` — `list_tickets` transitive provenance (service, CRUD + batch-aggregate)

**Analog:** itself — the WR-05 batched-detail-aggregate precedent (`service.py:849-901`)

**Existing batching shape to extend, verbatim** (`service.py:849-901`):
```python
# WR-05: batch ALL per-URL detail aggregates into ONE query keyed by
# external_ticket_url (previously this ran one detail_q per grouped row — up
# to page_size=100 extra round-trips per list call).
page_urls = [row.external_ticket_url for row in grouped_rows]
details_by_url: dict = {}
if page_urls:
    details_q = (
        select(
            Ticket.external_ticket_url.label("url"),
            ...
            func.min(Vulnerability.cve_id).label("cve_id"),
        )
        .select_from(Ticket)
        .join(Vulnerability, Ticket.vulnerability_id == Vulnerability.id)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Ticket.external_ticket_url.in_(page_urls),
            Ticket.tenant_id == tenant_id,
        )
        .group_by(Ticket.external_ticket_url)
    )
    details_by_url = {d.url: d for d in (await db.execute(details_q)).all()}
```
**What to add:** a THIRD batched query (2 queries total already exist here — `grouped_q` + `details_q`; provenance needs one more, or extend `details_q` to also emit `array_agg(DISTINCT Vulnerability.source)` grouped by URL, then bulk-fetch matching `VulnerabilityCorrelation` rows via `tuple_((cve_id, asset_id)).in_(...)` scoped to the page's linked vulns' keys, exactly mirroring Pattern 1). Per CONTEXT.md [RESOLVED A4]: union all linked vulns' correlation sources for a grouped ticket-task row (a task spanning multiple CVEs is "multi-source" if ANY linked vuln is corroborated).

**What differs:** `details_q` already aggregates `func.min(Vulnerability.cve_id)` (a REPRESENTATIVE pick, not exhaustive — comment at `service.py:882-890` explicitly flags "a ticket group CAN span >1 Vulnerability, this is a representative pick, not a claim of single-CVE-per-ticket"). Provenance must NOT reuse `func.min` for sources (that would show only ONE ticket's source, not the union) — needs `array_agg(DISTINCT ...)` across ALL rows in the group, then correlation-union on top, per the locked union rule.

---

### `backend/app/ticketing/schemas.py` — `TicketResponse`/`TicketSummary` (schema, transform)

**Analog:** itself (`schemas.py:13-47`)

**Current** (`schemas.py:37-47`):
```python
class TicketSummary(BaseModel):
    id: uuid.UUID
    provider: str
    external_ticket_id: str
    external_ticket_url: str
    external_status: str | None
    assignee: str | None
    cve_id: str | None
    severity: str | None
    hostname: str | None
    ticket_created_at: datetime | None
```
Add `sources: list[str] = Field(default_factory=list)` and `sources_count: int = 1` alongside the existing `cve_id`/`severity`/`hostname` joined fields — same additive pattern, same defaulting convention as Vulnerabilities' `VulnerabilitySummary`.

---

### `backend/tests/test_query_count_assertions.py` (NEW — no existing analog)

**Analog:** NONE exists (verified: `grep -rn "before_cursor_execute\|query_count\|statement_count" backend/tests backend/app` → zero matches). Build from `backend/tests/conftest.py`'s fixture shape.

**Closest attach point** (`conftest.py:157-189`, `db_session` fixture):
```python
async def db_session(redis_test_url) -> AsyncIterator[Any]:
    ...
    from app.db.session import async_session_factory
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
```
`app.db.session.engine` is the module-level ASYNC engine (asyncpg dialect) referenced directly at `conftest.py:406` (`from app.db.session import engine`) in the `_reset_engine_pool` fixture — this confirms the import path. SQLAlchemy's `before_cursor_execute` event must attach to `engine.sync_engine` (the sync engine asyncpg wraps internally), not the async engine object directly — this is a SQLAlchemy 2.0 async-engine idiom, not something this codebase has done before.

**New harness shape (synthesize, no verbatim precedent):**
```python
from sqlalchemy import event

@pytest_asyncio.fixture
async def query_counter(db_session):
    from app.db.session import engine
    counts: list[str] = []
    def _listener(conn, cursor, statement, parameters, context, executemany):
        counts.append(statement)
    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    yield counts
    event.remove(engine.sync_engine, "before_cursor_execute", _listener)
```
Use this to assert `list_vulnerabilities`/`list_assets`/CSPM-list/`list_tickets` each issue a FIXED query count independent of page size (seed 5-row vs 50-row page, assert identical count) — SRC-08's hardest requirement.

---

### `backend/tests/test_asset_source_filter.py` (NEW)

**Analog:** `backend/tests/test_vuln_source_filter.py` (full file, 77 lines)

**Seed-helper + fixture shape to copy verbatim structure** (`test_vuln_source_filter.py:23-34,44-51`):
```python
def _seed(tenant_id, source: str, cve_id: str) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(tenant_id=tenant_id, cve_id=cve_id, severity="HIGH", source=source, ...)

@pytest.mark.asyncio
async def test_source_filter_qualys(client, db_session, tenant_a):
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-Q-001"))
    db_session.add(_seed(tenant_a, "RAPID7", "CVE-R-001"))
    await db_session.commit()
    resp = await client.get("/api/v1/vulnerabilities?source=QUALYS")
    assert resp.status_code == 200
    sources = {i["source"] for i in resp.json()["items"]}
    assert sources == {"QUALYS"}
```
**What differs:** need an `Asset`-seeding helper (not `Vulnerability`) with `seen_by_sources=[...]` set directly, and the new test must additionally assert (a) OR-default with 2 scanners returns the union (fixing the bug — today this same shape would wrongly assert AND), (b) enrichment source (`JAMF`) does NOT leak into a `?scanner=` filter result (SRC-06, per RESEARCH.md Test Map).

---

### `backend/tests/test_cspm_source_filter.py` (NEW)

**Analog:** `test_vuln_source_filter.py` (seed+assert shape) + `test_risk_exposure_service.py::test_compute_uses_correlation_sources_count` (~lines 369-395, for seeding a multi-source fixture pattern)

```python
db_session.add(
    VulnerabilityCorrelation(
        tenant_id=tenant_a, cve_id=cve_id, asset_id=asset.id,
        sources=["QUALYS", "RAPID7", "NESSUS"], sources_count=3, confidence="HIGH",
    )
)
```
**What differs:** CSPM has no `Correlation` model to seed — instead seed 2+ `Misconfiguration` rows sharing the SAME `(rule_id, resource_id)` with different `source` values (the `uq_misconfig_dedup` constraint), and a second set on DIFFERENT `(rule_id, resource_id)` pairs, to prove AND-mode only matches the former (RESEARCH.md Test Map SRC-05 exact scenario).

---

### `backend/tests/test_ticket_source_provenance.py` (NEW)

**Analog:** `test_risk_exposure_service.py::test_compute_uses_correlation_sources_count` (seeds `VulnerabilityCorrelation` directly) + `test_asset_groups.py::test_group_list_and_detail_include_member_count` (lines 152-179, N+1-avoidance assertion phrasing: `"32-05-PLAN's frontend management page needs a member_count ... to avoid an N+1 round trip per group"`)

Seed a `Ticket` linked to a QUALYS `Vulnerability`, and a `VulnerabilityCorrelation` row for the same `(cve_id, asset_id)` with `sources=["QUALYS","RAPID7"]` — assert the ticket list/detail response's `sources` field shows both, per [RESOLVED A4]'s union rule.

---

### `frontend/src/components/vulnerabilities/source-badge-group.tsx` (NEW)

**Analog:** `frontend/src/components/tickets/provider-mark.tsx` (full file, 54 lines) for the mark shape; `visual-language.md:41-47` + `:143-150` for pill chrome

**Mark pattern to copy verbatim structure** (`provider-mark.tsx:17-53`):
```typescript
const PROVIDER_GRADIENTS: Record<TicketProvider, string> = {
  jira:   'var(--gradient-provider-jira)',
  ...
};
const PROVIDER_GLYPH: Record<TicketProvider, string> = { jira: 'J', ... };

export function ProviderMark({ provider, className }: ProviderMarkProps) {
  const gradient = PROVIDER_GRADIENTS[provider];
  const glyph = PROVIDER_GLYPH[provider];
  return (
    <span className={cn('inline-grid size-3.5 shrink-0 place-items-center rounded-[3px] text-[8px] font-bold leading-none text-white', className)}
      style={{ background: gradient }} role="img" aria-label={provider}>
      {glyph}
    </span>
  );
}
```
Reuse this LITERAL-LOOKUP-OBJECT pattern (never string concatenation into a CSS var name — T-13-14 XSS mitigation) for a per-scanner mark: `SOURCE_GRADIENTS: Record<VulnSourceValue, string>` + `SOURCE_GLYPH` (single-letter, e.g. `Q` for QUALYS, `R` for RAPID7, `N` for NESSUS, `D` for DEFENDER, `W` for WIZ, `C` for CROWDSTRIKE).

**Pill chrome to copy** (`visual-language.md:42-46`, severity pill; `:150`, SLA-ok green tint):
```css
.sev-pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; }
.sla-pill.ok { background: rgba(74, 222, 128, 0.12); color: var(--color-success); border: 1px solid rgba(74, 222, 128, 0.3); }
```
Per CONTEXT.md [RESOLVED A3]: single-source = ONE mark, neutral/muted (no color, no `--color-success`), NO check/confirmed styling. Multi-source = group of marks + "N sources" count using this SAME `--color-success` green-tint chrome (already used for "SLA ok" — reused here to mean corroboration, a NEW mapping with no other precedent, per RESEARCH.md Pitfall 4/Assumption A3 — flagged as reviewable, not silently invented).

**KEV-pill placement precedent** (`vuln-table.tsx:290-310`, desktop Status column; `:380-401`, mobile Row 3):
```tsx
<td data-col="status" className="px-3 py-2.5">
  <span className="inline-flex items-center gap-1.5 text-text-muted">
    {row.cisa_kev && (<span aria-label="CISA KEV" className="rounded-md border border-severity-critical bg-pink-soft px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide text-[var(--color-severity-critical-on-soft)]">★ KEV</span>)}
    {row.exploit_available && (<span aria-label="exploit available" className="rounded-md bg-amber-soft px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-amber-on-soft)]">⚡</span>)}
    <span className="text-xs">{row.status}</span>
  </span>
</td>
```
**Where to slot `<SourceBadgeGroup>`:** adjacent to this existing KEV/exploit badge cluster (desktop Status column, `vuln-table.tsx:291-309`) and the mobile Row-3 cluster (`vuln-table.tsx:380-401`) — matching `visual-language.md`'s "always inline alongside the severity pill or CVE ID" KEV-badge convention. `vuln-table.tsx` has ZERO source/correlation display today (confirmed: `row.source` is only used internally for `failedSources` stale-tint checks, `vuln-table.tsx:245,344` — never rendered).

**What differs from `ProviderMark`:** `SourceBadgeGroup` must render a GROUP of marks + count (not a single mark like `ProviderMark`), and must encode a non-overclaiming state machine (1 source = neutral, 2+ = corroboration-tinted) that `ProviderMark` has no equivalent of (every ticket has exactly one provider, never a group).

---

### `frontend/src/components/vulnerabilities/source-badge-group.test.tsx` (NEW)

**Analog:** `frontend/src/components/tickets/provider-mark.test.tsx` (full file)

```typescript
it('jira: references the jira gradient CSS variable (not raw hex)', () => {
  const { container } = render(<ProviderMark provider="jira" />);
  const el = container.firstChild as HTMLElement;
  expect(el.style.background).toContain('--gradient-provider-jira');
});
it('renders NO img element and NO logo asset reference', () => { ... });
```
Copy this CSS-variable-reference + no-raw-`<img>`/no-hex assertion style. Add NEW assertions this analog doesn't need: (a) single-source render never contains the word "confirmed" (SRC-01 structural test), (b) multi-source render shows the count and the corroboration tint class, (c) `sources.length === 0` (defensive) renders the empty/neutral state, not a crash.

---

### `frontend/src/components/vulnerabilities/chip-bar.tsx` (AND toggle + `SOURCES` fix)

**Analog:** itself (stale list + existing `sourceAxis`) + `ChipBar.tsx:134-157` (chip-button shape for the new toggle) + `use-url-state.ts` (singular hook)

**Stale allow-list to FIX** (`chip-bar.tsx:26`):
```typescript
const SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK'] as const;
```
`TENABLE`/`AWS_INSPECTOR`/`MOCK` are not real `VulnSource` members; `NESSUS`/`DEFENDER` are real but absent. Per CONTEXT.md's locked decision, derive from the backend `VulnSource` enum (single source of truth) — since no generated-types bridge exists, hardcode the CORRECT 6-value list matching `vulnerabilities/models.py:32-38` exactly: `['CROWDSTRIKE', 'NESSUS', 'DEFENDER', 'WIZ', 'QUALYS', 'RAPID7']`.

**Existing `sourceAxis` to extend** (`chip-bar.tsx:69-74`):
```typescript
const sourceAxis: ChipAxis = {
  key: 'source',
  allowList: SOURCES,
  counts: facets.source,
  derivedFromCounts: true,
};
```
No `ChipAxis` boolean/mode field exists (`ChipBar.tsx:53-73`) — the AND toggle needs a SIBLING control, not an axis extension.

**Chip-button shape to mirror for the AND toggle** (`ChipBar.tsx:134-157`):
```tsx
<button type="button" onClick={() => { onChipFlush(); toggle(c.value); }} aria-pressed={active}
  className={cn('inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors',
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
    active ? 'border-border bg-surface-2 text-text' : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text')}>
```
Reuse this exact `aria-pressed` + active/inactive class shape for a single non-multi-select boolean toggle chip (per RESEARCH.md's "Don't Hand-Roll" — no `Switch`/`Toggle` primitive exists anywhere in `components/ui/`, verified empty).

**URL-state hook to reuse** (`use-url-state.ts:11-43`, the singular sibling of `useUrlStateList`):
```typescript
export function useUrlState<T extends string>(key: string, allowed: readonly T[], defaultValue: T): [T, (next: T) => void]
```
```typescript
const [sourceMode, setSourceMode] = useUrlState('source_mode', ['or', 'and'] as const, 'or');
```
Same clamp convention as `useUrlStateList` (XSS allow-list on read+write, `use-url-state.ts:20-28`) — zero new hook code needed (RESEARCH.md "Don't Hand-Roll").

**Per Pitfall 1 (RESEARCH.md):** disable/no-op the AND toggle when `filters.source` has fewer than 2 entries — document this explicitly, don't leave ambiguous.

---

### `frontend/src/components/assets/assets-chip-bar.tsx` (scanner/enrichment split + `SOURCES` fix)

**Analog:** itself

**Stale list, identical bug to `chip-bar.tsx:26`** (`assets-chip-bar.tsx:22`):
```typescript
const SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK'] as const;
```

**Current single `source` axis to SPLIT into two axes** (`assets-chip-bar.tsx:69-75`):
```typescript
{
  key: 'source',
  label: microcopy.chips.source,
  allowList: SOURCES,
  counts: facets?.source,
  derivedFromCounts: true,
},
```
**What differs:** per SRC-06 (locked decision), split into a `scanner` axis (`allowList: SCANNER_SOURCES`, gets the AND toggle) and a separate `enrichment_source` axis (`allowList: ['JAMF','HUMAANS','INTUNE']`, plain OR facet, NO AND-corroboration semantics per RESEARCH.md Pattern 3 — these are presence facts, not multi-tool corroboration signals).

## Shared Patterns

### Batched no-N+1 provenance fetch
**Source:** `backend/app/vulnerabilities/risk_exposure_service.py:320-345` (bulk-dict-lookup shape) + `backend/app/ticketing/service.py:849-901` (WR-05 page-scoped batching precedent)
**Apply to:** `vulnerabilities/service.py::list_vulnerabilities`, `assets/router.py::list_assets`, `cspm/service.py::list_misconfigurations`, `ticketing/service.py::list_tickets` — every one of these 4 list endpoints needs exactly 2 queries per page load (1 primary + 1 batched provenance/grouping), independent of page size, per SRC-08.
```python
corr_rows = (await db.execute(select(...).where(VulnerabilityCorrelation.tenant_id == tenant_id))).all()
corr_by_key = {(row.cve_id, row.asset_id): row.sources_count for row in corr_rows}
```
**Critical difference for THIS phase's usage:** unlike the tenant-wide precedent, scope the second query to the CURRENT PAGE's keys via `tuple_(...).in_(keys)`, not the whole tenant (RESEARCH.md §3).

### Tenant scoping on the SECOND (batched) query
**Source:** `ticketing/service.py:781-787` (T-12-21 documented IDOR-safe subquery reasoning)
**Apply to:** all 4 new/extended batched provenance queries above
```python
# T-12-21 mitigation — the Vulnerability subquery is unscoped, but the outer
# Ticket.tenant_id == tenant_id constraint still applies...
```
Per RESEARCH.md's V4 Access Control note: the safer, more auditable practice this phase should follow is to explicitly scope BOTH queries with `tenant_id == tenant_id`, not rely on the outer query's scoping alone — every new `tuple_(...).in_(...)` batched lookup this phase adds must carry its own explicit tenant filter.

### `Literal[...]` field for enum-like filter params (reject, don't silently default)
**Source:** `vulnerabilities/schemas.py:134` (`order: Literal["asc", "desc"] = "desc"`)
**Apply to:** `VulnerabilityFilter.source_mode`, `MisconfigFilter.source_mode`, any Assets equivalent
```python
order: Literal["asc", "desc"] = "desc"
```

### Allow-list frozenset for source-value partitions
**Source:** `vulnerabilities/service.py:31` (`_ALLOWED_FACET_GROUPS: frozenset[str] = frozenset({"severity", "source", "status"})`)
**Apply to:** new `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` constants in `assets/router.py` (or a shared module)
```python
SCANNER_SOURCES = frozenset(s.value for s in VulnSource)
ENRICHMENT_SOURCES = frozenset({"JAMF", "HUMAANS", "INTUNE"})
```

### Frontend multi-value + singular URL-state hooks
**Source:** `frontend/src/hooks/use-url-state-list.ts` (full file) + `use-url-state.ts` (full file)
**Apply to:** all chip-bar source axes (`useUrlStateList`) + the new AND toggle (`useUrlState`)
No new hook code required — both already implement the XSS allow-list clamp on read AND write (T-12-05).

### Literal lookup object, never string concatenation, for CSS-variable/glyph mapping
**Source:** `frontend/src/components/tickets/provider-mark.tsx:17-29`
**Apply to:** `SourceBadgeGroup`'s per-scanner gradient + glyph maps
```typescript
const PROVIDER_GRADIENTS: Record<TicketProvider, string> = { jira: 'var(--gradient-provider-jira)', ... };
```

## No Analog Found / Genuinely New Mechanisms

| File/Mechanism | Role | Data Flow | Reason |
|---|---|---|---|
| CSPM `(tenant_id, rule_id, resource_id)` computed GROUP BY corroboration | service (new aggregate) | transform/batch | No `MisconfigurationCorrelation` table, no CSPM correlation-maintenance job, no grouping query anywhere under `app/cspm/` today — genuinely new mechanism (MEDIUM confidence per RESEARCH.md; recommended read-time GROUP BY over a persisted table per CONTEXT.md [RESOLVED A2]) |
| `SourceBadgeGroup` visual treatment (single vs multi-source color mapping) | component (visual design) | N/A | `sketch-findings-getvul/visual-language.md` has ZERO existing "corroboration" visual concept (verified via grep) — CONTEXT.md [RESOLVED A3] recommends reusing the `--color-success`/SLA-ok green tint for multi-source, neutral/no-color for single-source, but this is a NEW mapping, not a discovered one |
| `backend/tests/test_query_count_assertions.py` (before_cursor_execute harness) | test infra | N/A | Zero query-count-assertion harness exists anywhere in this codebase (verified via grep) — must be built from `conftest.py`'s engine/session fixture shape, not copied from an existing test |

## Anti-Patterns to Avoid

- **Do NOT reintroduce the multi-select-ANDs bug.** The Assets fix (`assets/router.py:154-159`) and the ticketing/rule_engine.py fix (`rule_engine.py:71-73`) must default to OR (`or_(*[.contains([s]) for s in scanners])`), with AND only behind an explicit toggle — do not leave the chained-`.where()`-loop shape as the default anywhere.
- **Do NOT imply "confirmed" from a single scanner.** `SourceBadgeGroup`'s single-source state must be neutral/muted with no color, no checkmark, no "confirmed" copy — per SRC-01 and CONTEXT.md [RESOLVED A3]. This applies to badge copy AND visual treatment.
- **Do NOT add per-row provenance queries.** Never call a single-key lookup (e.g. an equivalent of `correlation_service.get_correlation_for_vuln`, `correlation_service.py:170-193`) inside a `for row in results:` loop in any of the 4 list endpoints — always batch via the page-scoped `tuple_(...).in_(...)` dict-lookup pattern (Pattern 1). This is the literal SRC-08 anti-pattern RESEARCH.md names explicitly.
- **Do NOT touch `backend/app/assets/service.py` or `backend/app/assets/schemas.py`.** Confirmed dead code: zero importers anywhere in the codebase (`grep -rn "from app.assets.service\|from app.assets import service\|assets.schemas"` across `backend/app` returns zero hits outside the files themselves). All live Assets logic is in `assets/router.py` (inline query building) and `assets/models.py`.
- **Do NOT source the frontend scanner list from a literal that isn't the `VulnSource` enum's real value set.** Both `chip-bar.tsx:26` and `assets-chip-bar.tsx:22` currently include fake `TENABLE`/`AWS_INSPECTOR`/`MOCK` and are missing real `NESSUS`/`DEFENDER` — reconcile both to the exact 6-value set (`CROWDSTRIKE`, `NESSUS`, `DEFENDER`, `WIZ`, `QUALYS`, `RAPID7`) matching `vulnerabilities/models.py:32-38`.
- **Do NOT treat "no correlation row" as an error, null, or "unknown" state.** It is the expected single-source case — every consumer (filters, badges, ticket provenance) must default to `[vuln.source]` / `sources_count=1`, mirroring `risk_exposure_service.py:352`'s `corr_by_key.get((...), 1)` convention.
- **Do NOT reuse `func.min(...)` for ticket provenance aggregation.** `ticketing/service.py:890`'s `func.min(Vulnerability.cve_id)` is explicitly a "representative pick, not exhaustive" (per its own comment) — provenance needs `array_agg(DISTINCT ...)` across the FULL group, then a correlation-union on top, per CONTEXT.md [RESOLVED A4]'s union rule.
- **Do NOT model Assets' `seen_by_sources` shape on `backend/app/enrich_assets.py:130-141`.** That standalone `__main__`-only script overwrites the field as a dict (not a list), silently breaking every `.contains([s])` reader — confirmed dead/never scheduler-invoked, but must not be extended or treated as a shape precedent.
- **Do NOT let CSPM's grouping query become a per-row N+1** relocated from Vulnerabilities to CSPM — same 2-query page-scoped discipline applies (RESEARCH.md Pitfall 2).
- **Do NOT skip the `Literal["or","and"]` type on `source_mode`.** Use a Pydantic `Literal` (auto-422 on bad input), not a raw `str` — matches the existing `order: Literal["asc","desc"]` convention (`schemas.py:134`) and the codebase's V5 Input Validation posture.

## Metadata

**Analog search scope:** `backend/app/{vulnerabilities,assets,cspm,ticketing}/`, `backend/tests/`, `frontend/src/components/{vulnerabilities,assets,tickets,ui}/`, `frontend/src/hooks/`, `.claude/skills/sketch-findings-getvul/references/visual-language.md`
**Files scanned:** 24 read directly this session (backend: service/schemas/models/router/rule_engine × 4 modules + risk_exposure_service.py + correlation_service.py + conftest.py + 3 test files; frontend: ChipBar.tsx, chip-bar.tsx, assets-chip-bar.tsx, provider-mark.tsx + test, vuln-table.tsx, use-url-state.ts, use-url-state-list.ts) + 35-RESEARCH.md (649 lines) + 35-CONTEXT.md (65 lines) fully ingested as primary source
**Pattern extraction date:** 2026-08-12
