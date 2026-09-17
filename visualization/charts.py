"""Plotly chart builders. Every function handles empty data gracefully."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

DARK_TEMPLATE = "plotly_dark"
ACCENT = "#58a6ff"


def _empty_figure(message: str, title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template=DARK_TEMPLATE,
        annotations=[dict(text=message, x=0.5, y=0.5, showarrow=False)],
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=320,
    )
    return fig


def language_donut(df: pd.DataFrame):
    if df is None or df.empty:
        return _empty_figure("No language data available.", "Language distribution")
    fig = px.pie(
        df,
        names="language",
        values="repo_count",
        hole=0.55,
        title="Primary language share (by repository count)",
    )
    fig.update_layout(template=DARK_TEMPLATE, height=380)
    fig.update_traces(hovertemplate="%{label}: %{value} repos (%{percent})")
    return fig


def language_bar(df: pd.DataFrame):
    if df is None or df.empty:
        return _empty_figure("No language data available.", "Top languages")
    top = df.head(10).sort_values("repo_count")
    fig = px.bar(
        top,
        x="repo_count",
        y="language",
        orientation="h",
        title="Top languages by repository count",
        labels={"repo_count": "Repositories", "language": "Language"},
    )
    fig.update_layout(template=DARK_TEMPLATE, height=360)
    return fig


def top_repos_bar(repos: list[dict], metric: str = "stargazers_count", top_n: int = 10):
    rows = sorted(repos, key=lambda r: int(r.get(metric, 0) or 0), reverse=True)[:top_n]
    if not rows:
        return _empty_figure("No repository data.", "Top repositories")
    label = {"stargazers_count": "Stars", "forks_count": "Forks", "size": "Size (KB)"}.get(
        metric, metric
    )
    fig = px.bar(
        x=[r.get("name", "") for r in rows],
        y=[int(r.get(metric, 0) or 0) for r in rows],
        title=f"Top repositories by {label.lower()}",
        labels={"x": "Repository", "y": label},
    )
    fig.update_layout(template=DARK_TEMPLATE, height=380, xaxis_tickangle=-25)
    return fig


def creation_timeline(by_month: dict):
    if not by_month:
        return _empty_figure("Not enough data for a timeline.", "Repositories created over time")
    df = pd.DataFrame([{"month": k, "count": v} for k, v in sorted(by_month.items())])
    fig = px.bar(df, x="month", y="count", title="Repositories created per month",
                 labels={"month": "Month", "count": "Repos created"})
    fig.update_layout(template=DARK_TEMPLATE, height=340, xaxis_tickangle=-30)
    return fig


def activity_timeline(by_date_df: pd.DataFrame):
    if by_date_df is None or by_date_df.empty:
        return _empty_figure("No recent public activity.", "Observable activity over time")
    fig = px.line(by_date_df, x="date", y="events", markers=True,
                  title="Observable public events per day",
                  labels={"date": "Date", "events": "Events"})
    fig.update_layout(template=DARK_TEMPLATE, height=340)
    return fig


def activity_type_chart(by_type_df: pd.DataFrame):
    if by_type_df is None or by_type_df.empty:
        return _empty_figure("No event-type data.", "Events by type")
    fig = px.bar(by_type_df, x="label", y="events", title="Observable events by type",
                 labels={"label": "Event type", "events": "Count"})
    fig.update_layout(template=DARK_TEMPLATE, height=340, xaxis_tickangle=-20)
    return fig


def update_bucket_chart(buckets: dict):
    if not buckets or sum(buckets.values()) == 0:
        return _empty_figure("No update data.", "Repository recency")
    df = pd.DataFrame(
        [
            {"period": "Last 30 days", "count": buckets.get("last_30_days", 0)},
            {"period": "31-90 days", "count": buckets.get("last_90_days", 0)},
            {"period": "3-12 months", "count": buckets.get("last_year", 0)},
            {"period": "Over a year ago", "count": buckets.get("older", 0)},
        ]
    )
    fig = px.bar(df, x="period", y="count", title="When were repositories last pushed?",
                 labels={"period": "Last push", "count": "Repositories"})
    fig.update_layout(template=DARK_TEMPLATE, height=340)
    return fig


def comparison_chart(name_a: str, name_b: str, metric: str, val_a: float, val_b: float):
    fig = go.Figure(
        data=[go.Bar(x=[name_a, name_b], y=[val_a, val_b], marker_color=[ACCENT, "#f778ba"])]
    )
    fig.update_layout(title=f"{metric}: {name_a} vs {name_b}", template=DARK_TEMPLATE, height=320)
    return fig
