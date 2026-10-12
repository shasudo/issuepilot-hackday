import pytest

from issuepilot.llm.retry import invoke_with_retry, is_transient


class FakeStatusError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"provider failed with {code}")
        self.code = code


class ScriptedInvoker:
    def __init__(self, script: list) -> None:
        self.script = script
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        action = self.script[min(self.calls - 1, len(self.script) - 1)]
        if isinstance(action, Exception):
            raise action
        return action


def test_transient_statuses_detected() -> None:
    assert is_transient(FakeStatusError(429)) is True
    assert is_transient(FakeStatusError(504)) is True
    assert is_transient(FakeStatusError(500)) is True
    assert is_transient(FakeStatusError(400)) is False
    assert is_transient(ValueError("bad schema")) is False
    assert is_transient(RuntimeError("Deadline expired before completion")) is True


def test_retry_then_success() -> None:
    invoker = ScriptedInvoker([FakeStatusError(504), FakeStatusError(503), "ok"])
    assert invoke_with_retry(invoker, [("human", "hi")]) == "ok"
    assert invoker.calls == 3


def test_non_transient_raises_immediately() -> None:
    invoker = ScriptedInvoker([FakeStatusError(400)])
    with pytest.raises(FakeStatusError):
        invoke_with_retry(invoker, [("human", "hi")])
    assert invoker.calls == 1
