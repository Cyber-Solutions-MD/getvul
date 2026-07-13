"""Operational logging configuration for the GetVul API.

This module configures structured logging via structlog for the FastAPI
application, unifying the app structlog stream and the stdlib uvicorn.*
loggers through a single processor chain (D-11, D-12).

It is wholly distinct from the audit CEF/syslog pipeline in app/audit.py
(D-18). The two channels are kept independent by design: configure_logging()
does not touch the SysLogHandler that audit.py wires, and audit.py does not
call configure_logging().

Usage (from lifespan in main.py):
    from app.logging import configure_logging
    configure_logging()  # must be the FIRST call in lifespan — before any
                         # structlog.get_logger() is used (Pitfall 5 / A3)
"""

import logging
import re
import sys
from collections.abc import Callable

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from app.config import settings

# D-17: Keys whose values must be scrubbed to "[REDACTED]" before any log
# rendering.  The frozenset is intentionally immutable so processors can
# iterate over it safely without risk of mutation.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "password",
        "token",
        "secret",
        "credentials",
        "api_key",
    }
)


def _is_sensitive(key: object) -> bool:
    """True if `key` names a sensitive value, matched case-insensitively (D-17).

    HTTP header keys arrive title-cased (`Authorization`, `Cookie`) via the
    uvicorn foreign_pre_chain, so an exact-case comparison would miss them.
    SENSITIVE_KEYS is stored lowercase; compare against `key.lower()`.
    """
    return isinstance(key, str) and key.lower() in SENSITIVE_KEYS


def _redact_value(value: object) -> object:
    """Recursively redact sensitive keys nested inside mappings/sequences.

    A leaked credential is just as sensitive one level down (e.g. a
    `headers={"Authorization": ...}` sub-dict), so the scrub must descend into
    nested dicts and lists rather than only touching the top level.
    """
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _is_sensitive(k) else _redact_value(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_redact_value(v) for v in value)
    return value


def redact_sensitive_keys(logger: WrappedLogger, method: str, event_dict: EventDict) -> EventDict:
    """Scrub known-sensitive keys from the structlog event dict before rendering.

    Structlog processor signature: (logger, method, event_dict) -> event_dict.
    Must run BEFORE the renderer (JSONRenderer / ConsoleRenderer) in the
    processor chain so that sensitive values never reach the output stream.

    Matching is case-insensitive (title-cased HTTP header keys) and recursive
    (nested dicts/lists), because this processor also runs over foreign uvicorn
    records via foreign_pre_chain where credentials appear nested and
    title-cased (D-17, CR-01).

    Snapshots the key list before mutating so reassigning values never triggers
    a "dict changed size during iteration" error (Pitfall 6). Does not raise on
    an empty dict.
    """
    for key in list(event_dict.keys()):
        if _is_sensitive(key):
            event_dict[key] = "[REDACTED]"
        else:
            event_dict[key] = _redact_value(event_dict[key])
    return event_dict


class _ProbePathFilter(logging.Filter):
    """Drop uvicorn.access records for /health and /ready probe paths (D-19).

    Suppresses ONLY the "GET /ready ... 503" / "GET /health ... 200" lines
    emitted by the uvicorn access logger — it does NOT touch the application
    structlog logger, so a failed /ready still emits its own
    readiness_check_failed event (Pitfall 7: different logger instances).
    """

    _PROBE_PATHS = frozenset({"/health", "/ready"})
    # uvicorn access lines look like: '127.0.0.1:52340 - "GET /ready HTTP/1.1" 200'
    # Capture the request target between the method and " HTTP/", dropping any
    # query string, so we match the exact path — not a substring. Substring
    # matching would wrongly suppress /health-history or ?redirect=/ready (WR-01).
    _REQUEST_LINE = re.compile(r'"[A-Z]+ (?P<path>[^ ?]+)(?:\?[^ ]*)? HTTP/')

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        match = self._REQUEST_LINE.search(record.getMessage())
        if match is None:
            return True  # not a request line we recognize — keep it
        return match.group("path") not in self._PROBE_PATHS


