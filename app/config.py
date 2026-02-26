import os
import sys
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application configuration with validation."""
    
    # UniFi Controller
    unifi_base_url: str = Field(..., description="UniFi controller URL")
    unifi_username: str = Field(..., description="UniFi admin username")
    unifi_password: str = Field(..., description="UniFi admin password")
    unifi_site: str = Field(default="default", description="UniFi site name")
    unifi_verify_ssl: bool = Field(default=False, description="Verify SSL certificates")
    
    # Application
    app_host: str = Field(default="0.0.0.0", description="Application host")
    app_port: int = Field(default=8000, description="Application port")
    app_secret_key: str = Field(
        default="change-this-to-a-random-secret-key-in-production",
        description="Secret key for sessions"
    )
    
    # Development
    development_mode: bool = Field(default=True, description="Development mode")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/unifi_dashboard.log", description="Log file path")
    
    # Timezone
    tz: str = Field(default="UTC", description="Timezone")
    app_timezone: str = Field(default="America/New_York", description="Application timezone")
    
    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/unifi_dashboard.db",
        description="Database URL"
    )
    
    # Scheduler
    scheduler_enabled: bool = Field(default=True, description="Enable scheduler")
    
    # Device Polling
    device_poll_interval: int = Field(default=30, description="Device poll interval in seconds")
    device_online_timeout: int = Field(default=300, description="Max wait time for device online (seconds)")
    device_reboot_delay: int = Field(default=300, description="Delay between rolling reboots (seconds)")
    
    # PoE Power Cycle
    poe_power_off_duration: int = Field(default=15, description="PoE power off duration (seconds)")
    
    @validator("unifi_base_url")
    def validate_unifi_url(cls, v):
        """Ensure UniFi URL is properly formatted."""
        if not v:
            raise ValueError("UNIFI_BASE_URL is required")
        if not v.startswith(("http://", "https://")):
            raise ValueError("UNIFI_BASE_URL must start with http:// or https://")
        return v.rstrip("/")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def get_settings() -> Settings:
    """Get validated settings instance."""
    try:
        settings = Settings()
        return settings
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        print("See .env.example for reference.")
        sys.exit(1)


def ensure_directories():
    """Create required directories if they don't exist."""
    directories = [
        Path("data"),
        Path("logs"),
        Path("static"),
        Path("templates"),
    ]
    
    for directory in directories:
        directory.mkdir(exist_ok=True, parents=True)


def validate_configuration():
    """Validate configuration on startup."""
    print("🔍 Validating configuration...")
    
    settings = get_settings()
    ensure_directories()
    
    print(f"✅ UniFi Controller: {settings.unifi_base_url}")
    print(f"✅ UniFi Site: {settings.unifi_site}")
    print(f"✅ App Host: {settings.app_host}:{settings.app_port}")
    print(f"✅ Database: {settings.database_url}")
    print(f"✅ Log Level: {settings.log_level}")
    print(f"✅ Timezone: {settings.tz}")
    print(f"✅ Development Mode: {settings.development_mode}")
    print(f"✅ SSL Verification: {settings.unifi_verify_ssl}")
    
    if settings.app_secret_key == "change-this-to-a-random-secret-key-in-production":
        print("⚠️  WARNING: Using default SECRET_KEY. Change this in production!")
    
    print("✅ Configuration validated successfully\n")
    
    return settings


settings = get_settings()
