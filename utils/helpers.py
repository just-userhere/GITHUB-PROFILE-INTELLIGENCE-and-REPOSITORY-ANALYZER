"""Generic helpers: formatting + export payload builders."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd


def safe_get(mapping: dict, key: str, default=""):
    value = mapping.get(key, default)
    return default if value is None else value


def format_number(value: int | float | None) -> str:
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return "0"
    return f"{n:,}"


def format_date(iso_value: str | None) -> str:
    if not iso_value:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except Exception:
        return str(iso_value)[:10]


def truncate(text: str | None, limit: int = 120) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_export_payload(
    profile: dict,
    repos: list[dict],
    repo_stats: dict,
    language_df: pd.DataFrame,
    activity: dict,
    insights: list[str],
) -> dict:
    """Build the JSON-serializable export payload (strip DataFrames)."""
    lang_records = (
        language_df.to_dict(orient="records") if language_df is not None and not language_df.empty else []
    )
    stats_copy = {k: v for k, v in (repo_stats or {}).items() if k != "by_month_created"}
    stats_copy["by_month_created"] = (repo_stats or {}).get("by_month_created", {})
    # Full repo dicts embedded in stats (most_starred etc.) are fine; drop nothing else.
    activity_copy = {k: v for k, v in (activity or {}).items() if not k.endswith("_df")}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "GitScope",
        "profile": profile,
        "repository_stats": stats_copy,
        "languages": lang_records,
        "repositories": repos,
        "activity_summary": activity_copy,
        "insights": insights,
        "notes": [
            "Primary language = most significant language per repo (GitHub), not exact code volume.",
            "Activity = observable public events only, not the full GitHub contribution graph.",
            "Completeness = observable repo characteristics, not developer quality.",
        ],
    }


def repos_to_csv(repos: list[dict]) -> str:
    """Return repository analytics as CSV text."""
    columns = [
        "name", "full_name", "description", "language", "stargazers_count",
        "forks_count", "watchers_count", "open_issues_count", "size",
        "created_at", "updated_at", "pushed_at", "license", "archived",
        "fork", "html_url",
    ]
    df = pd.DataFrame(repos)
    if df.empty:
        df = pd.DataFrame(columns=columns)
    else:
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df[columns]
    return df.to_csv(index=False)


def payload_to_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, default=str)
