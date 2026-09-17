"""Tests for the GitHub API client (all mocked, no live requests)."""

import requests

from github_api.client import (
    GitHubAPIClient,
    GitHubAPIError,
    GitHubNetworkError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, ok=True):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.ok = ok

    def json(self):
        if isinstance(self._payload, Exception):
            raise ValueError("bad json")
        return self._payload


class FakeSession:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "params": params})
        if self._exc:
            raise self._exc
        return self._response


def _client(resp=None, exc=None, token=None):
    return GitHubAPIClient(token=token, session=FakeSession(response=resp, exc=exc))


def test_successful_request_returns_json_and_headers():
    resp = FakeResponse(200, {"login": "octocat"}, {"X-RateLimit-Remaining": "59"}, ok=True)
    client = _client(resp)
    data, headers = client.get("/users/octocat")
    assert data["login"] == "octocat"
    assert headers["X-RateLimit-Remaining"] == "59"


def test_404_raises_not_found():
    resp = FakeResponse(404, {"message": "Not Found"}, {}, ok=False)
    client = _client(resp)
    try:
        client.get("/users/does-not-exist-xyz")
        assert False, "expected GitHubNotFoundError"
    except GitHubNotFoundError as exc:
        assert exc.status_code == 404


def test_rate_limit_detected_via_headers():
    resp = FakeResponse(
        403,
        {"message": "API rate limit exceeded"},
        {"X-RateLimit-Remaining": "0"},
        ok=False,
    )
    client = _client(resp)
    try:
        client.get("/users/octocat")
        assert False, "expected GitHubRateLimitError"
    except GitHubRateLimitError:
        pass


def test_rate_limit_detected_via_429():
    resp = FakeResponse(429, {"message": "too many"}, {}, ok=False)
    client = _client(resp)
    try:
        client.get("/users/octocat")
        assert False, "expected GitHubRateLimitError"
    except GitHubRateLimitError:
        pass


def test_network_error_wrapped():
    client = _client(exc=requests.ConnectionError("dns down"))
    try:
        client.get("/users/octocat")
        assert False, "expected GitHubNetworkError"
    except GitHubNetworkError:
        pass


def test_timeout_wrapped():
    client = _client(exc=requests.Timeout("slow"))
    try:
        client.get("/users/octocat")
        assert False, "expected GitHubNetworkError"
    except GitHubNetworkError:
        pass


def test_auth_header_sent_only_with_token():
    resp = FakeResponse(200, {}, {}, ok=True)
    authed = _client(resp, token="secret123")
    authed.get("/users/x")
    assert authed.session.calls[0]["headers"].get("Authorization") == "Bearer secret123"

    anon = _client(resp, token=None)
    anon.get("/users/x")
    assert "Authorization" not in anon.session.calls[0]["headers"]


def test_pagination_merges_pages():
    page1 = FakeResponse(200, [{"id": 1}, {"id": 2}], {}, ok=True)
    empty = FakeResponse(200, [], {}, ok=True)

    class PagedSession(FakeSession):
        def get(self, url, headers=None, params=None, timeout=None):
            if (params or {}).get("page", 1) == 1:
                return page1
            return empty

    client = GitHubAPIClient(token=None, session=PagedSession())
    result = client.get_paginated("/users/x/repos", per_page=5, max_pages=3)
    assert len(result) == 2


def test_server_error_raises_api_error():
    resp = FakeResponse(500, {}, {}, ok=False)
    client = _client(resp)
    try:
        client.get("/users/x")
        assert False, "expected GitHubAPIError"
    except GitHubAPIError as exc:
        assert exc.status_code == 500
