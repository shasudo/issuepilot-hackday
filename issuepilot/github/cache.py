from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import NamedTuple


class CachedResponse(NamedTuple):
    etag: str | None
    body: str


class ResponseCache:
    """Tiny SQLite cache keyed by full request URL.

    Stores ETags so repeat reads cost a cheap 304 revalidation instead
    of a full response — this is what keeps the live demo fast and
    safely under GitHub's rate limit.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                url TEXT PRIMARY KEY,
                etag TEXT,
                body TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, url: str) -> CachedResponse | None:
        row = self._conn.execute("SELECT etag, body FROM responses WHERE url = ?", (url,)).fetchone()
        if row is None:
            return None
        return CachedResponse(etag=row[0], body=row[1])

    def put(self, url: str, etag: str | None, body: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO responses (url, etag, body) VALUES (?, ?, ?)",
            (url, etag, body),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