def configure_logging() -> None:
    """Configure structlog + stdlib root logger for a unified output stream.

    Environment-gated renderer selection (D-11, D-16):
    - ENVIRONMENT=production  →  JSON via JSONRenderer(serializer=orjson.dumps)
    - any other value          →  human-readable ConsoleRenderer

    Level gating (D-16):
    - production (DEBUG=false)  →  INFO
    - dev (DEBUG=true)          →  DEBUG

    Processor chain (D-15, D-11):
    Both structlog loggers and stdlib loggers (uvicorn.access, uvicorn.error,
    uvicorn) flow through the same shared_processors chain, unified via
    ProcessorFormatter and foreign_pre_chain.

    Sensitive key redaction (D-17, T-07-02-01):
    redact_sensitive_keys runs LAST in shared_processors (i.e., immediately
    before the renderer) so it scrubs values regardless of which code path
    produced the event.

    Probe-path suppression (D-19):
    _ProbePathFilter is added to the uvicorn.access logger to suppress the
    routine access-log lines for /health and /ready. Application-level
    readiness_check_failed events (different logger) are not affected.

    IMPORTANT — Pitfall 5 / A3:
    structlog.reset_defaults() is called FIRST to guarantee a clean slate,
    defeating the module-level `logger = structlog.get_logger()` cache in
    main.py (line 34) regardless of import order.
    """
    # Step 1: Reset structlog to a clean slate BEFORE any configuration.
    # This defeats the module-level logger cache in main.py (Pitfall 5 / A3).
    structlog.reset_defaults()

    import orjson  # local import — keeps side effects minimal at module load

    # Step 2: Level gating — INFO in production, DEBUG in dev (D-16).
    min_level = logging.DEBUG if settings.debug else logging.INFO

    # Step 3: Build the shared processor chain.
    # Order is significant (D-15 default field keys, Pitfall 6, T-07-02-03):
    #   - merge_contextvars FIRST so request_id is injected before any other
    #     processor sees the event dict.
    #   - redact_sensitive_keys LAST so it runs after all context enrichment
    #     and immediately before the renderer.
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # injects request_id (D-13)
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        redact_sensitive_keys,  # MUST be last before renderer (D-17)
    ]

    # Step 4: Choose renderer based on environment (D-11).
    # structlog's JSONRenderer calls serializer(event_dict, default=...) —
    # passing a `default` callable for types the serializer can't handle
    # natively. orjson.dumps accepts `default` too, so forward it (rather than
    # dropping it, which would raise TypeError on any non-native type — WR-04).
    # orjson returns bytes; decode to str for ProcessorFormatter.
    def _json_serializer(obj: object, default: Callable[..., object] | None = None, **_kw: object) -> str:
        return orjson.dumps(obj, default=default).decode("utf-8")

    renderer: Processor
    if settings.environment == "production":
        renderer = structlog.processors.JSONRenderer(serializer=_json_serializer)
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # Step 5: Configure structlog.
    # processors list must end with wrap_for_formatter so structlog-native log
    # events are routed through the stdlib StreamHandler below (D-11, Pitfall 2).
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        cache_logger_on_first_use=True,
    )

    # Step 6: Create ProcessorFormatter for the stdlib side.
    # remove_processors_meta MUST be first — strips _record/_from_structlog
    # internal keys that ProcessorFormatter injects (Pitfall 2).
    # foreign_pre_chain applies shared_processors to records that originate
    # from stdlib loggers (uvicorn.access, uvicorn.error, etc.) so they travel
    # through the same enrichment chain (D-11, T-07-02-03).
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # Step 7: Attach ONE StreamHandler to the root logger.
    # Clearing existing handlers first prevents duplicate output if
    # configure_logging() is ever called more than once (e.g., in tests).
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = []  # remove any handler basicConfig may have added
    root_logger.addHandler(handler)
    root_logger.setLevel(min_level)

    # Step 8: Suppress /health + /ready from uvicorn.access (D-19).
    # Failed /ready still emits its own readiness_check_failed via the
    # application structlog logger — that path is a different logger and
    # is NOT suppressed here (Pitfall 7).
    logging.getLogger("uvicorn.access").addFilter(_ProbePathFilter())
