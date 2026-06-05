# AI Persona — [YOUR NAME]

> **Scaler AI Engineer Internship Screening Assignment**
> An end-to-end AI persona system you can call, chat with, and use to book a real interview — with no human in the loop.

---

## 🔗 Live Links

| Interface | URL |
|---|---|
| 📞 **Voice Agent Phone Number** | `+1 (XXX) XXX-XXXX` ← _Fill after Vapi setup_ |
| 💬 **Chat Interface** | `https://your-project.vercel.app` ← _Fill after Vercel deploy_ |
| 🔧 **Backend API** | `https://your-project.railway.app` ← _Fill after Railway deploy_ |
| 📁 **GitHub Repo** | `https://github.com/yourusername/ai-persona` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     USER                                 │
│         Chat (browser) │ Phone call (Vapi)              │
└──────────────┬──────────────────┬───────────────────────┘
               │                  │
               ▼                  ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│   Next.js 14 UI      │  │   Vapi Voice Agent           │
│   (Vercel)           │  │   ├─ Deepgram STT            │
│   - Chat interface   │  │   ├─ Gemini 1.5 Flash LLM    │
│   - BookingWidget    │  │   └─ ElevenLabs TTS          │
└──────────┬───────────┘  └──────────────┬───────────────┘
           │                             │
           ▼ REST                        ▼ Webhook
┌──────────────────────────────────────────────────────────┐
│              FastAPI Backend (Railway)                    │
│   POST /chat  POST /slots  POST /book  POST /vapi/webhook │
│                                                          │
│   ┌──────────────────┐   ┌──────────────────────────┐  │
│   │  RAG Pipeline    │   │  Calendar Integration    │  │
│   │  ├─ Retriever    │   │  └─ Cal.com v1 API       │  │
│   │  ├─ Prompt       │   └──────────────────────────┘  │
│   │  │  Builder      │                                  │
│   │  └─ Ingest       │   ┌──────────────────────────┐  │
│   └────────┬─────────┘   │  Gemini 1.5 Flash        │  │
│            │             │  (Google AI Studio)      │  │
│            ▼             └──────────────────────────┘  │
│   ┌──────────────────┐                                  │
│   │  Pinecone        │ ← OpenAI text-embedding-3-small │
│   │  Index: persona  │                                  │
│   │  Namespace: RAG  │                                  │
│   └──────────────────┘                                  │
└──────────────────────────────────────────────────────────┘
           ▲
           │ Ingest (one-time + on update)
┌──────────────────────────────────────────────────────────┐
│  Data Sources                                            │
│  ├─ data/resume.pdf       (PyMuPDF → chunked → embedded) │
│  └─ data/github_repos.json (fetch_github.py → embedded)  │
└──────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| LLM | Gemini 1.5 Flash | Chat responses + voice LLM |
| Embeddings | OpenAI text-embedding-3-small | Semantic search vectors |
| Eval Judge | GPT-4o | Golden Q&A scoring |
| Vector DB | Pinecone (Serverless) | RAG retrieval store |
| Voice | Vapi + ElevenLabs + Deepgram | Phone voice agent |
| Calendar | Cal.com v1 API | Real availability + booking |
| Backend | FastAPI + Uvicorn | REST API |
| Frontend | Next.js 14 + Tailwind CSS | Chat UI |
| Backend Hosting | Railway | Docker container deploy |
| Frontend Hosting | Vercel | Serverless Next.js |

---

## Cost Breakdown

### Per Chat Session (~10 messages)
| Item | Cost |
|---|---|
| Gemini 1.5 Flash (input ~2k tokens × 10) | ~$0.0015 |
| OpenAI embeddings (10 queries × 300 tokens) | ~$0.0001 |
| Pinecone queries (10 × top-6) | ~$0.00005 |
| **Total per session** | **~$0.002** |

### Per Voice Call (~5 min)
| Item | Cost |
|---|---|
| Vapi platform (~$0.05/min) | ~$0.25 |
| Deepgram Nova-2 (~$0.0043/min) | ~$0.022 |
| ElevenLabs TTS (~2000 chars) | ~$0.03 |
| Gemini 1.5 Flash (~5 turns) | ~$0.001 |
| **Total per call** | **~$0.30** |

### Monthly (light usage: 100 chats, 20 calls)
~$6.20/month total

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- Accounts: Gemini AI Studio, OpenAI, Pinecone, Vapi, ElevenLabs, Cal.com

### 1. Clone & Configure

```bash
git clone https://github.com/yourusername/ai-persona.git
cd ai-persona

# Copy env template and fill in your keys
cp .env.example .env
```

Edit `.env` with your API keys (see `.env.example` for all required keys).

### 2. Add Your Resume

```bash
cp /path/to/your/resume.pdf data/resume.pdf
```

### 3. Fetch GitHub Repos

