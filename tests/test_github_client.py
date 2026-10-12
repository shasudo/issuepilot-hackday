import httpx
import pytest
import respx

from issuepilot.config import Settings
from issuepilot.github.client import (
    MAX_PATCH_CHARS,
    GitHubAPIError,
    GitHubClient,
    GitHubNotFoundError,
)

API = "https://api.github.com"
CREATED = "2026-01-01T00:00:00Z"
UPDATED = "2026-01-02T00:00:00Z"


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        github_token="x",
        cache_db_path=tmp_path / "cache.db",
        trace_db_path=tmp_path / "traces.db",
    )
    owned = GitHubClient(settings)
    yield owned
    owned.close()


def issue_payload(number=1, **overrides):
    data = {
        "number": number,
        "title": "Bug",
        "body": "Body",
        "state": "open",
        "labels": [{"name": "bug"}],
        "user": {"login": "ada"},
        "comments": 1,
        "created_at": CREATED,
        "updated_at": UPDATED,
        "html_url": f"https://github.com/o/r/issues/{number}",
    }
    data.update(overrides)
    return data


def comment_payload():
    return {"id": 1, "user": {"login": "bob"}, "body": "hi", "created_at": CREATED}


@respx.mock
def test_fetch_issue(client) -> None:
    respx.get(f"{API}/repos/o/r/issues/1").mock(
        return_value=httpx.Response(200, json=issue_payload())
    )
    respx.get(f"{API}/repos/o/r/issues/1/comments").mock(
        return_value=httpx.Response(200, json=[comment_payload()])
    )
    issue = client.fetch_issue("o", "r", 1)
    assert issue.title == "Bug"
    assert issue.comments[0].author == "bob"


@respx.mock
def test_get_uses_etag_cache(client) -> None:
    route = respx.get(f"{API}/repos/o/r/issues/1").mock(
        return_value=httpx.Response(200, json=issue_payload(), headers={"ETag": '"v1"'})
    )
    client.get_issue("o", "r", 1)
    route.mock(return_value=httpx.Response(304))
    cached = client.get_issue("o", "r", 1)
    assert cached["title"] == "Bug"
    assert len(respx.calls) == 2
    assert respx.calls[1].request.headers["If-None-Match"] == '"v1"'


@respx.mock
def test_not_found(client) -> None:
    respx.get(f"{API}/repos/o/r/issues/404").mock(return_value=httpx.Response(404))
    with pytest.raises(GitHubNotFoundError):
        client.get_issue("o", "r", 404)


@respx.mock
def test_transient_500_retries(client) -> None:
    respx.get(f"{API}/repos/o/r/issues/1").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json=issue_payload()),
        ]
    )
    assert client.get_issue("o", "r", 1)["number"] == 1


@respx.mock
def test_rate_limit_sleeps_then_retries(client) -> None:
    respx.get(f"{API}/repos/o/r/issues/1").mock(
        side_effect=[
            httpx.Response(403, headers={"Retry-After": "0"}),
            httpx.Response(200, json=issue_payload()),
        ]
    )
    assert client.get_issue("o", "r", 1)["number"] == 1


@respx.mock
def test_list_repo_issues_filters_pull_requests(client) -> None:
    respx.get(f"{API}/repos/o/r/issues").mock(
        return_value=httpx.Response(
            200,
            json=[
                issue_payload(number=1, pull_request={"url": "x"}),
                issue_payload(number=2),
            ],
        )
    )
    issues = client.list_repo_issues("o", "r")
    assert [i.number for i in issues] == [2]


@respx.mock
def test_pagination_follows_next_link(client) -> None:
    # Specific route first: respx matches in registration order.
    respx.get(f"{API}/repos/o/r/issues", params={"page": "2"}).mock(
        return_value=httpx.Response(200, json=[issue_payload(number=2)])
    )
    respx.get(f"{API}/repos/o/r/issues").mock(
        return_value=httpx.Response(
            200,
            json=[issue_payload(number=1)],
            headers={"Link": f'<{API}/repos/o/r/issues?page=2>; rel="next"'},
        )
    )
    issues = client.list_repo_issues("o", "r")
    assert [i.number for i in issues] == [1, 2]


@respx.mock
def test_fetch_pull_caps_patches(client) -> None:
    pull = issue_payload(number=9)
    pull.update({"draft": False, "base": {"ref": "main"}, "head": {"ref": "fix"}})
    respx.get(f"{API}/repos/o/r/pulls/9").mock(return_value=httpx.Response(200, json=pull))
    respx.get(f"{API}/repos/o/r/issues/9/comments").mock(
        return_value=httpx.Response(200, json=[])
    )
    files = [
        {
            "filename": f"f{i}.py",
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "patch": "x" * (MAX_PATCH_CHARS + 100),
        }
        for i in range(11)
    ]
    respx.get(f"{API}/repos/o/r/pulls/9/files").mock(
        return_value=httpx.Response(200, json=files)
    )
    result = client.fetch_pull("o", "r", 9)
    assert len(result.files) == 11
    assert len(result.files[0].patch) == MAX_PATCH_CHARS
    assert result.files[10].patch == ""


@respx.mock
def test_fetch_repo_includes_languages(client) -> None:
    respx.get(f"{API}/repos/o/r").mock(
        return_value=httpx.Response(
            200,
            json={
                "owner": {"login": "o"},
                "name": "r",
                "full_name": "o/r",
                "description": "demo",
                "topics": [],
                "stargazers_count": 3,
                "open_issues_count": 1,
                "updated_at": UPDATED,
                "html_url": "https://github.com/o/r",
            },
        )
    )
    respx.get(f"{API}/repos/o/r/languages").mock(
        return_value=httpx.Response(200, json={"Python": 90, "JavaScript": 10})
    )
    repo = client.fetch_repo("o", "r")
    assert repo.languages == ["JavaScript", "Python"]


@respx.mock
def test_persistent_server_error(client) -> None:
    respx.get(f"{API}/repos/o/r/issues/1").mock(return_value=httpx.Response(500))
    with pytest.raises(GitHubAPIError):
        client.get_issue("o", "r", 1)
