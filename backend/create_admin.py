"""Create default tenant and admin user if none exist."""

import asyncio
import sys

from sqlalchemy import text

from app.db.session import async_session_factory


async def create_admin():
    async with async_session_factory() as db:
        # Check if any user with password exists (app user, not synced directory user)
        result = await db.execute(text("SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL"))
        count = result.scalar()
        if count > 0:
            print("    App users already exist — skipping.")
            return

        # Ensure a tenant exists
        result = await db.execute(text("SELECT id FROM tenants LIMIT 1"))
        tenant = result.scalar()
        if not tenant:
            await db.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, domain, idp_provider, is_active) "
                    "VALUES (gen_random_uuid(), 'GetVul', 'getvul', 'localhost', 'LOCAL', true)"
                )
            )
            await db.commit()
            result = await db.execute(text("SELECT id FROM tenants LIMIT 1"))
            tenant = result.scalar()
            print("    Tenant created.")

        from app.auth.password import hash_password

        hashed = hash_password("Admin123!")
        await db.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, display_name, role, password_hash, is_active, idp_subject, idp_source, must_change_password) "
                "VALUES (gen_random_uuid(), :tid, 'admin@getvul.local', 'Admin', 'OWNER', :pw, true, 'local-admin', 'local', true)"
            ),
            {"tid": str(tenant), "pw": hashed},
        )
        await db.commit()
        print("    Default admin user created.")
        print("    Email:    admin@getvul.local")
        print("    Password: Admin123!")


if __name__ == "__main__":
    try:
        asyncio.run(create_admin())
    except Exception as e:
        print(f"    Error: {e}", file=sys.stderr)
        sys.exit(1)
