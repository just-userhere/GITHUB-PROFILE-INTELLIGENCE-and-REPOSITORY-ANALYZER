"""GitScope — GitHub Profile Intelligence & Repository Analyzer (Streamlit)."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from analysis.activity_analyzer import analyze_events, recent_activity_list
from analysis.language_analyzer import language_distribution, top_language
from analysis.profile_analyzer import summarize_profile
from analysis.repository_analyzer import (
    aggregate_repositories,
    completeness_for_repo,
)
from github_api.activity import get_user_events
from github_api.client import (
    GitHubAPIError,
    GitHubAPIClient,
    GitHubNetworkError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from github_api.repositories import get_repositories
from github_api.users import get_user
from utils.cache import CACHE_TTL_SECONDS
from utils.helpers import (
    build_export_payload,
    format_date,
    format_number,
    payload_to_json,
    repos_to_csv,
    truncate,
)
from visualization import charts

load_dotenv()

st.set_page_config(
    page_title="GitScope — GitHub Profile Intelligence",
    page_icon="🔭",
    layout="wide",
)

# ---------------------------------------------------------------- CSS ---
st.markdown(
    """
<style>
:root { color-scheme: dark; }
.block-container { padding-top: 1.2rem; max-width: 1200px; }
.gitscope-hero {
  background: linear-gradient(135deg, #0d1117 0%, #161b22 55%, #1c2a4a 100%);
  border: 1px solid #30363d; border-radius: 16px; padding: 22px 26px; margin-bottom: 14px;
}
.gitscope-hero h1 { margin: 0; font-size: 2rem; letter-spacing: .5px; }
.gitscope-hero h1 span { color: #58a6ff; }
.gitscope-hero p { color: #9aa4b2; margin: 6px 0 0 0; }
.metric-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 12px;
  padding: 14px 16px; text-align: center;
}
.metric-card .v { font-size: 1.5rem; font-weight: 700; }
.metric-card .l { color: #9aa4b2; font-size: .82rem; }
.profile-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 14px; padding: 18px;
}
.repo-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 14px 16px; margin-bottom: 10px;
}
.repo-card h4 { margin: 0 0 4px 0; }
.small-muted { color: #9aa4b2; font-size: .85rem; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
a { color: #58a6ff; }
</style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------- cached fetchers ---
def _make_client() -> GitHubAPIClient:
    return GitHubAPIClient(token=os.getenv("GITHUB_TOKEN"))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_profile(username: str) -> dict:
    return get_user(_make_client(), username)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_repos(username: str, check_readme: bool = False) -> list:
    return get_repositories(_make_client(), username, check_readme=check_readme)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_events(username: str) -> list:
    return get_user_events(_make_client(), username)


# --------------------------------------------------------------- insights ---
def build_insights(profile: dict, stats: dict, lang_df: pd.DataFrame, activity: dict) -> list[str]:
    insights: list[str] = []
    login = profile.get("login", "This profile")
    insights.append(
        f"{login} has {format_number(stats.get('total_repos', 0))} public repositories "
        f"with {format_number(stats.get('total_stars', 0))} total stars and "
        f"{format_number(stats.get('total_forks', 0))} total forks."
    )
    if lang_df is not None and not lang_df.empty:
        top = lang_df.iloc[0]
        insights.append(
            f"{top['language']} is the most represented primary language "
            f"({int(top['repo_count'])} repos, {top['percentage']}%). "
            "This counts repositories by primary language, not lines of code."
        )
    most = stats.get("most_starred")
    if most:
        insights.append(
            f"Highest-starred repository is {most.get('full_name')} "
            f"with {format_number(most.get('stargazers_count'))} stars."
        )
    recent = stats.get("recently_updated")
    if recent:
        insights.append(
            f"Most recently pushed repository is {recent.get('full_name')} "
            f"(pushed {format_date(recent.get('pushed_at'))})."
        )
    if stats.get("archived_count"):
        insights.append(f"{stats['archived_count']} repositories are archived.")
    if stats.get("fork_count"):
        insights.append(
            f"{stats['fork_count']} repositories are forks; "
            f"{stats.get('original_count', 0)} are original."
        )
    buckets = stats.get("update_buckets", {})
    if buckets.get("last_30_days"):
        insights.append(
            f"{buckets['last_30_days']} repositories were pushed in the last 30 days."
        )
    elif buckets.get("older"):
        insights.append(
            f"{buckets.get('older')} repositories have not been pushed in over a year."
        )
    if activity.get("total_events"):
        insights.append(
            f"{activity['total_events']} observable public events found recently "
            f"across {activity.get('repos_involved', 0)} repositories "
            f"({activity.get('pushes', 0)} pushes observed). "
            "This is observable activity, not the full contribution graph."
        )
    else:
        insights.append("No recent observable public activity was found for this user.")
    oldest = stats.get("oldest")
    if oldest:
        insights.append(
            f"Oldest repository is {oldest.get('full_name')} "
            f"(created {format_date(oldest.get('created_at'))})."
        )
    return insights


def _friendly_error_message(exc: Exception) -> str:
    if isinstance(exc, GitHubNotFoundError):
        return "GitHub user not found. Check the spelling and try again."
    if isinstance(exc, GitHubRateLimitError):
        return (
            "GitHub API rate limit exceeded. Wait a few minutes, or set a "
            "`GITHUB_TOKEN` in a `.env` file to get a higher limit, then refresh."
        )
    if isinstance(exc, GitHubNetworkError):
        return f"Network problem: {exc}. Check your connection and retry."
    if isinstance(exc, GitHubAPIError):
        return f"GitHub API error: {exc}"
    return f"Unexpected error: {exc}"


# ------------------------------------------------------------------ sidebar ---
with st.sidebar:
    st.markdown("## 🔭 GitScope")
    st.caption("GitHub Profile Intelligence & Repository Analyzer")
    username = st.text_input("GitHub username", placeholder="e.g. torvalds", key="username_input")
    col_a, col_b = st.columns(2)
    with col_a:
        analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)
    with col_b:
        refresh_clicked = st.button("Refresh", use_container_width=True)
    st.divider()
    st.markdown("### Options")
    check_readme = st.checkbox(
        "Check README presence",
        value=False,
        help="Calls the contents API for up to 20 repos. Uses extra API requests.",
    )
    repo_sort = st.selectbox("Top-repo ordering", ["stars", "forks", "recent updates", "size"])
    st.divider()
    client_probe = _make_client()
    if client_probe.is_authenticated:
        st.success("Authenticated API access (GITHUB_TOKEN set)")
    else:
        st.info("Public API mode (no token). Set GITHUB_TOKEN for higher limits.")
    try:
        rl = client_probe.rate_limit_status()
        st.caption(f"API quota: {rl.get('remaining')}/{rl.get('limit')} remaining")
    except Exception:
        pass
    if refresh_clicked:
        st.cache_data.clear()
        st.toast("Cache cleared — run Analyze again for fresh data.")

if analyze_clicked and username.strip():
    st.session_state["active_user"] = username.strip()
    st.session_state["check_readme"] = check_readme

active_user: str = st.session_state.get("active_user", "")

# -------------------------------------------------------------------- hero ---
st.markdown(
    """
<div class="gitscope-hero">
  <h1>🔭 <span>GitScope</span> — GitHub Profile Intelligence & Repository Analyzer</h1>
  <p>Enter a GitHub username to turn public profile, repository and activity data into
  transparent, explainable analytics. No private data. No mystery scores.</p>
</div>
    """,
    unsafe_allow_html=True,
)

if not active_user:
    st.info("👈 Enter a GitHub username in the sidebar and click **Analyze** to begin.")
    st.markdown(
        """
**What GitScope shows**

- Public profile summary with metric cards
- Repository totals, extremes (most starred / forked / recent) and recency buckets
- Primary-language distribution (by repo count — not lines of code)
- Observable public activity timeline (not the full GitHub contribution graph)
- Transparent per-repository completeness checklist
- Side-by-side repository comparison and JSON/CSV export
        """
    )
    st.stop()

# ------------------------------------------------------------------ loading ---
profile: dict | None = None
repos: list = []
events: list = []
load_error: str | None = None

with st.spinner(f"Analyzing @{active_user} …"):
    try:
        profile = fetch_profile(active_user)
    except Exception as exc:  # noqa: BLE001 - UX boundary, message shown below
        load_error = _friendly_error_message(exc)
        profile = None
    if profile is not None:
        try:
            repos = fetch_repos(active_user, st.session_state.get("check_readme", False))
        except Exception as exc:  # noqa: BLE001
            load_error = _friendly_error_message(exc)
            repos = []
        try:
            events = fetch_events(active_user)
        except GitHubNotFoundError as exc:
            load_error = _friendly_error_message(exc)
            events = []
        except Exception:  # noqa: BLE001 - activity is optional
            events = []

if load_error and profile is None:
    st.error(load_error)
    st.stop()
if load_error:
    st.warning(load_error + " (showing partial results)")

summary = summarize_profile(profile or {})
stats = aggregate_repositories(repos)
lang_df = language_distribution(repos)
activity = analyze_events(events)
insights = build_insights(profile or {}, stats, lang_df, activity)

# --------------------------------------------------------------------- tabs ---
tab_overview, tab_repos, tab_activity, tab_compare, tab_export = st.tabs(
    ["📌 Overview", "📦 Repositories", "📈 Activity", "⚖️ Comparison", "💾 Export"]
)

# ================================================================ OVERVIEW ===
with tab_overview:
    c1, c2 = st.columns([1, 2])
    with c1:
        if summary.get("avatar_url"):
            st.image(summary["avatar_url"], width=220)
    with c2:
        st.markdown(f"### {summary.get('name', active_user)} (`@{summary.get('login')}`)")
        st.write(summary.get("bio") or "")
        meta = []
        if (profile or {}).get("location"):
            meta.append(f"📍 {profile['location']}")
        if (profile or {}).get("company"):
            meta.append(f"🏢 {profile['company']}")
        if (profile or {}).get("blog"):
            meta.append(f"🔗 {profile['blog']}")
        if meta:
            st.caption(" · ".join(meta))
        st.caption(
            f"Account created {format_date(summary.get('created_at'))} · "
            f"[View on GitHub]({summary.get('html_url')})"
        )
    m1, m2, m3, m4 = st.columns(4)
    for col, label, key in [
        (m1, "Repositories", "public_repos"),
        (m2, "Followers", "followers"),
        (m3, "Following", "following"),
        (m4, "Public Gists", "public_gists"),
    ]:
        col.markdown(
            f"<div class='metric-card'><div class='v'>{format_number(summary.get(key))}</div>"
            f"<div class='l'>{label}</div></div>",
            unsafe_allow_html=True,
        )

    st.subheader("Repository analytics (observable metrics)")
    if not repos:
        st.info("No public repositories found for this user.")
    else:
        r1, r2, r3, r4 = st.columns(4)
        for col, label, val in [
            (r1, "Total ⭐ stars", format_number(stats["total_stars"])),
            (r2, "Total 🍴 forks", format_number(stats["total_forks"])),
            (r3, "Avg ⭐ / repo", stats["avg_stars"]),
            (r4, "Avg 🍴 / repo", stats["avg_forks"]),
        ]:
            col.markdown(
                f"<div class='metric-card'><div class='v'>{val}</div>"
                f"<div class='l'>{label}</div></div>",
                unsafe_allow_html=True,
            )
        e1, e2, e3 = st.columns(3)
        most = stats.get("most_starred") or {}
        forked = stats.get("most_forked") or {}
        recent = stats.get("recently_updated") or {}
        e1.markdown(
            f"<div class='repo-card'><b>⭐ Most starred</b><br>"
            f"<a href='{most.get('html_url', '#')}'>{most.get('full_name', '—')}</a><br>"
            f"<span class='small-muted'>{format_number(most.get('stargazers_count'))} stars</span></div>",
            unsafe_allow_html=True,
        )
        e2.markdown(
            f"<div class='repo-card'><b>🍴 Most forked</b><br>"
            f"<a href='{forked.get('html_url', '#')}'>{forked.get('full_name', '—')}</a><br>"
            f"<span class='small-muted'>{format_number(forked.get('forks_count'))} forks</span></div>",
            unsafe_allow_html=True,
        )
        e3.markdown(
            f"<div class='repo-card'><b>🕒 Recently pushed</b><br>"
            f"<a href='{recent.get('html_url', '#')}'>{recent.get('full_name', '—')}</a><br>"
            f"<span class='small-muted'>{format_date(recent.get('pushed_at'))}</span></div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(charts.top_repos_bar(repos, "stargazers_count"), use_container_width=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            st.plotly_chart(charts.creation_timeline(stats.get("by_month_created", {})), use_container_width=True)
        with cc2:
            st.plotly_chart(charts.update_bucket_chart(stats.get("update_buckets", {})), use_container_width=True)
        st.caption(
            f"Active: {stats['active_count']} · Archived: {stats['archived_count']} · "
            f"Original: {stats['original_count']} · Forks: {stats['fork_count']}"
        )

    st.subheader("Language intelligence")
    st.caption(
        "Based on each repository's **primary language** (GitHub's classification). "
        "Percentages = share of repositories, **not** exact lines of code written."
    )
    if lang_df.empty:
        st.info("Language information is unavailable (no repositories or no language data).")
    else:
        lc1, lc2 = st.columns(2)
        with lc1:
            st.plotly_chart(charts.language_donut(lang_df), use_container_width=True)
        with lc2:
            st.plotly_chart(charts.language_bar(lang_df), use_container_width=True)
        st.dataframe(lang_df, use_container_width=True, hide_index=True)

    st.subheader("Data-driven insights")
    for item in insights:
        st.markdown(f"- {item}")

# ============================================================ REPOSITORIES ===
with tab_repos:
    st.subheader("Top repositories")
    if not repos:
        st.info("No public repositories found.")
    else:
        key_map = {
            "stars": "stargazers_count",
            "forks": "forks_count",
            "recent updates": "pushed_at",
            "size": "size",
        }
        sort_key = key_map.get(repo_sort, "stargazers_count")
        if sort_key == "pushed_at":
            ordered = sorted(repos, key=lambda r: r.get("pushed_at") or "", reverse=True)[:15]
        else:
            ordered = sorted(repos, key=lambda r: int(r.get(sort_key, 0) or 0), reverse=True)[:15]
        for repo in ordered:
            st.markdown(
                f"<div class='repo-card'><h4><a href='{repo.get('html_url')}'>{repo.get('full_name')}</a></h4>"
                f"<div class='small-muted'>{truncate(repo.get('description') or 'No description.', 160)}</div>"
                f"<div class='small-muted'>🛠 {repo.get('language')} · ⭐ {format_number(repo.get('stargazers_count'))} · "
                f"🍴 {format_number(repo.get('forks_count'))} · updated {format_date(repo.get('pushed_at'))}</div></div>",
                unsafe_allow_html=True,
            )
        with st.expander("Full repository table"):
            df = pd.DataFrame(repos)
            cols = ["name", "language", "stargazers_count", "forks_count", "open_issues_count",
                    "size", "license", "archived", "fork", "updated_at", "html_url"]
            st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)

    st.subheader("Repository completeness (transparent checklist)")
    st.caption(
        "Each repository is checked against 6 explicit observable criteria. "
        "This measures **completeness of repository metadata**, not developer quality. "
        + (
            "README checks were enabled for the top 20 repos."
            if st.session_state.get("check_readme") else
            "README detection is off — enable **Check README presence** in the sidebar for that criterion."
        )
    )
    if not repos:
        st.info("Not enough data to evaluate completeness.")
    else:
        choice = st.selectbox("Select a repository", [r["full_name"] for r in repos])
        selected = next((r for r in repos if r["full_name"] == choice), repos[0])
        result = completeness_for_repo(selected)
        st.progress(result["score"] / result["total"], text=f"{result['score']} / {result['total']} criteria met")
        for detail in result["details"]:
            icon = "✅" if detail["passed"] else "⬜"
            st.markdown(f"{icon} {detail['label']}")

# =============================================================== ACTIVITY ===
with tab_activity:
    st.subheader("Observable public activity")
    st.caption(
        "Built from the recent public-events API (up to ~90 days / ~300 events). "
        "This is **observable public activity**, not GitHub's exact contribution graph "
        "(which also counts private contributions and uses a different method)."
    )
    if not events:
        st.info("No recent public activity available for this user.")
    else:
        a1, a2, a3 = st.columns(3)
        for col, label, val in [
            (a1, "Observable events", activity["total_events"]),
            (a2, "Pushes observed", activity["pushes"]),
            (a3, "Repositories involved", activity["repos_involved"]),
        ]:
            col.markdown(
                f"<div class='metric-card'><div class='v'>{format_number(val)}</div>"
                f"<div class='l'>{label}</div></div>",
                unsafe_allow_html=True,
            )
        st.plotly_chart(charts.activity_timeline(activity["by_date_df"]), use_container_width=True)
        st.plotly_chart(charts.activity_type_chart(activity["by_type_df"]), use_container_width=True)
        st.markdown("#### Recent activity")
        for item in recent_activity_list(events):
            st.markdown(
                f"<div class='repo-card'><b>{item['label']}</b> · "
                f"<a href='{item['url']}'>{item['repo']}</a> · "
                f"<span class='small-muted'>{format_date(item['date'])}</span></div>",
                unsafe_allow_html=True,
            )

# ============================================================= COMPARISON ===
with tab_compare:
    st.subheader("Repository comparison")
    st.caption("Side-by-side measurable differences. No overall winner is declared.")
    if len(repos) < 2:
        st.info("Not enough data to compare repositories (need at least 2).")
    else:
        names = [r["full_name"] for r in repos]
        c1, c2 = st.columns(2)
        with c1:
            name_a = st.selectbox("Repository A", names, index=0, key="cmp_a")
        with c2:
            default_b = 1 if len(names) > 1 else 0
            name_b = st.selectbox("Repository B", names, index=default_b, key="cmp_b")
        repo_a = next(r for r in repos if r["full_name"] == name_a)
        repo_b = next(r for r in repos if r["full_name"] == name_b)
        rows = [
            ("Stars", format_number(repo_a["stargazers_count"]), format_number(repo_b["stargazers_count"])),
            ("Forks", format_number(repo_a["forks_count"]), format_number(repo_b["forks_count"])),
            ("Watchers", format_number(repo_a["watchers_count"]), format_number(repo_b["watchers_count"])),
            ("Open issues", format_number(repo_a["open_issues_count"]), format_number(repo_b["open_issues_count"])),
            ("Language", repo_a["language"], repo_b["language"]),
            ("Size (KB)", format_number(repo_a["size"]), format_number(repo_b["size"])),
            ("Created", format_date(repo_a["created_at"]), format_date(repo_b["created_at"])),
            ("Last push", format_date(repo_a["pushed_at"]), format_date(repo_b["pushed_at"])),
            ("Archived", str(repo_a["archived"]), str(repo_b["archived"])),
            ("License", repo_a["license"], repo_b["license"]),
            ("Topics", ", ".join(repo_a["topics"]) or "—", ", ".join(repo_b["topics"]) or "—"),
        ]
        comp_a = completeness_for_repo(repo_a)
        comp_b = completeness_for_repo(repo_b)
        rows.append(("Completeness", f"{comp_a['score']}/{comp_a['total']}", f"{comp_b['score']}/{comp_b['total']}"))
        st.table(pd.DataFrame(rows, columns=["Metric", name_a, name_b]))
        st.plotly_chart(
            charts.comparison_chart(
                repo_a["name"], repo_b["name"], "Stars",
                repo_a["stargazers_count"], repo_b["stargazers_count"],
            ),
            use_container_width=True,
        )
        st.plotly_chart(
            charts.comparison_chart(
                repo_a["name"], repo_b["name"], "Forks",
                repo_a["forks_count"], repo_b["forks_count"],
            ),
            use_container_width=True,
        )

# ================================================================= EXPORT ===
with tab_export:
    st.subheader("Export analysis")
    st.caption("Download the analyzed data. No database required.")
    payload = build_export_payload(profile or {}, repos, stats, lang_df, activity, insights)
    json_text = payload_to_json(payload)
    st.download_button(
        "⬇️ Download JSON report",
        data=json_text,
        file_name=f"gitscope_{active_user}.json",
        mime="application/json",
        use_container_width=True,
    )
    st.download_button(
        "⬇️ Download repositories CSV",
        data=repos_to_csv(repos),
        file_name=f"gitscope_{active_user}_repos.csv",
        mime="text/csv",
        use_container_width=True,
    )
    with st.expander("Preview JSON"):
        st.code(json_text[:4000] + ("…" if len(json_text) > 4000 else ""), language="json")

st.divider()
st.caption(
    "GitScope · public GitHub data only · primary language ≠ code volume · "
    "observable events ≠ full contributions · completeness ≠ developer quality"
)
