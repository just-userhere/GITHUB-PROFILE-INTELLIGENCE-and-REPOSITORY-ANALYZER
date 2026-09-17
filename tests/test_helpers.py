"""Tests for helper utilities."""

import pandas as pd

from utils.helpers import (
    build_export_payload,
    format_date,
    format_number,
    payload_to_json,
    repos_to_csv,
    truncate,
)


def test_format_number():
    assert format_number(1234567) == "1,234,567"
    assert format_number(0) == "0"
    assert format_number(None) == "0"


def test_format_date():
    assert format_date("2024-01-15T10:00:00Z") == "15 Jan 2024"
    assert format_date("") == "—"
    assert format_date(None) == "—"


def test_truncate():
    assert truncate("hello", 10) == "hello"
    assert truncate("hello world", 6).endswith("…")


def test_repos_csv_has_header_and_rows():
    repos = [
        {"name": "a", "full_name": "u/a", "description": "x", "language": "Python",
         "stargazers_count": 1, "forks_count": 0, "watchers_count": 0,
         "open_issues_count": 0, "size": 10, "created_at": "", "updated_at": "",
         "pushed_at": "", "license": "MIT", "archived": False, "fork": False,
         "html_url": "https://github.com/u/a"},
    ]
    csv_text = repos_to_csv(repos)
    assert "full_name" in csv_text.splitlines()[0]
    assert "u/a" in csv_text


def test_repos_csv_empty():
    csv_text = repos_to_csv([])
    assert "full_name" in csv_text.splitlines()[0]


def test_export_payload_is_json_serializable():
    lang_df = pd.DataFrame([{"language": "Python", "repo_count": 2, "percentage": 100.0}])
    payload = build_export_payload(
        {"login": "u"}, [], {"total_repos": 0, "by_month_created": {}},
        lang_df, {"total_events": 0}, ["insight"],
    )
    text = payload_to_json(payload)
    assert '"GitScope"' in text
    assert "primary language" in text.lower() or "notes" in text
