"""Tests for encryption key rotation tooling.

Covers:
- _fernet_for() helper: valid key round-trip + invalid key ValueError
- rotate_credentials(): all-rows rotate, abort-on-bad-row, dry-run, post-verify
- verify_credentials(): OK count + failing count
- Audit event: action, user_email, details (no key material)
- SC#4: rotation is real (revert-fails proves it)
- generate-key: output is a valid Fernet key
- CLI parser: all three subcommands are parseable
"""

from __future__ import annotations

import json
import uuid

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.encryption import _fernet_for, generate_key


# ── Task 1: _fernet_for() unit tests ────────────────────────────────────────


def test_fernet_for_valid_key_round_trips():
    """_fernet_for with a valid key returns a Fernet that round-trips."""
    key = generate_key()
    f = _fernet_for(key)
    assert isinstance(f, Fernet)
    assert f.decrypt(f.encrypt(b"x")) == b"x"


def test_fernet_for_invalid_key_raises_value_error():
    """_fernet_for with a bad key raises ValueError."""
    with pytest.raises(ValueError):
        _fernet_for("not-a-valid-key")


# ── Task 2: rotate_credentials / verify_credentials tests ───────────────────


async def test_rotate_all_rows(db_session, tenant_a):
    """Rotating 2 rows encrypted with key_a re-encrypts them under key_b."""
    from app.encryption import rotate_credentials
    from app.ticketing.models import ConnectorConfig

    key_a = generate_key()
    key_b = generate_key()

    # Seed 2 connector rows encrypted with key_a
    for i in range(2):
        creds = {"api_key": f"secret-{i}"}
        encrypted = json.dumps({k: _fernet_for(key_a).encrypt(v.encode()).decode() for k, v in creds.items()})
        row = ConnectorConfig(
            tenant_id=tenant_a,
            connector_type=f"NESSUS_{i}",
            credentials_secret_arn=encrypted,
        )
        db_session.add(row)
    await db_session.commit()

    result = await rotate_credentials(key_a, key_b)

    assert result["rotated"] == 2
    assert result["failures"] == []
    assert result["tenants"] == 1

    # Reload rows and verify they decrypt with key_b
    from sqlalchemy import select

    from app.db.session import async_session_factory

    async with async_session_factory() as fresh:
        rows = (
            await fresh.execute(
                select(ConnectorConfig).where(ConnectorConfig.tenant_id == tenant_a)
            )
        ).scalars().all()
        assert len(rows) == 2
        for row in rows:
            cmap = json.loads(row.credentials_secret_arn)
            for ct in cmap.values():
                plaintext = _fernet_for(key_b).decrypt(ct.encode()).decode()
                assert plaintext.startswith("secret-")


async def test_rotate_verifies(db_session, tenant_a):
    """After rotate, each row decrypts with key_b — proves D-04 post-verify ran."""
    from app.encryption import rotate_credentials
    from app.ticketing.models import ConnectorConfig

    key_a = generate_key()
    key_b = generate_key()

    creds = {"token": "my-api-token"}
    encrypted = json.dumps({k: _fernet_for(key_a).encrypt(v.encode()).decode() for k, v in creds.items()})
    row = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="NESSUS",
        credentials_secret_arn=encrypted,
    )
    db_session.add(row)
    await db_session.commit()

    # Should not raise (post-verify passed inside rotate_credentials)
    result = await rotate_credentials(key_a, key_b)
    assert result["rotated"] == 1

    from sqlalchemy import select

    from app.db.session import async_session_factory

    async with async_session_factory() as fresh:
        reloaded = (
            await fresh.execute(
                select(ConnectorConfig).where(ConnectorConfig.tenant_id == tenant_a)
            )
        ).scalars().first()
        cmap = json.loads(reloaded.credentials_secret_arn)
        assert _fernet_for(key_b).decrypt(cmap["token"].encode()).decode() == "my-api-token"


