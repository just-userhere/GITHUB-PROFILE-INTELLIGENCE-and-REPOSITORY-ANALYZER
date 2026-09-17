"""Observable public activity (events) fetching."""

from __future__ import annotations

from .client import GitHubAPIClient


def get_user_events(
    client: GitHubAPIClient,
    username: str,
    per_page: int = 30,
    max_pages: int = 3,
) -> list[dict]:
    """Fetch recent public events for a user.

    GitHub exposes at most ~300 recent events / 90 days for this endpoint.
    This is OBSERVABLE activity, not the full contribution graph.
    Returns [] when the user has no visible events (instead of erroring),
    except 404 which propagates as "user not found".
    """
    username = (username or "").strip()
    if not username:
        raise ValueError("Username must not be empty.")
    try:
        events = client.get_paginated(
            f"/users/{username}/events/public",
            params={},
            max_pages=max_pages,
            per_page=per_page,
        )
    except Exception:
        raise
    return [e for e in events if isinstance(e, dict)]
