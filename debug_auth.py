#!/usr/bin/env python3
"""Debug authentication issues with UniFi controller."""

import asyncio
import sys
from pathlib import Path
import httpx
import json

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings

async def test_auth():
    """Test different authentication methods."""
    
    print("=" * 70)
    print("UniFi Authentication Debug")
    print("=" * 70)
    print(f"\nController: {settings.unifi_base_url}")
    print(f"Username: {settings.unifi_username}")
    print(f"Password: {'*' * len(settings.unifi_password)}")
    print(f"SSL Verify: {settings.unifi_verify_ssl}")
    
    client = httpx.AsyncClient(verify=settings.unifi_verify_ssl, timeout=10.0)
    
    # Test 1: Try standard login endpoint
    print("\n" + "=" * 70)
    print("Test 1: Standard /api/login endpoint")
    print("=" * 70)
    
    try:
        login_url = f"{settings.unifi_base_url}/api/login"
        payload = {
            "username": settings.unifi_username,
            "password": settings.unifi_password
        }
        
        print(f"POST {login_url}")
        print(f"Payload: {json.dumps({'username': settings.unifi_username, 'password': '***'})}")
        
        response = await client.post(login_url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✅ Authentication successful!")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Try with remember=false
    print("\n" + "=" * 70)
    print("Test 2: Login with remember=false")
    print("=" * 70)
    
    try:
        payload = {
            "username": settings.unifi_username,
            "password": settings.unifi_password,
            "remember": False
        }
        
        response = await client.post(login_url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✅ Authentication successful!")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Try alternative auth endpoint
    print("\n" + "=" * 70)
    print("Test 3: Alternative /api/auth/login endpoint")
    print("=" * 70)
    
    try:
        alt_login_url = f"{settings.unifi_base_url}/api/auth/login"
        payload = {
            "username": settings.unifi_username,
            "password": settings.unifi_password
        }
        
        print(f"POST {alt_login_url}")
        response = await client.post(alt_login_url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✅ Authentication successful!")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Check if it's UniFi OS (new controllers)
    print("\n" + "=" * 70)
    print("Test 4: UniFi OS /api/auth/login (new controllers)")
    print("=" * 70)
    
    try:
        unifi_os_url = f"{settings.unifi_base_url}/api/auth/login"
        payload = {
            "username": settings.unifi_username,
            "password": settings.unifi_password
        }
        
        response = await client.post(unifi_os_url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            print("✅ Authentication successful - This is a UniFi OS controller!")
            print("\n⚠️  You need to use the UniFi OS API endpoints.")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await client.aclose()
    
    print("\n" + "=" * 70)
    print("Troubleshooting Tips:")
    print("=" * 70)
    print("1. Verify username and password are correct")
    print("2. Check if this is a UniFi OS controller (UDM/UDM-Pro/Cloud Key Gen2+)")
    print("3. Try logging into the web UI with these credentials")
    print("4. Check for special characters in password that might need escaping")
    print("5. Ensure the user has admin privileges")
    
    return False

if __name__ == "__main__":
    asyncio.run(test_auth())
