from __future__ import annotations

from scripts.summarize_bonus import failure_patterns, junit_summary


def test_bonus_patterns_use_observed_calls_instead_of_dataset_failure_labels() -> None:
    run = {"results": [{
        "id": "args_only", "expect": {"tool_calls": [{"name": "lookup", "args": {"topic": "news"}}]},
        "result": {"case_failure_type": "missing_info", "failure_type": "missing_info",
                   "actual_tool_calls": [{"name": "lookup", "args": {"topic": "general"}}],
                   "routing_correct": True, "args_correct": False, "observed_mismatch": "wrong_arg_value"},
    }]}

    patterns = failure_patterns(run, {"lookup", "clarify"})

    assert patterns["case_counts"]["wrong_args_with_correct_routing"] == 1
    assert patterns["case_counts"]["missed_clarify"] == 0
    assert patterns["case_counts"]["wrong_tool_name"] == 0


def test_bonus_patterns_exclude_provider_errors_from_no_call_counts() -> None:
    run = {"results": [
        {"id": "model_failed", "expect": {"tool_calls": [{"name": "clarify"}]},
         "result": {"actual_tool_calls": [], "observed_mismatch": "provider_error"}},
        {"id": "really_missed", "expect": {"tool_calls": [{"name": "clarify"}]},
         "result": {"actual_tool_calls": [], "observed_mismatch": "missing_tool_call"}},
        {"id": "no_tool_success", "expect": {"no_tool": True},
         "result": {"actual_tool_calls": [], "observed_mismatch": None}},
    ]}

    patterns = failure_patterns(run, {"clarify"})

    assert patterns["case_counts"]["required_no_call"] == 1
    assert patterns["examples"]["missed_clarify"] == ["really_missed"]


def test_bonus_patterns_only_count_identical_calls_as_duplicates_and_keep_json_errors_visible() -> None:
    run = {"results": [
        {"id": "different_pages", "expect": {"tool_calls": [{"name": "fetch"}, {"name": "fetch"}]},
         "result": {"actual_tool_calls": [{"name": "fetch", "args": {"url": "https://one.example"}}, {"name": "fetch", "args": {"url": "https://two.example"}}]}},
        {"id": "exact_repeat", "expect": {"tool_calls": [{"name": "fetch"}]},
         "result": {"actual_tool_calls": [{"name": "fetch", "args": {"url": "https://one.example"}}] * 2}},
        {"id": "bad_json", "expect": {"tool_calls": [{"name": "lookup"}]},
         "result": {"actual_tool_calls": [{"name": "invented_tool", "args": {"_invalid_json_arguments": "{broken"}}]}},
    ]}

    patterns = failure_patterns(run, {"fetch", "lookup"})

    assert patterns["examples"]["duplicate_calls"] == ["exact_repeat"]
    assert patterns["examples"]["invalid_json_arguments"] == ["bad_json"]
    assert patterns["unknown_names"] == {"invented_tool": 1}
    assert patterns["examples"]["wrong_tool_name"] == ["bad_json"]


def test_junit_summary_reads_real_counts_without_counting_skips_as_passed(tmp_path) -> None:
    report = tmp_path / "pytest.xml"
    report.write_text('<testsuites><testsuite tests="8" failures="1" errors="1" skipped="2" time="1.25" timestamp="2026-11-10T17:00:00"/></testsuites>', encoding="utf-8")

    result = junit_summary(report)

    assert result["passed"] == 4
    assert result["skipped"] == 2
    assert result["seconds"] == 1.25
    assert junit_summary(tmp_path / "missing.xml") == {"available": False}
