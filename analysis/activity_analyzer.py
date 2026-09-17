"""Observable public activity analysis."""

from __future__ import annotations

from collections import Counter

import pandas as pd


FRIENDLY_EVENT_NAMES = {
    "PushEvent": "Push",
    "CreateEvent": "Repository/Event created",
    "IssuesEvent": "Issue",
    "PullRequestEvent": "Pull Request",
    "IssueCommentEvent": "Issue Comment",
    "WatchEvent": "Star",
    "ForkEvent": "Fork",
    "DeleteEvent": "Delete",
    "ReleaseEvent": "Release",
    "PublicEvent": "Made public",
}


def friendly_event_name(event_type: str) -> str:
    return FRIENDLY_EVENT_NAMES.get(event_type or "", event_type or "Other")


def analyze_events(events: list[dict]) -> dict:
    """Aggregate observable events by type / date / repository."""
    by_type: Counter = Counter()
    by_date: Counter = Counter()
    by_repo: Counter = Counter()
    pushes = 0

    for event in events:
        etype = event.get("type", "Unknown")
        by_type[etype] += 1
        if etype == "PushEvent":
            pushes += 1
        created = (event.get("created_at") or "")[:10]
        if created:
            by_date[created] += 1
        repo_name = ((event.get("repo") or {}).get("name")) or "unknown"
        by_repo[repo_name] += 1

    by_date_df = pd.DataFrame(
        [{"date": d, "events": c} for d, c in sorted(by_date.items())],
        columns=["date", "events"],
    )
    by_type_df = pd.DataFrame(
        [
            {"event_type": t, "label": friendly_event_name(t), "events": c}
            for t, c in by_type.most_common()
        ],
        columns=["event_type", "label", "events"],
    )
    return {
        "total_events": len(events),
        "pushes": pushes,
        "repos_involved": len(by_repo),
        "by_type": dict(by_type),
        "by_date": dict(sorted(by_date.items())),
        "by_repo": dict(by_repo.most_common(10)),
        "by_date_df": by_date_df,
        "by_type_df": by_type_df,
    }


def recent_activity_list(events: list[dict], limit: int = 15) -> list[dict]:
    """Flatten events into a readable recent-activity list."""
    items: list[dict] = []
    for event in events[:limit]:
        etype = event.get("type", "Unknown")
        items.append(
            {
                "type": etype,
                "label": friendly_event_name(etype),
                "repo": ((event.get("repo") or {}).get("name")) or "unknown",
                "date": event.get("created_at") or "",
                "url": f"https://github.com/{((event.get('repo') or {}).get('name')) or ''}",
            }
        )
    return items
