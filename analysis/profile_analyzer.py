"""Profile-level summary helpers."""

from __future__ import annotations


def summarize_profile(profile: dict) -> dict:
    """Return a small dict of display-ready profile metrics."""
    return {
        "login": profile.get("login", ""),
        "name": profile.get("name") or profile.get("login", ""),
        "bio": profile.get("bio") or "No bio available.",
        "location": profile.get("location") or "Not specified",
        "company": profile.get("company") or "Not specified",
        "blog": profile.get("blog") or "",
        "avatar_url": profile.get("avatar_url") or "",
        "html_url": profile.get("html_url") or "",
        "created_at": profile.get("created_at") or "",
        "public_repos": int(profile.get("public_repos") or 0),
        "followers": int(profile.get("followers") or 0),
        "following": int(profile.get("following") or 0),
        "public_gists": int(profile.get("public_gists") or 0),
    }
