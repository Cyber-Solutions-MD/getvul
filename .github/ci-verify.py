#!/usr/bin/env python3
"""Phase 2 ci.yml structural verifier. Exits 0 if the armed-CI invariants hold.

Checks:
  - on: block has push, pull_request, schedule (push/PR enabled, nightly DAST cron present)
  - dast job has if: github.event_name != 'pull_request'
  - all three ZAP steps keep continue-on-error: true (advisory)
  - mypy step is baseline-filtered (no '|| true')
  - frontend lint + tsc steps have no '|| true'

Works with or without PyYAML: if PyYAML is importable it does a structural parse,
otherwise it falls back to text/regex checks (the invariants are simple patterns).
"""
import re
import sys

PATH = ".github/workflows/ci.yml"
with open(PATH) as fh:
    raw = fh.read()

problems = []

# --- Triggers: push, pull_request, schedule must be enabled (uncommented) ---
try:
    import yaml

    doc = yaml.safe_load(raw)
    on = doc.get(True, doc.get("on"))  # PyYAML parses bare `on:` as boolean True
    for trig in ("push", "pull_request", "schedule"):
        if trig not in on:
            problems.append(f"missing trigger: {trig}")
    dast_if = doc["jobs"]["dast"].get("if")
    if dast_if != "github.event_name != 'pull_request'":
        problems.append(f"dast if: is {dast_if!r} (expected pull_request guard)")
    mode = "yaml"
except ImportError:
    # Regex fallback — look for uncommented trigger keys under `on:`.
    for trig in ("push", "pull_request", "schedule"):
        if not re.search(rf"^\s{{2}}{trig}:", raw, re.MULTILINE):
            problems.append(f"missing/commented trigger: {trig}")
    if "if: github.event_name != 'pull_request'" not in raw:
        problems.append("dast job missing if: github.event_name != 'pull_request'")
    mode = "regex"

# --- Textual invariants (same regardless of parse mode) ---
if raw.count("continue-on-error: true") < 3:
    problems.append(
        f"expected >=3 'continue-on-error: true' (ZAP advisory), found {raw.count('continue-on-error: true')}"
    )
if "mypy app/ | mypy-baseline filter" not in raw:
    problems.append("mypy step is not baseline-filtered")
if "|| true" in raw:
    problems.append("a '|| true' mask still present in ci.yml")

if problems:
    print(f"ci.yml FAIL ({mode} mode):")
    for p in problems:
        print("  -", p)
    sys.exit(1)

print(f"ci.yml OK ({mode} mode): triggers armed, dast PR-gated, ZAP advisory, mypy baseline-filtered, no masks")
sys.exit(0)
