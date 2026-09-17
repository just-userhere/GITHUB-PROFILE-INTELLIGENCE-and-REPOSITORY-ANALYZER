"""GitHub API client with error handling, rate-limit detection and pagination."""

from __future__ import annotations

import os
import requests


BASE_URL = "https://api.github.com"
DEFAULT_TIMEOUT = 15


class GitHubAPIError(Exception):
    """Base error for GitHub API failures."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubNotFoundError(GitHubAPIError):
    """Raised when a resource (user/repo) does not exist (HTTP 404)."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when the GitHub API rate limit is exceeded."""

    def __init__(self, message: str, reset_time: str | None = None):
        super().__init__(message, status_code=403)
        self.reset_time = reset_time


class GitHubNetworkError(GitHubAPIError):
    """Raised on network failures / timeouts."""


def _is_rate_limited(response: requests.Response) -> bool:
    """Detect rate limiting from status code + headers/body."""
    if response.status_code not in (403, 429):
        return False
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining == "0":
        return True
    try:
        body = response.json()
        msg = str(body.get("message", "")).lower()
        if "rate limit" in msg or "api rate limit exceeded" in msg:
            return True
    except Exception:
        pass
    # 429 is (almost) always a rate limit
    return response.status_code == 429


class GitHubAPIClient:
    """Reusable client for the GitHub REST API."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN") or None
        # Never store empty-string tokens
        if self.token is not None and not self.token.strip():
            self.token = None
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.last_rate_remaining: str | None = None
        self.last_rate_limit: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GitScope/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, endpoint: str, params: dict | None = None) -> tuple[dict | list, dict]:
        """GET an endpoint. Returns (json_body, response_headers).

        Raises GitHubNotFoundError / GitHubRateLimitError / GitHubAPIError /
        GitHubNetworkError.
        """
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(
                url, headers=self._headers(), params=params, timeout=self.timeout
            )
        except requests.Timeout as exc:
            raise GitHubNetworkError(f"Request timed out after {self.timeout}s: {url}") from exc
        except requests.ConnectionError as exc:
            raise GitHubNetworkError(f"Network connection failed for {url}: {exc}") from exc
        except requests.RequestException as exc:
            raise GitHubNetworkError(f"Network error for {url}: {exc}") from exc

        self.last_rate_remaining = response.headers.get("X-RateLimit-Remaining")
        self.last_rate_limit = response.headers.get("X-RateLimit-Limit")

        if response.status_code == 404:
            raise GitHubNotFoundError(f"Resource not found: {url}", status_code=404)
        if _is_rate_limited(response):
            reset = response.headers.get("X-RateLimit-Reset")
            raise GitHubRateLimitError(
                "GitHub API rate limit exceeded. "
                "Wait a while or configure a GITHUB_TOKEN to raise the limit.",
                reset_time=reset,
            )
        if response.status_code == 401:
            raise GitHubAPIError(
                "Unauthorized (401). Your GITHUB_TOKEN may be invalid.", status_code=401
            )
        if response.status_code == 403:
            try:
                msg = response.json().get("message", "Forbidden")
            except Exception:
                msg = "Forbidden"
            raise GitHubAPIError(f"GitHub API forbade the request (403): {msg}", status_code=403)
        if not response.ok:
            raise GitHubAPIError(
                f"GitHub API request failed ({response.status_code}): {url}",
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise GitHubAPIError(f"Invalid JSON response from {url}") from exc
        return data, dict(response.headers)

    def get_paginated(
        self,
        endpoint: str,
        params: dict | None = None,
        max_pages: int = 20,
        per_page: int = 100,
    ) -> list:
        """Fetch all pages of a paginated list endpoint."""
        merged: list = []
        query = dict(params or {})
        query["per_page"] = per_page
        page = 1
        while page <= max_pages:
            query["page"] = page
            data, _ = self.get(endpoint, params=query)
            if not isinstance(data, list):
                # Non-list endpoint: return single payload wrapped
                return [data] if isinstance(data, dict) else []
            if not data:
                break
            merged.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return merged

    def rate_limit_status(self) -> dict:
        """Return last observed rate-limit headers (may call API if unknown)."""
        if self.last_rate_remaining is not None:
            return {
                "remaining": self.last_rate_remaining,
                "limit": self.last_rate_limit,
            }
        try:
            data, headers = self.get("/rate_limit")
            core = (data.get("resources", {}) or {}).get("core", {})
            return {
                "remaining": str(core.get("remaining", "?")),
                "limit": str(core.get("limit", "?")),
            }
        except GitHubAPIError:
            return {"remaining": "?", "limit": "?"}
