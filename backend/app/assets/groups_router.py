"""AssetGroup API routes — CRUD + membership + group-scope exposure override
(Phase 32 Plan 03, EXPO-04/EXPO-05).

`GET`/list is available to any authenticated tenant member (analysts may
view group context for the exposure card); every mutating endpoint
(create/update/delete, member add/remove, the exposure-context override)
is admin-gated via `app.auth.rbac.require_admin` — this is a new router
file with no legacy `require_role("admin")` import to match, so it follows
`connectors/router.py`'s newer convention (32-PATTERNS.md).

404-not-403 on every cross-tenant probe (group id, asset id) keeps
cross-tenant existence private, mirroring `assets/router.py`'s per-asset
override endpoint (T-32-02 precedent).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.assets.exposure import EXPOSURE_FIELDS, apply_precedence_to_asset
from app.assets.groups_service import (
    add_member,
    count_members,
    create_group,
    delete_group,
    get_group,
    get_group_exposure_overrides,
    list_groups_with_member_counts,
    list_members,
    remove_member,
    update_group,
)
from app.assets.models import (
    Asset,
    AssetGroup,
    AssetGroupExposureOverride,
    AssetGroupMember,
    BusinessCriticality,
    DataSensitivity,
)
from app.audit import audit
from app.auth.dependencies import get_current_user
from app.auth.rbac import require_admin
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession

router = APIRouter()


class _AssetGroupCreate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class _AssetGroupUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class _GroupExposureOverrideUpdate(BaseModel):
    """T-32-09 mitigation: `extra="forbid"` (mass-assignment defense) +
    `field` allow-list + `value` validated against the enum matching `field`
    — mirrors `assets/router.py::_ExposureOverrideUpdate`."""

    model_config = {"extra": "forbid"}
    field: str
    value: str

    @model_validator(mode="after")
    def _validate_field_and_value(self) -> _GroupExposureOverrideUpdate:
        if self.field not in EXPOSURE_FIELDS:
            raise ValueError(f"field must be one of {sorted(EXPOSURE_FIELDS)}")
        if self.field == "internet_facing":
            if self.value.strip().lower() not in {"true", "false"}:
                raise ValueError("value must be 'true' or 'false' for internet_facing")
        else:
            enum_cls = BusinessCriticality if self.field == "business_criticality" else DataSensitivity
            valid_values = {member.value for member in enum_cls}
            if self.value not in valid_values:
                raise ValueError(f"value must be one of {sorted(valid_values)}")
        return self


def _group_to_dict(group: AssetGroup, member_count: int | None = None) -> dict:
    d: dict[str, str | int | None] = {
        "id": str(group.id),
        "tenant_id": str(group.tenant_id),
        "name": group.name,
        "description": group.description,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }
    if member_count is not None:
        d["member_count"] = member_count
    return d


@router.get("")
async def list_asset_groups(db: DBSession, user: Annotated[CurrentUser, Depends(get_current_user)]):
    """List groups with a `member_count` — the management page's list view
    (32-05-PLAN) needs this without a per-group N+1 round trip."""
    groups_with_counts = await list_groups_with_member_counts(db, user.tenant_id)
    return [_group_to_dict(g, member_count=c) for g, c in groups_with_counts]


@router.post("", status_code=201)
async def create_asset_group(
    body: _AssetGroupCreate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    group = await create_group(db, user.tenant_id, body.name, body.description)
    await audit(db, user, "asset_group.create", "asset_group", str(group.id), {"name": group.name})
    await db.commit()
    await db.refresh(group)
    return _group_to_dict(group)


@router.get("/{group_id}")
async def get_asset_group(
    group_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    group = await get_group(db, user.tenant_id, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Asset group not found")
    member_count = await count_members(db, group_id)
    return _group_to_dict(group, member_count=member_count)


@router.get("/{group_id}/members")
async def get_asset_group_members(
    group_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[dict[str, str | None]]:
    """Lists the group's member assets (id + hostname) — read-only, any
    authenticated tenant member may view (matches the list/detail gating);
    powers the management page's member-management panel (32-05-PLAN)."""
    members = await list_members(db, user.tenant_id, group_id)
    if members is None:
        raise HTTPException(status_code=404, detail="Asset group not found")
    return [{"id": str(a.id), "hostname": a.hostname} for a in members]


