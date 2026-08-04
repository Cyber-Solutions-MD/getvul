---
phase: 29
slug: harden-forced-rotation-password-policy
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-04
---

# Phase 29 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| client → POST /auth/change-password | A flagged (first-login) user submits an attacker-chosen `new_password` + `current_password` across the network. | Plaintext credentials (untrusted) into the auth/credential store |
| forced-rotation gate → credential persistence | The `must_change_password` gate must hold: a weak/near-default/recycled rotation must not defeat it. | New bcrypt hash + `must_change_password` flag state |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-29-near-default-cred | Elevation of Privilege | flagged branch, `router.py` | high | mitigate | `is_too_similar(new_password, ["Admin123!", current])` (ratio ≥ 0.7) at [router.py:244](backend/app/auth/router.py#L244) + `FORCED_ROTATION_POLICY` (min-12 + 4 classes) via `policy_override` at [router.py:255](backend/app/auth/router.py#L255). Test `test_rotation_rejects_near_default_variant`. | closed |
| T-29-history-bypass | Elevation of Privilege | history check, `password.py` | high | mitigate | `FORCED_ROTATION_POLICY.history_count=5` ([password.py:40](backend/app/auth/password.py#L40)) flows through `merge_policy_floor` → `check_password_history` active on forced path ([password.py:286](backend/app/auth/password.py#L286)). Test `test_rotation_rejects_superseded_password_history` (3-rotation isolation). | closed |
| T-29-similar-to-prev | Elevation of Privilege | similarity guard, `router.py` | medium | mitigate | Submitted `current_password` appended to forbidden set with distinct message branch at [router.py:240-248](backend/app/auth/router.py#L240-L248). Test `test_rotation_rejects_similar_to_current`. | closed |
| T-29-similarity-dos | Denial of Service | `password_similarity_ratio`, `password.py` | medium | mitigate | Inputs normalized then truncated to 128 chars before O(n·m) `SequenceMatcher` ([password.py:73-74](backend/app/auth/password.py#L73-L74)). Test `test_password_similarity_helpers` (cap observable). | closed |
| T-29-wr01-regression | Elevation of Privilege | existing guards, `router.py` | high | mitigate | Exact/whitespace/case default-credential guard ([router.py:229-230](backend/app/auth/router.py#L229-L230)) + current-hash reuse guard kept BEFORE `change_password` ([router.py:236-238](backend/app/auth/router.py#L236-L238)). Full Phase 06 WR-01 suite green. | closed |
| T-29-overbroad-reject | Denial of Service (legit user) | new complexity/similarity guards | low | mitigate | Positive control: strong dissimilar password succeeds 200 + clears flag. Test `test_rotation_accepts_strong_distinct_password` ([router.py](backend/app/auth/router.py); test at line 646). | closed |
| T-29-bcrypt-72-truncation | Tampering | `hash_password`/bcrypt, `password.py` | low | accept | bcrypt silently truncates at 72 bytes; with a 12-char minimum + class diversity this is not exploitable for the default-credential-adjacent threat. Documented residual ([router.py:223-224](backend/app/auth/router.py#L223-L224)). | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-29-01 | T-29-bcrypt-72-truncation | bcrypt truncates input at 72 bytes; with FORCED_ROTATION_POLICY's 12-char minimum + required character-class diversity, this is not exploitable for the near-default-credential threat this phase targets. Out of scope; documented residual. | gsd-secure-phase (agent) | 2026-08-04 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-04 | 7 | 7 | 0 | gsd-secure-phase (Claude, L1 grep-depth) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-04
