"""
AI Persona — FastAPI Backend
============================
Routes:
  POST /chat              → RAG-grounded chat via Gemini 1.5 Flash
  POST /slots             → Fetch live Cal.com availability
  POST /book              → Book a confirmed meeting slot
  POST /voice/call        -> Start Vobiz outbound voice call
  POST /vobiz/answer      -> Vobiz XML answer URL
  POST /vobiz/respond     -> Vobiz speech turn handler
  POST /vobiz/status      -> Vobiz call status callback
  WS   /vobiz/media       -> Vobiz media WebSocket
  GET  /health            → System health + index stats
  GET  /                  → API info
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import require_env
from rag.prompt_builder import build_prompt, PERSONA_IDENTITY, is_injection_attempt
from rag.retriever import retrieve, retrieve_with_sources, check_index_health
from voice.calendar_tool import get_availability, book_slot, format_slots_for_chat
from voice.vobiz_handler import (
    answer_xml,
    handle_vobiz_media,
    log_status_callback,
    response_xml,
    start_outbound_call,
    vobiz_config,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ─── Gemini setup ─────────────────────────────────────────────────────────────
genai.configure(api_key=require_env("GEMINI_API_KEY")["GEMINI_API_KEY"])
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
PROJECT_ROOT = Path(__file__).resolve().parent

gemini_model = genai.GenerativeModel(
    model_name=GEMINI_MODEL,
    system_instruction=PERSONA_IDENTITY,
    generation_config=genai.GenerationConfig(
        temperature=0.3,
        max_output_tokens=800,
    ),
)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Persona API",
    description="RAG-grounded AI persona — Gemini 1.5 Flash + Pinecone + Cal.com",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request / Response models ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[ChatMessage] = []


class BookRequest(BaseModel):
    name: str
    email: str
    slot_start: str
    notes: Optional[str] = ""


class VoiceCallRequest(BaseModel):
    phone: str
    name: Optional[str] = ""
    message: Optional[str] = ""


DIRECT_ANSWERS = {
    "why should scaler hire you": (
        "I'm a pre-final year student who has already shipped a production-grade multi-agent RAG system "
        "to real users - not a demo, a live system with streaming FastAPI backend, vector retrieval over "
        "500+ chunks, and a self-built eval loop measuring hallucination and retrieval quality. I reduced "
        "load time 30% at a real company. I was Top 10 at Microsoft Hackathon Innovate 2025 nationwide. "
        "I can build the stack, I can eval it, and I can do it now."
    ),
    "what makes you unique": (
        "Three things most candidates at my stage can't say together: I ship to real users, I close the "
        "eval loop myself, and I cover the full AI stack - RAG, agents, GANs, LSTM, FastAPI, vector DBs, "
        "frontend. The Microsoft hackathon is external proof it works. And I don't just build - I write "
        "the docs and quickstarts so others can use what I build, which matters at a learning platform."
    ),
}


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _load_github_repos() -> list[dict]:
    path = PROJECT_ROOT / "data" / "github_repos.json"
    if not path.exists():
        return []
    try:
        repos = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return repos if isinstance(repos, list) else []


def _extract_readme_summary(readme: str, limit: int = 420) -> str:
    text = re.sub(r"```.*?```", " ", readme or "", flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
    text = re.sub(r"[*_#>`|~-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _repo_response(repo: dict) -> dict:
    languages = repo.get("languages") or {}
    if isinstance(languages, dict):
        language_list = list(languages.keys())
    else:
        language_list = []
    primary = repo.get("language") or (language_list[0] if language_list else "Unknown")
    return {
        "name": repo.get("name", "unknown"),
        "description": repo.get("description") or _extract_readme_summary(repo.get("readme", ""), 140),
        "primary_language": primary,
        "languages": language_list,
        "topics": repo.get("topics", []),
        "stars": repo.get("stars", 0),
        "forks": repo.get("forks", 0),
        "url": repo.get("url", ""),
        "updated_at": repo.get("updated_at", ""),
        "commits": repo.get("commits", [])[:8],
        "summary": _extract_readme_summary(repo.get("readme", "")),
    }


def _tech_stack_from_repos(repos: list[dict]) -> list[str]:
    known = [
        "Python", "JavaScript", "TypeScript", "React", "Vite", "Tailwind CSS",
        "FastAPI", "Flask", "Express", "PostgreSQL", "Vercel", "Render",
        "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "OpenAI",
        "RAG", "Vector Database", "Endee", "Pinecone", "Docker", "HTML", "CSS",
        "Shadcn/ui", "Radix UI", "Recharts", "Framer Motion", "React Router",
        "Zod", "React Hook Form", "jsPDF", "html2canvas", "Multer", "PDF-Parse",
        "Mammoth", "Jupyter Notebook", "Random Forest", "LSTM", "ResNet",
        "DCGAN", "GAN",
    ]
    blob = "\n".join(
        " ".join([
            repo.get("name", ""),
            repo.get("description", "") or "",
            repo.get("readme", "") or "",
            " ".join((repo.get("languages") or {}).keys()),
        ])
        for repo in repos
    ).lower()
    found = []
    for tech in known:
        if tech.lower() in blob:
            found.append(tech)
    return found


def _generate_persona_answer(message: str) -> dict:
    """Generate a RAG-grounded answer for chat or voice."""
    normalized_message = re.sub(r"[^\w\s]", "", message.lower()).strip()

    for question, answer in DIRECT_ANSWERS.items():
        if question in normalized_message:
            return {
                "answer": answer,
                "sources": ["resume", "github"],
                "booking_available": False,
                "retrieval": {
                    "total_retrieved": 0,
                    "avg_score": 1,
                    "mode": "direct",
                    "error": None,
                },
            }

    if is_injection_attempt(message):
        return {
            "answer": "I'm here to discuss [YOUR NAME]'s background - happy to answer genuine questions!",
            "sources": [],
            "booking_available": False,
            "flagged": True,
            "retrieval": {
                "total_retrieved": 0,
                "avg_score": 0,
                "mode": "safety",
                "error": None,
            },
        }

    retrieval_error = None
    try:
        retrieval = retrieve_with_sources(message, top_k=10)
        chunks = retrieval["chunks"]
        retrieval_error = retrieval.get("error")
    except Exception as e:
        logger.exception("Retrieval error")
        retrieval_error = str(e)
        retrieval = {
            "chunks": [],
            "sources": [],
            "total_retrieved": 0,
            "avg_score": 0,
            "mode": "error",
        }
        chunks = []

    prompt = build_prompt(message, chunks)
    try:
        chat_session = gemini_model.start_chat(history=[])
        response = chat_session.send_message(prompt)
        answer = response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    return {
        "answer": answer,
        "sources": retrieval["sources"],
        "booking_available": False,
        "retrieval": {
            "total_retrieved": retrieval["total_retrieved"],
            "avg_score": retrieval["avg_score"],
            "mode": retrieval.get("mode", "unknown"),
            "error": retrieval_error,
        },
    }


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "AI Persona API",
        "version": "1.0.0",
        "endpoints": ["/chat", "/slots", "/book", "/github/repos", "/voice/config", "/voice/call", "/vobiz/answer", "/vobiz/respond", "/vobiz/status", "/vobiz/media", "/health"],
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.
    1. Retrieves relevant chunks from Pinecone
    2. Detects booking intent
    3. Builds grounded prompt
    4. Calls Gemini 1.5 Flash
    5. Returns answer + sources + latency
    """
    start_time = time.time()
    logger.info(f"Chat: '{req.message[:80]}...'")
    normalized_message = re.sub(r"[^\w\s]", "", req.message.lower()).strip()

    for question, answer in DIRECT_ANSWERS.items():
        if question in normalized_message:
            return {
                "answer": answer,
                "sources": ["resume", "github"],
                "booking_available": False,
                "latency_ms": int((time.time() - start_time) * 1000),
                "retrieval_stats": {
                    "chunks_retrieved": 0,
                    "avg_score": 1,
                    "mode": "direct",
                    "error": None,
                },
            }

    # Safety check
    if is_injection_attempt(req.message):
        return {
            "answer": (
                "I'm here to discuss [YOUR NAME]'s background — happy to answer genuine questions!"
            ),
            "sources": [],
            "booking_available": False,
            "latency_ms": int((time.time() - start_time) * 1000),
            "flagged": True,
        }

    # Retrieve context
    retrieval_error = None
    try:
        retrieval = retrieve_with_sources(req.message, top_k=10)
        chunks = retrieval["chunks"]
        retrieval_error = retrieval.get("error")
    except Exception as e:
        logger.exception("Retrieval error")
        retrieval_error = str(e)
        retrieval = {
            "chunks": [],
            "sources": [],
            "total_retrieved": 0,
            "avg_score": 0,
        }
        chunks = []

    # Detect booking intent
    booking_keywords = [
        "book", "schedule", "availability", "call", "meeting",
        "slot", "interview", "time", "calendar", "available",
        "appoint", "speak", "talk",
    ]
    wants_booking = any(kw in req.message.lower() for kw in booking_keywords)

    # Build prompt
    prompt = build_prompt(req.message, chunks)

    # Augment with live slots if booking intent detected
    if wants_booking:
        slots = get_availability(days_ahead=7, max_slots=6)
        if slots:
            slots_text = format_slots_for_chat(slots)
            prompt += f"\n\n{slots_text}\n\nPresent these options naturally in your response."

    # Build Gemini conversation history (last 10 turns)
    history = []
    for msg in req.conversation_history[-10:]:
        role = "user" if msg.role == "user" else "model"
        history.append({"role": role, "parts": [msg.content]})

    # Call Gemini
    try:
        chat_session = gemini_model.start_chat(history=history)
        response = chat_session.send_message(prompt)
        answer = response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(f"Chat response — latency: {latency_ms}ms | sources: {retrieval['sources']}")

    return {
        "answer": answer,
        "sources": retrieval["sources"],
        "booking_available": wants_booking,
        "latency_ms": latency_ms,
        "retrieval_stats": {
            "chunks_retrieved": retrieval["total_retrieved"],
            "avg_score": retrieval["avg_score"],
            "mode": retrieval.get("mode", "unknown"),
            "error": retrieval_error,
        },
    }