@router.get("/{group_id}/exposure-context")
async def get_asset_group_exposure_context(
    group_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    """Returns the group's current field->value exposure overrides — powers
    the management page's per-group override panel (32-05-PLAN) so an admin
    can see/edit the existing override rather than only blind-setting one."""
    overrides = await get_group_exposure_overrides(db, user.tenant_id, group_id)
    if overrides is None:
        raise HTTPException(status_code=404, detail="Asset group not found")
    return overrides


@router.patch("/{group_id}")
async def update_asset_group(
    group_id: uuid.UUID,
    body: _AssetGroupUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    group = await get_group(db, user.tenant_id, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Asset group not found")

    old_name = group.name
    updated = await update_group(db, user.tenant_id, group_id, name=body.name, description=body.description)
    # `updated` cannot be None here — `get_group` above already confirmed the
    # row exists in this same transaction; asserting narrows the type for
    # mypy and fails loudly (rather than a confusing AttributeError) in the
    # unreachable case of a concurrent delete slipping in between the two
    # queries.
    assert updated is not None
    await audit(
        db,
        user,
        "asset_group.update",
        "asset_group",
        str(group_id),
        {"old_name": old_name, "new_name": updated.name},
    )
    await db.commit()
    await db.refresh(updated)
    return _group_to_dict(updated)


@router.delete("/{group_id}")
async def delete_asset_group(
    group_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    group = await get_group(db, user.tenant_id, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Asset group not found")

    await audit(db, user, "asset_group.delete", "asset_group", str(group_id), {"name": group.name})
    await delete_group(db, user.tenant_id, group_id)
    await db.commit()
    return {"message": "Asset group deleted"}


@router.post("/{group_id}/members/{asset_id}", status_code=201)
async def add_group_member(
    group_id: uuid.UUID,
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    added = await add_member(db, user.tenant_id, group_id, asset_id)
    if not added:
        raise HTTPException(status_code=404, detail="Asset group or asset not found")
    await audit(db, user, "asset_group.member_add", "asset_group", str(group_id), {"asset_id": str(asset_id)})
    await db.commit()
    return {"message": "Member added"}


@router.delete("/{group_id}/members/{asset_id}")
async def remove_group_member(
    group_id: uuid.UUID,
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    removed = await remove_member(db, user.tenant_id, group_id, asset_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Membership not found")
    await audit(db, user, "asset_group.member_remove", "asset_group", str(group_id), {"asset_id": str(asset_id)})
    await db.commit()
    return {"message": "Member removed"}


@router.patch("/{group_id}/exposure-context")
async def set_group_exposure_override(
    group_id: uuid.UUID,
    body: _GroupExposureOverrideUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Admin-only group-scope exposure-context override (Phase 32 — EXPO-04).

    Upserts the `AssetGroupExposureOverride` row (unique group_id+field),
    then re-applies precedence to every member asset whose field is not
    already `ASSET_OVERRIDE` — this is what makes the override apply to
    members immediately rather than waiting for the next full-tenant
    recompute. Writes exactly one `asset_group.exposure_override` audit row
    for the mutation itself (member-level changes are not individually
    audited here — that would flood `audit_logs` on large groups; mirrors
    the "auto-inference audits only on change" anti-pattern guidance).
    """
    group = await get_group(db, user.tenant_id, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Asset group not found")

    field = body.field
    new_value_raw = body.value

    existing = (
        await db.execute(
            select(AssetGroupExposureOverride).where(
                AssetGroupExposureOverride.group_id == group_id, AssetGroupExposureOverride.field == field
            )
        )
    ).scalar_one_or_none()
    old_value = existing.value if existing else None

    if existing is None:
        db.add(AssetGroupExposureOverride(group_id=group_id, field=field, value=new_value_raw))
    else:
        existing.value = new_value_raw
    await db.flush()

    member_asset_ids = (
        (await db.execute(select(AssetGroupMember.asset_id).where(AssetGroupMember.group_id == group_id)))
        .scalars()
        .all()
    )
    if member_asset_ids:
        member_assets = (
            (await db.execute(select(Asset).where(Asset.id.in_(member_asset_ids), Asset.tenant_id == user.tenant_id)))
            .scalars()
            .all()
        )
        for asset in member_assets:
            await apply_precedence_to_asset(db, asset)

    await audit(
        db,
        user,
        "asset_group.exposure_override",
        "asset_group",
        str(group_id),
        {"field": field, "old": old_value, "new": new_value_raw},
    )
    await db.commit()
    return {"group_id": str(group_id), "field": field, "value": new_value_raw}
