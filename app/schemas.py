from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class DeviceInfo(BaseModel):
    """Device information schema."""
    id: str
    mac: str
    name: str
    model: str
    type: str
    ip: str
    state: int
    online: bool
    adopted: bool
    version: str
    uptime: int
    last_seen: int
    site_id: str
    is_switch: bool
    is_ap: bool
    port_count: int


class PortInfo(BaseModel):
    """Switch port information schema."""
    port_idx: int
    name: Optional[str] = None
    poe_enable: bool = False
    poe_mode: Optional[str] = None
    poe_power: Optional[float] = None
    up: bool = False
    speed: Optional[int] = None


class RebootRequest(BaseModel):
    """Request to reboot a device."""
    device_id: str = Field(..., description="Device ID or MAC address")
    wait_for_online: bool = Field(default=False, description="Wait for device to come back online")
    site: Optional[str] = Field(default=None, description="Site name (optional)")


class PoEControlRequest(BaseModel):
    """Request to control PoE on a port."""
    device_id: str = Field(..., description="Switch device ID or MAC")
    port_idx: int = Field(..., description="Port index (1-based)")
    mode: str = Field(..., description="PoE mode: auto, off, pasv24, passthrough")
    site: Optional[str] = Field(default=None, description="Site name (optional)")


class PoEPowerCycleRequest(BaseModel):
    """Request to power cycle a PoE port."""
    device_id: str = Field(..., description="Switch device ID or MAC")
    port_idx: int = Field(..., description="Port index (1-based)")
    off_duration: Optional[int] = Field(default=None, description="Seconds to keep power off")
    site: Optional[str] = Field(default=None, description="Site name (optional)")


class PortCycleRequest(BaseModel):
    """Request to cycle a port (disable/enable)."""
    device_id: str = Field(..., description="Switch device ID or MAC")
    port_idx: int = Field(..., description="Port index (1-based)")
    off_duration: Optional[int] = Field(default=15, description="Seconds to keep port disabled")
    poe_only: bool = Field(default=False, description="Only cycle PoE, not the entire port")
    site: Optional[str] = Field(default=None, description="Site name (optional)")


class SiteInventoryCreate(BaseModel):
    """Create a business-level site record."""
    name: str = Field(..., min_length=1, max_length=255)
    unifi_site_name: str = Field(..., min_length=1, max_length=255)
    client_name: Optional[str] = Field(default=None, max_length=255)
    property_type: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = None
    timezone: Optional[str] = Field(default=None, max_length=100)
    maintenance_window: Optional[str] = Field(default=None, max_length=255)
    service_tier: Optional[str] = Field(default=None, max_length=100)
    priority: int = Field(default=3, ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    is_active: bool = True


class SiteInventoryUpdate(BaseModel):
    """Update a business-level site record."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    unifi_site_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    client_name: Optional[str] = Field(default=None, max_length=255)
    property_type: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = None
    timezone: Optional[str] = Field(default=None, max_length=100)
    maintenance_window: Optional[str] = Field(default=None, max_length=255)
    service_tier: Optional[str] = Field(default=None, max_length=100)
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    is_active: Optional[bool] = None


class SiteInventoryResponse(BaseModel):
    """Site inventory response schema."""
    id: int
    name: str
    unifi_site_name: str
    client_name: Optional[str]
    property_type: Optional[str]
    address: Optional[str]
    timezone: Optional[str]
    maintenance_window: Optional[str]
    service_tier: Optional[str]
    priority: int
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str]
    internal_notes: Optional[str]
    is_active: bool
    asset_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ManagedAssetCreate(BaseModel):
    """Create a tracked managed asset."""
    site_inventory_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    asset_type: str = Field(..., min_length=1, max_length=100)
    device_id: Optional[str] = Field(default=None, max_length=255)
    device_name: Optional[str] = Field(default=None, max_length=255)
    port_idx: Optional[int] = Field(default=None, ge=1)
    port_label: Optional[str] = Field(default=None, max_length=255)
    vendor: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    location_details: Optional[str] = None
    recovery_playbook: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    auto_cycle_policy: str = Field(
        default="manual_approval_required",
        description="safe_to_auto_cycle, manual_approval_required, or never_touch",
    )
    is_enabled: bool = True


class ManagedAssetUpdate(BaseModel):
    """Update a tracked managed asset."""
    site_inventory_id: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    asset_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    device_id: Optional[str] = Field(default=None, max_length=255)
    device_name: Optional[str] = Field(default=None, max_length=255)
    port_idx: Optional[int] = Field(default=None, ge=1)
    port_label: Optional[str] = Field(default=None, max_length=255)
    vendor: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    location_details: Optional[str] = None
    recovery_playbook: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    auto_cycle_policy: Optional[str] = None
    is_enabled: Optional[bool] = None


class ManagedAssetResponse(BaseModel):
    """Managed asset response schema."""
    id: int
    site_inventory_id: int
    site_name: Optional[str] = None
    unifi_site_name: Optional[str] = None
    name: str
    asset_type: str
    device_id: Optional[str]
    device_name: Optional[str]
    port_idx: Optional[int]
    port_label: Optional[str]
    vendor: Optional[str]
    model: Optional[str]
    serial_number: Optional[str]
    location_details: Optional[str]
    recovery_playbook: Optional[str]
    notes: Optional[str]
    tags: List[str] = Field(default_factory=list)
    auto_cycle_policy: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ScheduleCreate(BaseModel):
    """Create a new maintenance schedule."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    frequency: str = Field(..., description="hourly, daily, weekly, monthly")
    time_of_day: Optional[str] = Field(None, description="HH:MM format")
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="0=Monday, 6=Sunday")
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    device_ids: List[str] = Field(..., min_items=1)
    site_name: Optional[str] = Field(default=None, description="UniFi site name")
    rolling_mode: bool = Field(default=True)
    delay_between_devices: int = Field(default=300, ge=0)
    max_wait_time: int = Field(default=300, ge=0)
    continue_on_failure: bool = Field(default=False)
    enabled: bool = Field(default=True)


