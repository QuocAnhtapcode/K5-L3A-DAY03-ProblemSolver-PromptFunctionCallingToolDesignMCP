"""The scripted confirmation harness must never reach Telegram."""
from __future__ import annotations

from scripts.verify_confirmation import DryRunExecutor, SECOND_DRAFT, check_turn
from providers.base import ToolCall
from tools import TOOL_FUNCTIONS


def test_scripted_confirmation_cannot_dispatch_the_real_send_tool(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("The confirmation harness must not call real Telegram")

    monkeypatch.setitem(TOOL_FUNCTIONS, "send", forbidden)
    executor = DryRunExecutor()

    before = executor(ToolCall("send", {"text": SECOND_DRAFT, "confirmed": True}))
    executor.scripted_confirmation = True
    after = executor(ToolCall("send", {"text": SECOND_DRAFT, "confirmed": True}))

    assert before["result"]["status"] == "blocked_by_test_harness"
    assert after["result"]["status"] == "dry_run"
    assert before["result"]["sent"] is False and after["result"]["sent"] is False


def test_scripted_confirmation_rejects_changed_payload_and_truthy_string():
    executor = DryRunExecutor()
    executor.scripted_confirmation = True

    changed = executor(ToolCall("send", {"text": "Changed content", "confirmed": True}))
    wrong_type = executor(ToolCall("send", {"text": SECOND_DRAFT, "confirmed": "true"}))

    assert changed["result"]["status"] == "blocked_by_test_harness"
    assert wrong_type["result"]["status"] == "blocked_by_test_harness"


def test_check_marks_early_send_or_missing_confirmation_as_failure():
    executor = DryRunExecutor()
    event = executor(ToolCall("send", {"text": SECOND_DRAFT, "confirmed": True}))

    assert check_turn(1, {"status": "waiting_for_user", "tool_events": [event]})["passed"] is False
    assert check_turn(1, {"status": "answered", "tool_events": []})["passed"] is False
    assert check_turn(2, {"status": "provider_error", "tool_events": []})["passed"] is False


def test_executor_blocks_unrelated_tools_without_dispatch(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("Only the control tool may execute")

    monkeypatch.setitem(TOOL_FUNCTIONS, "lookup", forbidden)

    result = DryRunExecutor()(ToolCall("lookup", {"query": "AI"}))

    assert result["result"]["error"] == "blocked_by_test_harness"


def test_check_rejects_a_send_requested_after_clarify_in_the_same_batch():
    # chat's loop pauses on clarify before executing the later send, but the
    # model still violated the declaration by requesting both in one response.
    result = {
        "status": "waiting_for_user",
        "rounds": [{"tool_calls": [
            {"name": "clarify", "args": {"response_type": "yes_no"}},
            {"name": "send", "args": {"text": SECOND_DRAFT, "confirmed": True}},
        ]}],
        "tool_events": [{"tool": "clarify", "args": {"response_type": "yes_no"}}],
    }

    assert check_turn(1, result)["passed"] is False
