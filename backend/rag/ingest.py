"""
RAG Ingestion Pipeline
======================
Chunks resume PDF + GitHub repo data.
Embeds with OpenAI text-embedding-3-small.
Stores in Pinecone (serverless, aws us-east-1).

Usage:
    cd backend
    python rag/ingest.py
    python rag/ingest.py --only resume
    python rag/ingest.py --only github
    python rag/ingest.py --clear   # wipe and re-ingest everything
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
from config import require_env
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

env = require_env("OPENAI_API_KEY", "PINECONE_API_KEY")

# ─── Clients ──────────────────────────────────────────────────────────────────
openai_client = OpenAI(api_key=env["OPENAI_API_KEY"])
pc = Pinecone(api_key=env["PINECONE_API_KEY"])
INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "ai-persona")
NAMESPACE = "persona"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# ─── Index management ─────────────────────────────────────────────────────────

def get_or_create_index() -> "pinecone.Index":
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Wait for index to be ready
        for _ in range(10):
            time.sleep(2)
            idx_info = pc.describe_index(INDEX_NAME)
            if idx_info.status.get("ready", False):
                break
        print(f"Index '{INDEX_NAME}' ready.")
    else:
        print(f"Using existing index '{INDEX_NAME}'.")
    return pc.Index(INDEX_NAME)


def clear_namespace(index) -> None:
    print(f"Clearing namespace '{NAMESPACE}'...")
    try:
        index.delete(delete_all=True, namespace=NAMESPACE)
        time.sleep(1)
        print("Namespace cleared.")
    except Exception as e:
        print(f"Warning: could not clear namespace: {e}")


# ─── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    """Split text into overlapping word-count windows."""
    words = text.split()
    chunks = []
    step = max(1, size - overlap)
    for i in range(0, len(words), step):
        chunk = words[i : i + size]
        if chunk:
            chunks.append(" ".join(chunk))
    return chunks


# ─── Embedding ────────────────────────────────────────────────────────────────

def embed(text: str) -> list[float]:
    """Embed a single text string using OpenAI."""
    resp = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text[:8000]],  # Safety truncation
    )
    return resp.data[0].embedding


def embed_batch(texts: list[str], delay: float = 0.05) -> list[list[float]]:
    """Embed a list of texts with rate-limit protection."""
    embeddings = []
    for t in texts:
        embeddings.append(embed(t))
        time.sleep(delay)
    return embeddings


# ─── Upsert helper ────────────────────────────────────────────────────────────

def upsert_vectors(index, vectors: list[dict], batch_size: int = 100) -> None:
    """Upsert in batches to stay within Pinecone request limits."""
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch, namespace=NAMESPACE)
        time.sleep(0.1)
    print(f"  ✓ Upserted {len(vectors)} vectors")


# ─── Resume ingestion ─────────────────────────────────────────────────────────

def ingest_resume(index) -> int:
    resume_path = Path("data/resume.pdf")
    if not resume_path.exists():
        # Try one level up
        resume_path = Path("../data/resume.pdf")
    if not resume_path.exists():
        print("⚠️  data/resume.pdf not found — skipping resume ingestion.")
        print("   Place your resume at ai-persona/data/resume.pdf and re-run.")
        return 0

    print("Ingesting resume...")
    doc = fitz.open(str(resume_path))
    full_text = "\n".join(page.get_text() for page in doc)
    doc.close()

    chunks = chunk_text(full_text, size=350, overlap=70)
    vectors = []
    for i, chunk in enumerate(chunks):
        vectors.append({
            "id": f"resume-{i}",
            "values": embed(chunk),
            "metadata": {
                "source": "resume",
                "chunk_index": i,
                "text": chunk[:1000],  # Pinecone metadata limit
            },
        })
        time.sleep(0.05)
        sys.stdout.write(f"\r  Embedded {i+1}/{len(chunks)} resume chunks...")
        sys.stdout.flush()
    print()

    upsert_vectors(index, vectors)
    return len(vectors)


# ─── GitHub ingestion ─────────────────────────────────────────────────────────

def ingest_github(index) -> int:
    github_path = Path("data/github_repos.json")
    if not github_path.exists():
        github_path = Path("../data/github_repos.json")
    if not github_path.exists():
        print("⚠️  data/github_repos.json not found — skipping GitHub ingestion.")
        print("   Run: python scripts/fetch_github.py")
        return 0

    repos = json.loads(github_path.read_text(encoding="utf-8"))
    print(f"Ingesting {len(repos)} GitHub repos...")

    vectors = []
    for repo in repos:
        # Build rich repo context
        lines = [
            f"Repository: {repo.get('name', 'unknown')}",
            f"Description: {repo.get('description') or 'No description'}",
            f"Language: {repo.get('language') or 'Unknown'}",
            f"Topics: {', '.join(repo.get('topics', [])) or 'none'}",
            f"Stars: {repo.get('stars', 0)}",
            f"URL: {repo.get('url', '')}",
        ]

        readme = repo.get("readme", "")
        if readme:
            lines.append(f"\nREADME:\n{readme[:3000]}")

        commits = repo.get("commits", [])
        if commits:
            lines.append(f"\nRecent commits:\n" + "\n".join(f"- {c}" for c in commits[:15]))

        full_text = "\n".join(lines)

        for i, chunk in enumerate(chunk_text(full_text, size=300, overlap=60)):
            vectors.append({
                "id": f"github-{repo.get('name','repo')}-{i}",
                "values": embed(chunk),
                "metadata": {
                    "source": "github",
                    "repo": repo.get("name", ""),
                    "url": repo.get("url", ""),
                    "language": repo.get("language", ""),
                    "text": chunk[:1000],
                },
            })
            time.sleep(0.05)

    sys.stdout.write(f"\r  Embedded {len(vectors)} GitHub chunks\n")
    upsert_vectors(index, vectors)
    return len(vectors)


# ─── Additional context ingestion (manual bio, etc.) ─────────────────────────

def ingest_manual_context(index) -> int:
    """
    Ingest any extra hand-written context (cover letter snippets, project notes, etc.)
    Place .txt files in data/extra/ and they'll be picked up here.
    """
    extra_dir = Path("data/extra")
    if not extra_dir.exists():
        extra_dir = Path("../data/extra")
    if not extra_dir.exists():
        return 0

    txt_files = list(extra_dir.glob("*.txt"))
    if not txt_files:
        return 0

    print(f"Ingesting {len(txt_files)} extra context file(s)...")
    vectors = []
    for txt_file in txt_files:
        text = txt_file.read_text(encoding="utf-8")
        for i, chunk in enumerate(chunk_text(text)):
            vectors.append({
                "id": f"extra-{txt_file.stem}-{i}",
                "values": embed(chunk),
                "metadata": {
                    "source": f"extra/{txt_file.name}",
                    "text": chunk[:1000],
                },
            })
            time.sleep(0.05)

    upsert_vectors(index, vectors)
    return len(vectors)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest data into Pinecone for AI persona RAG")
    parser.add_argument("--only", choices=["resume", "github", "extra"], help="Ingest only this source")
    parser.add_argument("--clear", action="store_true", help="Clear namespace before ingesting")
    args = parser.parse_args()

    # Change to project root so relative paths work
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)

    index = get_or_create_index()

    if args.clear:
        clear_namespace(index)

    total = 0
    if args.only == "resume":
        total += ingest_resume(index)
    elif args.only == "github":
        total += ingest_github(index)
    elif args.only == "extra":
        total += ingest_manual_context(index)
    else:
        total += ingest_resume(index)
        total += ingest_github(index)
        total += ingest_manual_context(index)

    print(f"\n✅ Ingestion complete — {total} total vectors in namespace '{NAMESPACE}'")

    # Show index stats
    stats = index.describe_index_stats()
    ns_count = stats.namespaces.get(NAMESPACE, {}).get("vector_count", "unknown")
    print(f"   Pinecone reports {ns_count} vectors in '{NAMESPACE}'")


if __name__ == "__main__":
    main()
