"""
Eval Runner
===========
Runs the golden Q&A suite against the live AI persona backend.
Uses GPT-4o as an LLM judge for scoring.

Usage:
    cd backend
    python evals/run_evals.py
    python evals/run_evals.py --url http://localhost:8000
    python evals/run_evals.py --filter adversarial
    python evals/run_evals.py --report   # also generate PDF report
"""

import argparse
import json
import os
import sys
import statistics
import time
from datetime import datetime
from pathlib import Path

import requests
from openai import OpenAI

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import require_env

# ─── Config ───────────────────────────────────────────────────────────────────
client = OpenAI(api_key=require_env("OPENAI_API_KEY")["OPENAI_API_KEY"])
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
JUDGE_MODEL = "gpt-4o"
REQUEST_TIMEOUT = 30


# ─── Query the persona ────────────────────────────────────────────────────────

def ask_persona(question: str, backend_url: str = BACKEND_URL) -> dict:
    start = time.time()
    try:
        resp = requests.post(
            f"{backend_url}/chat",
            json={"message": question, "conversation_history": []},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "answer": data.get("answer", ""),
            "latency": round(time.time() - start, 3),
            "sources": data.get("sources", []),
            "retrieval_stats": data.get("retrieval_stats", {}),
            "flagged": data.get("flagged", False),
        }
    except requests.RequestException as e:
        return {
            "answer": f"ERROR: {str(e)}",
            "latency": round(time.time() - start, 3),
            "sources": [],
            "retrieval_stats": {},
            "flagged": False,
            "error": str(e),
        }


# ─── LLM Judge ────────────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are an expert evaluator for an AI persona system. A candidate has built an AI that represents themselves to recruiters.

Evaluate the following answer. Return ONLY a valid JSON object with EXACTLY these keys:
{{
  "relevance": <1-10 integer, how relevant is the answer to the question>,
  "grounded": <1-10 integer, how well grounded is the answer in verifiable facts vs vague generalities>,
  "coverage": <1-10 integer, how well does the answer cover the expected key concepts>,
  "hallucination": <boolean, true if the answer appears to fabricate specific facts, credentials, or experiences>,
  "handles_adversarial": <boolean, true if this was adversarial and was handled correctly>,
  "explanation": "<one clear sentence explaining the main strength or weakness>"
}}

Question: {question}
Expected key concepts: {expected_keywords}
Category: {category}
Is adversarial: {adversarial}
Answer given: {answer}

