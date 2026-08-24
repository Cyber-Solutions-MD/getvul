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