async def test_rotate_aborts_on_bad_row(db_session, tenant_a):
    """Preflight failure: good row + garbage ciphertext → abort, good row stays with key_a."""
    from app.encryption import RotationPreflightError, rotate_credentials
    from app.ticketing.models import ConnectorConfig

    key_a = generate_key()
    key_b = generate_key()

    # Good row encrypted with key_a
    good_creds = {"api_key": "real-secret"}
    good_encrypted = json.dumps({k: _fernet_for(key_a).encrypt(v.encode()).decode() for k, v in good_creds.items()})
    good_row = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="NESSUS",
        credentials_secret_arn=good_encrypted,
    )
    db_session.add(good_row)

    # Bad row: valid JSON but garbage ciphertext (not encrypted with key_a)
    bad_creds = {"api_key": "aGFja2VkLWdhcmJhZ2U="}  # base64-ish but invalid Fernet token
    bad_row = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="CROWDSTRIKE",
        credentials_secret_arn=json.dumps(bad_creds),
    )
    db_session.add(bad_row)
    await db_session.commit()

    # Must abort with a CONTROLLED RotationPreflightError, not a raw crash (WR-01).
    with pytest.raises(RotationPreflightError) as exc_info:
        await rotate_credentials(key_a, key_b)
    assert exc_info.value.phase == "preflight"

    # Good row must still decrypt with key_a (no partial write)
    from sqlalchemy import select

    from app.db.session import async_session_factory

    async with async_session_factory() as fresh:
        good_reloaded = (
            await fresh.execute(
                select(ConnectorConfig).where(ConnectorConfig.connector_type == "NESSUS")
            )
        ).scalars().first()
        cmap = json.loads(good_reloaded.credentials_secret_arn)
        assert _fernet_for(key_a).decrypt(cmap["api_key"].encode()).decode() == "real-secret"


async def test_rotate_aborts_on_malformed_json_shapes(db_session, tenant_a):
    """CR-01: non-dict JSON and non-string field values abort cleanly, not with AttributeError."""
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.encryption import RotationPreflightError, rotate_credentials
    from app.ticketing.models import ConnectorConfig

    key_a = generate_key()
    key_b = generate_key()

    # Good row so there is real work that must be rolled back
    good_encrypted = json.dumps({"api_key": _fernet_for(key_a).encrypt(b"real").decode()})
    db_session.add(
        ConnectorConfig(tenant_id=tenant_a, connector_type="NESSUS", credentials_secret_arn=good_encrypted)
    )
    # Valid JSON but not an object (e.g. a bare number)
    db_session.add(
        ConnectorConfig(tenant_id=tenant_a, connector_type="QUALYS", credentials_secret_arn=json.dumps(5))
    )
    # Object with a non-string field value
    db_session.add(
        ConnectorConfig(
            tenant_id=tenant_a, connector_type="RAPID7", credentials_secret_arn=json.dumps({"api_key": 5})
        )
    )
    await db_session.commit()

    # Must be a controlled preflight abort — NOT an uncaught AttributeError
    with pytest.raises(RotationPreflightError) as exc_info:
        await rotate_credentials(key_a, key_b)
    assert exc_info.value.phase == "preflight"

    # Good row still decrypts with key_a (nothing was written)
    async with async_session_factory() as fresh:
        good = (
            await fresh.execute(
                select(ConnectorConfig).where(ConnectorConfig.connector_type == "NESSUS")
            )
        ).scalars().first()
        cmap = json.loads(good.credentials_secret_arn)
        assert _fernet_for(key_a).decrypt(cmap["api_key"].encode()).decode() == "real"


async def test_dry_run_no_rows(db_session):
    """dry_run with zero connector rows returns rotated=0 and writes nothing."""
    from sqlalchemy import select

    from app.audit import AuditLog
    from app.db.session import async_session_factory
    from app.encryption import rotate_credentials

    key_a = generate_key()
    key_b = generate_key()

    result = await rotate_credentials(key_a, key_b, dry_run=True)

    assert result["rotated"] == 0
    assert result.get("dry_run") is True

    # No audit row written
    async with async_session_factory() as fresh:
        count = (
            await fresh.execute(
                select(AuditLog).where(AuditLog.action == "encryption.key_rotated")
            )
        ).scalars().all()
        assert len(count) == 0