class ScheduleUpdate(BaseModel):
    """Update an existing schedule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    frequency: Optional[str] = None
    time_of_day: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    device_ids: Optional[List[str]] = None
    site_name: Optional[str] = None
    rolling_mode: Optional[bool] = None
    delay_between_devices: Optional[int] = Field(None, ge=0)
    max_wait_time: Optional[int] = Field(None, ge=0)
    continue_on_failure: Optional[bool] = None
    enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    """Schedule response schema."""
    id: int
    name: str
    description: Optional[str]
    frequency: str
    time_of_day: Optional[str]
    day_of_week: Optional[int]
    day_of_month: Optional[int]
    device_ids: List[str]
    site_name: Optional[str] = None
    device_names: Optional[List[str]] = None
    rolling_mode: bool
    delay_between_devices: int
    max_wait_time: int
    continue_on_failure: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class JobRunResponse(BaseModel):
    """Job run history response schema."""
    id: int
    schedule_id: Optional[int]
    job_type: str
    device_id: str
    device_name: Optional[str]
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    error_message: Optional[str]
    job_metadata: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AuditLogResponse(BaseModel):
    """Audit log response schema."""
    id: int
    action_type: str
    device_id: Optional[str]
    device_name: Optional[str]
    source: str
    user_ip: Optional[str]
    timestamp: datetime
    details: Optional[Dict[str, Any]]
    success: bool
    error_message: Optional[str]
    
    class Config:
        from_attributes = True


class PoEScheduleCreate(BaseModel):
    """Create a PoE/port cycle schedule."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    device_id: str
    site_name: Optional[str] = None
    port_idx: int = Field(..., ge=1)
    frequency: str
    time_of_day: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    poe_only: bool = Field(default=True, description="True for PoE cycle, False for full port disable/enable")
    off_duration: int = Field(default=15, ge=5, le=300)
    enabled: bool = Field(default=True)


class PoEScheduleUpdate(BaseModel):
    """Update an existing PoE/port cycle schedule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    device_id: Optional[str] = None
    site_name: Optional[str] = None
    port_idx: Optional[int] = Field(None, ge=1)
    frequency: Optional[str] = None
    time_of_day: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    poe_only: Optional[bool] = None
    off_duration: Optional[int] = Field(None, ge=5, le=300)
    enabled: Optional[bool] = None


class PoEScheduleResponse(BaseModel):
    """PoE/port cycle schedule response schema."""
    id: int
    name: str
    description: Optional[str]
    device_id: str
    site_name: Optional[str]
    port_idx: int
    frequency: str
    time_of_day: Optional[str]
    day_of_week: Optional[int]
    day_of_month: Optional[int]
    poe_only: bool
    off_duration: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime]

    class Config:
        from_attributes = True


class ClientInfo(BaseModel):
    """Connected WiFi client information."""
    mac: str
    hostname: str
    ip: str
    essid: str
    ap_mac: str
    signal: Optional[int] = None
    rssi: Optional[int] = None
    tx_bytes: int = 0
    rx_bytes: int = 0
    uptime: int = 0
    is_wired: bool = False
    blocked: bool = False
    oui: str = ""


class ClientActionRequest(BaseModel):
    """Block or unblock a single client."""
    mac: str = Field(..., description="Client MAC address")
    site: Optional[str] = Field(default=None, description="Site name (optional)")


class BulkClientActionRequest(BaseModel):
    """Block multiple clients at once."""
    macs: List[str] = Field(..., min_length=1)
    site: Optional[str] = Field(default=None, description="Site name (optional)")


class BulkRebootRequest(BaseModel):
    """Request to reboot multiple devices at once."""
    device_ids: List[str] = Field(..., min_length=1)
    site: Optional[str] = Field(default=None, description="Site name (optional)")
    wait_for_online: bool = Field(default=False)


class ScheduleTemplateCreate(BaseModel):
    """Create a reusable schedule configuration template."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_type: str = Field(..., description="device_reboot or port_cycle")
    frequency: str = Field(..., description="hourly, daily, weekly, monthly")
    time_of_day: Optional[str] = Field(None, description="HH:MM format")
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    # Device reboot specific
    rolling_mode: Optional[bool] = None
    delay_between_devices: Optional[int] = Field(None, ge=0)
    max_wait_time: Optional[int] = Field(None, ge=0)
    continue_on_failure: Optional[bool] = None
    # Port cycle specific
    poe_only: Optional[bool] = None
    off_duration: Optional[int] = Field(None, ge=5, le=300)


class ScheduleTemplateResponse(ScheduleTemplateCreate):
    """Schedule template response schema."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
