import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ManagedAsset, SiteInventory
from app.schemas import (
    ManagedAssetCreate,
    ManagedAssetResponse,
    ManagedAssetUpdate,
    SiteInventoryCreate,
    SiteInventoryResponse,
    SiteInventoryUpdate,
)
from app.unifi_client import UniFiClient

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_site(site: SiteInventory, asset_count: int = 0) -> dict:
    """Normalize site payloads for API responses."""
    return {
        "id": site.id,
        "name": site.name,
        "unifi_site_name": site.unifi_site_name,
        "client_name": site.client_name,
        "property_type": site.property_type,
        "address": site.address,
        "timezone": site.timezone,
        "maintenance_window": site.maintenance_window,
        "service_tier": site.service_tier,
        "priority": site.priority,
        "tags": site.tags or [],
        "notes": site.notes,
        "internal_notes": site.internal_notes,
        "is_active": site.is_active,
        "asset_count": asset_count,
        "created_at": site.created_at,
        "updated_at": site.updated_at,
    }


def _serialize_asset(
    asset: ManagedAsset,
    site_name: Optional[str],
    unifi_site_name: Optional[str],
) -> dict:
    """Normalize managed asset payloads for API responses."""
    return {
        "id": asset.id,
        "site_inventory_id": asset.site_inventory_id,
        "site_name": site_name,
        "unifi_site_name": unifi_site_name,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "device_id": asset.device_id,
        "device_name": asset.device_name,
        "port_idx": asset.port_idx,
        "port_label": asset.port_label,
        "vendor": asset.vendor,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "location_details": asset.location_details,
        "recovery_playbook": asset.recovery_playbook,
        "notes": asset.notes,
        "tags": asset.tags or [],
        "auto_cycle_policy": asset.auto_cycle_policy,
        "is_enabled": asset.is_enabled,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


async def _get_site_or_404(site_id: int, db: AsyncSession) -> SiteInventory:
    """Fetch a site inventory record or raise 404."""
    result = await db.execute(select(SiteInventory).where(SiteInventory.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site inventory record not found")
    return site


async def _site_counts(db: AsyncSession) -> dict[int, int]:
    """Get managed asset counts by site."""
    result = await db.execute(
        select(ManagedAsset.site_inventory_id, func.count(ManagedAsset.id))
        .group_by(ManagedAsset.site_inventory_id)
    )
    return {site_id: count for site_id, count in result.all()}


@router.get("/site-inventory", response_model=List[SiteInventoryResponse])
async def list_site_inventory(
    active_only: bool = False,
    client_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all business-level site inventory records."""
    try:
        query = select(SiteInventory).order_by(
            SiteInventory.priority.asc(),
            SiteInventory.name.asc(),
        )

        if active_only:
            query = query.where(SiteInventory.is_active == True)

        if client_name:
            query = query.where(SiteInventory.client_name == client_name)

        result = await db.execute(query)
        sites = result.scalars().all()
        counts = await _site_counts(db)

        return [_serialize_site(site, counts.get(site.id, 0)) for site in sites]
    except Exception as e:
        logger.error(f"Failed to list site inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/site-inventory", response_model=SiteInventoryResponse)
async def create_site_inventory(
    site: SiteInventoryCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new site inventory record."""
    try:
        existing = await db.execute(
            select(SiteInventory).where(SiteInventory.unifi_site_name == site.unifi_site_name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A site inventory record already exists for that UniFi site")

        db_site = SiteInventory(**site.model_dump())
        db.add(db_site)
        await db.commit()
        await db.refresh(db_site)

        logger.info(f"Created site inventory record for {db_site.unifi_site_name}")
        return _serialize_site(db_site)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create site inventory record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/site-inventory/import-unifi-sites")
async def import_unifi_sites(db: AsyncSession = Depends(get_db)):
    """Seed site inventory records from the UniFi controller."""
    try:
        existing_result = await db.execute(select(SiteInventory.unifi_site_name))
        existing_sites = {row[0] for row in existing_result.all()}

        async with UniFiClient() as client:
            unifi_sites = await client.get_sites()

        created = []
        skipped = []

        for site in unifi_sites:
            site_name = site.get("name")
            if not site_name:
                continue

            if site_name in existing_sites:
                skipped.append(site_name)
                continue

            record = SiteInventory(
                name=site.get("desc") or site_name,
                unifi_site_name=site_name,
                tags=[],
            )
            db.add(record)
            existing_sites.add(site_name)
            created.append(site_name)

        await db.commit()

        logger.info(f"Imported {len(created)} UniFi site records into site inventory")
        return {
            "success": True,
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created": created,
            "skipped": skipped,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to import UniFi sites into site inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/site-inventory/{site_id}", response_model=SiteInventoryResponse)
async def get_site_inventory(site_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single site inventory record."""
    try:
        site = await _get_site_or_404(site_id, db)
        counts = await _site_counts(db)
        return _serialize_site(site, counts.get(site.id, 0))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get site inventory {site_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/site-inventory/{site_id}", response_model=SiteInventoryResponse)
async def update_site_inventory(
    site_id: int,
    site_update: SiteInventoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a site inventory record."""
    try:
        site = await _get_site_or_404(site_id, db)
        update_data = site_update.model_dump(exclude_unset=True)

        new_unifi_site_name = update_data.get("unifi_site_name")
        if new_unifi_site_name and new_unifi_site_name != site.unifi_site_name:
            existing = await db.execute(
                select(SiteInventory).where(SiteInventory.unifi_site_name == new_unifi_site_name)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="A site inventory record already exists for that UniFi site")

        for field, value in update_data.items():
            setattr(site, field, value)

        site.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(site)

        counts = await _site_counts(db)
        logger.info(f"Updated site inventory record {site_id}")
        return _serialize_site(site, counts.get(site.id, 0))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update site inventory {site_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/site-inventory/{site_id}")
async def delete_site_inventory(site_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a site inventory record."""
    try:
        site = await _get_site_or_404(site_id, db)
        asset_count = await db.scalar(
            select(func.count(ManagedAsset.id)).where(ManagedAsset.site_inventory_id == site_id)
        )

        if asset_count:
            raise HTTPException(
                status_code=409,
                detail="Delete or reassign managed assets before removing this site inventory record",
            )

        await db.delete(site)
        await db.commit()

        logger.info(f"Deleted site inventory record {site_id}")
        return {"success": True, "message": f"Site inventory record {site_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete site inventory {site_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/managed-assets", response_model=List[ManagedAssetResponse])
async def list_managed_assets(
    site_inventory_id: Optional[int] = None,
    unifi_site_name: Optional[str] = None,
    asset_type: Optional[str] = None,
    auto_cycle_policy: Optional[str] = None,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List all managed asset records."""
    try:
        query = (
            select(ManagedAsset, SiteInventory.name, SiteInventory.unifi_site_name)
            .join(SiteInventory, ManagedAsset.site_inventory_id == SiteInventory.id)
            .order_by(SiteInventory.name.asc(), ManagedAsset.name.asc())
        )

        if site_inventory_id:
            query = query.where(ManagedAsset.site_inventory_id == site_inventory_id)

        if unifi_site_name:
            query = query.where(SiteInventory.unifi_site_name == unifi_site_name)

        if asset_type:
            query = query.where(ManagedAsset.asset_type == asset_type)

        if auto_cycle_policy:
            query = query.where(ManagedAsset.auto_cycle_policy == auto_cycle_policy)

        if enabled_only:
            query = query.where(ManagedAsset.is_enabled == True)

        result = await db.execute(query)
        rows = result.all()

        return [
            _serialize_asset(asset, site_name, site_unifi_name)
            for asset, site_name, site_unifi_name in rows
        ]
    except Exception as e:
        logger.error(f"Failed to list managed assets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/managed-assets", response_model=ManagedAssetResponse)
async def create_managed_asset(
    asset: ManagedAssetCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new managed asset record."""
    try:
        site = await _get_site_or_404(asset.site_inventory_id, db)

        db_asset = ManagedAsset(**asset.model_dump())
        db.add(db_asset)
        await db.commit()
        await db.refresh(db_asset)

        logger.info(f"Created managed asset '{db_asset.name}' for site {site.unifi_site_name}")
        return _serialize_asset(db_asset, site.name, site.unifi_site_name)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create managed asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/managed-assets/{asset_id}", response_model=ManagedAssetResponse)
async def get_managed_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single managed asset record."""
    try:
        result = await db.execute(
            select(ManagedAsset, SiteInventory.name, SiteInventory.unifi_site_name)
            .join(SiteInventory, ManagedAsset.site_inventory_id == SiteInventory.id)
            .where(ManagedAsset.id == asset_id)
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Managed asset not found")

        asset, site_name, site_unifi_name = row
        return _serialize_asset(asset, site_name, site_unifi_name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get managed asset {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/managed-assets/{asset_id}", response_model=ManagedAssetResponse)
async def update_managed_asset(
    asset_id: int,
    asset_update: ManagedAssetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a managed asset record."""
    try:
        result = await db.execute(select(ManagedAsset).where(ManagedAsset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Managed asset not found")

        update_data = asset_update.model_dump(exclude_unset=True)

        site_id = update_data.get("site_inventory_id", asset.site_inventory_id)
        site = await _get_site_or_404(site_id, db)

        for field, value in update_data.items():
            setattr(asset, field, value)

        asset.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(asset)

        logger.info(f"Updated managed asset {asset_id}")
        return _serialize_asset(asset, site.name, site.unifi_site_name)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update managed asset {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/managed-assets/{asset_id}")
async def delete_managed_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a managed asset record."""
    try:
        result = await db.execute(select(ManagedAsset).where(ManagedAsset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Managed asset not found")

        await db.delete(asset)
        await db.commit()

        logger.info(f"Deleted managed asset {asset_id}")
        return {"success": True, "message": f"Managed asset {asset_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete managed asset {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