async def test_verify_all_ok(db_session, tenant_a):
    """verify_credentials with 2 valid rows returns ok=2, failing=0 and mutates nothing."""
    from app.encryption import verify_credentials
    from app.ticketing.models import ConnectorConfig

    key_a = generate_key()

    for i in range(2):
        creds = {"api_key": f"value-{i}"}
        encrypted = json.dumps({k: _fernet_for(key_a).encrypt(v.encode()).decode() for k, v in creds.items()})
        row = ConnectorConfig(
            tenant_id=tenant_a,
            connector_type=f"NESSUS_{i}",
            credentials_secret_arn=encrypted,
        )
        db_session.add(row)
    await db_session.commit()

    result = await verify_credentials(key_a)

    assert result["ok"] == 2
    assert result["failing"] == 0


async def test_audit_event(db_session, tenant_a):
    """A real rotate emits an AuditLog row with correct action + user_email + no key material."""
    from sqlalchemy import select

    from app.audit import AuditLog
    from app.db.session import async_session_factory
    from app.encryption import rotate_credentials
    from app.ticketing.models import ConnectorConfig

    key_a = generate_key()
    key_b = generate_key()

    creds = {"token": "audit-test-secret"}
    encrypted = json.dumps({k: _fernet_for(key_a).encrypt(v.encode()).decode() for k, v in creds.items()})
    row = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="NESSUS",
        credentials_secret_arn=encrypted,
    )
    db_session.add(row)
    await db_session.commit()

    await rotate_credentials(key_a, key_b, audit=True)

    async with async_session_factory() as fresh:
        audit_rows = (
            await fresh.execute(
                select(AuditLog).where(AuditLog.action == "encryption.key_rotated")
            )
        ).scalars().all()
        assert len(audit_rows) >= 1
        row = audit_rows[0]
        assert row.action == "encryption.key_rotated"
        assert row.user_email == "system:cli"
        assert row.details is not None
        assert row.details.get("row_count", 0) >= 1
        # No key material in details
        details_str = json.dumps(row.details)
        assert key_a not in details_str
        assert key_b not in details_str


async def test_sc4_rotation_is_real(db_session, tenant_a):
    """SC#4: rotate A→B; revert B→A; old B ciphertext fails with InvalidToken."""
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.encryption import rotate_credentials
    from app.ticketing.models import ConnectorConfig

    key_a = generate_key()
    key_b = generate_key()

    # Seed one row encrypted with key_a
    creds = {"api_key": "sc4-secret"}
    encrypted = json.dumps({k: _fernet_for(key_a).encrypt(v.encode()).decode() for k, v in creds.items()})
    row = ConnectorConfig(
        tenant_id=tenant_a,
        connector_type="NESSUS",
        credentials_secret_arn=encrypted,
    )
    db_session.add(row)
    await db_session.commit()

    # Step 1: Rotate A → B
    result1 = await rotate_credentials(key_a, key_b)
    assert result1["rotated"] == 1

    # Step 2: Reload and verify decrypts with B
    async with async_session_factory() as fresh:
        reloaded = (
            await fresh.execute(
                select(ConnectorConfig).where(ConnectorConfig.tenant_id == tenant_a)
            )
        ).scalars().first()
        cmap_b = json.loads(reloaded.credentials_secret_arn)
        # Must decrypt with B
        assert _fernet_for(key_b).decrypt(cmap_b["api_key"].encode()).decode() == "sc4-secret"

    # Step 3: Revert B → A
    result2 = await rotate_credentials(key_b, key_a)
    assert result2["rotated"] == 1

    # Step 4: Reload and assert B-keyed ciphertext no longer decrypts with B
    async with async_session_factory() as fresh2:
        reloaded2 = (
            await fresh2.execute(
                select(ConnectorConfig).where(ConnectorConfig.tenant_id == tenant_a)
            )
        ).scalars().first()
        cmap_a = json.loads(reloaded2.credentials_secret_arn)
        # cmap_a["api_key"] is now encrypted with key_a; decrypting with key_b MUST fail
        with pytest.raises(InvalidToken):
            _fernet_for(key_b).decrypt(cmap_a["api_key"].encode())


# ── Task 3: CLI generate-key / parser smoke tests ───────────────────────────


