"""Asset group management — tenant-scoped CRUD + membership (Phase 32 Plan 03, EXPO-04).

Mirrors `app/connectors/service.py`'s tenant-scoped CRUD shape: every query
filters `tenant_id` first, and returns `None`/`False` on a miss rather than
raising — the router layer converts that to 404. No encryption step (an
`AssetGroup` carries no secret material, unlike `ConnectorConfig`'s
credentials).

`add_member`/`remove_member` immediately re-apply the per-asset > group >
auto exposure-context precedence to the affected asset (32-CONTEXT.md
execution note) so a newly-added member picks up an existing group override
— or a removed member reverts to the auto tier — without waiting for a
full-tenant recompute.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.exposure import apply_precedence_to_asset, audit_auto_inference_changes
from app.assets.models import Asset, AssetGroup, AssetGroupExposureOverride, AssetGroupMember


async def list_groups(db: AsyncSession, tenant_id: uuid.UUID) -> list[AssetGroup]:
    result = await db.execute(select(AssetGroup).where(AssetGroup.tenant_id == tenant_id).order_by(AssetGroup.name))
    return list(result.scalars().all())


async def list_groups_with_member_counts(db: AsyncSession, tenant_id: uuid.UUID) -> list[tuple[AssetGroup, int]]:
    """Same as `list_groups` but paired with a member-count (frontend
    management page's list view — 32-05-PLAN). A single outer-join + GROUP BY
    avoids an N+1 count-per-group query."""
    result = await db.execute(
        select(AssetGroup, func.count(AssetGroupMember.asset_id))
        .outerjoin(AssetGroupMember, AssetGroupMember.group_id == AssetGroup.id)
        .where(AssetGroup.tenant_id == tenant_id)
        .group_by(AssetGroup.id)
        .order_by(AssetGroup.name)
    )
    return [(g, c) for g, c in result.all()]


async def count_members(db: AsyncSession, group_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(AssetGroupMember.asset_id)).where(AssetGroupMember.group_id == group_id)
    )
    return result.scalar_one()


async def get_group(db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID) -> AssetGroup | None:
    result = await db.execute(select(AssetGroup).where(AssetGroup.id == group_id, AssetGroup.tenant_id == tenant_id))
    return result.scalar_one_or_none()


async def create_group(db: AsyncSession, tenant_id: uuid.UUID, name: str, description: str | None = None) -> AssetGroup:
    group = AssetGroup(tenant_id=tenant_id, name=name, description=description)
    db.add(group)
    await db.flush()
    await db.refresh(group)
    return group


async def update_group(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    group_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
) -> AssetGroup | None:
    group = await get_group(db, tenant_id, group_id)
    if group is None:
        return None
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    await db.flush()
    return group


async def delete_group(db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID) -> bool:
    group = await get_group(db, tenant_id, group_id)
    if group is None:
        return False
    await db.delete(group)
    return True


async def add_member(db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID, asset_id: uuid.UUID) -> bool:
    """Idempotent add (TicketWatcher composite-PK pattern). Re-applies
    per-asset > group > auto precedence to the affected asset immediately
    (32-CONTEXT.md execution note) so a newly-added member picks up any
    applicable group override without waiting for a full recompute.
    """
    group = await get_group(db, tenant_id, group_id)
    if group is None:
        return False
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if asset is None:
        return False

    existing = (
        await db.execute(
            select(AssetGroupMember).where(AssetGroupMember.group_id == group_id, AssetGroupMember.asset_id == asset_id)
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(AssetGroupMember(group_id=group_id, asset_id=asset_id))
        await db.flush()

    changes = await apply_precedence_to_asset(db, asset)
    if changes:
        audit_auto_inference_changes(db, tenant_id, asset.id, changes)
    return True


async def list_members(db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID) -> list[Asset] | None:
    """Returns the group's member assets (tenant-scoped), or `None` if the
    group itself does not exist/belong to this tenant (router converts to
    404 — same not-found convention as every other lookup in this module)."""
    group = await get_group(db, tenant_id, group_id)
    if group is None:
        return None
    result = await db.execute(
        select(Asset)
        .join(AssetGroupMember, AssetGroupMember.asset_id == Asset.id)
        .where(AssetGroupMember.group_id == group_id, Asset.tenant_id == tenant_id)
        .order_by(Asset.hostname)
    )
    return list(result.scalars().all())


async def get_group_exposure_overrides(
    db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID
) -> dict[str, str] | None:
    """Returns the group's current field->value exposure overrides, or
    `None` if the group does not exist/belong to this tenant."""
    group = await get_group(db, tenant_id, group_id)
    if group is None:
        return None
    result = await db.execute(select(AssetGroupExposureOverride).where(AssetGroupExposureOverride.group_id == group_id))
    return {row.field: row.value for row in result.scalars().all()}


async def remove_member(db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID, asset_id: uuid.UUID) -> bool:
    """Removes membership then re-applies precedence — an asset that loses
    its only source of a GROUP_OVERRIDE reverts to the auto tier for that
    field (32-CONTEXT.md execution note)."""
    group = await get_group(db, tenant_id, group_id)
    if group is None:
        return False

    member = (
        await db.execute(
            select(AssetGroupMember).where(AssetGroupMember.group_id == group_id, AssetGroupMember.asset_id == asset_id)
        )
    ).scalar_one_or_none()
    if member is None:
        return False
    await db.delete(member)
    await db.flush()

    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if asset is not None:
        changes = await apply_precedence_to_asset(db, asset)
        if changes:
            audit_auto_inference_changes(db, tenant_id, asset.id, changes)
    return True
