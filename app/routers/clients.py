import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.unifi_client import UniFiClient
from app.schemas import ClientInfo, ClientActionRequest, BulkClientActionRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/clients", response_model=list[ClientInfo])
async def list_clients(site: Optional[str] = Query(default=None, description="Site name")):
    """List all currently connected WiFi clients on a site."""
    try:
        async with UniFiClient() as client:
            raw = await client.get_clients(site)
            return [client.format_client_info(c) for c in raw]
    except Exception as e:
        logger.error(f"Failed to list clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients/blocked", response_model=list[ClientInfo])
async def list_blocked_clients(site: Optional[str] = Query(default=None, description="Site name")):
    """List all blocked clients on a site."""
    try:
        async with UniFiClient() as client:
            raw = await client.get_blocked_clients(site)
            return [
                {
                    "mac": u.get("mac", ""),
                    "hostname": u.get("hostname") or u.get("name") or u.get("mac", "Unknown"),
                    "ip": u.get("last_ip", ""),
                    "essid": "",
                    "ap_mac": "",
                    "signal": None,
                    "rssi": None,
                    "tx_bytes": 0,
                    "rx_bytes": 0,
                    "uptime": 0,
                    "is_wired": False,
                    "blocked": True,
                    "oui": u.get("oui", ""),
                }
                for u in raw
            ]
    except Exception as e:
        logger.error(f"Failed to list blocked clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clients/block")
async def block_client(req: ClientActionRequest):
    """Block a WiFi client by MAC address."""
    try:
        async with UniFiClient() as client:
            await client.block_client(req.mac, req.site)
        logger.info(f"Blocked client {req.mac}")
        return {"success": True, "mac": req.mac, "action": "blocked"}
    except Exception as e:
        logger.error(f"Failed to block client {req.mac}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clients/unblock")
async def unblock_client(req: ClientActionRequest):
    """Unblock a WiFi client by MAC address."""
    try:
        async with UniFiClient() as client:
            await client.unblock_client(req.mac, req.site)
        logger.info(f"Unblocked client {req.mac}")
        return {"success": True, "mac": req.mac, "action": "unblocked"}
    except Exception as e:
        logger.error(f"Failed to unblock client {req.mac}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clients/bulk-block")
async def bulk_block_clients(req: BulkClientActionRequest):
    """Block multiple WiFi clients at once."""
    results = {"blocked": [], "failed": []}
    async with UniFiClient() as client:
        for mac in req.macs:
            try:
                await client.block_client(mac, req.site)
                results["blocked"].append(mac)
            except Exception as e:
                results["failed"].append({"mac": mac, "error": str(e)})
    return results
