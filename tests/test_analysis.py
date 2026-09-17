"""Tests for analysis modules (deterministic, mocked data)."""

from datetime import datetime, timezone

from analysis.activity_analyzer import analyze_events
from analysis.language_analyzer import language_distribution, top_language
from analysis.profile_analyzer import summarize_profile
from analysis.repository_analyzer import aggregate_repositories, completeness_for_repo


SAMPLE_REPOS = [
    {
        "name": "alpha", "full_name": "u/alpha", "description": "A",
        "language": "Python", "stargazers_count": 10, "forks_count": 2,
        "watchers_count": 3, "open_issues_count": 1, "size": 100,
        "created_at": "2020-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2024-01-01T00:00:00Z", "default_branch": "main",
        "license": "MIT", "topics": ["demo"], "archived": False, "fork": False,
        "visibility": "public", "html_url": "https://github.com/u/alpha",
        "has_readme": True,
    },
    {
        "name": "beta", "full_name": "u/beta", "description": "",
        "language": "Python", "stargazers_count": 30, "forks_count": 5,
        "watchers_count": 6, "open_issues_count": 0, "size": 200,
        "created_at": "2021-06-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z",
        "pushed_at": "2023-01-01T00:00:00Z", "default_branch": "main",
        "license": "No license", "topics": [], "archived": True, "fork": True,
        "visibility": "public", "html_url": "https://github.com/u/beta",
        "has_readme": False,
    },
    {
        "name": "gamma", "full_name": "u/gamma", "description": "G",
        "language": "JavaScript", "stargazers_count": 5, "forks_count": 1,
        "watchers_count": 1, "open_issues_count": 2, "size": 50,
        "created_at": "2022-03-01T00:00:00Z", "updated_at": "2024-06-01T00:00:00Z",
        "pushed_at": "2024-06-01T00:00:00Z", "default_branch": "main",
        "license": "Apache-2.0", "topics": ["web"], "archived": False, "fork": False,
        "visibility": "public", "html_url": "https://github.com/u/gamma",
        "has_readme": True,
    },
]

SAMPLE_EVENTS = [
    {"type": "PushEvent", "created_at": "2024-06-01T10:00:00Z", "repo": {"name": "u/alpha"}},
    {"type": "PushEvent", "created_at": "2024-06-01T11:00:00Z", "repo": {"name": "u/alpha"}},
    {"type": "IssuesEvent", "created_at": "2024-06-02T10:00:00Z", "repo": {"name": "u/gamma"}},
]


def test_repo_aggregation_totals_and_averages():
    stats = aggregate_repositories(SAMPLE_REPOS)
    assert stats["total_repos"] == 3
    assert stats["total_stars"] == 45
    assert stats["total_forks"] == 8
    assert stats["avg_stars"] == 15.0
    assert stats["archived_count"] == 1
    assert stats["fork_count"] == 1
    assert stats["original_count"] == 2


def test_repo_extremes():
    stats = aggregate_repositories(SAMPLE_REPOS)
    assert stats["most_starred"]["name"] == "beta"
    assert stats["most_forked"]["name"] == "beta"
    assert stats["newest"]["name"] == "gamma"
    assert stats["oldest"]["name"] == "alpha"


def test_repo_aggregation_empty():
    stats = aggregate_repositories([])
    assert stats["total_repos"] == 0
    assert stats["avg_stars"] == 0.0
    assert stats["most_starred"] is None


def test_language_distribution_counts_and_percentages():
    df = language_distribution(SAMPLE_REPOS)
    assert list(df.columns) == ["language", "repo_count", "percentage"]
    assert df.iloc[0]["language"] == "Python"
    assert df.iloc[0]["repo_count"] == 2
    assert abs(df["percentage"].sum() - 100.0) < 0.2
    assert top_language(SAMPLE_REPOS) == "Python"


def test_language_distribution_empty():
    df = language_distribution([])
    assert df.empty
    assert top_language([]) is None


def test_activity_aggregation():
    result = analyze_events(SAMPLE_EVENTS)
    assert result["total_events"] == 3
    assert result["pushes"] == 2
    assert result["repos_involved"] == 2
    assert result["by_type"]["PushEvent"] == 2
    assert result["by_date"]["2024-06-01"] == 2


def test_activity_empty():
    result = analyze_events([])
    assert result["total_events"] == 0
    assert result["by_date_df"].empty
    assert result["by_type_df"].empty


def test_completeness_full_repo():
    now = datetime(2024, 6, 15, tzinfo=timezone.utc)
    result = completeness_for_repo(SAMPLE_REPOS[0], now=now)
    assert result["total"] == 6
    assert result["score"] == 6
    assert all(d["passed"] for d in result["details"])


def test_completeness_partial_repo():
    now = datetime(2024, 6, 15, tzinfo=timezone.utc)
    result = completeness_for_repo(SAMPLE_REPOS[1], now=now)
    # beta: no description, no license, no readme, no topics, old push, archived
    assert result["score"] == 0


def test_profile_summary_defaults():
    summary = summarize_profile({"login": "octocat"})
    assert summary["bio"] == "No bio available."
    assert summary["followers"] == 0
