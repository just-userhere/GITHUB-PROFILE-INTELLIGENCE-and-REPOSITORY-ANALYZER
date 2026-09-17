"""User profile fetching."""

from __future__ import annotations

from .client import GitHubAPIClient


def get_user(client: GitHubAPIClient, username: str) -> dict:
    """Fetch a public GitHub user profile. Raises API errors on failure."""
    username = (username or "").strip()
    if not username:
        raise ValueError("Username must not be empty.")
    data, _ = client.get(f"/users/{username}")
    if not isinstance(data, dict):
        raise ValueError("Unexpected user payload from GitHub API.")
    return data
