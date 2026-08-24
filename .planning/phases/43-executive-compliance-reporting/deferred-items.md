# Deferred Items — Phase 43 (Executive & Compliance Reporting)

Out-of-scope discoveries made during plan execution. Logged per the executor's
Scope Boundary rule (only auto-fix issues directly caused by the current
task's changes) — not fixed here.

## Plan 02, Task 2

### `generate_executive_summary_pdf`'s `sections` toggle is a no-op for all 6 pre-existing sections

**Found during:** Writing `test_generate_executive_summary_pdf_without_new_sections_is_backward_compatible`.

**Issue:** In `backend/app/export.py::generate_executive_summary_pdf`, only the
"Vulnerability Overview" section's *header* is actually gated on `"vulns" in
sec`:

```python
if "vulns" not in sec:
    pass
else:
    section("Vulnerability Overview")
for label, val in [...]:
    row(label, val)   # <-- always runs, regardless of the if/else above
```

The `for` loop that draws the vuln rows is **not** nested inside the
if/else, so it always executes. The five other pre-existing sections
("Assets by Type", "Risk Distribution", "Top N Riskiest Hosts", "Top N
Remediations", "Ticket Status") have **no gating at all** — they call
`section(...)` and draw their rows unconditionally, regardless of what the
caller's `sections` list contains.

Net effect: passing a `sections` list that omits any of the original 6 keys
still renders that section's header-less body content. Only the *new* 3
sections this plan adds (`risk_trend`/`mttr_by_tier`/`sla_compliance`) are
genuinely toggle-gated end-to-end (each guarded by a single `if "X" in sec:`
wrapping both the header and body).

**Why not fixed here:** Pre-existing behavior, unrelated to Plan 02's own
task scope (extending the PDF with 3 new sections). No test exercised
`generate_executive_summary_pdf` before this plan (RESEARCH.md's documented
Wave 0 gap), so this has been latent and undiscovered rather than a
regression introduced by this plan.

**Suggested fix (future):** Wrap each of the 6 pre-existing sections'
header + body in the same `if "X" in sec: ... ` pattern the 3 new sections
use, then add a regression test asserting each section can be individually
suppressed.

**Impact:** Low — every real caller (the on-demand export route, scheduled
reports) always requests the full default section list; no user-visible
under- or over-rendering has been observed. It is a dead code-path
(unused toggle capability), not a correctness bug for current callers.

## Plan 03, Task 2 (checkpoint pre-verification)

### Page-break footer/row overlap in a real multi-page board PDF — RESOLVED

**Status:** Fixed per an explicit user directive at checkpoint approval time
(scope expansion into `backend/app/export.py`, approved for Plan 03). Root
cause + fix: `generate_executive_summary_pdf`'s retroactive per-page footer
loop ran with `set_auto_page_break(auto=True, margin=15)` still active;
`set_y(-15)` positions exactly at the auto-break trigger threshold, so
fpdf2's own auto-break fired on the footer's own `cell()` call — corrupting
placement (page N's footer landed at the top of page N+1) and minting a
genuinely spurious, otherwise-blank trailing page. Fix: call
`pdf.set_auto_page_break(auto=False)` immediately before the footer loop (a
manual, already-fully-paginated stamp pass has no business triggering a new
page). Verified via a throwaway fpdf2 repro before touching production
code, and via a real regression test
(`test_pdf_footer_loop_never_spawns_a_spurious_trailing_page` in
`backend/tests/test_export.py`) confirmed to fail on the pre-fix code and
pass on the post-fix code.

**Found during:** Pre-verification for the Task 2 human-verify checkpoint —
generating a real board PDF end-to-end (dev-seeded tenant, default `quarter`
period) via `GET /api/v1/export/summary` against the live local backend, then
reading the resulting PDF to confirm section order/branding.

**Issue:** With the full 9-section default (20 assets / 204 open vulns
seeded), the "Top 5 Riskiest Hosts" table spans the page 1 -> page 2 break.
The last visible row on page 1 ("dev-server-01 94 - -") visually overlaps
the "Demo Organization — Confidential | Page 1/2" footer text drawn at the
bottom of the same page — the row and the footer render on top of each
other. The single-page ("charts off", 6-section) variant does not exhibit
this, since it never spans a page break.

**Why not fixed here:** Pagination/page-break layout is pre-existing
`generate_executive_summary_pdf` (`backend/app/export.py`) behavior,
untouched by this plan (`43-03`'s `files_modified` is frontend-only: the
export dialog + its test). Plan 02's own SUMMARY already flagged this
exact gap: "multi-page pagination under a large realistic dataset ... was
not exercised." This is the first real multi-page sample generated against
a realistically-seeded (not hand-crafted) dataset, surfacing the gap Plan 02
called out in advance.

**Suggested fix (future):** Reserve bottom margin for the footer (e.g. an
fpdf2 page-break check before drawing each table row, comparing `pdf.get_y()`
against the footer's y-position) so a row never draws underneath it.

**Impact:** Cosmetic only — data is not lost or wrong, just visually
overlapping at the exact page-break boundary. Does not block Plan 03 (no
file in this plan's scope produces or fixes it). Worth a small dedicated fix
in a future reporting-polish pass.

### "Top 0 Remediations (by impact)" section header renders a literal 0

**Found during:** Same pre-verification pass as above.

**Issue:** When the seeded tenant has no closed/remediated CVE-host pairs
(only fresh `OPEN` findings), the "Top Remediations" section header renders
as literally "Top 0 Remediations (by impact)" followed by an empty table
(header row only, no data rows) — a real zero-count number rather than an
honest empty-state message ("No remediations recorded yet" or similar).

**Why not fixed here:** Pre-existing `_collect_summary_data`/
`generate_executive_summary_pdf` section, untouched by this plan. Not a new
regression from `43-03`'s frontend-only change; also not one of the 3
sections (risk_trend/mttr_by_tier/sla_compliance) that Plan 02 was scoped to
make zero-data-honest.

**Suggested fix (future):** When the top-remediations list is empty, render
an explanatory line instead of "Top 0 ...", consistent with the
zero-denominator discipline already applied to the 3 new RPT-01 sections.

**Impact:** Low — cosmetic, and only visible for a brand-new/lightly-seeded
tenant with no remediation history yet (matches this checkpoint's demo
data, not a typical production tenant with real closed tickets).
