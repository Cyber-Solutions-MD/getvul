# Phase 39 — API Coverage Decision

**Detector result:** the phase scope mentions Slack / Teams / email / PagerDuty (in
`detect_and_escalate`) and Jira / Asana ticket creation (in `ticketing/rule_engine.py`),
which can trip the external-API detector.

**Decision: No external API integration.**

Phase 39 integrates **no** external API, SDK, or service. It is internal exclusion logic
over the existing `Vulnerability` model plus one new internal `exceptions` table. The
escalation channels and ticket providers named above are pre-existing integrations owned by
Phase 36 (SLA escalation) and Phases 23/37 (ticketing). Phase 39's only interaction with
them is to **suppress** their firing for actively-excepted findings by adding a `WHERE`
predicate (`~active_exception_subquery`) to the queries that feed them — it adds no new
capability, endpoint, auth, or payload against any external provider.

- New dependencies: **none** (RESEARCH.md §Standard Stack — zero new packages).
- New external endpoints called: **none**.
- The only infrastructure touch is an Alembic migration (`050_add_exceptions`) against the
  same Postgres instance every prior phase already migrates.

Therefore a capability coverage matrix does not apply. This reasoned declaration is written
per the API Coverage checkpoint's "if it fires but the phase genuinely integrates no
external API, write a reasoned no-integration declaration" rule.
