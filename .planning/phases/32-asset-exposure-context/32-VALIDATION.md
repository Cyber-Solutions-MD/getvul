---
phase: 32
slug: asset-exposure-context
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
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
| **Quick run command** | `cd backend && ENCRYPTION_KEY=<fernet> JWT_SECRET_KEY=test python -m pytest tests/test_asset_exposure.py -q` |
| **Full suite command** | per-file across touched asset/exposure/group test files (avoid whole-dir async/rate-limit flakes) |
| **Estimated runtime** | ~5–20s per file |

---

## Sampling Rate

- **After every task commit:** run the touched test file
- **After every plan wave:** run all Phase 32 test files
- **Before `/gsd-verify-work`:** full Phase 32 suite green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Populated by the planner (one row per task) — EXPO-01..06 must each map to at least one automated test.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (planner fills) | | | EXPO-01..06 | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_asset_exposure.py` — auto-inference + override precedence + calibration
- [ ] `backend/tests/test_asset_groups.py` — AssetGroup CRUD + membership + tenant isolation
- [ ] realistic seed fixture proving the EXPO-06 calibration cap

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Internet-facing real-detection accuracy per vendor | EXPO-02 | Needs live vendor payloads (no creds in env) | Confirm on a live sync that internet-facing populates from real vendor signals, not just the external_ip/tag fallback |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
