"""Repository collection + normalization."""

from __future__ import annotations

from .client import GitHubAPIClient


REPO_FIELDS = [
    "name", "full_name", "description", "language", "stargazers_count",
    "forks_count", "watchers_count", "open_issues_count", "size",
    "created_at", "updated_at", "pushed_at", "default_branch",
    "license", "topics", "archived", "fork", "visibility", "html_url",
]


def normalize_repo(raw: dict) -> dict:
    """Extract the fields GitScope cares about from a raw repo payload."""
    license_info = raw.get("license") or {}
    return {
        "name": raw.get("name", ""),
        "full_name": raw.get("full_name", ""),
        "description": raw.get("description") or "",
        "language": raw.get("language") or "Unknown",
        "stargazers_count": int(raw.get("stargazers_count") or 0),
        "forks_count": int(raw.get("forks_count") or 0),
        "watchers_count": int(raw.get("watchers_count") or 0),
        "open_issues_count": int(raw.get("open_issues_count") or 0),
        "size": int(raw.get("size") or 0),  # KB
        "created_at": raw.get("created_at") or "",
        "updated_at": raw.get("updated_at") or "",
        "pushed_at": raw.get("pushed_at") or "",
        "default_branch": raw.get("default_branch") or "main",
        "license": license_info.get("name") or license_info.get("spdx_id") or "No license",
        "topics": raw.get("topics") or [],
        "archived": bool(raw.get("archived", False)),
        "fork": bool(raw.get("fork", False)),
        "visibility": raw.get("visibility") or ("private" if raw.get("private") else "public"),
        "html_url": raw.get("html_url") or "",
        "has_readme": False,  # filled optionally below (cheap heuristic)
    }


def get_repositories(
    client: GitHubAPIClient,
    username: str,
    sort: str = "updated",
    direction: str = "desc",
    check_readme: bool = False,
) -> list[dict]:
    """Fetch ALL public repos for a user (handles pagination)."""
    username = (username or "").strip()
    if not username:
        raise ValueError("Username must not be empty.")
    raw_repos = client.get_paginated(
        f"/users/{username}/repos",
        params={"sort": sort, "direction": direction, "type": "owner"},
        per_page=100,
    )
    repos = [normalize_repo(r) for r in raw_repos if isinstance(r, dict)]

    if check_readme and repos:
        # Lightweight README check: only for first 20 repos to save API calls.
        for repo in repos[:20]:
            try:
                client.get(f"/repos/{repo['full_name']}/readme")
                repo["has_readme"] = True
            except Exception:
                repo["has_readme"] = False
    return repos
