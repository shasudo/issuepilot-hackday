import sqlite3

import pytest

from issuepilot.observability.trace_store import TraceStore, trace


def read_rows(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT node_name, prompt_version, error FROM traces"
        ).fetchall()
    finally:
        conn.close()


def test_trace_records_success(tmp_path) -> None:
    db_path = tmp_path / "traces.db"
    store = TraceStore(db_path)
    with trace(store, "demo_node", "v1"):
        pass
    store.close()
    assert read_rows(db_path) == [("demo_node", "v1", None)]


def test_trace_records_error(tmp_path) -> None:
    db_path = tmp_path / "traces.db"
    store = TraceStore(db_path)
    with pytest.raises(RuntimeError, match="boom"):
        with trace(store, "demo_node", "v1"):
            raise RuntimeError("boom")
    store.close()
    assert read_rows(db_path) == [("demo_node", "v1", "boom")]
