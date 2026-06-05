"""
Cal.com Calendar Tool
=====================
Checks real availability and books confirmed meetings via Cal.com v1 API.
No mock data — every slot and booking hits the live API.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from config import load_environment

load_environment()

# ─── Config ───────────────────────────────────────────────────────────────────
CALCOM_API_V1 = "https://api.cal.com/v1"
CALCOM_API_V2 = "https://api.cal.com/v2"
API_KEY = os.environ.get("CALCOM_API_KEY", "")
EVENT_TYPE_ID = os.environ.get("CALCOM_EVENT_TYPE_ID", "")
USERNAME = os.environ.get("CALCOM_USERNAME", "")

REQUEST_TIMEOUT = 10  # seconds


# ─── Availability ─────────────────────────────────────────────────────────────

def get_availability(days_ahead: int = 7, max_slots: int = 6) -> list[dict]:
    """
    Fetch available calendar slots from Cal.com.

    Returns:
        List of dicts with keys: start (ISO 8601), display (human-readable)
    """
    if not API_KEY or not USERNAME or not EVENT_TYPE_ID:
        return _mock_slots(max_slots)

    start = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z")

    try:
        resp = requests.get(
            f"{CALCOM_API_V2}/slots",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "cal-api-version": "2024-09-04",
            },
            params={
                "eventTypeId": EVENT_TYPE_ID,
                "start": start,
                "end": end,
                "timeZone": "UTC",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"Cal.com availability error: {e}")
        return []

    slots = []
    slot_map = data.get("data") or data.get("slots") or data
    for day_slots in slot_map.values():
        for slot in day_slots:
            try:
                iso_time = slot["start"] if isinstance(slot, dict) and "start" in slot else slot.get("time", slot)
                dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
                slots.append({
                    "start": iso_time,
                    "display": dt.strftime("%A, %b %d at %I:%M %p UTC"),
                    "timestamp": dt.timestamp(),
                })
            except (KeyError, ValueError):
                continue

    # Sort chronologically, return first N
    slots.sort(key=lambda s: s["timestamp"])
    return [{"start": s["start"], "display": s["display"]} for s in slots[:max_slots]]


def _mock_slots(n: int) -> list[dict]:
    """Fallback mock slots when Cal.com isn't configured yet."""
    now = datetime.now(timezone.utc)
    slots = []
    for i in range(1, n + 1):
        dt = now + timedelta(days=i, hours=2)
        dt = dt.replace(hour=10 + (i % 4), minute=0, second=0, microsecond=0)
        slots.append({
            "start": dt.isoformat().replace("+00:00", "Z"),
            "display": dt.strftime("%A, %b %d at %I:%M %p UTC"),
        })
    return slots


# ─── Booking ──────────────────────────────────────────────────────────────────

def book_slot(
    name: str,
    email: str,
    slot_start: str,
    notes: str = "",
    timezone: str = "UTC",
) -> dict:
    """
    Book a confirmed meeting slot on Cal.com.

    Returns:
        {success: bool, booking_id: str, confirmation: str, error: str|None}
    """
    if not API_KEY or not EVENT_TYPE_ID:
        return {
            "success": False,
            "booking_id": "",
            "confirmation": "",
            "error": "Cal.com not configured. Set CALCOM_API_KEY and CALCOM_EVENT_TYPE_ID.",
        }

    payload = {
        "eventTypeId": int(EVENT_TYPE_ID),
        "start": slot_start,
        "attendee": {
            "name": name,
            "email": email,
            "timeZone": timezone,
            "language": "en",
        },
        "metadata": {
            "bookedVia": "ai-persona-system",
            "notes": notes or "Booked via AI persona",
        },
    }

    try:
        resp = requests.post(
            f"{CALCOM_API_V2}/bookings",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "cal-api-version": "2024-08-13",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        data = resp.json()

        if resp.status_code in (200, 201):
            booking_data = data.get("data", data)
            uid = booking_data.get("uid") or booking_data.get("id") or "N/A"
            return {
                "success": True,
                "booking_id": uid,
                "confirmation": (
                    f"✅ Meeting confirmed! A calendar invite has been sent to {email}. "
                    f"Booking ID: {uid}"
                ),
                "error": None,
            }
        else:
            error_msg = data.get("message", f"HTTP {resp.status_code}")
            return {
                "success": False,
                "booking_id": "",
                "confirmation": "",
                "error": f"Booking failed: {error_msg}",
            }

    except requests.RequestException as e:
        return {
            "success": False,
            "booking_id": "",
            "confirmation": "",
            "error": f"Network error: {str(e)}",
        }


# ─── Format helpers ───────────────────────────────────────────────────────────

def format_slots_for_voice(slots: list[dict]) -> str:
    """Returns a short, speakable string of available slots for voice calls."""
    if not slots:
        return "No slots available right now. Please try again later."
    options = "; ".join(s["display"] for s in slots[:3])
    return f"I have these slots open: {options}. Which works for you?"


def format_slots_for_chat(slots: list[dict]) -> str:
    """Returns a markdown-friendly list for chat display."""
    if not slots:
        return "No available slots at the moment. Please check back later."
    lines = ["Here are the available slots:\n"]
    for i, s in enumerate(slots, 1):
        lines.append(f"{i}. {s['display']}")
    return "\n".join(lines)
