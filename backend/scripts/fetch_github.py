"""
GitHub Repo Fetcher
===================
Fetches public repos, READMEs, topics, and recent commit messages
for a given GitHub username. Output: data/github_repos.json

Usage:
    python scripts/fetch_github.py
    GITHUB_USERNAME=yourname python scripts/fetch_github.py
    python scripts/fetch_github.py --username yourname --token ghp_xxx
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "env", override=False)

# ─── Config ───────────────────────────────────────────────────────────────────
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "YOUR_GITHUB_USERNAME")  # REPLACE THIS
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # Optional: higher rate limits
API_BASE = "https://api.github.com"
MAX_REPOS = 50
MAX_README_CHARS = 4000
MAX_COMMITS = 20


def get_headers(token: str = "") -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    t = token or GITHUB_TOKEN
    if t:
        headers["Authorization"] = f"token {t}"
    return headers


def fetch_repos(username: str, headers: dict) -> list:
    url = f"{API_BASE}/users/{username}/repos"
    params = {"per_page": MAX_REPOS, "sort": "updated", "type": "public"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    if resp.status_code == 404:
        print(f"ERROR: GitHub user '{username}' not found.")
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def fetch_readme(username: str, repo_name: str, headers: dict) -> str:
    url = f"{API_BASE}/repos/{username}/{repo_name}/readme"
    raw_headers = {**headers, "Accept": "application/vnd.github.v3.raw"}
    resp = requests.get(url, headers=raw_headers, timeout=10)
    if resp.status_code == 200:
        return resp.text[:MAX_README_CHARS]
    return ""


def fetch_commits(username: str, repo_name: str, headers: dict) -> list:
    url = f"{API_BASE}/repos/{username}/{repo_name}/commits"
    resp = requests.get(url, headers=headers, params={"per_page": MAX_COMMITS}, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list):
            return [c["commit"]["message"].split("\n")[0] for c in data]
    return []


def fetch_languages(username: str, repo_name: str, headers: dict) -> dict:
    url = f"{API_BASE}/repos/{username}/{repo_name}/languages"
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 200:
        return resp.json()
    return {}


def main(username: str, token: str = ""):
    headers = get_headers(token)

    print(f"Fetching repos for @{username}...")
    repos = fetch_repos(username, headers)
    print(f"Found {len(repos)} public repos. Processing...")

    output = []
    for i, repo in enumerate(repos, 1):
        name = repo["name"]
        print(f"[{i}/{len(repos)}] {name}...")

        readme = fetch_readme(username, name, headers)
        commits = fetch_commits(username, name, headers)
        languages = fetch_languages(username, name, headers)

        output.append({
            "name": name,
            "description": repo.get("description") or "",
            "language": repo.get("language") or "",
            "languages": languages,
            "topics": repo.get("topics", []),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "readme": readme,
            "commits": commits,
            "url": repo.get("html_url", ""),
            "created_at": repo.get("created_at", ""),
            "updated_at": repo.get("updated_at", ""),
            "size_kb": repo.get("size", 0),
            "is_fork": repo.get("fork", False),
            "default_branch": repo.get("default_branch", "main"),
        })

        # Be respectful of GitHub rate limits
        time.sleep(0.3)

    # Write output
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / "github_repos.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✅ Fetched {len(output)} repos → {output_path}")

    # Print summary
    total_stars = sum(r["stars"] for r in output)
    languages_seen = set(r["language"] for r in output if r["language"])
    print(f"   Total stars: {total_stars}")
    print(f"   Languages: {', '.join(sorted(languages_seen))}")
    print(f"   Repos with README: {sum(1 for r in output if r['readme'])}")
    print(f"   Non-fork repos: {sum(1 for r in output if not r['is_fork'])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch GitHub repos for RAG ingestion")
    parser.add_argument("--username", default=GITHUB_USERNAME, help="GitHub username")
    parser.add_argument("--token", default="", help="GitHub personal access token (optional)")
    args = parser.parse_args()

    if args.username == "YOUR_GITHUB_USERNAME":
        print("ERROR: Set GITHUB_USERNAME in .env or pass --username yourname")
        sys.exit(1)

    main(args.username, args.token)