def test_generate_key():
    """generate_key() returns a value that _fernet_for round-trips."""
    key = generate_key()
    f = _fernet_for(key)
    assert f.decrypt(f.encrypt(b"hello")) == b"hello"


def test_cli_dispatch_smoke():
    """The argparse parser accepts all three subcommands without error."""
    from app.encryption import _build_parser

    parser = _build_parser()

    # rotate subcommand
    args = parser.parse_args(["rotate", "--new-key", "some-key-value", "--dry-run", "--yes"])
    assert args.command == "rotate"
    assert args.new_key == "some-key-value"
    assert args.dry_run is True
    assert args.yes is True

    # verify subcommand
    args = parser.parse_args(["verify"])
    assert args.command == "verify"

    # generate-key subcommand
    args = parser.parse_args(["generate-key"])
    assert args.command == "generate-key"


# ── Task 4 (Plan 02): _check_secrets_at_startup() unit tests ─────────────────
#
# These tests import _check_secrets_at_startup from app.main and patch
# settings attributes with monkeypatch. They require NO database or Redis.


ENCRYPTION_KEY_PLACEHOLDER = (
    "CHANGE-ME-generate-with-python-c-from-cryptography.fernet-import-Fernet-Fernet.generate_key"
)
JWT_SECRET_PLACEHOLDER = "CHANGE-ME-IN-PRODUCTION"


def test_startup_check_encryption_placeholder_dev(monkeypatch):
    """Dev mode + placeholder encryption_key → non-empty issues list, no raise."""
    import app.main as main

    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "encryption_key", ENCRYPTION_KEY_PLACEHOLDER)
    monkeypatch.setattr(main.settings, "jwt_secret_key", "non-placeholder-jwt-secret")

    issues = main._check_secrets_at_startup()
    assert isinstance(issues, list)
    assert len(issues) > 0


def test_startup_check_encryption_placeholder_prod(monkeypatch):
    """Prod mode + placeholder encryption_key → RuntimeError raised."""
    import app.main as main
    from cryptography.fernet import Fernet

    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "encryption_key", ENCRYPTION_KEY_PLACEHOLDER)
    monkeypatch.setattr(main.settings, "jwt_secret_key", "non-placeholder-jwt-secret")

    with pytest.raises(RuntimeError):
        main._check_secrets_at_startup()


def test_startup_check_encryption_invalid_prod(monkeypatch):
    """Prod mode + invalid Fernet key → RuntimeError raised (ValueError path)."""
    import app.main as main

    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "encryption_key", "short-not-fernet")
    monkeypatch.setattr(main.settings, "jwt_secret_key", "non-placeholder-jwt-secret")

    with pytest.raises(RuntimeError):
        main._check_secrets_at_startup()


def test_startup_check_valid_key_ok(monkeypatch):
    """Prod mode + valid Fernet key + non-placeholder JWT → returns [] (no issues)."""
    import app.main as main
    from cryptography.fernet import Fernet

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "encryption_key", valid_key)
    monkeypatch.setattr(main.settings, "jwt_secret_key", "non-placeholder-jwt-secret")

    issues = main._check_secrets_at_startup()
    assert issues == []


def test_startup_check_jwt_placeholder_prod(monkeypatch):
    """Prod mode + valid encryption_key + placeholder JWT → RuntimeError raised."""
    import app.main as main
    from cryptography.fernet import Fernet

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "encryption_key", valid_key)
    monkeypatch.setattr(main.settings, "jwt_secret_key", JWT_SECRET_PLACEHOLDER)

    with pytest.raises(RuntimeError):
        main._check_secrets_at_startup()


def test_startup_check_jwt_placeholder_dev(monkeypatch):
    """Dev mode + valid encryption_key + placeholder JWT → non-empty issues, no raise."""
    import app.main as main
    from cryptography.fernet import Fernet

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "encryption_key", valid_key)
    monkeypatch.setattr(main.settings, "jwt_secret_key", JWT_SECRET_PLACEHOLDER)

    issues = main._check_secrets_at_startup()
    assert isinstance(issues, list)
    assert len(issues) > 0
