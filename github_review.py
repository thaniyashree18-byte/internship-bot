"""Read-only retrieval of public GitHub repository evidence for intern reviews."""

from __future__ import annotations

import os
import re

import requests
from dotenv import load_dotenv

from data import log_action

load_dotenv()
API_ROOT = "https://api.github.com"


def fetch_repository_report(username: str, task_title: str = "") -> str:
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        raise ValueError("Enter a valid GitHub username.")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Internship-Automation-System",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session = requests.Session()
    session.headers.update(headers)
    try:
        response = session.get(
            f"{API_ROOT}/users/{username}/repos",
            params={"sort": "updated", "per_page": 100, "type": "owner"},
            timeout=20,
        )
        response.raise_for_status()
        repositories = response.json()
        if not isinstance(repositories, list) or not repositories:
            raise ValueError("No public repositories were found for this username.")
        title_words = {word.lower() for word in re.findall(r"[a-z0-9]+", task_title) if len(word) > 3}

        def relevance(repo: dict) -> int:
            words = set(re.findall(r"[a-z0-9]+", f"{repo.get('name', '')} {repo.get('description', '')}".lower()))
            return len(title_words & words)

        repository = max(repositories, key=relevance)
        owner = repository.get("owner", {}).get("login", username)
        repo_name = repository.get("name", "")
        if not repo_name:
            raise ValueError("GitHub returned a repository without a name.")
        repo_url = f"{API_ROOT}/repos/{owner}/{repo_name}"
        details_response = session.get(repo_url, timeout=20)
        details_response.raise_for_status()
        details = details_response.json()
        commits_response = session.get(f"{repo_url}/commits", params={"per_page": 10}, timeout=20)
        commits_response.raise_for_status()
        commits = commits_response.json()
        languages_response = session.get(f"{repo_url}/languages", timeout=20)
        languages_response.raise_for_status()
        languages = languages_response.json()
        contents_response = session.get(f"{repo_url}/readme", timeout=20)
        readme_text = "README not found."
        if contents_response.ok:
            readme_text = f"README exists: {contents_response.json().get('html_url', '')}"
            try:
                readme_response = session.get(contents_response.json().get("download_url", ""), timeout=20)
                if readme_response.ok:
                    readme_text += "\n" + readme_response.text[:3500]
            except requests.RequestException:
                readme_text += "\nREADME content could not be downloaded."
        else:
            readme_text += f" HTTP {contents_response.status_code}."
        tree_response = session.get(
            f"{repo_url}/git/trees/{details.get('default_branch', 'main')}",
            params={"recursive": "1"},
            timeout=20,
        )
        tree_response.raise_for_status()
        tree = tree_response.json().get("tree", [])
        files = [item.get("path", "") for item in tree if item.get("type") == "blob"][:80]
        commit_lines = []
        for commit in commits[:10]:
            commit_data = commit.get("commit", {})
            message = commit_data.get("message", "").splitlines()[0]
            commit_lines.append(f"- {message[:180]} ({commit_data.get('author', {}).get('date', 'date unknown')})")
        report = (
            f"Repository: {owner}/{repo_name}\n"
            f"URL: {details.get('html_url', '')}\n"
            f"Description: {details.get('description') or 'No description'}\n"
            f"Stars: {details.get('stargazers_count', 0)}\n"
            f"Languages: {languages}\n"
            f"Recent commits:\n" + ("\n".join(commit_lines) or "- No commits returned") +
            "\nFiles:\n" + ("\n".join(f"- {path}" for path in files) or "- No files returned") +
            f"\n{readme_text}"
        )
        log_action("github_review", "success", f"Fetched public evidence for {owner}/{repo_name}.")
        return report
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        log_action("github_review", "fallback", f"GitHub evidence unavailable ({type(exc).__name__}).")
        raise RuntimeError(f"Could not retrieve GitHub evidence: {exc}") from exc
