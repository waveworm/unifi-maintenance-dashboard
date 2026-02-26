#!/usr/bin/env python3
"""Direct authentication test with different methods."""

import asyncio
import httpx
import json

async def test_all_methods():
    """Test various authentication approaches."""
    
    base_url = "https://10.91.0.10:8443"
    username = "unifiALI"
    password = "*ZoEegqNY2ryj9Xwu"
    
    client = httpx.AsyncClient(verify=False, timeout=30.0, follow_redirects=True)
    
    # Method 1: Form data instead of JSON
    print("=" * 70)
    print("Method 1: Form data authentication")
    print("=" * 70)
    try:
        response = await client.post(
            f"{base_url}/api/login",
            data={"username": username, "password": password}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        if response.status_code == 200:
            print("✅ SUCCESS with form data!")
            print(f"Cookies: {response.cookies}")
            await client.aclose()
            return True
    except Exception as e:
        print(f"Error: {e}")
    
    # Method 2: JSON with strict=False
    print("\n" + "=" * 70)
    print("Method 2: JSON authentication")
    print("=" * 70)
    try:
        response = await client.post(
            f"{base_url}/api/login",
            json={"username": username, "password": password, "remember": True}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        if response.status_code == 200:
            print("✅ SUCCESS with JSON!")
            print(f"Cookies: {response.cookies}")
            await client.aclose()
            return True
    except Exception as e:
        print(f"Error: {e}")
    
    # Method 3: Check if it's UniFi OS (needs /proxy/network/api)
    print("\n" + "=" * 70)
    print("Method 3: UniFi OS proxy endpoint")
    print("=" * 70)
    try:
        response = await client.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "password": password}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        
        if response.status_code == 200:
            print("✅ SUCCESS - This is UniFi OS!")
            print(f"Cookies: {response.cookies}")
            
            # Now try to access network API through proxy
            print("\nTrying to access devices through UniFi OS proxy...")
            devices_response = await client.get(
                f"{base_url}/proxy/network/api/s/default/stat/device",
                cookies=response.cookies
            )
            print(f"Devices Status: {devices_response.status_code}")
            print(f"Devices Response: {devices_response.text[:300]}")
            
            await client.aclose()
            return True
    except Exception as e:
        print(f"Error: {e}")
    
    # Method 4: URL-encoded form
    print("\n" + "=" * 70)
    print("Method 4: URL-encoded form")
    print("=" * 70)
    try:
        response = await client.post(
            f"{base_url}/api/login",
            data=f"username={username}&password={password}",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        if response.status_code == 200:
            print("✅ SUCCESS with URL-encoded!")
            await client.aclose()
            return True
    except Exception as e:
        print(f"Error: {e}")
    
    await client.aclose()
    return False

if __name__ == "__main__":
    result = asyncio.run(test_all_methods())
    if result:
        print("\n" + "=" * 70)
        print("✅ Found working authentication method!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ All methods failed")
        print("=" * 70)
