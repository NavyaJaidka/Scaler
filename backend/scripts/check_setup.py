"""
Check local setup for the AI persona assignment without printing secrets.

Usage:
    python scripts/check_setup.py
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
load_dotenv(BACKEND_DIR / ".env", override=False)
load_dotenv(BACKEND_DIR / "env", override=False)


def present(name: str) -> str:
    return "set" if os.environ.get(name) else "missing"


def main() -> None:
    github_path = BACKEND_DIR / "data" / "github_repos.json"
    resume_path = BACKEND_DIR / "data" / "resume.pdf"

    repo_count = 0
    readme_count = 0
    if github_path.exists():
        try:
            repos = json.loads(github_path.read_text(encoding="utf-8"))
            repo_count = len(repos)
            readme_count = sum(1 for repo in repos if repo.get("readme"))
        except json.JSONDecodeError:
            print("github_repos.json: invalid JSON")

    print("Environment")
    for name in (
        "GITHUB_USERNAME",
        "GITHUB_TOKEN",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "PINECONE_INDEX_NAME",
        "CALCOM_API_KEY",
        "CALCOM_EVENT_TYPE_ID",
        "CALCOM_USERNAME",
    ):
        print(f"  {name}: {present(name)}")

    print("\nData")
    print(f"  resume.pdf: {'present' if resume_path.exists() else 'missing'}")
    print(f"  github_repos.json: {'present' if github_path.exists() else 'missing'}")
    print(f"  GitHub repos fetched: {repo_count}")
    print(f"  Repos with README: {readme_count}")

    print("\nNext steps")
    if not os.environ.get("GITHUB_USERNAME"):
        print("  Add GITHUB_USERNAME to env, then run: python scripts/fetch_github.py")
    elif repo_count == 0:
        print("  Run: python scripts/fetch_github.py")

    if not resume_path.exists():
        print("  Add your resume at: data/resume.pdf")

    if repo_count or resume_path.exists():
        print("  Run ingestion from backend/: python rag/ingest.py --clear")


if __name__ == "__main__":
    main()