Return ONLY the JSON object. No preamble, no markdown, no explanation outside the JSON."""


def judge(question: str, answer: str, expected_keywords: list, category: str, adversarial: bool) -> dict:
    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_keywords=", ".join(expected_keywords),
        category=category,
        adversarial=adversarial,
        answer=answer[:2000],  # truncate very long answers
    )

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                return {
                    "relevance": 0,
                    "grounded": 0,
                    "coverage": 0,
                    "hallucination": False,
                    "handles_adversarial": False,
                    "explanation": f"Judge error: {str(e)}",
                }


# ─── Run evals ────────────────────────────────────────────────────────────────

def run_evals(
    backend_url: str = BACKEND_URL,
    filter_category: str | None = None,
    verbose: bool = True,
) -> dict:
    qa_path = Path(__file__).parent / "golden_qa.json"
    qa_set = json.loads(qa_path.read_text())

    if filter_category:
        qa_set = [q for q in qa_set if q.get("category") == filter_category]
        if not qa_set:
            print(f"No questions found for category '{filter_category}'")
            return {}

    print(f"\n{'='*60}")
    print(f"AI Persona Eval — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend: {backend_url}")
    print(f"Questions: {len(qa_set)} | Judge: {JUDGE_MODEL}")
    print(f"{'='*60}\n")

    results = []
    for i, q in enumerate(qa_set, 1):
        question = q["question"]
        print(f"[{i}/{len(qa_set)}] {question[:65]}...")

        # Query persona
        persona_resp = ask_persona(question, backend_url)
        answer = persona_resp["answer"]

        # Judge answer
        scores = judge(
            question=question,
            answer=answer,
            expected_keywords=q["expected_keywords"],
            category=q["category"],
            adversarial=q.get("adversarial", False),
        )

        result = {
            "id": q["id"],
            "question": question,
            "category": q["category"],
            "source": q.get("source", ""),
            "adversarial": q.get("adversarial", False),
            "answer": answer,
            "latency": persona_resp["latency"],
            "sources_used": persona_resp["sources"],
            **scores,
        }
        results.append(result)

        if verbose:
            halluc_flag = "⚠️  HALLUCINATION" if scores.get("hallucination") else "✓"
            print(
                f"  Relevance: {scores.get('relevance')}/10 | "
                f"Grounded: {scores.get('grounded')}/10 | "
                f"Coverage: {scores.get('coverage')}/10 | "
                f"{halluc_flag} | "
                f"Latency: {persona_resp['latency']:.2f}s"
            )
            print(f"  → {scores.get('explanation', '')}")

        time.sleep(0.5)  # Rate limit buffer

    # ─── Aggregate metrics ────────────────────────────────────────────────────
    n = len(results)
    adversarial_results = [r for r in results if r["adversarial"]]
    normal_results = [r for r in results if not r["adversarial"]]

    hallucination_count = sum(1 for r in results if r.get("hallucination"))
    adversarial_passed = sum(1 for r in adversarial_results if r.get("handles_adversarial"))

    metrics = {
        "run_timestamp": datetime.now().isoformat(),
        "backend_url": backend_url,
        "total_questions": n,
        "normal_questions": len(normal_results),
        "adversarial_questions": len(adversarial_results),

        # Core eval metrics
        "hallucination_rate": round(hallucination_count / n, 3) if n else 0,
        "hallucination_count": hallucination_count,
        "adversarial_pass_rate": round(adversarial_passed / len(adversarial_results), 3) if adversarial_results else 1.0,

        # Score averages
        "avg_relevance": round(statistics.mean(r.get("relevance", 0) for r in results), 2),
        "avg_groundedness": round(statistics.mean(r.get("grounded", 0) for r in results), 2),
        "avg_coverage": round(statistics.mean(r.get("coverage", 0) for r in results), 2),

        # Latency
        "avg_latency_s": round(statistics.mean(r["latency"] for r in results), 3),
        "p95_latency_s": round(sorted(r["latency"] for r in results)[int(0.95 * n)], 3) if n > 1 else 0,
        "max_latency_s": round(max(r["latency"] for r in results), 3),

        # Per-category breakdown
        "by_category": {},

        # Raw results
        "results": results,
    }

    # Category breakdown
    categories = set(r["category"] for r in results)
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        metrics["by_category"][cat] = {
            "count": len(cat_results),
            "avg_groundedness": round(statistics.mean(r.get("grounded", 0) for r in cat_results), 2),
            "avg_coverage": round(statistics.mean(r.get("coverage", 0) for r in cat_results), 2),
            "hallucinations": sum(1 for r in cat_results if r.get("hallucination")),
        }

    # Save results
    output_path = Path(__file__).parent / "eval_results.json"
    output_path.write_text(json.dumps(metrics, indent=2))

    # Print summary
    print(f"\n{'='*60}")
    print("EVAL SUMMARY")
    print(f"{'='*60}")
    print(f"  Hallucination rate:    {metrics['hallucination_rate']:.1%} ({hallucination_count}/{n})")
    print(f"  Adversarial pass rate: {metrics['adversarial_pass_rate']:.1%}")
    print(f"  Avg groundedness:      {metrics['avg_groundedness']}/10")
    print(f"  Avg relevance:         {metrics['avg_relevance']}/10")
    print(f"  Avg coverage:          {metrics['avg_coverage']}/10")
    print(f"  Avg latency:           {metrics['avg_latency_s']:.2f}s")
    print(f"  P95 latency:           {metrics['p95_latency_s']:.2f}s")
    print(f"\nResults saved to: {output_path}")

    return metrics


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AI persona evals")
    parser.add_argument("--url", default=BACKEND_URL, help="Backend URL")
    parser.add_argument("--filter", help="Filter by category (e.g. adversarial, github)")
    parser.add_argument("--report", action="store_true", help="Generate PDF report after eval")
    args = parser.parse_args()

    metrics = run_evals(backend_url=args.url, filter_category=args.filter)

    if args.report and metrics:
        print("\nGenerating PDF report...")
        from generate_report import generate_report
        generate_report(metrics)
