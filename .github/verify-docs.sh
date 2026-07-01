#!/usr/bin/env bash
# Phase 2 docs verifier. Exits 0 only if the CI-gating docs are present and the
# stale "workflow_dispatch only" trigger note in docs/12 has been corrected.
set -u
fail=0

if ! grep -qF "CI Gating & Branch Protection" docs/13-deployment.md; then
  echo "FAIL: docs/13-deployment.md missing '## CI Gating & Branch Protection' section"; fail=1
fi
if ! grep -qF "branch-protection.json" docs/13-deployment.md; then
  echo "FAIL: docs/13-deployment.md does not reference the committed branch-protection.json body"; fail=1
fi
for s in "Backend" "Frontend" "Semgrep SAST" "Terraform Validate"; do
  grep -qF "$s" docs/13-deployment.md || { echo "FAIL: docs/13 missing required check '$s'"; fail=1; }
done
if grep -qiE "workflow_dispatch only|manual dispatch" docs/12-pipelines-cicd.md; then
  echo "FAIL: docs/12-pipelines-cicd.md still describes triggers as manual/workflow_dispatch-only (stale)"; fail=1
fi

if [ "$fail" -eq 0 ]; then echo "docs OK"; fi
exit "$fail"
