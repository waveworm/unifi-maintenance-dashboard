"""Telegram notification helpers for UniFi Maintenance Dashboard."""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _fmt_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s" if m else f"{s}s"


async def send_message(text: str) -> bool:
    """Send a Telegram message. Returns True on success, False on failure.
    Silent no-op if Telegram is disabled or not configured."""
    from app.config import settings

    if not settings.telegram_enabled:
        return False
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram enabled but BOT_TOKEN or CHAT_ID is missing — skipping notification")
        return False

    url = _TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if not resp.is_success:
                logger.warning(f"Telegram API returned {resp.status_code}: {resp.text[:200]}")
                return False
        return True
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")
        return False


async def notify_schedule_complete(
    schedule_name: str,
    site_display: str,
    results: list,
) -> None:
    """Send a grouped summary after a device reboot schedule completes.

    Each result dict: {device_name, status, duration_seconds, error_message}
    status values: "completed" | "failed"
    """
    if not results:
        return

    total = len(results)
    succeeded = sum(1 for r in results if r.get("status") == "completed")
    all_ok = succeeded == total

    header_icon = "✅" if all_ok else "⚠️"
    header_label = "Maintenance Complete" if all_ok else "Maintenance Partial"
    site_part = f" — {site_display}" if site_display else ""

    lines = [
        f"{header_icon} <b>{header_label}{site_part}</b>",
        f"📋 {schedule_name}",
        "",
        f"{succeeded} / {total} device{'s' if total != 1 else ''} rebooted:",
    ]

    for r in results:
        name = r.get("device_name", "Unknown")
        status = r.get("status", "")
        duration = r.get("duration_seconds")
        error = r.get("error_message", "")

        if status == "completed":
            dur_str = f"  {_fmt_duration(duration)}" if duration else ""
            lines.append(f"  • {name} ✅{dur_str}")
        else:
            err_str = f"  {error[:60]}" if error else "  error"
            lines.append(f"  • {name} ❌{err_str}")

    await send_message("\n".join(lines))


async def notify_device_back_online(
    device_name: str,
    duration_seconds: int,
    source: str = "manual",
) -> None:
    """Send 'device is back online' notification after a reboot."""
    dur = _fmt_duration(duration_seconds)
    source_label = "Manual reboot" if source == "manual" else "Reboot"
    text = (
        f"✅ <b>{device_name}</b> is back online\n"
        f"🔄 {source_label} — back up in {dur}"
    )
    await send_message(text)


async def notify_device_reboot_timeout(
    device_name: str,
    timeout_seconds: int = 300,
) -> None:
    """Send notification when a device doesn't come back online after reboot."""
    mins = timeout_seconds // 60
    text = (
        f"⚠️ <b>{device_name}</b> did not come back online\n"
        f"🔄 Manual reboot — no response after {mins} minute{'s' if mins != 1 else ''}"
    )
    await send_message(text)
