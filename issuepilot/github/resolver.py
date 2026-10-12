from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlparse

EntityKind = Literal["issue", "pull", "repo", "org"]

ACCEPTED_FORMS = (
    "a github.com issue URL (/owner/repo/issues/123), PR URL (/owner/repo/pull/123), "
    "repo URL (/owner/repo), org URL (/org), or shorthand like 'owner/repo' or 'owner/repo#123'"
)


class UnsupportedLinkError(ValueError):
    """Raised when input text is not a supported GitHub link form."""


class AccountLookup(Protocol):
    """The one client capability link resolution needs."""

    def fetch_account_type(self, name: str) -> str: ...


@dataclass(frozen=True)
class ResolvedLink:
    kind: EntityKind
    owner: str
    repo: str | None = None
    number: int | None = None

    @property
    def label(self) -> str:
        if self.kind in ("issue", "pull"):
            return f"{self.owner}/{self.repo}#{self.number}"
        if self.kind == "repo":
            return f"{self.owner}/{self.repo}"
        return self.owner


def resolve(text: str, accounts: AccountLookup) -> ResolvedLink:
    """Parse link text into a concrete entity, disambiguating bare accounts via the API."""
    kind, owner, repo, number = _parse(text.strip())
    if kind == "account":
        account_type = accounts.fetch_account_type(owner)
        if account_type != "Organization":
            raise UnsupportedLinkError(
                f"'{owner}' is a user account, not an organization. "
                f"Please paste {ACCEPTED_FORMS}."
            )
        return ResolvedLink(kind="org", owner=owner)
    assert kind in ("issue", "pull", "repo")
    return ResolvedLink(kind=kind, owner=owner, repo=repo, number=number)  # type: ignore[arg-type]


def _parse(text: str) -> tuple[str, str, str | None, int | None]:
    if "://" in text or text.startswith("github.com/") or text.startswith("www.github.com/"):
        return _parse_url(text)
    return _parse_shorthand(text)


def _parse_url(text: str) -> tuple[str, str, str | None, int | None]:
    prefixed = text if "://" in text else f"https://{text}"
    parsed = urlparse(prefixed)
    if parsed.hostname not in ("github.com", "www.github.com"):
        raise UnsupportedLinkError(f"Only github.com links are supported; got: {text}")
    segments = [seg for seg in parsed.path.split("/") if seg]
    if len(segments) == 1:
        return ("account", segments[0], None, None)
    if len(segments) >= 2:
        owner, repo = segments[0], segments[1]
        if len(segments) == 2:
            return ("repo", owner, repo, None)
        if len(segments) >= 4 and segments[2] == "issues" and segments[3].isdigit():
            return ("issue", owner, repo, int(segments[3]))
        if len(segments) >= 4 and segments[2] == "pull" and segments[3].isdigit():
            return ("pull", owner, repo, int(segments[3]))
    raise UnsupportedLinkError(f"Could not understand this link: {text}. Please paste {ACCEPTED_FORMS}.")


def _parse_shorthand(text: str) -> tuple[str, str, str | None, int | None]:
    body, _, fragment = text.partition("#")
    if "/" not in body:
        raise UnsupportedLinkError(f"Could not understand this link: {text}. Please paste {ACCEPTED_FORMS}.")
    owner, _, repo = body.partition("/")
    owner, repo = owner.strip(), repo.strip()
    if not owner or not repo or "/" in repo:
        raise UnsupportedLinkError(f"Could not understand this link: {text}. Please paste {ACCEPTED_FORMS}.")
    if fragment:
        if not fragment.strip().isdigit():
            raise UnsupportedLinkError(
                f"Could not understand this link: {text}. Please paste {ACCEPTED_FORMS}."
            )
        return ("issue", owner, repo, int(fragment.strip()))
    return ("repo", owner, repo, None)
