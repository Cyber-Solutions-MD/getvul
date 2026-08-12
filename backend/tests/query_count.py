r"""SRC-08 no-N+1 proof harness — Phase 35 Plan 01.

No query-count-assertion surface existed in this codebase before Phase 35
(verified via `grep -rn "before_cursor_execute\|query_count\|statement_count"
backend/tests backend/app` -> zero matches). This is a plain context manager
(no pytest fixture wrapper needed) that attaches a SQLAlchemy
`before_cursor_execute` event listener to the module-level ASYNC engine's
underlying sync engine (`app.db.session.engine.sync_engine` -- the asyncpg
async-engine idiom: the event system only fires on the sync engine that the
async engine wraps internally, not on the `AsyncEngine` object itself).

Reused by Plans 03 (Assets) and 04 (CSPM + Tickets) to prove their own list
endpoints are page-size-invariant in statement count.

Usage:
    from tests.query_count import count_queries

    with count_queries() as statements:
        await some_list_call()
    assert len(statements) == 2  # e.g. 1 primary + 1 batched provenance query
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event


@contextmanager
def count_queries() -> Iterator[list[str]]:
    """Yield a list that accumulates one entry per SQL statement executed
    against the app's async engine while the context manager is active.

    Attaches to `engine.sync_engine` (not the `AsyncEngine` wrapper) per the
    SQLAlchemy 2.0 async-engine idiom -- `before_cursor_execute` only fires
    on the underlying sync engine. Listener is always removed on exit, even
    if the block raises, so a failed assertion never leaks a dangling
    listener into subsequent tests.
    """
    from app.db.session import engine

    statements: list[str] = []

    def _listener(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)
