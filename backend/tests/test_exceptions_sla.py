"""Phase 39 Plan 03 (EXC-02/EXC-04, D-15/D-16) -- wiring the exception
exclusion join into the Phase 36 SLA engine + the D-16 SLA-clock
subtraction on resurface.

Task 1 (this section): pure-function unit tests for `_merge_intervals`
(Pitfall 4 / T-39-12 -- overlapping lapsed-exception windows must be
interval-merged before summing, never naively added) and
`compute_sla_state`'s new `excepted_seconds` parameter (D-16). Neither
needs `db_session`/`tenant_a` -- both are pure, no DB I/O, mirroring
`test_sla_tier_service.py`'s documented pure-vs-DB-backed split.

Task 2 (appended below): DB-backed integration tests proving the full
D-15/D-16 wiring end-to-end -- `list_vulnerabilities`/`get_vulnerability`
read-time subtraction, `run_sla_tier_pass`'s persisted-mirror agreement
(Pitfall 1), and `detect_and_escalate`'s exclusion (T-39-11) + its own
subtraction (so a just-resurfaced finding doesn't fire an instant-breach
escalation storm -- the plan's own stated objective).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret pytest tests/test_exceptions_sla.py -x
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.exceptions.service import _merge_intervals
from app.vulnerabilities.sla_tier_service import (
    DEFAULT_APPROACHING_PCT,
    DEFAULT_TIER_POLICY,
    compute_sla_state,
)

# ── _merge_intervals (Pitfall 4 / T-39-12: overlap counted once) ───────────


def test_merge_intervals_empty():
    assert _merge_intervals([]) == 0


def test_merge_intervals_single():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=3)
    assert _merge_intervals([(start, end)]) == int(timedelta(days=3).total_seconds())


def test_merge_intervals_disjoint():
    """Two non-overlapping windows sum plainly -- no merge needed."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    window_a = (start, start + timedelta(days=1))
    window_b = (start + timedelta(days=5), start + timedelta(days=6))
    expected = int(timedelta(days=1).total_seconds()) * 2
    assert _merge_intervals([window_a, window_b]) == expected
    # Order-independent -- sorted internally.
    assert _merge_intervals([window_b, window_a]) == expected


def test_merge_intervals_overlap_union_not_sum():
    """Two overlapping windows must count the union once, NOT the naive
    sum of each window's own duration (T-39-12 -- prevents an
    over-credited SLA clock when D-12 permits simultaneous overlapping
    exceptions)."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    window_a = (start, start + timedelta(days=3))  # [0, 3]
    window_b = (start + timedelta(days=1), start + timedelta(days=4))  # [1, 4]
    naive_sum = int(timedelta(days=3).total_seconds()) + int(timedelta(days=3).total_seconds())
    union_seconds = int(timedelta(days=4).total_seconds())  # [0, 4] merged
    result = _merge_intervals([window_a, window_b])
    assert result == union_seconds
    assert result != naive_sum


def test_merge_intervals_touching_adjacent_merged():
    """Windows that exactly touch (one's end == the other's start) merge
    into a single continuous run."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    window_a = (start, start + timedelta(days=2))
    window_b = (start + timedelta(days=2), start + timedelta(days=5))
    assert _merge_intervals([window_a, window_b]) == int(timedelta(days=5).total_seconds())


# ── compute_sla_state's excepted_seconds param (D-16) ───────────────────────


def test_excepted_seconds_subtraction():
    """excepted_seconds shifts the effective start (and therefore the due
    date) later by exactly that many seconds -- the classification
    thresholds (tier_days/approaching_pct) themselves are unchanged."""
    first_detected_at = datetime(2026, 1, 1, tzinfo=UTC)
    tier_days = DEFAULT_TIER_POLICY["critical"]  # 7
    approaching_pct = DEFAULT_APPROACHING_PCT
    excepted_seconds = int(timedelta(days=10).total_seconds())

    baseline_due, _ = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=first_detected_at,
    )
    shifted_due, shifted_state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=first_detected_at,
        excepted_seconds=excepted_seconds,
    )

    assert shifted_due == baseline_due + timedelta(seconds=excepted_seconds)
    # 10 days of excepted time pushed the due date well into the future
    # relative to `now` (still first_detected_at) -- on_track, not
    # breached, proving the shift actually moves the classification too.
    assert shifted_state == "on_track"
