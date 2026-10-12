import pytest

from issuepilot.github.resolver import (
    ResolvedLink,
    UnsupportedLinkError,
    resolve,
)


class StubAccounts:
    def __init__(self, account_type: str) -> None:
        self.account_type = account_type

    def fetch_account_type(self, name: str) -> str:
        assert name
        return self.account_type


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://github.com/octo/repo/issues/12", ResolvedLink("issue", "octo", "repo", 12)),
        ("https://github.com/octo/repo/issues/12#issue-1", ResolvedLink("issue", "octo", "repo", 12)),
        ("https://github.com/octo/repo/pull/34", ResolvedLink("pull", "octo", "repo", 34)),
        ("https://github.com/octo/repo/pull/34/files", ResolvedLink("pull", "octo", "repo", 34)),
        ("https://github.com/octo/repo/", ResolvedLink("repo", "octo", "repo", None)),
        ("https://github.com/octo/repo", ResolvedLink("repo", "octo", "repo", None)),
        ("github.com/octo/repo/pull/7", ResolvedLink("pull", "octo", "repo", 7)),
        ("octo/repo", ResolvedLink("repo", "octo", "repo", None)),
        ("octo/repo#5", ResolvedLink("issue", "octo", "repo", 5)),
    ],
)
def test_resolve_matrix(text: str, expected: ResolvedLink) -> None:
    assert resolve(text, StubAccounts("Organization")) == expected


def test_bare_org_resolves_via_api() -> None:
    assert resolve("https://github.com/octo-org", StubAccounts("Organization")) == ResolvedLink(
        "org", "octo-org", None, None
    )


def test_bare_user_rejected() -> None:
    with pytest.raises(UnsupportedLinkError, match="user account"):
        resolve("https://github.com/someuser", StubAccounts("User"))


@pytest.mark.parametrize(
    "text",
    [
        "https://gitlab.com/octo/repo",
        "https://github.com/octo/repo/blob/main/a.py",
        "notaurl",
        "octo/repo#xyz",
        "justonenochannel",
        "https://github.com/",
    ],
)
def test_unsupported_links_rejected(text: str) -> None:
    with pytest.raises(UnsupportedLinkError):
        resolve(text, StubAccounts("Organization"))
