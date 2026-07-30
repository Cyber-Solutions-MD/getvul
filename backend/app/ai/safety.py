"""Dangerous-command denylist (D-04/D-05) -- the maintained, single-source-
of-truth safety gate every AI-authored 'explain'/'remediation' response is
scanned against before it is ever cached or streamed to an analyst.

`contains_dangerous_pattern()` reuses `app.ai.explain._contains_leak_marker`'s
exact haystack-composition idiom (summary + business_risk + every citation's
text), then additionally lowercase+whitespace-normalizes before scanning --
D-05's "obfuscation-resistant matching where cheap": mixed case, extra/
collapsed whitespace, and a dangerous phrase split across summary/
business_risk/a citation's text (all stitched into one contiguous,
single-spaced string by the haystack's " ".join) are all still caught.

This is a pure text scan over already schema-validated LLM prose -- NOT a
shell-AST / base64-decode / command-substitution canonicalization pipeline.
GetVul's threat model here is a small, known set of destructive phrases
appearing in generated guidance, not an adversary actively evading a live
command interceptor (25-RESEARCH.md "Don't Hand-Roll" / Alternatives
Considered -- a full canonicalization engine would be substantial unused
complexity for this scope). D-04 applies uniformly to scanner_verbatim and
ai_interpreted text alike -- there is no provenance carve-out: on any hit
the ENTIRE guidance is refused (25-RESEARCH.md Assumptions A2).

Scope (25-RESEARCH.md Open Question 1, resolved at plan time): ships ONLY
the 8 categories below this phase. A candidate 9th "credential-rotation
instructions" category was considered and explicitly DEFERRED -- D-05's
maintained-constant design makes adding a category a trivial one-line
follow-up if real usage shows a need, and D-04's literal example list is
already fully covered by these 8.
"""

from __future__ import annotations

import re

from app.ai.schemas import ExplainResponseBase

DANGEROUS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rm -rf", re.compile(r"\brm\s+(-[a-z]*\s+)*-[a-z]*r[a-z]*f[a-z]*\b")),
    ("drop table/database", re.compile(r"\bdrop\s+(table|database)\b")),
    ("truncate table", re.compile(r"\btruncate\s+table\b")),
    ("mkfs", re.compile(r"\bmkfs\.\w+\b|\bmkfs\s")),
    ("dd to a block device", re.compile(r"\bdd\s+if=\S+\s+of=/dev/")),
    ("chmod 777 / a+rwx", re.compile(r"\bchmod\s+(-r\s+)?(777|a\+rwx)\b")),
    ("pipe download to shell", re.compile(r"\b(curl|wget)\b[^|\n]*\|\s*(sh|bash|zsh)\b")),
    (
        "disable security control",
        re.compile(
            r"\bdisable\s+(the\s+)?(firewall|edr|antivirus|selinux|apparmor)\b"
            r"|\bsetenforce\s+0\b|\bufw\s+disable\b|\bstop\b.*\bfirewalld\b"
        ),
    ),
)


def contains_dangerous_pattern(candidate: ExplainResponseBase) -> str | None:
    """Scan `candidate`'s text fields for a DANGEROUS_PATTERNS hit.

    Composes the haystack using the IDENTICAL idiom as
    `_contains_leak_marker` (summary + business_risk + every citation.text),
    then lowercase+whitespace-normalizes before matching. Returns the
    matched pattern's label (for the audit row) on the first hit, else None.
    """
    haystack = " ".join([candidate.summary, candidate.business_risk, *(c.text for c in candidate.citations)])
    normalized = re.sub(r"\s+", " ", haystack.lower())
    for label, pattern in DANGEROUS_PATTERNS:
        if pattern.search(normalized):
            return label
    return None