@app.post("/slots")
async def get_slots():
    """Return available Cal.com booking slots."""
    slots = get_availability(days_ahead=7, max_slots=6)
    return {"slots": slots, "count": len(slots)}


@app.get("/github/repos")
async def github_repos():
    """Return public GitHub repo summaries fetched into data/github_repos.json."""
    repos = [_repo_response(repo) for repo in _load_github_repos()]
    return {
        "repos": repos,
        "count": len(repos),
        "tech_stack": _tech_stack_from_repos(_load_github_repos()),
    }


@app.get("/voice/config")
async def voice_config():
    """Return safe voice-call configuration status for the frontend."""
    config = vobiz_config()
    config["configured"]["calcom_api_key"] = _env_present("CALCOM_API_KEY")
    config["configured"]["calcom_event_type_id"] = _env_present("CALCOM_EVENT_TYPE_ID")
    return config


@app.post("/voice/call")
async def voice_call(req: VoiceCallRequest):
    """Start an outbound Vobiz call to the submitted phone number."""
    result = start_outbound_call(
        phone_number=req.phone,
        name=req.name or "",
        message=req.message or "",
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unable to start voice call."))
    return result


@app.post("/book")
async def book(req: BookRequest):
    """Book a confirmed meeting slot via Cal.com."""
    if not req.name.strip() or not req.email.strip() or not req.slot_start.strip():
        raise HTTPException(status_code=400, detail="name, email, and slot_start are required")

    result = book_slot(
        name=req.name,
        email=req.email,
        slot_start=req.slot_start,
        notes=req.notes or "Booked via AI persona chat",
    )
    return result


@app.api_route("/vobiz/answer", methods=["GET", "POST"])
async def vobiz_answer(request: Request):
    """Return Vobiz XML when an outbound call is answered."""
    first_message = ""
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            payload = await request.json()
        else:
            form = await request.form()
            payload = dict(form)
        custom_data = payload.get("custom_data") or payload.get("CustomField") or ""
        if custom_data:
            parsed = json.loads(custom_data)
            first_message = parsed.get("first_message", "")
    except Exception:
        first_message = ""
    return answer_xml(first_message=first_message)


@app.api_route("/vobiz/respond", methods=["GET", "POST"])
async def vobiz_respond(request: Request):
    """Receive Vobiz speech transcription, answer with Gemini/RAG, and keep listening."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    elif request.method == "GET":
        payload = dict(request.query_params)
    else:
        form = await request.form()
        payload = dict(form)

    speech = (
        payload.get("Speech")
        or payload.get("speech")
        or payload.get("StableSpeech")
        or payload.get("UnstableSpeech")
        or ""
    ).strip()

    if not speech:
        return response_xml("I did not catch that. Could you say it once more?")

    if re.search(r"\b(bye|goodbye|hang up|end call|that is all|that's all)\b", speech, re.I):
        return response_xml("Thanks for calling. Have a great day.", hangup=True)

    result = _generate_persona_answer(speech)
    answer = result["answer"]
    # Phone calls need short turns; Vobiz will gather the next question after speaking.
    if len(answer) > 900:
        answer = answer[:880].rsplit(" ", 1)[0] + "."
    return response_xml(answer)


@app.post("/vobiz/status")
async def vobiz_status(request: Request):
    """Vobiz call status callback."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)
    return log_status_callback(payload)


@app.websocket("/vobiz/media")
async def vobiz_media(websocket: WebSocket):
    """Vobiz bidirectional media WebSocket."""
    await handle_vobiz_media(websocket)


@app.get("/health")
async def health():
    """Health check + Pinecone index stats."""
    index_health = check_index_health()
    return {
        "status": "ok",
        "version": "1.0.0",
        "pinecone": index_health,
        "gemini_model": GEMINI_MODEL,
        "embedding_model": "text-embedding-3-small",
    }