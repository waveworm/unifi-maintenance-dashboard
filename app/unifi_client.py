import asyncio
import copy
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Per-device lock to serialize port_overrides read-modify-write cycles
# Prevents race conditions when cycling multiple ports on the same switch
_device_locks: Dict[str, asyncio.Lock] = {}
_device_locks_lock = asyncio.Lock()


async def _get_device_lock(device_id: str) -> asyncio.Lock:
    """Get or create a per-device asyncio Lock."""
    async with _device_locks_lock:
        if device_id not in _device_locks:
            _device_locks[device_id] = asyncio.Lock()
        return _device_locks[device_id]


class UniFiClient:
    """
    Async UniFi Controller API client.
    
    Handles authentication, device management, and PoE control.
    Supports self-signed certificates and multi-site access.
    """
    
    def __init__(self):
        self.base_url = settings.unifi_base_url
        self.username = settings.unifi_username
        self.password = settings.unifi_password
        self.site = settings.unifi_site
        self.verify_ssl = settings.unifi_verify_ssl
        
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated = False
        self._cookies: Optional[httpx.Cookies] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def connect(self):
        """Initialize HTTP client and authenticate."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=30.0,
                follow_redirects=True
            )
        
        if not self._authenticated:
            await self.login()
    
    async def close(self):
        """Close HTTP client and cleanup."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._authenticated = False
        self._cookies = None
    
    async def login(self):
        """Authenticate with UniFi controller."""
        logger.info(f"Authenticating to UniFi controller at {self.base_url}")
        
        url = f"{self.base_url}/api/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "remember": True
        }
        
        try:
            response = await self._client.post(url, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                raise Exception(f"Authentication failed: {response.status_code}")
            
            self._cookies = response.cookies
            self._authenticated = True
            logger.info("✅ Successfully authenticated to UniFi controller")
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during authentication: {e}")
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise
    
    async def get_sites(self) -> List[Dict[str, Any]]:
        """Get all sites from the controller."""
        await self.connect()
        
        url = f"{self.base_url}/api/self/sites"
        response = await self._client.get(url, cookies=self._cookies)
        
        if response.status_code != 200:
            logger.error(f"Failed to get sites: {response.status_code} - {response.text}")
            raise Exception(f"Failed to get sites: {response.status_code}")
        
        data = response.json()
        sites = data.get("data", [])
        
        logger.info(f"Found {len(sites)} site(s)")
        return sites
    
    async def get_devices(self, site: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all devices from the specified site (or configured default site)."""
        await self.connect()
        
        target_site = site or self.site
        url = f"{self.base_url}/api/s/{target_site}/stat/device"
        response = await self._client.get(url, cookies=self._cookies)
        
        if response.status_code != 200:
            logger.error(f"Failed to get devices: {response.status_code} - {response.text}")
            raise Exception(f"Failed to get devices: {response.status_code}")
        
        data = response.json()
        devices = data.get("data", [])
        
        logger.info(f"Retrieved {len(devices)} devices from site '{target_site}'")
        return devices
    
    async def get_device_ports(self, device_id: str, site: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get port information for a specific device."""
        devices = await self.get_devices(site)
        device = next((d for d in devices if d.get("_id") == device_id), None)
        
        if not device:
            raise Exception(f"Device {device_id} not found")
        
        return device.get("port_table", [])
    
    def format_device_info(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """Format device data for API response."""
        return {
            "id": device.get("_id", ""),
            "mac": device.get("mac", ""),
            "name": device.get("name", "Unknown"),
            "model": device.get("model", "Unknown"),
            "type": device.get("type", "unknown"),
            "ip": device.get("ip", ""),
            "state": device.get("state", 0),
            "online": device.get("state") == 1,
            "adopted": device.get("adopted", False),
            "version": device.get("version", ""),
            "uptime": device.get("uptime", 0),
            "last_seen": device.get("last_seen", 0),
            "site_id": device.get("site_id", ""),
            "is_switch": device.get("type") == "usw",
            "is_ap": device.get("type") in ["uap", "u7"],
            "port_count": len(device.get("port_table", []))
        }
    
    async def get_device_by_id(self, device_id: str, site: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific device by ID or MAC."""
        devices = await self.get_devices(site)
        return next((d for d in devices if d.get("_id") == device_id or d.get("mac") == device_id), None)
    
    async def reboot_device(self, device_id: str, site: Optional[str] = None) -> Dict[str, Any]:
        """Reboot a device."""
        await self.connect()
        
        target_site = site or self.site
        url = f"{self.base_url}/api/s/{target_site}/cmd/devmgr"
        payload = {
            "cmd": "restart",
            "mac": device_id
        }
        
        response = await self._client.post(url, json=payload, cookies=self._cookies)
        
        if response.status_code != 200:
            logger.error(f"Failed to reboot device: {response.status_code} - {response.text}")
            raise Exception(f"Failed to reboot device: {response.status_code}")
        
        logger.info(f"Reboot command sent to device {device_id}")
        return response.json()
    
    async def set_poe_mode(self, device_id: str, port_idx: int, mode: str, site: Optional[str] = None) -> Dict[str, Any]:
        """
        Set PoE mode for a specific port.
        
        Args:
            device_id: Device MAC address
            port_idx: Port index (1-based)
            mode: PoE mode - "auto", "off", "pasv24", "passthrough"
            site: Optional site name
        """
        await self.connect()
        
        target_site = site or self.site
        url = f"{self.base_url}/api/s/{target_site}/rest/device/{device_id}"
        
        payload = {
            "port_overrides": [
                {
                    "port_idx": port_idx,
                    "poe_mode": mode
                }
            ]
        }
        
        response = await self._client.put(url, json=payload, cookies=self._cookies)
        
        if response.status_code != 200:
            logger.error(f"Failed to set PoE mode: {response.status_code} - {response.text}")
            raise Exception(f"Failed to set PoE mode: {response.status_code}")
        
        logger.info(f"Set PoE mode to '{mode}' for device {device_id} port {port_idx}")
        return response.json()
    
    async def set_port_config(self, device_id: str, port_idx: int, port_enabled: bool, site: Optional[str] = None) -> Dict[str, Any]:
        """
        Enable or disable a port (link up/down).
        
        Uses forward="disabled"/"all" with full port override fields,
        followed by force-provision. This is the exact approach the
        UniFi Network UI uses on controller 10.0.162 / US8P60 hardware.
        
        Args:
            device_id: Device MAC address or _id
            port_idx: Port index (1-based)
            port_enabled: True to enable port, False to disable
            site: Optional site name
        """
        await self.connect()
        
        target_site = site or self.site
        
        # Get current device config to find MAC and existing overrides
        devices = await self.get_devices(target_site)
        device = next((d for d in devices if d.get("_id") == device_id or d.get("mac") == device_id), None)
        
        if not device:
            raise Exception(f"Device {device_id} not found")
        
        device_mongo_id = device.get("_id", device_id)
        device_mac = device.get("mac")
        url = f"{self.base_url}/api/s/{target_site}/rest/device/{device_mongo_id}"
        
        # Find existing port override to preserve custom settings
        port_overrides = device.get("port_overrides", [])
        existing_override = next((p for p in port_overrides if p.get("port_idx") == port_idx), {})
        
        # Find the port's current native network for re-enable
        port_entry = next((p for p in device.get("port_table", []) if p.get("port_idx") == port_idx), {})
        native_net = existing_override.get("native_networkconf_id") or port_entry.get("native_networkconf_id", "")
        
        # Build the full port override with all required fields.
        # Controller 10.0.162 silently ignores partial overrides for
        # forward="disabled"; the UI sends the complete field set.
        if port_enabled:
            new_override = {
                "port_idx": port_idx,
                "setting_preference": "auto",
                "name": existing_override.get("name", f"Port {port_idx}"),
                "port_security_enabled": False,
                "port_security_mac_address": [],
                "native_networkconf_id": native_net,
                "tagged_vlan_mgmt": "auto",
                "multicast_router_networkconf_ids": [],
                "lldpmed_enabled": True,
                "voice_networkconf_id": "",
                "stormctrl_bcast_enabled": False,
                "stormctrl_bcast_rate": 100,
                "stormctrl_mcast_enabled": False,
                "stormctrl_mcast_rate": 100,
                "stormctrl_ucast_enabled": False,
                "stormctrl_ucast_rate": 100,
                "egress_rate_limit_kbps_enabled": False,
                "autoneg": True,
                "isolation": False,
                "stp_port_mode": True,
                "port_keepalive_enabled": False,
                "forward": "all",
            }
        else:
            new_override = {
                "port_idx": port_idx,
                "setting_preference": "auto",
                "name": existing_override.get("name", f"Port {port_idx}"),
                "port_security_enabled": True,
                "port_security_mac_address": [],
                "native_networkconf_id": "",
                "tagged_vlan_mgmt": "block_all",
                "multicast_router_networkconf_ids": [],
                "lldpmed_enabled": True,
                "voice_networkconf_id": "",
                "stormctrl_bcast_enabled": False,
                "stormctrl_bcast_rate": 100,
                "stormctrl_mcast_enabled": False,
                "stormctrl_mcast_rate": 100,
                "stormctrl_ucast_enabled": False,
                "stormctrl_ucast_rate": 100,
                "egress_rate_limit_kbps_enabled": False,
                "autoneg": True,
                "isolation": False,
                "stp_port_mode": True,
                "port_keepalive_enabled": False,
                "forward": "disabled",
            }
        
        # Replace the override for this port, keep others
        other_overrides = [p for p in port_overrides if p.get("port_idx") != port_idx]
        other_overrides.append(new_override)
        
        payload = {"port_overrides": other_overrides}
        
        response = await self._client.put(url, json=payload, cookies=self._cookies)
        
        if response.status_code != 200:
            logger.error(f"Failed to set port state: {response.status_code} - {response.text}")
            raise Exception(f"Failed to set port state: {response.status_code}")
        
        state = "enabled" if port_enabled else "disabled"
        logger.info(f"Port {port_idx} {state} for device {device_id} (forward={'all' if port_enabled else 'disabled'}) — switch will apply on next inform cycle")
        return response.json()
    
    async def cycle_port(self, device_id: str, port_idx: int, off_duration: int = 30, site: Optional[str] = None, poe_only: bool = False) -> Dict[str, Any]:
        """
        Cycle a port (disable/enable or PoE off/on).
        
        Full port cycle takes 4-5 minutes total on US8P60 / controller 10.0.162
        because provisioning takes 1-2 minutes to apply on the switch.
        
        Args:
            device_id: Device MAC address
            port_idx: Port index (1-based)
            off_duration: Seconds to hold port disabled after confirmed down (default 30)
            site: Optional site name
            poe_only: If True, only cycle PoE. If False, disable/enable the port entirely.
        """
        logger.info(f"Starting port cycle for device {device_id} port {port_idx} (poe_only={poe_only})")
        
        if poe_only:
            # PoE-only cycle — no port_overrides conflict
            await self.set_poe_mode(device_id, port_idx, "off", site)
            logger.info(f"Waiting {off_duration} seconds with PoE off...")
            await asyncio.sleep(off_duration)
            await self.set_poe_mode(device_id, port_idx, "auto", site)
        else:
            # Full port cycle — acquire per-device lock to prevent concurrent
            # port_overrides read-modify-write races on the same switch
            device_lock = await _get_device_lock(device_id)
            async with device_lock:
                await self._do_full_port_cycle(device_id, port_idx, off_duration, site)
        
        logger.info(f"Port cycle completed for device {device_id} port {port_idx}")
        return {"status": "success", "message": f"Port {port_idx} cycled"}

    async def _do_full_port_cycle(self, device_id: str, port_idx: int, off_duration: int, site: Optional[str] = None):
        """Full port cycle with proper save/restore. Must be called under per-device lock."""
        device = await self.get_device_by_id(device_id, site)
        if not device:
            raise Exception(f"Device {device_id} not found")
        
        port_entry = next((p for p in device.get("port_table", []) if p.get("port_idx") == port_idx), {})
        existing_override = next((o for o in device.get("port_overrides", []) if o.get("port_idx") == port_idx), None)
        
        # Deep-copy the entire original override so we can restore it exactly
        if existing_override:
            saved_override = copy.deepcopy(existing_override)
        else:
            # No override exists yet — build one from port_table defaults
            saved_override = {
                "port_idx": port_idx,
                "name": port_entry.get("name", f"Port {port_idx}"),
                "native_networkconf_id": port_entry.get("native_networkconf_id", ""),
                "forward": port_entry.get("forward", "all"),
            }
        
        # Fix: if override has empty native_networkconf_id but port_table has the real one, use that
        if not saved_override.get("native_networkconf_id") and port_entry.get("native_networkconf_id"):
            saved_override["native_networkconf_id"] = port_entry["native_networkconf_id"]
            logger.info(f"Port {port_idx}: override had empty native_networkconf_id, using port_table value: {port_entry['native_networkconf_id']}")
        
        saved_forward = saved_override.get("forward", "all")
        saved_native_net = saved_override.get("native_networkconf_id", "")
        logger.info(f"Saved full override for port {port_idx}: forward={saved_forward}, native_networkconf_id={saved_native_net}")
        
        # --- DISABLE ---
        await self.set_port_config(device_id, port_idx, False, site)
        logger.info("Disable sent. Waiting up to 5 minutes for port to go down...")
        went_down = await self.wait_for_port_state(
            device_id=device_id,
            port_idx=port_idx,
            expected_up=False,
            timeout=300,
            poll_interval=10,
            site=site,
        )
        if not went_down:
            # Restore port before raising
            logger.error(f"Port {port_idx} did not go down after 5 minutes. Restoring original config.")
            await self._restore_port_override(device_id, port_idx, saved_override, site)
            raise Exception(f"Port {port_idx} did not transition to down state after disable command (waited 5 min)")
        logger.info(f"Port {port_idx} confirmed DOWN")
        
        # --- HOLD DISABLED ---
        logger.info(f"Holding port disabled for {off_duration} seconds...")
        await asyncio.sleep(off_duration)
        
        # --- RE-ENABLE with exact original config ---
        await self._restore_port_override(device_id, port_idx, saved_override, site)
        logger.info("Re-enable sent. Waiting up to 5 minutes for port to come back up...")
        back_up = await self.wait_for_port_state(
            device_id=device_id,
            port_idx=port_idx,
            expected_up=True,
            timeout=300,
            poll_interval=10,
            site=site,
        )
        if back_up:
            logger.info(f"Port {port_idx} confirmed UP")
        else:
            logger.warning(f"Port {port_idx} not yet up after 5 minutes — re-enable was sent, link may still be negotiating")

    async def _restore_port_override(self, device_id: str, port_idx: int, saved_override: dict, site: Optional[str] = None) -> Dict[str, Any]:
        """Restore a port's override to its exact original state (before disable).
        
        This puts back the complete saved override, preserving forward mode,
        VLAN assignments, security settings, and all other fields exactly as
        they were before the cycle started.
        """
        await self.connect()
        target_site = site or self.site
        
        device = await self.get_device_by_id(device_id, target_site)
        if not device:
            raise Exception(f"Device {device_id} not found")
        
        device_mongo_id = device.get("_id", device_id)
        url = f"{self.base_url}/api/s/{target_site}/rest/device/{device_mongo_id}"
        
        port_overrides = device.get("port_overrides", [])
        
        # Replace the override for this port with the exact saved copy
        other_overrides = [p for p in port_overrides if p.get("port_idx") != port_idx]
        other_overrides.append(saved_override)
        
        response = await self._client.put(url, json={"port_overrides": other_overrides}, cookies=self._cookies)
        if response.status_code != 200:
            logger.error(f"Failed to restore port override: {response.status_code} - {response.text}")
            raise Exception(f"Failed to restore port config: {response.status_code}")
        
        fwd = saved_override.get("forward", "?")
        nid = saved_override.get("native_networkconf_id", "?")
        logger.info(f"Port {port_idx} restored: forward={fwd}, native_networkconf_id={nid} — switch will apply on next inform cycle")
        return response.json()

    async def wait_for_port_state(
        self,
        device_id: str,
        port_idx: int,
        expected_up: bool,
        timeout: int = 10,
        poll_interval: int = 1,
        site: Optional[str] = None,
    ) -> bool:
        """Wait until a specific switch port reports the expected link state."""
        start = datetime.now()

        while (datetime.now() - start).total_seconds() < timeout:
            device = await self.get_device_by_id(device_id, site)
            if device:
                port = next(
                    (p for p in device.get("port_table", []) if p.get("port_idx") == port_idx),
                    None,
                )
                if port and bool(port.get("up")) == expected_up:
                    return True

            await asyncio.sleep(poll_interval)

        return False
    
    async def power_cycle_port(self, device_id: str, port_idx: int, off_duration: int = 15, site: Optional[str] = None) -> Dict[str, Any]:
        """
        Power cycle a PoE port (turn off, wait, turn back on).
        
        Args:
            device_id: Device MAC address
            port_idx: Port index (1-based)
            off_duration: Seconds to keep power off (default 15)
            site: Optional site name
        """
        return await self.cycle_port(device_id, port_idx, off_duration, site, poe_only=True)
    
    async def wait_for_device_online(self, device_id: str, timeout: int = 300, poll_interval: int = 10, site: Optional[str] = None) -> bool:
        """
        Wait for a device to come back online after reboot.
        
        Args:
            device_id: Device ID or MAC
            timeout: Maximum seconds to wait (default 300)
            poll_interval: Seconds between polls (default 10)
            site: Optional site name
        
        Returns:
            True if device came online, False if timeout
        """
        logger.info(f"Waiting for device {device_id} to come online (timeout: {timeout}s)")
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                devices = await self.get_devices(site)
                device = next((d for d in devices if d.get("_id") == device_id or d.get("mac") == device_id), None)
                
                if device and device.get("state") == 1:
                    logger.info(f"✅ Device {device_id} is online")
                    return True
                
                logger.debug(f"Device {device_id} not online yet, waiting {poll_interval}s...")
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                logger.warning(f"Error checking device status: {e}")
                await asyncio.sleep(poll_interval)
        
        logger.warning(f"⏱️ Timeout waiting for device {device_id} to come online")
        return False


# Global client instance
_client: Optional[UniFiClient] = None


async def get_unifi_client() -> UniFiClient:
    """Get or create the global UniFi client instance."""
    global _client
    if _client is None:
        _client = UniFiClient()
    await _client.connect()
    return _client


async def test_connection() -> bool:
    """
    Test UniFi controller connectivity and basic API access.

    Returns:
        bool: True if authentication and device retrieval succeed.
    """
    try:
        async with UniFiClient() as client:
            sites = await client.get_sites()
            print(f"\nFound {len(sites)} site(s):")
            for site in sites:
                site_name = site.get("desc") or site.get("name") or "unknown"
                print(f"  - {site_name}")

            devices = await client.get_devices()
            print(f"\nFound {len(devices)} device(s):\n")
            for device in devices:
                info = client.format_device_info(device)
                status = "online" if info["online"] else "offline"
                print(f"{info['name']} ({info['model']}) - {status} - {info['ip']}")

            return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        print(f"\nConnection test failed: {e}")
        return False
