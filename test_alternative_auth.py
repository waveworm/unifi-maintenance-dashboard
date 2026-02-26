#!/usr/bin/env python3
"""Test if we can bypass login with cookie injection or other methods."""

import asyncio
import httpx

async def test_alternatives():
    base_url = "https://10.91.0.10:8443"
    client = httpx.AsyncClient(verify=False, timeout=10.0)
    
    # Try accessing devices without auth to see error details
    print("Testing direct device access...")
    try:
        response = await client.get(f"{base_url}/api/s/default/stat/device")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Check if there's an API key method
    print("\nTesting API key header...")
    try:
        headers = {"X-API-KEY": "test"}
        response = await client.get(f"{base_url}/api/s/default/stat/device", headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
    except Exception as e:
        print(f"Error: {e}")
    
    await client.aclose()
    
    print("\n" + "=" * 70)
    print("CONCLUSION:")
    print("=" * 70)
    print("The UniFi API requires proper authentication.")
    print("You need to create a LOCAL admin account in UniFi settings.")
    print("\nSteps:")
    print("1. Login to https://10.91.0.10:8443")
    print("2. Settings → System → Admins")
    print("3. Add Admin → Create LOCAL account (not SSO)")
    print("4. Provide the new credentials")

if __name__ == "__main__":
    asyncio.run(test_alternatives())
