"""Saved filters — store and retrieve named filter presets."""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedFilter(Base):
    __tablename__ = "saved_filters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    filter_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "vulnerability" or "remediation"
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


async def list_saved_filters(db: AsyncSession, tenant_id: uuid.UUID, filter_type: str | None = None) -> list[dict]:
    q = select(SavedFilter).where(SavedFilter.tenant_id == tenant_id).order_by(SavedFilter.name)
    if filter_type:
        q = q.where(SavedFilter.filter_type == filter_type)
    rows = (await db.execute(q)).scalars().all()
    return [{"id": str(r.id), "name": r.name, "filter_type": r.filter_type, "filters": r.filters} for r in rows]


async def create_saved_filter(db: AsyncSession, tenant_id: uuid.UUID, name: str, filter_type: str, filters: dict) -> dict:
    sf = SavedFilter(tenant_id=tenant_id, name=name, filter_type=filter_type, filters=filters)
    db.add(sf)
    await db.flush()
    await db.refresh(sf)
    return {"id": str(sf.id), "name": sf.name, "filter_type": sf.filter_type, "filters": sf.filters}


async def update_saved_filter(db: AsyncSession, tenant_id: uuid.UUID, filter_id: uuid.UUID, name: str | None, filters: dict | None) -> dict | None:
    result = await db.execute(select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.tenant_id == tenant_id))
    sf = result.scalar_one_or_none()
    if sf is None:
        return None
    if name is not None:
        sf.name = name
    if filters is not None:
        sf.filters = filters
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(sf, "filters")

        # Sync linked automation rules — update their conditions
        from app.ticketing.models import TicketRule
        rules = (await db.execute(
            select(TicketRule).where(TicketRule.saved_filter_id == filter_id, TicketRule.tenant_id == tenant_id)
        )).scalars().all()
        for rule in rules:
            rule.conditions = map_filter_to_conditions(filters)
            flag_modified(rule, "conditions")

    return {"id": str(sf.id), "name": sf.name, "filter_type": sf.filter_type, "filters": sf.filters, "rules_updated": len(rules) if filters else 0}


def map_filter_to_conditions(filters: dict) -> dict:
    """Convert saved filter fields to rule engine conditions."""
    conditions: dict = {}
    if filters.get("severity"):
        conditions["severity"] = filters["severity"]
    if filters.get("source"):
        conditions["source"] = filters["source"]
    if filters.get("exploit_available"):
        conditions["exploit_available"] = True
    if filters.get("cisa_kev"):
        conditions["cisa_kev"] = True
    if filters.get("device_category"):
        conditions["device_category"] = filters["device_category"] if isinstance(filters["device_category"], list) else [filters["device_category"]]
    if filters.get("min_risk_score"):
        conditions["min_risk_score"] = filters["min_risk_score"]
    if filters.get("search"):
        conditions["search"] = filters["search"]
    return conditions


async def delete_saved_filter(db: AsyncSession, tenant_id: uuid.UUID, filter_id: uuid.UUID) -> bool:
    result = await db.execute(select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.tenant_id == tenant_id))
    sf = result.scalar_one_or_none()
    if sf is None:
        return False
    await db.delete(sf)
    return True
