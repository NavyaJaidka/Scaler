"""
Vobiz voice handler.

Starts outbound Vobiz calls, returns Vobiz XML for answered calls, and exposes
a bidirectional media WebSocket for the live voice bot path.
"""

import html
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import requests
from fastapi import Response, WebSocket, WebSocketDisconnect

from config import load_environment

load_environment()
logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _public_base_url() -> str:
    base_url = (
        _env("PUBLIC_BACKEND_URL")
        or _env("BACKEND_URL")
        or _env("RAILWAY_PUBLIC_DOMAIN")
    )
    if not base_url:
        return ""
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    return base_url.rstrip("/")


def _answer_url() -> str:
    explicit = _env("VOBIZ_ANSWER_URL")
    if explicit:
        return explicit

    base_url = _public_base_url()
    if not base_url:
        return ""
    return f"{base_url}/vobiz/answer"


def _respond_url() -> str:
    explicit = _env("VOBIZ_RESPOND_URL")
    if explicit:
        return explicit

    base_url = _public_base_url()
    if not base_url:
        return ""
    return f"{base_url}/vobiz/respond"


def _status_callback_url() -> str:
    explicit = _env("VOBIZ_STATUS_CALLBACK_URL")
    if explicit:
        return explicit

    base_url = _public_base_url()
    if not base_url:
        return ""
    return f"{base_url}/vobiz/status"


def vobiz_config() -> dict[str, Any]:
    answer_url = _answer_url()
    respond_url = _respond_url()
    return {
        "enabled": bool(
            _env("VOBIZ_AUTH_ID")
            and _env("VOBIZ_AUTH_TOKEN")
            and _env("VOBIZ_CALLER_ID")
            and answer_url
            and respond_url
        ),
        "provider": "vobiz",
        "answer_url": answer_url,
        "respond_url": respond_url,
        "webhook_path": "/vobiz/status",
        "configured": {
            "vobiz_auth_id": bool(_env("VOBIZ_AUTH_ID")),
            "vobiz_auth_token": bool(_env("VOBIZ_AUTH_TOKEN")),
            "vobiz_caller_id": bool(_env("VOBIZ_CALLER_ID")),
            "vobiz_answer_url": bool(answer_url),
            "vobiz_respond_url": bool(respond_url),
        },
    }


def _normalise_phone_number(phone_number: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", phone_number.strip())
    if cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = "+91" + cleaned[1:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = "+" + cleaned
    elif re.fullmatch(r"\d{10}", cleaned):
        cleaned = "+91" + cleaned
    return cleaned


def start_outbound_call(phone_number: str, name: str = "", message: str = "") -> dict[str, Any]:
    """Ask Vobiz to call the recruiter and fetch our answer URL when answered."""
    auth_id = _env("VOBIZ_AUTH_ID")
    auth_token = _env("VOBIZ_AUTH_TOKEN")
    caller_id = _env("VOBIZ_CALLER_ID")
    answer_url = _answer_url()

    missing = [
        key
        for key, value in (
            ("VOBIZ_AUTH_ID", auth_id),
            ("VOBIZ_AUTH_TOKEN", auth_token),
            ("VOBIZ_CALLER_ID", caller_id),
            ("VOBIZ_ANSWER_URL or PUBLIC_BACKEND_URL", answer_url),
        )
        if not value
    ]
    if missing:
        return {"success": False, "error": f"Missing Vobiz config: {', '.join(missing)}"}

    to_number = _normalise_phone_number(phone_number)
    if not re.fullmatch(r"\+[1-9]\d{7,14}", to_number):
        return {
            "success": False,
            "error": "Enter a valid phone number, for example +919876543210.",
        }

    payload: dict[str, Any] = {
        "from": caller_id,
        "to": to_number,
        "answer_url": answer_url,
        "answer_method": "POST",
    }
    callback_url = _status_callback_url()
    if callback_url:
        payload["callback_url"] = callback_url
        payload["callback_method"] = "POST"
    if name.strip() or message.strip():
        payload["custom_data"] = json.dumps({
            "name": name.strip(),
            "first_message": message.strip(),
        })[:512]

    try:
        response = requests.post(
            f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/",
            headers={
                "Content-Type": "application/json",
                "X-Auth-ID": auth_id,
                "X-Auth-Token": auth_token,
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json() if response.text else {}
    except requests.HTTPError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        logger.warning("Vobiz outbound call failed: %s", detail)
        return {"success": False, "error": detail}
    except Exception as exc:
        logger.warning("Vobiz outbound call error: %s", exc)
        return {"success": False, "error": str(exc)}

    return {
        "success": True,
        "provider": "vobiz",
        "message": data.get("message") or "Call started. You should receive a Vobiz call shortly.",
        "call": {
            "api_id": data.get("api_id", ""),
            "request_uuid": data.get("request_uuid", ""),
        },
    }


def _voice_xml(text: str, include_gather: bool = True) -> Response:
    safe_text = html.escape(text.strip() or "I did not catch that. Could you repeat?")
    action = html.escape(_respond_url())
    if include_gather and action:
        body = f"""
    <Gather inputType="speech" action="{action}" method="POST" speechModel="phone_call" language="en-US" executionTimeout="30" speechEndTimeout="3" redirect="true">
        <Speak voice="WOMAN" language="en-US">{safe_text}</Speak>
    </Gather>
    <Speak voice="WOMAN" language="en-US">I did not hear anything. Please try again.</Speak>
    <Redirect method="POST">{action}</Redirect>"""
    else:
        body = f"""
    <Speak voice="WOMAN" language="en-US">{safe_text}</Speak>
    <Hangup/>"""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
{body}
</Response>"""
    return Response(content=xml, media_type="application/xml")


def answer_xml(first_message: str = "") -> Response:
    """Return initial Vobiz XML that asks the caller what they want to know."""
    greeting = (
        first_message.strip()
        or "Hi there. I am the AI representative. Ask me about the candidate's background, projects, skills, or availability."
    )
    return _voice_xml(greeting, include_gather=True)


def response_xml(answer: str, hangup: bool = False) -> Response:
    """Return Vobiz XML that speaks the AI answer and listens for the next turn."""
    return _voice_xml(answer, include_gather=not hangup)


def log_status_callback(payload: dict[str, Any]) -> dict[str, str]:
    logs_path = BACKEND_DIR / "logs" / "vobiz_status.jsonl"
    logs_path.parent.mkdir(parents=True, exist_ok=True)
    with open(logs_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")
    return {"status": "logged"}


async def handle_vobiz_media(websocket: WebSocket) -> None:
    """
    Accept Vobiz bidirectional media.

    This currently keeps the media connection alive and logs stream events. The
    STT -> Gemini -> TTS loop can be added here once the Vobiz call transport is
    confirmed with the trial account.
    """
    await websocket.accept()
    logger.info("Vobiz media stream connected")

    try:
        while True:
            message = await websocket.receive()
            if message.get("text"):
                logger.debug("Vobiz media text event: %s", message["text"][:300])
            elif message.get("bytes"):
                logger.debug("Vobiz media bytes: %s bytes", len(message["bytes"]))
    except WebSocketDisconnect:
        logger.info("Vobiz media stream disconnected")