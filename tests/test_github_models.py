from issuepilot.github.models import Comment, Issue, OrgInfo, PullRequest, RepoInfo

CREATED = "2026-01-01T00:00:00Z"
UPDATED = "2026-01-02T00:00:00Z"


def test_comment_from_api() -> None:
    comment = Comment.from_api(
        {"id": 7, "user": {"login": "bob"}, "body": "hi", "created_at": CREATED}
    )
    assert (comment.id, comment.author, comment.body) == (7, "bob", "hi")


def test_issue_from_api() -> None:
    issue = Issue.from_api(
        {
            "number": 1,
            "title": "Bug",
            "body": None,
            "state": "open",
            "labels": [{"name": "bug"}, {"name": "ui"}],
            "user": {"login": "ada"},
            "comments": 2,
            "created_at": CREATED,
            "updated_at": UPDATED,
            "html_url": "https://github.com/o/r/issues/1",
        }
    )
    assert issue.body == ""
    assert issue.labels == ["bug", "ui"]
    assert issue.is_pull is False


def test_issue_from_api_detects_pull() -> None:
    issue = Issue.from_api(
        {
            "number": 3,
            "title": "PR as issue",
            "body": "",
            "state": "open",
            "labels": [],
            "user": {"login": "ada"},
            "comments": 0,
            "created_at": CREATED,
            "updated_at": UPDATED,
            "html_url": "https://github.com/o/r/pull/3",
            "pull_request": {"url": "https://api.github.com/x"},
        }
    )
    assert issue.is_pull is True


def test_pull_from_api() -> None:
    pull = PullRequest.from_api(
        {
            "number": 9,
            "title": "Fix",
            "body": "fixes #1",
            "state": "open",
            "labels": [],
            "user": {"login": "ada"},
            "created_at": CREATED,
            "updated_at": UPDATED,
            "html_url": "https://github.com/o/r/pull/9",
            "draft": True,
            "additions": 10,
            "deletions": 2,
            "changed_files": 1,
            "base": {"ref": "main"},
            "head": {"ref": "fix"},
        },
        files=[{"filename": "a.py", "status": "modified", "additions": 10, "deletions": 2}],
    )
    assert pull.draft is True
    assert pull.base_branch == "main"
    assert pull.files[0].filename == "a.py"


def test_repo_from_api() -> None:
    repo = RepoInfo.from_api(
        {
            "owner": {"login": "o"},
            "name": "r",
            "full_name": "o/r",
            "description": None,
            "topics": ["ai"],
            "stargazers_count": 5,
            "open_issues_count": 2,
            "updated_at": UPDATED,
            "html_url": "https://github.com/o/r",
        },
        languages=["Python"],
    )
    assert repo.description == ""
    assert repo.languages == ["Python"]
    assert repo.topics == ["ai"]


def test_repo_default_branch() -> None:
    repo = RepoInfo.from_api(
        {"owner": {"login": "o"}, "name": "r", "full_name": "o/r", "default_branch": "main"}
    )
    assert repo.default_branch == "main"
    assert RepoInfo(owner="o", name="r", full_name="o/r").default_branch == ""


def test_org_from_api() -> None:
    org = OrgInfo.from_api({"login": "o", "name": None, "public_repos": 4})
    assert org.name == ""
    assert org.public_repos == 4
