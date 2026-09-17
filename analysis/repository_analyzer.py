"""Repository aggregate analytics (observable metrics only)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def aggregate_repositories(repos: list[dict], now: datetime | None = None) -> dict:
    """Compute aggregate stats over normalized repos."""
    now = now or datetime.now(timezone.utc)
    total = len(repos)
    total_stars = sum(int(r.get("stargazers_count", 0) or 0) for r in repos)
    total_forks = sum(int(r.get("forks_count", 0) or 0) for r in repos)

    result: dict = {
        "total_repos": total,
        "total_stars": total_stars,
        "total_forks": total_forks,
        "avg_stars": round(total_stars / total, 2) if total else 0.0,
        "avg_forks": round(total_forks / total, 2) if total else 0.0,
        "archived_count": sum(1 for r in repos if r.get("archived")),
        "fork_count": sum(1 for r in repos if r.get("fork")),
        "original_count": sum(1 for r in repos if not r.get("fork")),
        "most_starred": None,
        "most_forked": None,
        "newest": None,
        "oldest": None,
        "recently_updated": None,
        "by_month_created": {},
        "update_buckets": {"last_30_days": 0, "last_90_days": 0, "last_year": 0, "older": 0},
    }
    result["active_count"] = total - result["archived_count"]

    if not repos:
        return result

    result["most_starred"] = max(repos, key=lambda r: int(r.get("stargazers_count", 0) or 0))
    result["most_forked"] = max(repos, key=lambda r: int(r.get("forks_count", 0) or 0))

    created = [(r, _parse_dt(r.get("created_at"))) for r in repos]
    created_valid = [(r, d) for r, d in created if d is not None]
    if created_valid:
        result["newest"] = max(created_valid, key=lambda x: x[1])[0]
        result["oldest"] = min(created_valid, key=lambda x: x[1])[0]
        month_counter: Counter = Counter()
        for _, d in created_valid:
            month_counter[d.strftime("%Y-%m")] += 1
        result["by_month_created"] = dict(sorted(month_counter.items()))

    updated = [(r, _parse_dt(r.get("pushed_at") or r.get("updated_at"))) for r in repos]
    updated_valid = [(r, d) for r, d in updated if d is not None]
    if updated_valid:
        result["recently_updated"] = max(updated_valid, key=lambda x: x[1])[0]
        for _, d in updated_valid:
            age_days = (now - d).days
            if age_days <= 30:
                result["update_buckets"]["last_30_days"] += 1
            elif age_days <= 90:
                result["update_buckets"]["last_90_days"] += 1
            elif age_days <= 365:
                result["update_buckets"]["last_year"] += 1
            else:
                result["update_buckets"]["older"] += 1
    return result


COMPLETENESS_CRITERIA = [
    ("has_description", "Description available"),
    ("has_license", "License available"),
    ("has_readme", "README available"),
    ("has_topics", "Topics available"),
    ("recently_updated", "Updated in last year"),
    ("not_archived", "Not archived"),
]


def completeness_for_repo(repo: dict, now: datetime | None = None) -> dict:
    """Transparent completeness check: 6 explicit observable criteria.

    NOTE: has_readme is only known when the caller performed the optional
    README check; otherwise it counts as not-met (and the UI explains this).
    This is a completeness indicator, NOT a quality/skill score.
    """
    now = now or datetime.now(timezone.utc)
    dt = _parse_dt(repo.get("pushed_at") or repo.get("updated_at"))
    recent = dt is not None and (now - dt).days <= 365
    checks = {
        "has_description": bool((repo.get("description") or "").strip()),
        "has_license": (repo.get("license") or "No license") != "No license",
        "has_readme": bool(repo.get("has_readme", False)),
        "has_topics": bool(repo.get("topics")),
        "recently_updated": recent,
        "not_archived": not bool(repo.get("archived", False)),
    }
    passed = sum(1 for v in checks.values() if v)
    details = [
        {"key": key, "label": label, "passed": checks[key]}
        for key, label in COMPLETENESS_CRITERIA
    ]
    return {"score": passed, "total": len(checks), "checks": checks, "details": details}
