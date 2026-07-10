"""Operational logging configuration for the GetVul API.

This module provides structured logging via structlog for the FastAPI application.
It is distinct from the audit CEF/syslog pipeline in app/audit.py (D-18, kept
independent). The full implementation (ProcessorFormatter, JSONRenderer, stdlib
bridge) lands in plan 07-02. This stub exposes the three public names so that
`from app.logging import configure_logging, redact_sensitive_keys, SENSITIVE_KEYS`
resolves cleanly — allowing test collection (07-00) and middleware wiring (07-01)
to proceed before the real logging config is in place.
"""

# D-17: Keys whose values must be scrubbed to "[REDACTED]" before any log
# rendering. This set is intentionally frozen so processors can iterate over it
# safely without risk of mutation.
SENSITIVE_KEYS: frozenset = frozenset(
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


def redact_sensitive_keys(logger, method, event_dict):
    """Scrub known-sensitive keys from the structlog event dict before rendering.

    Structlog processor signature: (logger, method, event_dict) -> event_dict.
    Must run BEFORE the renderer (JSONRenderer / ConsoleRenderer) in the
    processor chain.

    Full implementation lands in plan 07-02. The stub raises NotImplementedError
    so that test_redact_sensitive_keys (which calls this directly) fails for the
    right reason — confirming the RED state — rather than silently passing with
    an empty implementation.
    """
    raise NotImplementedError("implemented in 07-02")


def configure_logging() -> None:
    """Configure structlog + stdlib root logger for a unified output stream.

    - production (ENVIRONMENT=production): JSON via JSONRenderer + orjson
    - dev: human-readable via ConsoleRenderer
    - Min level: INFO in prod, DEBUG in dev
    - Both structlog and stdlib loggers (uvicorn.*) emit through the same chain

    Full implementation lands in plan 07-02. The stub is a no-op so that
    app startup (lifespan) does not crash before 07-02 lands — logging tests
    will still be RED because they assert a ProcessorFormatter/JSONRenderer is
    configured, which a no-op does not do.
    """
    return
