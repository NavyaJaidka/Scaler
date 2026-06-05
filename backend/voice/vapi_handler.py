"""
Vapi webhook handler.

Supported events:
  - assistant-request: returns the voice assistant config
  - function-call: executes a single calendar tool call
  - tool-calls: executes one or more calendar tool calls
  - end-of-call-report: logs call metrics for evals
"""

import json
import logging
import os
from pathlib import Path

from config import load_environment
from rag.prompt_builder import PERSONA_IDENTITY
from voice.calendar_tool import book_slot, format_slots_for_voice, get_availability

load_environment()
logger = logging.getLogger(__name__)

VOICE_SYSTEM_PROMPT = PERSONA_IDENTITY + """

VOICE CALL RULES:
- You are on a PHONE CALL. Keep every response to 2-3 short sentences.
- Sound warm, natural, and conversational.
- When asked about availability, call the check_calendar tool immediately.
- When a caller selects a slot, call the book_meeting tool with their name, email, and slot.
- Never read out long lists. Say "I have a few slots. Want to hear them?"
- If interrupted, stop speaking and listen.
- End gracefully: "It was great talking! You'll get a calendar invite shortly."
"""

VAPI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_calendar",
            "description": "Check the candidate's available interview slots for the next 7 days.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_meeting",
            "description": "Book a confirmed interview slot on the candidate's calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Full name of the person booking.",
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address for the calendar invite.",
                    },
                    "slot_start": {
                        "type": "string",
                        "description": "ISO 8601 datetime of the selected slot.",
                    },
                },
                "required": ["name", "email", "slot_start"],
            },
        },
    },
]


def _build_assistant_config() -> dict:
    return {
        "firstMessage": (
            "Hi there! I'm the AI representative for [YOUR NAME]. "
            "I can answer questions about their background and experience, "
            "or help you book an interview directly. What would you like to know?"
        ),
        "model": {
            "provider": "google",
            "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            "systemPrompt": VOICE_SYSTEM_PROMPT,
            "tools": VAPI_TOOLS,
            "temperature": 0.3,
            "maxTokens": 300,
        },
        "voice": {
            "provider": "11labs",
            "voiceId": os.environ.get("ELEVENLABS_VOICE_ID", "rachel"),
            "stability": 0.5,
            "similarityBoost": 0.75,
            "style": 0.0,
            "useSpeakerBoost": True,
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en-US",
        },
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
        "backgroundSound": "off",
        "backchannelingEnabled": True,
        "endCallMessage": (
            "It was great talking with you! You'll receive a calendar confirmation shortly. "
            "Have a wonderful day!"
        ),
        "endCallPhrases": [
            "goodbye",
            "bye",
            "thanks bye",
            "that's all",
            "talk later",
            "see you",
        ],
    }


def _parse_parameters(raw_params) -> dict:
    if isinstance(raw_params, dict):
        return raw_params
    if isinstance(raw_params, str) and raw_params.strip():
        try:
            parsed = json.loads(raw_params)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            logger.warning("Could not parse Vapi tool parameters as JSON")
    return {}


def _normalise_function_call(function_call: dict) -> dict:
    function = function_call.get("function", {})
    return {
        "name": function_call.get("name") or function.get("name", ""),
        "parameters": _parse_parameters(
            function_call.get("parameters", function.get("arguments", {}))
        ),
    }


def _handle_function_call(function_call: dict) -> dict:
    call = _normalise_function_call(function_call)
    fn_name = call["name"]
    params = call["parameters"]

    logger.info("Voice tool call: %s(%s)", fn_name, params)

    if fn_name == "check_calendar":
        slots = get_availability(days_ahead=7, max_slots=3)
        return {"result": format_slots_for_voice(slots), "slots": slots}

    if fn_name == "book_meeting":
        name = params.get("name", "")
        email = params.get("email", "")
        slot_start = params.get("slot_start", "")

        if not all([name, email, slot_start]):
            return {
                "result": (
                    "I need your name, email, and the slot you'd like. "
                    "Could you confirm those for me?"
                )
            }

        booking = book_slot(name, email, slot_start, notes="Booked via voice AI")
        if booking["success"]:
            return {"result": booking["confirmation"]}
        return {
            "result": (
                f"I ran into an issue booking that slot: {booking['error']}. "
                "Would you like to try a different time?"
            )
        }

    return {"result": f"Unknown tool: {fn_name}"}


def _handle_tool_calls(tool_calls: list[dict]) -> dict:
    results = []
    for tool_call in tool_calls:
        result = _handle_function_call(tool_call)
        results.append(
            {
                "toolCallId": tool_call.get("id", tool_call.get("toolCallId", "")),
                "result": result.get("result", result),
            }
        )
    return {"results": results}


def _log_call_report(report: dict) -> None:
    logs_path = Path("logs/call_metrics.jsonl")
    logs_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": report.get("startedAt", ""),
        "duration_seconds": report.get("durationSeconds", 0),
        "cost": report.get("cost", {}),
        "ended_reason": report.get("endedReason", ""),
        "transcript_snippet": report.get("transcript", "")[:800],
        "summary": report.get("summary", ""),
        "messages_count": len(report.get("messages", [])),
    }

    with open(logs_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    logger.info(
        "Call logged - duration: %ss | reason: %s",
        record["duration_seconds"],
        record["ended_reason"],
    )


async def handle_vapi_webhook(body: dict) -> dict:
    """Dispatch Vapi webhook events to the appropriate handler."""
    message = body.get("message", body)
    event_type = message.get("type", body.get("type", ""))

    logger.debug("Vapi event: %s", event_type)

    if event_type == "assistant-request":
        return {"assistant": _build_assistant_config()}

    if event_type == "function-call":
        return _handle_function_call(message.get("functionCall", {}))

    if event_type == "tool-calls":
        return _handle_tool_calls(message.get("toolCalls", []))

    if event_type == "end-of-call-report":
        _log_call_report(message)
        return {"status": "logged"}

    if event_type in ("status-update", "hang", "speech-update", "transcript"):
        return {"status": "ok"}

    logger.warning("Unhandled Vapi event type: %s", event_type)
    return {"status": "ok", "note": f"unhandled event: {event_type}"}