```bash
# Edit scripts/fetch_github.py — replace YOUR_GITHUB_USERNAME
# Or set GITHUB_USERNAME in .env

python scripts/fetch_github.py
# Output: data/github_repos.json
```

### 4. Install Backend & Ingest Data

```bash
cd backend
pip install -r requirements.txt

# Ingest resume + GitHub into Pinecone
python rag/ingest.py

# Test ingest worked
python -c "from rag.retriever import retrieve; print(retrieve('Python projects'))"
```

### 5. Start Backend

```bash
cd backend
uvicorn main:app --reload --port 8000

# Test it
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about your background", "conversation_history": []}'
```

### 6. Start Frontend

```bash
cd frontend
npm install

# Create .env.local
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local

npm run dev
# Open http://localhost:3000
```

---

## Running Evals

```bash
cd backend

# Run full eval suite (requires backend running)
python evals/run_evals.py

# Filter by category
python evals/run_evals.py --filter adversarial
python evals/run_evals.py --filter github

# Generate PDF report from results
python evals/generate_report.py

# Run evals AND generate report in one command
python evals/run_evals.py --report

# Results saved to:
# backend/evals/eval_results.json
# backend/evals/eval_report.pdf
```

---

## Deployment

### Backend → Railway

```bash
cd backend

# Install Railway CLI
npm install -g @railway/cli
railway login

# Deploy
railway init
railway up

# Set environment variables in Railway dashboard
# (all keys from .env)
```

### Frontend → Vercel

```bash
cd frontend

# Install Vercel CLI
npm install -g vercel
vercel login

# Deploy
vercel

# Set environment variable:
# NEXT_PUBLIC_BACKEND_URL = https://your-railway-backend.up.railway.app
```

### Voice Agent → Vapi

1. Go to [vapi.ai](https://vapi.ai) → Create assistant
2. Set webhook URL: `https://your-railway-url.up.railway.app/vapi/webhook`
3. Set assistant type: "Server URL" (dynamic config from webhook)
4. Assign a phone number to the assistant
5. Test by calling the number

---

## Persona Customisation

Edit `backend/rag/prompt_builder.py`:
- Replace `[YOUR FULL NAME]` with your name
- Update the quick bio section with your real background
- The system will then use RAG to answer questions accurately

Edit `frontend/app/page.tsx`:
- Replace `[YOUR NAME]` in the initial message and header

---

## Project Structure

```
ai-persona/
├── backend/
│   ├── main.py                 # FastAPI app + all routes
│   ├── rag/
│   │   ├── ingest.py           # Data → Pinecone pipeline
│   │   ├── retriever.py        # Semantic search
│   │   └── prompt_builder.py   # Persona identity + prompt construction
│   ├── voice/
│   │   ├── vapi_handler.py     # Vapi webhook dispatcher
│   │   └── calendar_tool.py    # Cal.com availability + booking
│   ├── evals/
│   │   ├── run_evals.py        # Eval runner with GPT-4o judge
│   │   ├── golden_qa.json      # 18-question test suite
│   │   └── generate_report.py  # 1-page PDF report generator
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Main chat UI
│   │   ├── layout.tsx          # Next.js layout
│   │   └── globals.css         # Custom styles
│   ├── components/
│   │   └── BookingWidget.tsx   # Calendar booking flow
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.js
├── data/
│   ├── resume.pdf              # Your resume (gitignored)
│   └── github_repos.json       # Fetched repo data
├── scripts/
│   └── fetch_github.py         # GitHub scraper
├── .env.example
├── .gitignore
└── README.md
```

---

## Hard Requirements Checklist

- [x] Voice agent with phone number (Vapi + ElevenLabs)
- [x] < 2s first-response latency (Gemini 1.5 Flash + streaming config)
- [x] Handles barge-in/interruptions (Vapi VAD)
- [x] Real calendar booking (Cal.com v1 API)
- [x] RAG-grounded over actual resume + GitHub (Pinecone + OpenAI embeddings)
- [x] Prompt injection resistance (safety pattern detection)
- [x] Public chat URL (Next.js on Vercel)
- [x] Eval report with hallucination rate + metrics (GPT-4o judge)
- [x] 18-question golden Q&A set (adversarial + normal)
- [x] Clean README with architecture + cost breakdown
- [x] Public GitHub repo

---

## What I'd Build With 2 More Weeks

1. **Streaming chat responses** (SSE) to cut perceived latency from ~2s to sub-200ms first token
2. **Hybrid BM25 + dense retrieval** with Reciprocal Rank Fusion for better exact-match recall
3. **Automated eval regression** in CI — fail PR if hallucination rate > 5%
4. **Voice analytics dashboard** with per-call transcripts, scores, booking funnel
5. **Multi-turn voice memory** — persist context across tool calls so agent doesn't re-ask for name/email
