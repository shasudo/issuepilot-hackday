from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Comment(BaseModel):
    id: int
    author: str
    body: str
    created_at: datetime

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Comment:
        return cls(
            id=data["id"],
            author=data["user"]["login"],
            body=data.get("body") or "",
            created_at=data["created_at"],
        )


class Issue(BaseModel):
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    author: str
    comment_count: int
    created_at: datetime
    updated_at: datetime
    html_url: str
    is_pull: bool = False
    comments: list[Comment] = Field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], comments: list[dict[str, Any]] | None = None) -> Issue:
        return cls(
            number=data["number"],
            title=data["title"],
            body=data.get("body") or "",
            state=data["state"],
            labels=[label["name"] for label in data.get("labels", [])],
            author=data["user"]["login"],
            comment_count=data["comments"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            html_url=data["html_url"],
            is_pull="pull_request" in data,
            comments=[Comment.from_api(c) for c in (comments or [])],
        )


class PullFile(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> PullFile:
        return cls(
            filename=data["filename"],
            status=data.get("status", ""),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            patch=data.get("patch") or "",
        )


class PullRequest(BaseModel):
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    author: str
    created_at: datetime
    updated_at: datetime
    html_url: str
    draft: bool = False
    merged: bool = False
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    base_branch: str = ""
    head_branch: str = ""
    comments: list[Comment] = Field(default_factory=list)
    files: list[PullFile] = Field(default_factory=list)

    @classmethod
    def from_api(
        cls,
        data: dict[str, Any],
        comments: list[dict[str, Any]] | None = None,
        files: list[dict[str, Any]] | None = None,
    ) -> PullRequest:
        return cls(
            number=data["number"],
            title=data["title"],
            body=data.get("body") or "",
            state=data["state"],
            labels=[label["name"] for label in data.get("labels", [])],
            author=data["user"]["login"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            html_url=data["html_url"],
            draft=bool(data.get("draft", False)),
            merged=bool(data.get("merged", False)),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
            base_branch=(data.get("base") or {}).get("ref", ""),
            head_branch=(data.get("head") or {}).get("ref", ""),
            comments=[Comment.from_api(c) for c in (comments or [])],
            files=[PullFile.from_api(f) for f in (files or [])],
        )


class RepoInfo(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str = ""
    languages: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    stars: int = 0
    open_issues: int = 0
    updated_at: datetime | None = None
    html_url: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], languages: list[str] | None = None) -> RepoInfo:
        return cls(
            owner=data["owner"]["login"],
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description") or "",
            languages=languages or [],
            topics=data.get("topics", []),
            stars=data.get("stargazers_count", 0),
            open_issues=data.get("open_issues_count", 0),
            updated_at=data.get("updated_at"),
            html_url=data.get("html_url", ""),
        )


class OrgInfo(BaseModel):
    login: str
    name: str = ""
    description: str = ""
    public_repos: int = 0
    html_url: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> OrgInfo:
        return cls(
            login=data["login"],
            name=data.get("name") or "",
            description=data.get("description") or "",
            public_repos=data.get("public_repos", 0),
            html_url=data.get("html_url", ""),
        )
