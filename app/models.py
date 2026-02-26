from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Schedule(Base):
    """Scheduled maintenance job configuration."""
    
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Schedule timing
    frequency = Column(String(50), nullable=False)  # hourly, daily, weekly, monthly
    time_of_day = Column(String(10), nullable=True)  # HH:MM format
    day_of_week = Column(Integer, nullable=True)  # 0-6 for weekly
    day_of_month = Column(Integer, nullable=True)  # 1-31 for monthly
    
    # Target devices (JSON array of device IDs)
    device_ids = Column(JSON, nullable=False)
    site_name = Column(String(255), nullable=True)
    
    # Rolling reboot settings
    rolling_mode = Column(Boolean, default=True)
    delay_between_devices = Column(Integer, default=300)  # seconds
    max_wait_time = Column(Integer, default=300)  # seconds
    continue_on_failure = Column(Boolean, default=False)
    
    # Status
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    
    # Relationships
    job_runs = relationship("JobRun", back_populates="schedule", cascade="all, delete-orphan")


class JobRun(Base):
    """History of scheduled job executions."""
    
    __tablename__ = "job_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=True)
    
    # Job details
    job_type = Column(String(50), nullable=False)  # scheduled_reboot, manual_reboot, poe_cycle
    device_id = Column(String(255), nullable=False)
    device_name = Column(String(255), nullable=True)
    
    # Execution
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False)  # pending, running, success, failed, timeout
    
    # Results
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Additional data (JSON for flexibility)
    job_metadata = Column(JSON, nullable=True)
    
    # Relationships
    schedule = relationship("Schedule", back_populates="job_runs")


class AuditLog(Base):
    """Audit log for all actions (manual and automated)."""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Action details
    action_type = Column(String(50), nullable=False)  # reboot, poe_on, poe_off, poe_cycle, schedule_create, etc.
    device_id = Column(String(255), nullable=True)
    device_name = Column(String(255), nullable=True)
    
    # User/source
    source = Column(String(50), nullable=False)  # manual, scheduled, api
    user_ip = Column(String(50), nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Details
    details = Column(JSON, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)


class ScheduleTemplate(Base):
    """Reusable schedule configuration template."""

    __tablename__ = "schedule_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    template_type = Column(String(50), nullable=False)  # "device_reboot" | "port_cycle"

    # Schedule timing
    frequency = Column(String(50), nullable=False)
    time_of_day = Column(String(10), nullable=True)
    day_of_week = Column(Integer, nullable=True)
    day_of_month = Column(Integer, nullable=True)

    # Device reboot specific
    rolling_mode = Column(Boolean, nullable=True)
    delay_between_devices = Column(Integer, nullable=True)
    max_wait_time = Column(Integer, nullable=True)
    continue_on_failure = Column(Boolean, nullable=True)

    # Port cycle specific
    poe_only = Column(Boolean, nullable=True)
    off_duration = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PoESchedule(Base):
    """Scheduled PoE port power cycles."""

    __tablename__ = "poe_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Target
    device_id = Column(String(255), nullable=False)
    site_name = Column(String(255), nullable=True)
    port_idx = Column(Integer, nullable=False)
    
    # Schedule timing
    frequency = Column(String(50), nullable=False)
    time_of_day = Column(String(10), nullable=True)
    day_of_week = Column(Integer, nullable=True)
    day_of_month = Column(Integer, nullable=True)
    
    # Cycle settings
    poe_only = Column(Boolean, default=True)  # True: PoE cycle, False: full port disable/enable
    off_duration = Column(Integer, default=15)  # seconds
    
    # Status
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
