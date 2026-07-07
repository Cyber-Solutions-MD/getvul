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

            if not isinstance(encrypted_map, dict):
                failing_count += 1
                failures.append((str(connector.id), str(connector.tenant_id), "<not_object>"))
                continue

            row_ok = True
            for field, ciphertext in encrypted_map.items():
                if not isinstance(ciphertext, str):
                    row_ok = False
                    failures.append((str(connector.id), str(connector.tenant_id), field))
                    continue
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
    # audit_logs has FKs into users.id AND tenants.id (see app/audit.py). Both target
    # tables are owned by app/tenants/models.py. When rotate runs via the standalone CLI
    # (`python -m app.encryption`), those models are otherwise never imported, so persisting
    # AuditLog triggers mapper configuration that raises NoReferencedTableError before any
    # commit. Importing the module registers both User and Tenant, resolving both FKs.
    # (Phase 05 UAT gap — Test 5.) Do NOT remove: the eager conftest imports mask this in tests.
    from app.tenants import models as _tenants_models  # noqa: F401  (import for mapper registration)
    from app.ticketing.models import ConnectorConfig

    # Validate both keys upfront (raises ValueError for invalid keys)
    old_fernet = _fernet_for(old_key)
    new_fernet = _fernet_for(new_key)

    async with async_session_factory() as db:
        try:
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

                # Guard against valid-JSON-but-not-an-object shapes (e.g. "5", "[1,2]")
                if not isinstance(encrypted_map, dict):
                    preflight_failures.append((str(connector.id), str(connector.tenant_id), "<not_object>"))
                    continue

                row_plains: dict[str, str] = {}
                for field, ciphertext in encrypted_map.items():
                    # Guard against non-string field values (e.g. {"api_key": 5})
                    if not isinstance(ciphertext, str):
                        preflight_failures.append((str(connector.id), str(connector.tenant_id), field))
                        continue
                    try:
                        plaintext = old_fernet.decrypt(ciphertext.encode()).decode()
                        row_plains[field] = plaintext
                    except (InvalidToken, ValueError):
                        preflight_failures.append((str(connector.id), str(connector.tenant_id), field))

                decoded_maps[str(connector.id)] = row_plains

            if preflight_failures:
                await db.rollback()
                raise RotationPreflightError(preflight_failures, phase="preflight")

            # Rows actually carrying at least one re-encryptable field (WR-05:
            # empty "{}" maps are no-ops and must not inflate the audit row_count).
            rotated_count = sum(1 for c in connectors if decoded_maps.get(str(c.id)))

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

            # POST-VERIFY (D-04): decrypt every re-encrypted field with new_key before commit.
            # Re-encryption produced these maps, so they are always dict[str, str];
            # a failure here means a genuine Fernet/round-trip fault.
            post_failures: list[tuple[str, str, str]] = []
            for connector in connectors:
                encrypted_map = json.loads(connector.credentials_secret_arn)  # type: ignore[arg-type]
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
                # A tenant_id is guaranteed present: rotated_count > 0 implies a
                # non-empty connectors list, each with a NOT NULL tenant_id (WR-06:
                # reuse a loaded row rather than a second query that could disagree).
                log = AuditLog(
                    tenant_id=connectors[0].tenant_id,
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
        except RotationPreflightError:
            # Controlled abort — already rolled back above; re-raise for the caller.
            raise
        except Exception:
            # Defense-in-depth: no code path may leave the session mid-transaction
            # in a partially-mutated state (T-05-02). Roll back, then propagate.
            await db.rollback()
            raise

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


def _print_rotation_failure(e: RotationPreflightError) -> None:
    """Print a controlled rotation-failure report (no key material)."""
    print(f"Rotation failed ({e.phase}):")
    for connector_id, tenant_id, field in e.failures:
        print(f"  connector={connector_id} tenant={tenant_id} field={field}")
    print("No rows were modified. The old key is still active.")


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

    # D-05: for non-dry-run, show row/tenant count and ask for confirmation.
    # The count call runs the full pre-flight and can raise, so guard it too
    # (CR-02) — otherwise a bad dataset crashes before the friendly path.
    if not args.dry_run:
        try:
            dry_result = await rotate_credentials(
                old_key=settings.encryption_key,
                new_key=args.new_key,
                dry_run=True,
                audit=False,
            )
        except RotationPreflightError as e:
            _print_rotation_failure(e)
            sys.exit(1)
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
        _print_rotation_failure(e)
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
