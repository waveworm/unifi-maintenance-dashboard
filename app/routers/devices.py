import asyncio
import logging
import json
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.unifi_client import UniFiClient
import app.telegram_notifier as telegram_notifier
from app.schemas import (
    DeviceInfo,
    PortInfo,
    RebootRequest,
    BulkRebootRequest,
    PoEControlRequest,
    PoEPowerCycleRequest,
    PortCycleRequest,
    AuditLogResponse
)
from app.models import AuditLog, JobRun
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


async def log_audit(
    db: AsyncSession,
    action_type: str,
    device_id: str = None,
    device_name: str = None,
    source: str = "manual",
    user_ip: str = None,
    details: dict = None,
    success: bool = True,
    error_message: str = None
):
    """Create audit log entry."""
    audit_log = AuditLog(
        action_type=action_type,
        device_id=device_id,
        device_name=device_name,
        source=source,
        user_ip=user_ip,
        details=details,
        success=success,
        error_message=error_message
    )
    db.add(audit_log)
    await db.commit()


async def _poll_and_notify_online(device_mac: str, device_name: str, site: str, started_at: datetime, timeout: int = 300):
    """Background task: poll until device comes back online, then send Telegram notification."""
    try:
        async with UniFiClient() as client:
            online = await client.wait_for_device_online(device_mac, timeout=timeout, site=site)
        duration = int((datetime.utcnow() - started_at).total_seconds())
        if online:
            await telegram_notifier.notify_device_back_online(device_name, duration)
        else:
            await telegram_notifier.notify_device_reboot_timeout(device_name, timeout)
    except Exception as e:
        logger.warning(f"Telegram reboot notification failed for {device_name}: {e}")


@router.post("/telegram/test")
async def test_telegram():
    """Send a test Telegram message to verify configuration."""
    from app.config import settings
    if not settings.telegram_enabled:
        return {"success": False, "message": "Telegram is disabled (TELEGRAM_ENABLED=false)"}
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"success": False, "message": "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"}
    ok = await telegram_notifier.send_message(
        "✅ <b>UniFi Dashboard</b> — Telegram notifications are working!\n"
        "🔔 You will receive alerts for scheduled maintenance and manual reboots."
    )
    return {"success": ok, "message": "Test message sent" if ok else "Failed to send — check logs"}


@router.get("/sites")
async def list_sites():
    """Get all devices from the UniFi controller."""
    try:
        async with UniFiClient() as client:
            sites = await client.get_sites()
            return [{"name": s.get("name"), "desc": s.get("desc", "")} for s in sites]
    except Exception as e:
        logger.error(f"Failed to get sites: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices", response_model=List[DeviceInfo])
async def list_devices(site: str = None):
    """Get all UniFi devices."""
    try:
        async with UniFiClient() as client:
            devices = await client.get_devices(site)
            return [client.format_device_info(device) for device in devices]
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{device_id}", response_model=DeviceInfo)
async def get_device(device_id: str, site: str = None):
    """Get a specific device by ID."""
    try:
        async with UniFiClient() as client:
            device = await client.get_device_by_id(device_id, site)
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            return client.format_device_info(device)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{device_id}/ports", response_model=List[PortInfo])
async def get_device_ports(device_id: str, site: str = None):
    """Get port information for a switch."""
    try:
        async with UniFiClient() as client:
            ports = await client.get_device_ports(device_id, site)
            return ports
    except Exception as e:
        logger.error(f"Failed to get ports for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/reboot")
