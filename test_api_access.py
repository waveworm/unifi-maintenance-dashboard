#!/usr/bin/env python3
"""Validate UniFi API accessibility using configured credentials."""

import asyncio
import httpx

from app.config import settings


async def _print_status(client: httpx.AsyncClient, base_url: str) -> None:
    print("=" * 70)
    print("Check 1: Controller status")
    print("=" * 70)
    response = await client.get(f"{base_url}/status")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:300]}")


async def _try_login(client: httpx.AsyncClient, base_url: str) -> tuple[str, str]:
    payload = {
        "username": settings.unifi_username,
        "password": settings.unifi_password,
        "remember": True,
    }

    print("\n" + "=" * 70)
    print("Check 2: Standard login (/api/login)")
    print("=" * 70)
    standard = await client.post(f"{base_url}/api/login", json=payload)
    print(f"Status: {standard.status_code}")
    print(f"Response: {standard.text[:300]}")
    if standard.status_code == 200:
        return "standard", ""

    print("\n" + "=" * 70)
    print("Check 3: UniFi OS login (/api/auth/login)")
    print("=" * 70)
    unifi_os = await client.post(f"{base_url}/api/auth/login", json=payload)
    print(f"Status: {unifi_os.status_code}")
    print(f"Response: {unifi_os.text[:300]}")
    if unifi_os.status_code == 200:
        return "unifi_os", "/proxy/network"

    raise RuntimeError(
        f"Authentication failed with both methods "
        f"({standard.status_code}, {unifi_os.status_code})"
    )


async def _check_api_access(client: httpx.AsyncClient, base_url: str, api_prefix: str) -> None:
    print("\n" + "=" * 70)
    print("Check 4: Authenticated sites endpoint")
    print("=" * 70)
    sites = await client.get(f"{base_url}{api_prefix}/api/self/sites")
    print(f"Status: {sites.status_code}")
    print(f"Response: {sites.text[:300]}")

    print("\n" + "=" * 70)
    print("Check 5: Authenticated devices endpoint")
    print("=" * 70)
    devices = await client.get(
        f"{base_url}{api_prefix}/api/s/{settings.unifi_site}/stat/device"
    )
    print(f"Status: {devices.status_code}")
    print(f"Response: {devices.text[:300]}")


async def check_controller() -> None:
    base_url = settings.unifi_base_url.rstrip("/")

    async with httpx.AsyncClient(
        verify=settings.unifi_verify_ssl,
        timeout=20.0,
        follow_redirects=True,
    ) as client:
        await _print_status(client, base_url)
        login_mode, api_prefix = await _try_login(client, base_url)
        await _check_api_access(client, base_url, api_prefix)

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Base URL: {base_url}")
    print(f"Site: {settings.unifi_site}")
    print(f"Login mode: {login_mode}")


if __name__ == "__main__":
    asyncio.run(check_controller())
