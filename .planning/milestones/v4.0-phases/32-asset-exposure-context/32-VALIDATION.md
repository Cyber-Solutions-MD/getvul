---
phase: 32
slug: asset-exposure-context
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-10
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | backend/pyproject.toml · frontend/vitest.config.ts |
| **Quick run command** | `cd backend && ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") JWT_SECRET_KEY=test-secret .venv/bin/python -m pytest tests/test_asset_exposure.py -x` |
| **Full suite command** | per-file across touched asset/exposure/group/connector test files (avoid whole-dir async/rate-limit flakes) |
| **Estimated runtime** | ~5–20s per file |

Note: backend tests require a real Fernet ENCRYPTION_KEY + JWT_SECRET_KEY and must run per-file (MEMORY getvul-backend-pytest-env). Integration tests skip cleanly if Postgres is unreachable.

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every plan wave:** run all Phase 32 test files (per-file)
- **Before `/gsd-verify-work`:** full Phase 32 suite green + `alembic upgrade head` clean
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> One row per code-producing task. EXPO-01..06 each map to ≥1 automated test.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-01 T1 | 01 | 1 | EXPO-01,02,03,05 | T-32-01..04 | admin-only override, 404-not-403, audit-then-commit | integration+unit (RED) | `pytest tests/test_asset_exposure.py -x` | ❌ Wave 0 | ⬜ pending |
| 32-01 T2 | 01 | 1 | EXPO-01,02 | — | server_default backfill, pure inference (no tag mutation) | unit+migration | `pytest tests/test_asset_exposure.py -k "infer or default" -x` | ❌ Wave 0 | ⬜ pending |
| 32-01 T3 | 01 | 1 | EXPO-03,05 | T-32-01..04 | override-source flip permanence, audit-only-on-change, RBAC | integration | `pytest tests/test_asset_exposure.py -x` | ❌ Wave 0 | ⬜ pending |
| 32-02 T1 | 02 | 2 | EXPO-01,02 | — | real 3-field inference, tags never mutated | unit+integration | `pytest tests/test_asset_exposure.py -k "infer or internet_facing or overridden" -x` | ❌ Wave 0 | ⬜ pending |
| 32-02 T2 | 02 | 2 | EXPO-06 | T-32-05,06 | AUTO-only calibration, overrides exempt, admin-gated report | integration | `pytest tests/test_asset_exposure.py -k "calibration" -x` | ❌ Wave 0 | ⬜ pending |
| 32-03 T1 | 03 | 3 | EXPO-04,05 | T-32-07..10 | tenant isolation, RBAC, precedence, group audit (RED) | integration | `pytest tests/test_asset_groups.py tests/test_asset_exposure.py -k "group or tiebreak" -x` | ❌ Wave 0 | ⬜ pending |
| 32-03 T2 | 03 | 3 | EXPO-04 | T-32-07,08 | admin-gated CRUD, tenant-scoped membership, 404-not-403 | integration+migration | `pytest tests/test_asset_groups.py -x` | ❌ Wave 0 | ⬜ pending |
| 32-03 T3 | 03 | 3 | EXPO-04,05 | T-32-09,10 | per-asset>group>auto precedence, most-recent tiebreak, group audit | integration | `pytest tests/test_asset_groups.py tests/test_asset_exposure.py -x` | ❌ Wave 0 | ⬜ pending |
| 32-04 T1 | 04 | 4 | EXPO-02 | T-32-11 | detected-beats-proxy, override permanence (RED) | unit+integration | `pytest tests/test_asset_exposure.py -k "detected or proxy" -x` | ❌ Wave 0 | ⬜ pending |
| 32-04 T2 | 04 | 4 | EXPO-02 | T-32-11 | detected-signal precedence over proxy, AUTO-gate intact | unit+migration | `pytest tests/test_asset_exposure.py -k "detected or proxy" -x` | ❌ Wave 0 | ⬜ pending |
| 32-04 T3 | 04 | 4 | EXPO-02 | T-32-12 | real per-connector extraction, honest coverage doc | integration | `pytest tests/test_connector_internet_facing.py tests/test_asset_exposure.py -x` | ❌ Wave 0 | ⬜ pending |
| 32-05 T1 | 05 | 4 | EXPO-01,03 | T-32-13,14 | admin-gated inline override, non-admin read-only | vitest | `npx vitest run src/components/assets/exposure-context-card.test.tsx` | ❌ Wave 0 | ⬜ pending |
| 32-05 T2 | 05 | 4 | EXPO-04 | T-32-13,14 | mandatory states, admin-gated CRUD, non-admin read-only | vitest | `npx vitest run "src/app/(authed)/dashboard/asset-groups/page.test.tsx"` | ❌ Wave 0 | ⬜ pending |
| 32-05 T3 | 05 | 4 | EXPO-01,03,04 | T-32-13 | visual + role gating on live stack | checkpoint:human-verify | manual (see plan) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → Test coverage (every EXPO-01..06 has ≥1 automated test)

| Req | Primary automated test(s) | Plan |
|-----|---------------------------|------|
| EXPO-01 | test_upsert_sets_default_exposure_fields; test_infer_all_three_fields; exposure-context-card.test.tsx | 01, 02, 05 |
| EXPO-02 | test_infer_exposure_context_*; test_reinference_updates_auto_field; test_connector_internet_facing.py | 01, 02, 04 |
| EXPO-03 | test_asset_override_wins_over_reinference; test_override_requires_admin_role | 01, 05 |
| EXPO-04 | test_group_override_applies_to_group_members; test_asset_override_beats_group_override; test_conflicting_group_overrides_tiebreak; test_asset_group_crud_tenant_isolation | 03, 05 |
| EXPO-05 | test_asset_override_writes_audit_row; test_auto_inference_audits_only_on_change; test_group_override_writes_audit_row | 01, 03 |
| EXPO-06 | test_calibration_check_against_realistic_fixture; test_calibration_exempts_manual_overrides | 02 |

---

## Wave 0 Requirements

- [ ] `backend/tests/test_asset_exposure.py` — inference + per-asset override permanence + calibration + group precedence + detected-signal precedence (Plans 01/02/03/04)
- [ ] `backend/tests/test_asset_groups.py` — AssetGroup CRUD + membership + tenant isolation + RBAC (Plan 03)
- [ ] `backend/tests/test_connector_internet_facing.py` — per-connector real-signal extraction + fallback (Plan 04)
- [ ] realistic ~100-asset inline fixture proving the EXPO-06 calibration cap (Plan 02, in the test file — NOT app/seed.py)
- [ ] frontend `exposure-context-card.test.tsx` + `asset-groups/page.test.tsx` (Plan 05)
- [ ] Framework install: none — pytest/pytest-asyncio + vitest already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Internet-facing real-detection accuracy per vendor | EXPO-02 | Needs live vendor payloads (no creds in env) | On a live sync, confirm internet_facing populates from real vendor signals where documented, external_ip/tag fallback elsewhere; cross-check against the Plan 04 coverage table |
| Exposure card + asset-groups UI visual + role gating | EXPO-01/03/04 | Visual + interactive on live stack | Plan 05 Task 3 human-verify checkpoint |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
