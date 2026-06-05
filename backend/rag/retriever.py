"""
RAG Retriever
=============
Embeds incoming queries with OpenAI text-embedding-3-small
and retrieves the top-k most relevant chunks from Pinecone.
"""

import os
import re
import time
from functools import lru_cache
from pathlib import Path

from config import require_env
from openai import OpenAI
from pinecone import Pinecone

env = require_env("OPENAI_API_KEY", "PINECONE_API_KEY")

# ─── Clients (module-level singletons) ────────────────────────────────────────
openai_client = OpenAI(api_key=env["OPENAI_API_KEY"])
pc = Pinecone(api_key=env["PINECONE_API_KEY"])

INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "ai-persona")
NAMESPACE = "persona"
EMBEDDING_MODEL = "text-embedding-3-small"
MIN_SCORE = 0.30  # Discard low-relevance matches
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Lazy index connection
_index = None


def _get_index():
    global _index
    if _index is None:
        _index = pc.Index(INDEX_NAME)
    return _index


# ─── Core retrieval ───────────────────────────────────────────────────────────

def embed_query(text: str) -> list[float]:
    """Embed a query string; includes retry on rate-limit."""
    for attempt in range(3):
        try:
            resp = openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=[text[:8000]],
            )
            return resp.data[0].embedding
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise e


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9+#.]+", text.lower())
        if len(token) > 2
    }


@lru_cache(maxsize=1)
def _load_local_corpus() -> list[dict]:
    corpus = []

    github_path = PROJECT_ROOT / "data" / "github_repos.json"
    if github_path.exists():
        try:
            import json

            repos = json.loads(github_path.read_text(encoding="utf-8"))
            for repo in repos:
                parts = [
                    f"Repository: {repo.get('name', 'unknown')}",
                    f"Description: {repo.get('description') or 'No description'}",
                    f"Language: {repo.get('language') or 'Unknown'}",
                    f"Languages: {', '.join((repo.get('languages') or {}).keys())}",
                    f"Topics: {', '.join(repo.get('topics', [])) or 'none'}",
                    f"Stars: {repo.get('stars', 0)}",
                    f"Forks: {repo.get('forks', 0)}",
                    f"URL: {repo.get('url', '')}",
                    f"Recent commits: {'; '.join(repo.get('commits', [])[:10])}",
                    f"README: {(repo.get('readme') or '')[:3000]}",
                ]
                corpus.append({
                    "text": "\n".join(parts),
                    "source": "github",
                    "repo": repo.get("name", ""),
                    "url": repo.get("url", ""),
                })
        except Exception:
            pass

    resume_path = PROJECT_ROOT / "data" / "resume.pdf"
    if resume_path.exists():
        try:
            import fitz

            doc = fitz.open(str(resume_path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            words = text.split()
            for i in range(0, len(words), 260):
                corpus.append({
                    "text": " ".join(words[i : i + 320]),
                    "source": "resume",
                    "repo": "",
                    "url": "",
                })
        except Exception:
            pass

    return corpus


def retrieve_local(query: str, top_k: int = 6) -> list[dict]:
    """Fallback keyword retrieval when vector retrieval is unavailable."""
    q_lower = query.lower()
    broad_github_query = any(
        phrase in q_lower
        for phrase in (
            "github",
            "repo",
            "repos",
            "project",
            "projects",
            "tech stack",
            "technologies",
            "hire",
            "scaler",
        )
    )
    if broad_github_query:
        github_items = [item for item in _load_local_corpus() if item.get("source") == "github"]
        if github_items:
            return [
                {
                    "text": item["text"][:1200],
                    "source": item["source"],
                    "score": 1.0,
                    "repo": item.get("repo", ""),
                    "url": item.get("url", ""),
                }
                for item in github_items[:top_k]
            ]

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = []
    for item in _load_local_corpus():
        text = item.get("text", "")
        tokens = _tokenize(text)
        overlap = query_tokens & tokens
        if not overlap:
            continue
        score = len(overlap) / max(len(query_tokens), 1)
        scored.append((score, item))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [
        {
            "text": item["text"][:1200],
            "source": item["source"],
            "score": round(score, 4),
            "repo": item.get("repo", ""),
            "url": item.get("url", ""),
        }
        for score, item in scored[:top_k]
    ]


def retrieve(query: str, top_k: int = 6, min_score: float = MIN_SCORE) -> list[dict]:
    """
    Retrieve top-k relevant chunks from Pinecone for the given query.

    Returns:
        List of dicts with keys: text, source, score, and optional repo/url.
    """
    embedding = embed_query(query)
    index = _get_index()

    results = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=NAMESPACE,
        include_metadata=True,
    )

    chunks = []
    for match in results.matches:
        if match.score < min_score:
            continue
        metadata = match.metadata or {}
        chunks.append({
            "text": metadata.get("text", ""),
            "source": metadata.get("source", "unknown"),
            "score": round(match.score, 4),
            "repo": metadata.get("repo", ""),
            "url": metadata.get("url", ""),
        })

    return chunks


def retrieve_with_sources(query: str, top_k: int = 8) -> dict:
    """
    Extended retrieval that also returns source breakdown.
    Useful for debugging and eval reporting.
    """
    retrieval_error = None
    try:
        chunks = retrieve(query, top_k=top_k)
        mode = "pinecone"
    except Exception as e:
        retrieval_error = str(e)
        chunks = retrieve_local(query, top_k=top_k)
        mode = "local_keyword"
    source_counts = {}
    for c in chunks:
        source_counts[c["source"]] = source_counts.get(c["source"], 0) + 1

    return {
        "chunks": chunks,
        "sources": list(set(c["source"] for c in chunks)),
        "source_counts": source_counts,
        "total_retrieved": len(chunks),
        "avg_score": round(sum(c["score"] for c in chunks) / len(chunks), 4) if chunks else 0,
        "mode": mode,
        "error": retrieval_error,
    }


# ─── Health check ─────────────────────────────────────────────────────────────

def check_index_health() -> dict:
    """Returns index stats — useful for /health endpoint."""
    try:
        index = _get_index()
        stats = index.describe_index_stats()
        ns = stats.namespaces.get(NAMESPACE, {})
        return {
            "status": "ok",
            "index": INDEX_NAME,
            "namespace": NAMESPACE,
            "vector_count": ns.get("vector_count", 0),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
