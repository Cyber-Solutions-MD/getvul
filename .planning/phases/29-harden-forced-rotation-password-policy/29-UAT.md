---
status: complete
phase: 29-harden-forced-rotation-password-policy
source: [29-01-SUMMARY.md]
started: 2026-08-04T08:43:33Z
updated: 2026-08-04T08:44:30Z
---

## Current Test

[testing complete]

## Tests

### 1. Weak password rejected on forced rotation
expected: On the forced-rotation path, a new password below the FORCED_ROTATION_POLICY floor (min 12 chars + all 4 character classes) is rejected with 400 complexity error; must_change_password stays true.
result: pass
verified_by: tests/test_admin_hardening.py::test_rotation_rejects_weak_complexity (PASSED)

### 2. Near-default variant "Admin1234!" rejected (WR-01 residual closed)
expected: On forced rotation, submitting "Admin1234!" — a near-variant of the default "Admin123!" credential — is rejected by the similarity guard (400), even though it satisfies complexity. This is the specific WR-01 residual this phase closes.
result: pass
verified_by: tests/test_admin_hardening.py::test_rotation_rejects_near_default_variant (PASSED)

### 3. Superseded password-history reuse rejected
expected: After rotating through several distinct passwords, attempting to reuse an older superseded (non-current) password is rejected by the history check (history_count=5, 400). This is caught by check_password_history, distinct from the WR-01 current-hash guard.
result: pass
verified_by: tests/test_admin_hardening.py::test_rotation_rejects_superseded_password_history (PASSED)

### 4. New password too similar to current is rejected
expected: On forced rotation, a new password that is highly similar (difflib ratio ≥ 0.7) to the submitted current password is rejected with 400 and a distinct similarity message.
result: pass
verified_by: tests/test_admin_hardening.py::test_rotation_rejects_similar_to_current (PASSED)

### 5. Strong distinct password accepted, flag clears
expected: A genuinely strong, dissimilar new password (12+ chars, all 4 classes, unlike any forbidden/current value) is accepted on forced rotation; must_change_password clears to false and login proceeds. Positive control — the new guards are not over-broad.
result: pass
verified_by: tests/test_admin_hardening.py::test_rotation_accepts_strong_distinct_password (PASSED)

### 6. Policy-floor merge + similarity primitives behave correctly
expected: merge_policy_floor() is strictest-wins (a tenant can be stricter than the floor but never weaker); password_similarity_ratio() normalizes (casefold+strip) then truncates to 128 chars and returns the expected ratio; is_too_similar() flags at the 0.7 threshold.
result: pass
verified_by: tests/test_admin_hardening.py::test_password_similarity_helpers (PASSED)

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — all checkpoints passed]

## Verification Notes

Backend-only security phase with no UI surface. All six user-observable behaviors were
verified against their 1:1 backing integration tests in `tests/test_admin_hardening.py`,
run locally on 2026-08-04:

- Full suite: **19 passed** (14 pre-existing Phase 06 + 5 new Phase 29).
- Targeted re-run of the six Phase 29 behaviors: **6 passed, 13 deselected**.

Env: ENCRYPTION_KEY + JWT_SECRET_KEY set, run per-file via `.venv/bin/python -m pytest`.
