"""Language distribution analysis (primary language per repo)."""

from __future__ import annotations

from collections import Counter

import pandas as pd


def language_distribution(repos: list[dict]) -> pd.DataFrame:
    """Count repos by primary language.

    IMPORTANT: GitHub's `language` field is the primary language of each
    repo, not a measure of bytes written. Percentages below = share of
    repositories, not share of code.
    """
    langs = [(r.get("language") or "Unknown") for r in repos]
    counter: Counter = Counter(langs)
    total = sum(counter.values())
    rows = [
        {
            "language": lang,
            "repo_count": count,
            "percentage": round(count / total * 100, 1) if total else 0.0,
        }
        for lang, count in counter.most_common()
    ]
    df = pd.DataFrame(rows, columns=["language", "repo_count", "percentage"])
    return df


def top_language(repos: list[dict]) -> str | None:
    df = language_distribution(repos)
    if df.empty:
        return None
    return str(df.iloc[0]["language"])
