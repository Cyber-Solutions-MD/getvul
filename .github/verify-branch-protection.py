#!/usr/bin/env python3
"""Phase 2 branch-protection verifier (READ-ONLY).

Calls the live GitHub API to confirm main's protection matches the Phase 2 policy:
  - required status checks = exactly {Backend, Frontend, Semgrep SAST, Terraform Validate}
  - OWASP ZAP DAST is NOT required
  - a PR is required before merging (required_pull_request_reviews present)

Requires `gh` authenticated with repo admin. Exits 0 on match, 1 otherwise.
Usage: python3 .github/verify-branch-protection.py [owner/repo]
"""
import json
import subprocess
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "Cyber-Solutions-MD/getvul"
EXPECTED = {"Backend", "Frontend", "Semgrep SAST", "Terraform Validate"}

out = subprocess.run(
    ["gh", "api", f"repos/{REPO}/branches/main/protection"],
    capture_output=True, text=True,
)
if out.returncode != 0:
    print("FAIL: could not read branch protection:", out.stderr.strip())
    sys.exit(1)

data = json.loads(out.stdout)
problems = []

checks = data.get("required_status_checks", {}).get("checks", [])
contexts = {c["context"] for c in checks}
if contexts != EXPECTED:
    problems.append(f"required checks {sorted(contexts)} != expected {sorted(EXPECTED)}")
if "OWASP ZAP DAST" in contexts:
    problems.append("OWASP ZAP DAST must NOT be a required check (advisory)")

if "required_pull_request_reviews" not in data:
    problems.append("required_pull_request_reviews absent — PR not required before merge")

if problems:
    print("branch protection FAIL:")
    for p in problems:
        print("  -", p)
    sys.exit(1)

print("branch protection OK; required checks:", sorted(contexts))
print("enforce_admins:", data.get("enforce_admins", {}).get("enabled"))
sys.exit(0)
