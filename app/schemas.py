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
