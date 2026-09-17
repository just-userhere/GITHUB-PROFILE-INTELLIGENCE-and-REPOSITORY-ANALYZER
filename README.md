# GitScope

**GitHub Profile Intelligence & Repository Analyzer** — turn any public GitHub profile into transparent, explainable analytics.

Enter a username → GitScope fetches public profile, repository, and activity data from the GitHub REST API and renders metrics, Plotly charts, a repository completeness checklist, side-by-side repo comparison, data-driven insights, and JSON/CSV export.

## Overview

Recruiters, students, and developers often want quick answers: *how active is this profile? what languages show up? which repos matter? what's recently maintained?* GitScope answers those with **observable public data only** — no mystery scores, no claims about developer quality.

## Problem Statement

GitHub profiles expose a lot of raw data but little synthesis. Manually clicking through dozens of repositories to judge activity, language mix, recency, and maintenance is slow. GitScope automates that synthesis into one dashboard.

## Features

- Public profile card (avatar, bio, location, company, blog, created date) + metric cards
- Repository analytics: totals, averages, most starred / forked / recent, oldest / newest, recency buckets, archived-vs-active, original-vs-fork
- Language intelligence: donut + bar charts and a data table (share **by repo count**)
- Observable public activity: per-day timeline, event-type chart, clean recent-activity feed
- Transparent **repository completeness** checklist (6 explicit criteria — README, description, license, topics, recent update, not archived)
- Top repositories with sorting (stars / forks / recent / size)
- Side-by-side repository comparison (no "winner", just measurable differences)
- Data-driven insights (descriptive sentences generated from the actual numbers)
- JSON + CSV export via download buttons
- Rate-limit detection, friendly error states, empty states, 10-minute caching + refresh

## Tech Stack

- Python 3.11+
- Streamlit (dashboard)
- requests (GitHub REST API)
- pandas (aggregation / export)
- Plotly (charts)
- python-dotenv (optional `GITHUB_TOKEN`)
- pytest (tests, all mocked — no live API needed)

## Architecture

```text
GitScope/
├── app.py                    # Streamlit UI (sidebar, 5 tabs, export)
├── github_api/
│   ├── client.py             # reusable REST client: auth, timeout, errors, rate limits, pagination
│   ├── users.py              # GET /users/{username}
│   ├── repositories.py       # GET /users/{u}/repos (paginated) + normalize_repo()
│   └── activity.py           # GET /users/{u}/events/public (paginated)
├── analysis/
│   ├── profile_analyzer.py   # display-ready profile summary
│   ├── repository_analyzer.py# totals/averages/extremes/recency + completeness checklist
│   ├── language_analyzer.py  # primary-language distribution (by repo count)
│   └── activity_analyzer.py  # events by type/date/repo
├── visualization/charts.py   # Plotly builders (all handle empty data)
├── utils/
│   ├── helpers.py            # formatting + JSON/CSV export builders
│   └── cache.py              # cache TTL constant
└── tests/                    # pytest suite (mocked)
```

## How It Works

1. User enters a GitHub username in the sidebar and clicks **Analyze**.
2. `github_api/*` fetches profile → all repo pages → recent public events (Streamlit `cache_data`, 10-min TTL).
3. `analysis/*` computes aggregates with pandas/plain Python.
4. `visualization/charts.py` renders Plotly figures; tabs present overview, repos, activity, comparison, export.
5. Export builds a JSON payload + repo CSV entirely in memory.

## GitHub API Integration

Base: `https://api.github.com`. Endpoints used:

| Purpose | Endpoint |
|---|---|
| Profile | `GET /users/{username}` |
| Repositories (paginated, 100/page) | `GET /users/{username}/repos?type=owner&sort=updated` |
| README check (optional, ≤20 calls) | `GET /repos/{owner}/{repo}/readme` |
| Public events (≤3 pages) | `GET /users/{username}/events/public` |
| Quota display | `GET /rate_limit` |

The client (`github_api/client.py`) provides: auth header from `GITHUB_TOKEN`, 15 s timeouts, 404 / 401 / 403 / 5xx mapping to typed exceptions, rate-limit detection (status 403 + `X-RateLimit-Remaining: 0`, message match, or 429), and `get_paginated()` (stops at short page, caps pages).

## Data Analysis

- **Repositories**: totals, averages, extremes, creation-by-month, push-recency buckets (≤30 d / ≤90 d / ≤1 y / older), archived vs active, forks vs originals.
- **Languages**: counts + percentages of repos by `language` (primary language per repo).
- **Activity**: totals, push counts, repos involved, per-day and per-type distributions.
- **Completeness** (per repo, 6 checks, `X/6`): description · license · README · topics · pushed in last year · not archived.

## Visualizations

Plotly (dark template): language donut, language bar, top-repos bar, creation-per-month bar, push-recency bar, activity-per-day line, events-by-type bar, comparison bars. All builders return a labelled "empty" figure instead of crashing on missing data.

## Repository Comparison

Pick any two repos → metric table (stars, forks, watchers, issues, language, size, dates, archived, license, topics, completeness) + stars/forks bar charts.

## Export

- **JSON**: profile, repository stats, languages, full repo list, activity summary, insights, interpretation notes.
- **CSV**: one row per repository with key metrics.

## Installation

```bash
cd GitScope
py -m pip install -r requirements.txt
```

## Environment Setup

Optional but recommended (raises rate limit from 60 → 5,000 req/hour):

```bash
copy .env.example .env
# edit .env and set:
GITHUB_TOKEN=your_token_here
```

Get a token at <https://github.com/settings/tokens> (no scopes needed for public data). The app works without a token in public-only mode and shows which mode is active. Never commit `.env`.

## Run Locally

```bash
py -m streamlit run app.py
```

Then open the printed local URL, enter a username (e.g. `torvalds`), and click **Analyze**.

## Testing

```bash
py -m pytest -v
py -m compileall -q .
```

All tests use mocked API responses — no network required, fully deterministic.

## Screenshots

> Add screenshots here after first run:
>
> - `docs/screenshot-overview.png` — profile + analytics
> - `docs/screenshot-languages.png` — language intelligence
> - `docs/screenshot-activity.png` — activity timeline
> - `docs/screenshot-comparison.png` — repo comparison

## API Limitations

- **Rate limits**: 60 req/hour anonymous, 5,000 with token. GitScope detects limits, shows quota, and stops instead of retry-looping.
- **Public data only**: private repos, private contributions, and traffic stats are invisible.
- **Pagination**: repo listing pages through all results; events endpoint exposes only recent (~300 events / ~90 days).
- **README check** is opt-in (≤20 extra calls) to conserve quota.

## Important Data Interpretation Notes

- **Primary language ≠ code volume.** Percentages describe the share of *repositories* whose primary language is X, not lines written.
- **Observable events ≠ contributions.** The activity tab uses the public-events API; GitHub's own contribution graph uses a different, broader method (including private work).
- **Completeness ≠ quality.** The 6-point checklist measures visible metadata hygiene, never skill or talent. No scores, rankings, or "10x developer" claims are made.

## Future Improvements

- GitHub GraphQL integration (fewer calls for deep repo data)
- Historical snapshots + scheduled analysis
- Per-repo commit/issue analytics
- Organization-level analysis
- Shareable report links
