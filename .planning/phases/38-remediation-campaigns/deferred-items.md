# Phase 38 — Deferred Items

Out-of-scope discoveries logged during execution, per the executor's scope-boundary rule
(only auto-fix issues directly caused by the current task's changes).

## Plan 38-01

### Pre-existing mypy-baseline flake in unrelated files (not fixed)

**Found during:** Task 3 verification (`mypy app/ | mypy-baseline filter --allow-unsynced`).

**Issue:** The baseline-filtered mypy run reports a small, consistent delta of "new" violations
entirely inside two files this plan never touches:
- `app/ticketing/daily_sync.py:49,131,135,140,145,150` (missing type annotation / untyped-call /
  incompatible-assignment errors)
- `app/auth/dependencies.py:10` (a `jose`-stubs-missing `note`)

**Confirmed pre-existing, not introduced by this plan:** Reproduced identically via
`git stash` (reverting all Task 3 files, leaving only Task 2's already-committed
`campaigns/models.py` + migration in place) + `rm -rf .mypy_cache` + re-run. The exact same
delta signature (`+1 no-untyped-def, +2 assignment, +3 note, +3 no-untyped-call, -2 type-arg`)
appeared with zero campaigns-authored code present at all. This matches the previously-logged
project memory finding (`getvul-backend-test-harness-rot` / Phase 29 summary) of a
non-deterministic `mypy-baseline.txt` drift unrelated to any single plan's edits.

**Action:** Not fixed — out of scope (SCOPE BOUNDARY: pre-existing issues in unrelated files).
Genuinely new mypy issues introduced by this plan's own new files (`app/campaigns/service.py`
missing `dict[str, int]` type args, `app/campaigns/router.py` missing 3 endpoint return-type
annotations + a `dict` type-arg) were found and fixed before committing Task 3.

**Suggested follow-up:** Whoever next touches `app/ticketing/daily_sync.py` should confirm
whether `mypy-baseline.txt` needs a regeneration (`mypy-baseline sync`) to resync the checked-in
baseline against current `mypy`/stub versions.

## Plan 38-02

### Same pre-existing mypy-baseline flake, reconfirmed (not fixed)

**Found during:** Task 2 verification (`mypy app/ | mypy-baseline filter --allow-unsynced`).

**Issue:** Identical delta signature to the Plan 01 entry above
(`app/ticketing/daily_sync.py` untyped-def/untyped-call/assignment errors +
`app/auth/dependencies.py`'s jose-stub `note`), reproduced again via `git stash` (reverting
both Plan 02 commits) + rerun — byte-identical 9-fixed/9-new totals with zero campaigns code
present. Still out of scope; not fixed.

### `requirements ready-ids` SDK verb not installed in this environment

**Found during:** Pre-commit check of CAMP-02/CAMP-04's shared-requirement completion status.

**Issue:** `node .../get-shit-done-cc/sdk/dist/cli.js query requirements.ready-ids` falls back
to the bundled `gsd-tools.cjs`, which only exposes a `mark-complete` subcommand — `ready-ids`
does not exist in this environment's installed tooling.

**Action:** Not fixed (SDK installation is out of this plan's scope). Worked around by reading
every phase-38 `PLAN.md`'s `requirements:` frontmatter field directly: CAMP-02 is also declared
by `38-05-PLAN.md` (no `38-05-SUMMARY.md` yet) and CAMP-04 is also declared by `38-01`/`38-03`
(neither has marked it complete either) — both confirmed still blocked, matching what
`requirements ready-ids` would have reported were it available.

## Plan 38-05

### `JiraClient.create_ticket()` doesn't catch network/protocol-level exceptions (pre-existing, Phase 23, not fixed)

**Found during:** Task 3 checkpoint-prep — smoke-testing `POST /{campaign_id}/bulk-assign`
against the local dev stack before handing off the human-verify checkpoint.

**Issue:** `backend/app/ticketing/jira_client.py::create_ticket()`'s docstring promises
"Returns a `JiraIssue` on 201, `None` on failure" and the code DOES correctly return `None`
for any non-201 HTTP response — but it never wraps `self._client.post(...)` in a try/except,
so a connection-level failure (DNS failure, connection refused, or — as reproduced here — an
`httpx.UnsupportedProtocol` when the connector's stored `url` credential is an empty string)
raises an unhandled exception straight through `dispatch.py::JiraAdapter.create()` and
`campaigns/service.py::bulk_create_campaign_tickets()`, producing an unhandled 500 instead of
the graceful "add this owner to `failed_owners`" path `bulk_create_campaign_tickets()` already
implements correctly for the *handled* (bad-status-code) failure case.

**Reproduced:** The seed script (`backend/seed_data.py`) creates a `JIRA` `ConnectorConfig`
row with `config={"workspace": "Demo", "project_key": "VULN"}` but an EMPTY
`credentials_secret_arn` (`get_decrypted_credentials()` returns `{}`) — so `JiraClient` is
constructed with `email=""`, `api_token=""`, `base_url=""`, and the very first
`self._client.post("/rest/api/3/issue", ...)` call raises
`httpx.UnsupportedProtocol: Request URL is missing an 'http://' or 'https://' protocol`
(confirmed via the backend container's own traceback log, `campaigns/router.py:216` →
`campaigns/service.py:332` → `dispatch.py:80` → `jira_client.py:126`).

**Action:** NOT fixed — `backend/app/ticketing/jira_client.py` is Phase 23 code, outside this
plan's (`38-05`, frontend-only) file scope (SCOPE BOUNDARY: pre-existing issues in unrelated
files). Worked around at the DATA layer only (not code): updated the demo `JIRA`
`ConnectorConfig`'s encrypted credentials to point `url` at a real, reachable
non-Jira host (`https://httpbin.org`) so `POST /rest/api/3/issue` gets a real (404) HTTP
response instead of a connection-level exception — this lets the ALREADY-CORRECT
`bulk_create_campaign_tickets()` failure-handling path (`if url is None:
failed_owners.append(...)`) execute as designed, so the checkpoint's "Create N tickets" step
demonstrates the intended amber partial-failure banner instead of a 500. Verified live:
`POST /{id}/bulk-assign` now returns `{"created_tickets":0,...,"failed_owners":[null]}` (200,
not 500).

**Suggested follow-up:** `jira_client.py::create_ticket()` (and likely its `get`/`comment`/
`close` siblings, plus `asana_client.py`/`github_client.py`'s equivalents) should wrap their
`self._client.<verb>(...)` calls in a `try/except httpx.HTTPError` (or narrower) that logs and
returns `None`/no-ops on a connection-level failure, matching the docstring's existing
"`None` on failure" contract for the non-201-status case. Out of scope for a future phase to
pick up — flagged here so it isn't mistaken for a Phase 38 regression.
