"""Symmetric encryption for connector credentials using Fernet."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select

from app.config import settings


def _get_fernet() -> Fernet:
    """Get Fernet instance from the configured encryption key."""
    key = settings.encryption_key.encode()
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Returns plaintext."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """Generate a new Fernet encryption key. Run once, store in .env."""
    return Fernet.generate_key().decode()


def _fernet_for(key: str) -> Fernet:
    """Return a Fernet instance for an explicit key string.

    Raises ValueError if key is not a valid 32-byte url-safe base64 Fernet key.
    """
    return Fernet(key.encode())


# ── Rotation exceptions ──────────────────────────────────────────────────────


class RotationPreflightError(Exception):
    """Raised when one or more rows fail to decrypt during pre-flight or post-verify.

    Attributes:
        failures: list of (connector_id, tenant_id, field) tuples that failed.
        phase: "preflight" or "post_verify"
    """

    def __init__(self, failures: list[tuple[str, str, str]], phase: str = "preflight") -> None:
        self.failures = failures
        self.phase = phase
        super().__init__(
            f"Rotation {phase} failed for {len(failures)} field(s): "
            + ", ".join(f"{cid}/{field}" for cid, _, field in failures[:5])
        )


# ── Core rotation logic ──────────────────────────────────────────────────────


async def verify_credentials(current_key: str) -> dict:
    """Read-only: decrypt every connector credential row with current_key.

    Returns:
        {"ok": N, "failing": M, "failures": [(connector_id, tenant_id, field), ...]}

    Mutates nothing; commits nothing.
    """
    from app.db.session import async_session_factory
    from app.ticketing.models import ConnectorConfig

    ok_count = 0
    failing_count = 0
    failures: list[tuple[str, str, str]] = []

    async with async_session_factory() as db:
        result = await db.execute(
            select(ConnectorConfig).where(ConnectorConfig.credentials_secret_arn.isnot(None))
        )
        connectors = result.scalars().all()

        f = _fernet_for(current_key)

        for connector in connectors:
            try:
                encrypted_map = json.loads(connector.credentials_secret_arn)  # type: ignore[arg-type]
            except (json.JSONDecodeError, TypeError):
                failing_count += 1
                failures.append((str(connector.id), str(connector.tenant_id), "<json_parse>"))
                continue

            row_ok = True
            for field, ciphertext in encrypted_map.items():
                try:
                    f.decrypt(ciphertext.encode())
                except (InvalidToken, ValueError):
                    row_ok = False
                    failures.append((str(connector.id), str(connector.tenant_id), field))

            if row_ok:
                ok_count += 1
            else:
                failing_count += 1

    return {"ok": ok_count, "failing": failing_count, "failures": failures}


async def rotate_credentials(
    old_key: str,
    new_key: str,
    dry_run: bool = False,
    audit: bool = True,
) -> dict:
    """Re-encrypt every connector credential row from old_key to new_key.

    Single-transaction, abort-all-or-nothing:
    1. Validate both keys.
    2. Load all ConnectorConfig rows with non-null credentials_secret_arn.
    3. PRE-FLIGHT: decrypt every field with old_key; collect failures.
       Any failure → rollback + raise RotationPreflightError.
    4. If dry_run: rollback, return count without writing.
    5. RE-ENCRYPT: re-encrypt every field with new_key in-memory.
    6. POST-VERIFY: decrypt every re-encrypted field with new_key.
       Any failure → rollback + raise RotationPreflightError.
    7. AUDIT: write AuditLog row directly (not via audit() helper).
    8. COMMIT once.

    Returns:
        {"rotated": N, "tenants": M, "failures": [], "dry_run": bool}

    Raises:
        ValueError: if old_key or new_key is not a valid Fernet key.
        RotationPreflightError: if any row fails pre-flight or post-verify.
    """
    from app.audit import AuditLog
    from app.db.session import async_session_factory
    from app.ticketing.models import ConnectorConfig

    # Validate both keys upfront (raises ValueError for invalid keys)
    old_fernet = _fernet_for(old_key)
    new_fernet = _fernet_for(new_key)

    async with async_session_factory() as db:
        # Load all rows with credentials in a single query
        result = await db.execute(
            select(ConnectorConfig).where(ConnectorConfig.credentials_secret_arn.isnot(None))
        )
        connectors = result.scalars().all()

        # Count distinct tenants
        tenant_count_result = await db.execute(
            select(func.count(ConnectorConfig.tenant_id.distinct())).where(
                ConnectorConfig.credentials_secret_arn.isnot(None)
            )
        )
        tenant_count = tenant_count_result.scalar_one()

        # PRE-FLIGHT: decrypt every field with old key, collect failures
        preflight_failures: list[tuple[str, str, str]] = []
        # Store decoded plaintexts for re-encryption
        decoded_maps: dict[str, dict[str, str]] = {}

        for connector in connectors:
            try:
                encrypted_map = json.loads(connector.credentials_secret_arn)  # type: ignore[arg-type]
            except (json.JSONDecodeError, TypeError):
                preflight_failures.append((str(connector.id), str(connector.tenant_id), "<json_parse>"))
                continue

            row_plains: dict[str, str] = {}
            for field, ciphertext in encrypted_map.items():
                try:
                    plaintext = old_fernet.decrypt(ciphertext.encode()).decode()
                    row_plains[field] = plaintext
                except (InvalidToken, ValueError):
                    preflight_failures.append((str(connector.id), str(connector.tenant_id), field))

            decoded_maps[str(connector.id)] = row_plains

        if preflight_failures:
            await db.rollback()
            raise RotationPreflightError(preflight_failures, phase="preflight")

        rotated_count = len(connectors)

        # DRY RUN: report count and bail without writing
        if dry_run:
            await db.rollback()
            return {
                "rotated": rotated_count,
                "tenants": tenant_count,
                "failures": [],
                "dry_run": True,
            }

        # RE-ENCRYPT: build new ciphertexts with new_key, update rows in memory
        for connector in connectors:
            plains = decoded_maps[str(connector.id)]
            new_map = {
                field: new_fernet.encrypt(plaintext.encode()).decode()
                for field, plaintext in plains.items()
            }
            connector.credentials_secret_arn = json.dumps(new_map)

        # POST-VERIFY (D-04): decrypt every re-encrypted field with new_key before commit
        post_failures: list[tuple[str, str, str]] = []
        for connector in connectors:
            try:
                encrypted_map = json.loads(connector.credentials_secret_arn)  # type: ignore[arg-type]
            except (json.JSONDecodeError, TypeError):
                post_failures.append((str(connector.id), str(connector.tenant_id), "<json_parse>"))
                continue

            for field, ciphertext in encrypted_map.items():
                try:
                    new_fernet.decrypt(ciphertext.encode())
                except (InvalidToken, ValueError):
                    post_failures.append((str(connector.id), str(connector.tenant_id), field))

        if post_failures:
            await db.rollback()
            raise RotationPreflightError(post_failures, phase="post_verify")

        # AUDIT (D-08): write AuditLog directly (not via audit() helper — avoids FK sentinel)
        if audit and rotated_count > 0:
            # Query for a real tenant_id to satisfy the NOT NULL FK
            first_tenant_result = await db.execute(
                select(ConnectorConfig.tenant_id).where(
                    ConnectorConfig.credentials_secret_arn.isnot(None)
                ).limit(1)
            )
            first_tenant_id = first_tenant_result.scalar_one_or_none()

            if first_tenant_id is not None:
                log = AuditLog(
                    tenant_id=first_tenant_id,
                    user_id=None,
                    user_email="system:cli",
                    action="encryption.key_rotated",
                    resource_type="encryption_key",
                    resource_id=None,
                    details={
                        "row_count": rotated_count,
                        "tenant_count": tenant_count,
                        "dry_run": False,
                    },
                    ip_address=None,
                    created_at=datetime.now(UTC),
                )
                db.add(log)

        # COMMIT once (D-01/D-03: single transaction)
        await db.commit()

    return {
        "rotated": rotated_count,
        "tenants": tenant_count,
        "failures": [],
        "dry_run": False,
    }


# ── Argparse CLI parser (extracted for testability) ──────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="GetVul encryption key management",
        prog="python -m app.encryption",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate-key subcommand
    sub.add_parser("generate-key", help="Print a new Fernet encryption key")

    # verify subcommand
    sub.add_parser(
        "verify",
        help="Decrypt all connector credentials with the current key (read-only)",
    )

    # rotate subcommand
    rot = sub.add_parser(
        "rotate",
        help="Re-encrypt all connector credentials with a new key",
    )
    rot.add_argument("--new-key", required=True, help="New Fernet encryption key")
    rot.add_argument(
        "--dry-run",
        action="store_true",
        help="Report row count without writing any changes",
    )
    rot.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts",
    )

    return parser


# ── CLI async command implementations ────────────────────────────────────────


async def _cmd_verify() -> None:
    """Run verify subcommand."""
    result = await verify_credentials(settings.encryption_key)
    ok = result["ok"]
    failing = result["failing"]
    print(f"{ok} OK / {failing} failing")
    if result["failures"]:
        print("Failing connectors:")
        for connector_id, tenant_id, field in result["failures"]:
            print(f"  connector={connector_id} tenant={tenant_id} field={field}")
    if failing > 0:
        sys.exit(1)


async def _cmd_rotate(args: argparse.Namespace) -> None:
    """Run rotate subcommand."""
    # Validate new key before doing anything (D-04/T-05-04)
    try:
        _fernet_for(args.new_key)
    except ValueError:
        sys.exit("--new-key is not a valid Fernet key")

    # D-07: backup reminder FIRST, require acknowledgement
    print("IMPORTANT: Before rotating the encryption key:")
    print("  1. Back up the current ENCRYPTION_KEY value to your off-box secrets vault")
    print("     (1Password, HashiCorp Vault, or your cloud secrets manager).")
    print("  2. Take a database snapshot / backup.")
    print("  These steps are required to recover if rotation fails unexpectedly.")
    print()

    if not args.yes:
        ack = input("Have you backed up the key and taken a DB snapshot? [y/N] ").strip().lower()
        if ack != "y":
            print("Rotation aborted.")
            sys.exit(0)

    # D-05: for non-dry-run, show row/tenant count and ask for confirmation
    if not args.dry_run:
        dry_result = await rotate_credentials(
            old_key=settings.encryption_key,
            new_key=args.new_key,
            dry_run=True,
            audit=False,
        )
        n_rows = dry_result["rotated"]
        m_tenants = dry_result["tenants"]

        # D-06: confirmation prompt
        if not args.yes:
            confirm = input(
                f"This will re-encrypt {n_rows} rows across {m_tenants} tenants. Continue? [y/N] "
            ).strip().lower()
            if confirm != "y":
                print("Rotation aborted.")
                sys.exit(0)

    try:
        result = await rotate_credentials(
            old_key=settings.encryption_key,
            new_key=args.new_key,
            dry_run=args.dry_run,
        )
    except RotationPreflightError as e:
        print(f"Rotation failed ({e.phase}):")
        for connector_id, tenant_id, field in e.failures:
            print(f"  connector={connector_id} tenant={tenant_id} field={field}")
        print("No rows were modified. The old key is still active.")
        sys.exit(1)

    if args.dry_run:
        print(f"[dry-run] Would rotate {result['rotated']} rows across {result['tenants']} tenants.")
        print("[dry-run] No changes were written.")
    else:
        print(f"Rotated {result['rotated']} rows across {result['tenants']} tenants.")
        # D-02: print restart instruction WITHOUT echoing the actual key value
        print("Rotation complete. Set ENCRYPTION_KEY=<new key> in .env and restart the backend")


# ── CLI entrypoint ────────────────────────────────────────────────────────────


if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "generate-key":
        print(generate_key())
    elif args.command == "verify":
        asyncio.run(_cmd_verify())
    elif args.command == "rotate":
        asyncio.run(_cmd_rotate(args))
