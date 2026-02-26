#!/usr/bin/env python3
"""
Test script to verify UniFi controller connection.

This script will:
1. Load configuration from .env
2. Connect to UniFi controller
3. List all sites
4. List all devices with details
5. Verify API functionality

Run this before starting the main application to ensure your configuration is correct.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.config import validate_configuration
from app.logging_config import setup_logging
from app.unifi_client import test_connection


async def main():
    """Main test function."""
    print("=" * 70)
    print("UniFi Controller Connection Test")
    print("=" * 70)
    
    setup_logging()
    
    try:
        validate_configuration()
    except SystemExit:
        return 1
    
    print("\n🔌 Testing connection to UniFi controller...\n")
    
    success = await test_connection()
    
    if success:
        print("\n" + "=" * 70)
        print("✅ Connection test PASSED")
        print("=" * 70)
        print("\nYou can now start the application with:")
        print("  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        return 0
    else:
        print("\n" + "=" * 70)
        print("❌ Connection test FAILED")
        print("=" * 70)
        print("\nPlease check:")
        print("  1. UNIFI_BASE_URL is correct in .env")
        print("  2. UNIFI_USERNAME and UNIFI_PASSWORD are correct")
        print("  3. UniFi controller is running and accessible")
        print("  4. Network connectivity between this machine and controller")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