async def reboot_device(
    request: RebootRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Reboot a device."""
    try:
        async with UniFiClient() as client:
            device = await client.get_device_by_id(request.device_id, request.site)
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")

            device_name = device.get("name", "Unknown")
            device_mac = device.get("mac", request.device_id)
            started_at = datetime.utcnow()

            # Use MAC address for reboot command
            await client.reboot_device(device_mac, request.site)

            await log_audit(
                db, "reboot", device_mac, device_name,
                user_ip=http_request.client.host
            )

            # Fire background task to notify when device comes back online
            asyncio.create_task(
                _poll_and_notify_online(device_mac, device_name, request.site or "", started_at)
            )

            result = {"success": True, "device_id": request.device_id}

            if request.wait_for_online:
                online = await client.wait_for_device_online(device_mac, site=request.site)
                result["came_back_online"] = online

            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reboot device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/bulk-reboot")
async def bulk_reboot_devices(
    request: BulkRebootRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Reboot multiple devices at once (parallel, fire-and-forget)."""
    rebooted = []
    failed = []

    bulk_started_at = datetime.utcnow()

    try:
        async with UniFiClient() as client:
            for device_id in request.device_ids:
                try:
                    device = await client.get_device_by_id(device_id, request.site)
                    if not device:
                        failed.append({"device_id": device_id, "error": "Device not found"})
                        continue

                    device_name = device.get("name", "Unknown")
                    device_mac = device.get("mac", device_id)

                    await client.reboot_device(device_mac, request.site)

                    await log_audit(
                        db, "reboot", device_mac, device_name,
                        user_ip=http_request.client.host,
                        details={"bulk": True, "total": len(request.device_ids)}
                    )
                    rebooted.append({"device_id": device_id, "device_name": device_name})

                    # Fire background poll-and-notify for this device
                    asyncio.create_task(
                        _poll_and_notify_online(device_mac, device_name, request.site or "", bulk_started_at)
                    )

                except Exception as e:
                    logger.error(f"Bulk reboot failed for device {device_id}: {e}")
                    failed.append({"device_id": device_id, "error": str(e)})
                    await log_audit(
                        db, "reboot", device_id, None,
                        user_ip=http_request.client.host,
                        details={"bulk": True},
                        success=False,
                        error_message=str(e)
                    )
    except Exception as e:
        logger.error(f"Bulk reboot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": len(failed) == 0,
        "rebooted": rebooted,
        "failed": failed,
        "total": len(request.device_ids)
    }


@router.post("/devices/poe/control")
async def control_poe(
    request: PoEControlRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Control PoE mode on a switch port."""
    try:
        async with UniFiClient() as client:
            device = await client.get_device_by_id(request.device_id)
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            
            device_name = device.get("name", "Unknown")
            
            success = await client.set_poe_mode(
                request.device_id,
                request.port_idx,
                request.mode
            )
            
            await log_audit(
                db, f"poe_{request.mode}", request.device_id, device_name,
                user_ip=http_request.client.host,
                details={"port_idx": request.port_idx, "mode": request.mode},
                success=success
            )
            
            if not success:
                raise HTTPException(status_code=500, detail="PoE control failed")
            
            return {
                "success": True,
                "device_id": request.device_id,
                "port_idx": request.port_idx,
                "mode": request.mode
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to control PoE: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/poe/power-cycle")
async def power_cycle_port(
    request: PoEPowerCycleRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Power cycle a PoE port."""
    try:
        async with UniFiClient() as client:
            await client.power_cycle_port(
                request.device_id,
                request.port_idx,
                request.off_duration or 15,
                request.site
            )
            
            await log_audit(
                db, "poe_cycle", request.device_id, None,
                user_ip=http_request.client.host,
                details={
                    "port_idx": request.port_idx,
                    "off_duration": request.off_duration or 15
                },
                success=True
            )
            
            return {
                "success": True,
                "device_id": request.device_id,
                "port_idx": request.port_idx
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to power cycle port: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/devices/port/cycle")
async def cycle_port(
    request: PortCycleRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cycle a port (disable/enable or PoE off/on)."""
    action = "poe_cycle" if request.poe_only else "port_cycle"
    device_name = None
    started_at = datetime.utcnow()

    # Create job_run entry as "running" so it shows in history immediately
    site_desc = request.site or ""
    try:
        async with UniFiClient() as client:
            device = await client.get_device_by_id(request.device_id, request.site)
            if device:
                device_name = device.get("name", request.device_id)
            # Resolve site display name
            if request.site:
                sites = await client.get_sites()
                site_obj = next((s for s in sites if s.get("name") == request.site), None)
                if site_obj:
                    site_desc = site_obj.get("desc") or site_obj.get("name") or request.site

        display_name = f"{device_name} Port {request.port_idx}" if device_name else f"{request.device_id} Port {request.port_idx}"

        job_run = JobRun(
            job_type=action,
            device_id=request.device_id,
            device_name=display_name,
            started_at=started_at,
            status="running",
            job_metadata={"port_idx": request.port_idx, "off_duration": request.off_duration, "poe_only": request.poe_only, "source": "manual", "site_name": site_desc}
        )
        db.add(job_run)
        await db.commit()
        await db.refresh(job_run)
        job_id = job_run.id
    except Exception as e:
        logger.warning(f"Failed to create job_run entry: {e}")
        job_id = None

    try:
        async with UniFiClient() as client:
            await client.cycle_port(
                request.device_id,
                request.port_idx,
                request.off_duration,
                request.site,
                request.poe_only
            )

        # Mark job as success
        completed_at = datetime.utcnow()
        duration = int((completed_at - started_at).total_seconds())
        if job_id:
            job_run.status = "success"
            job_run.completed_at = completed_at
            job_run.duration_seconds = duration
            await db.commit()

        await log_audit(
            db, action, request.device_id, device_name,
            user_ip=http_request.client.host,
            details={"port_idx": request.port_idx, "off_duration": request.off_duration, "poe_only": request.poe_only},
            success=True
        )

        return {
            "success": True,
            "device_id": request.device_id,
            "port_idx": request.port_idx,
            "poe_only": request.poe_only
        }

    except HTTPException:
        raise
    except Exception as e:
        # Mark job as failed
        completed_at = datetime.utcnow()
        duration = int((completed_at - started_at).total_seconds())
        if job_id:
            try:
                job_run.status = "failed"
                job_run.completed_at = completed_at
                job_run.duration_seconds = duration
                job_run.error_message = str(e)
                await db.commit()
            except Exception:
                pass

        await log_audit(
            db, action, request.device_id, device_name,
            user_ip=http_request.client.host,
            details={"port_idx": request.port_idx, "off_duration": request.off_duration, "poe_only": request.poe_only},
            success=False, error_message=str(e)
        )

        logger.error(f"Failed to cycle port: {e}")
        raise HTTPException(status_code=500, detail=str(e))
